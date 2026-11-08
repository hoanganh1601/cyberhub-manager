"""LI-08 — Linh: ReportService xem hóa đơn và doanh thu theo ngày của một cửa hàng.

Service chỉ làm việc qua repository và database.transaction.transaction();
UI không gọi repository hay SQL trực tiếp.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.domain.dtos import (
    DailyRevenue,
    EmployeeSession,
    InvoiceDetail,
    InvoiceFilters,
    InvoiceSummary,
    SessionSummary,
)
from cyberhub_manager.domain.enums import InvoiceStatus, Role, SessionStatus
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.repositories.customer_repository import CustomerRepository
from cyberhub_manager.repositories.invoice_repository import InvoiceRepository
from cyberhub_manager.repositories.machine_repository import MachineRepository
from cyberhub_manager.repositories.session_repository import SessionRepository
from cyberhub_manager.services.db_errors import translate_db_errors

ActorProvider = Callable[[], EmployeeSession | None]

# P0: STAFF, MANAGER và ADMIN đều xem được hóa đơn/doanh thu của cửa hàng mình.
REPORT_ROLES = frozenset({Role.STAFF, Role.MANAGER, Role.ADMIN})

# Asia/Ho_Chi_Minh không có giờ mùa hè; tránh phụ thuộc gói tzdata trên Windows.
VN_TZ = timezone(timedelta(hours=7))

WRONG_STORE = "Bạn chỉ được xem dữ liệu của cửa hàng hiện tại"
STORE_ID_INVALID = "Mã cửa hàng không hợp lệ"
FILTERS_INVALID = "Bộ lọc hóa đơn không hợp lệ"
DATE_INVALID = "Ngày không hợp lệ"
DATE_FROM_REQUIRED = "Vui lòng chọn ngày bắt đầu"
DATE_TO_REQUIRED = "Vui lòng chọn ngày kết thúc"
DATE_RANGE_INVALID = "Ngày kết thúc phải sau hoặc bằng ngày bắt đầu"
KEYWORD_INVALID = "Từ khóa tìm kiếm không hợp lệ"
CUSTOMER_ID_INVALID = "Mã khách hàng không hợp lệ"
STATUS_INVALID = "Trạng thái hóa đơn không hợp lệ"
INVOICE_NOT_FOUND = "Không tìm thấy hóa đơn"
INCONSISTENT_INVOICE = "Dữ liệu hóa đơn và phiên không nhất quán"


def _is_positive_id(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def local_day_start_utc(day: date) -> datetime:
    """00:00 giờ Việt Nam của `day`, đổi sang UTC (= 17:00 UTC ngày hôm trước)."""

    return datetime.combine(day, time.min, tzinfo=VN_TZ).astimezone(timezone.utc)


def local_dates_to_utc_range(
    date_from: date | None, date_to: date | None
) -> tuple[datetime | None, datetime | None]:
    """Ngày địa phương [date_from, date_to] -> khoảng UTC nửa mở [start, end).

    Hai đầu mốc đều được tính: end là 00:00 của ngày sau date_to.
    Thiếu một đầu mốc nghĩa là không giới hạn phía đó.
    """

    start = None if date_from is None else local_day_start_utc(date_from)
    end = None if date_to is None else local_day_start_utc(date_to + timedelta(days=1))
    return start, end


def _validate_date_range(
    date_from: object, date_to: object, *, required: bool
) -> None:
    errors: dict[str, str] = {}
    for field, value, missing in (
        ("date_from", date_from, DATE_FROM_REQUIRED),
        ("date_to", date_to, DATE_TO_REQUIRED),
    ):
        if value is None:
            if required:
                errors[field] = missing
        # datetime là lớp con của date nhưng mang giờ; bộ lọc chỉ nhận ngày.
        elif not isinstance(value, date) or isinstance(value, datetime):
            errors[field] = DATE_INVALID
    if not errors and date_from is not None and date_to is not None:
        if date_from > date_to:
            errors["date_to"] = DATE_RANGE_INVALID
    if errors:
        raise ValidationError(field_errors=errors)


def _validate_filters(filters: InvoiceFilters | None) -> InvoiceFilters:
    """Trả bộ lọc đã chuẩn hóa; keyword được bỏ khoảng trắng hai đầu."""

    if filters is None:
        return InvoiceFilters()
    if not isinstance(filters, InvoiceFilters):
        raise ValidationError(FILTERS_INVALID)
    _validate_date_range(filters.date_from, filters.date_to, required=False)

    errors: dict[str, str] = {}
    if not isinstance(filters.keyword, str):
        errors["keyword"] = KEYWORD_INVALID
    if filters.customer_id is not None and not _is_positive_id(filters.customer_id):
        errors["customer_id"] = CUSTOMER_ID_INVALID
    status = filters.status
    if status is not None and not isinstance(status, InvoiceStatus):
        errors["status"] = STATUS_INVALID
    if errors:
        raise ValidationError(field_errors=errors)

    return InvoiceFilters(
        date_from=filters.date_from,
        date_to=filters.date_to,
        keyword=filters.keyword.strip(),
        customer_id=filters.customer_id,
        status=status,
    )


def _validate_store_id(store_id: object) -> None:
    if not _is_positive_id(store_id):
        raise ValidationError(field_errors={"store_id": STORE_ID_INVALID})


class ReportService:
    """Triển khai ReportServiceProtocol trên MySQL; chỉ đọc dữ liệu."""

    def __init__(
        self,
        invoice_repo: InvoiceRepository | None = None,
        auth_repo: AuthRepository | None = None,
        session_repo: SessionRepository | None = None,
        machine_repo: MachineRepository | None = None,
        customer_repo: CustomerRepository | None = None,
        actor_provider: ActorProvider | None = None,
        transaction_factory: Callable[[], AbstractContextManager[Any]] = transaction,
    ) -> None:
        self._invoices = invoice_repo or InvoiceRepository()
        self._auth = auth_repo or AuthRepository()
        self._sessions = session_repo or SessionRepository()
        self._machines = machine_repo or MachineRepository()
        self._customers = customer_repo or CustomerRepository()
        # Không có provider thì không có phiên đăng nhập, mọi thao tác bị từ chối.
        self._actor_provider = actor_provider
        self._transaction = transaction_factory

    def list_invoices(
        self,
        store_id: int,
        filters: InvoiceFilters,
    ) -> list[InvoiceSummary]:
        _validate_store_id(store_id)
        filters = _validate_filters(filters)
        start, end = local_dates_to_utc_range(filters.date_from, filters.date_to)

        with self._database() as conn:
            self._require_store(conn, store_id)
            # Repository đã sắp xếp mới nhất trước và chỉ trả DTO.
            return self._invoices.list_by_store(
                conn,
                store_id,
                created_from_utc=start,
                created_before_utc=end,
                keyword=filters.keyword,
                customer_id=filters.customer_id,
                status=filters.status,
            )

    def get_invoice(self, invoice_id: int) -> InvoiceDetail:
        # Id sai kiểu cũng coi như không tồn tại, giống các service khác.
        if not _is_positive_id(invoice_id):
            raise NotFoundError(INVOICE_NOT_FOUND)

        with self._database() as conn:
            current = self._require_actor(conn)
            summary = self._invoices.get_summary_by_id(conn, invoice_id)
            if summary is None:
                raise NotFoundError(INVOICE_NOT_FOUND)
            if summary.store_id != current.store_id:
                raise PermissionDeniedError(WRONG_STORE)
            session = self._sessions.get_by_id(conn, summary.session_id)
            machine = (
                None
                if session is None
                else self._machines.get_by_id(conn, session.machine_id)
            )
            customer = self._customers.get_by_id(conn, summary.customer_id)

        # Hóa đơn luôn gắn với một phiên đã kết thúc; thiếu dữ liệu là lỗi hệ thống.
        if session is None or machine is None or customer is None:
            raise ConflictError(INCONSISTENT_INVOICE)

        if (
            session.status is not SessionStatus.COMPLETED
            or session.ended_at is None
            or session.cost != summary.usage_cost
            or session.customer_id != summary.customer_id
            or session.closed_by != summary.employee_id
            or machine.store_id != summary.store_id
            or customer.id != session.customer_id
        ):
            raise ConflictError(INCONSISTENT_INVOICE)

        return InvoiceDetail(
            invoice=summary,
            session=SessionSummary(
                session_id=session.id,
                session_code=session.code,
                customer_id=customer.id,
                customer_code=customer.code,
                customer_name=customer.full_name,
                machine_id=machine.id,
                machine_code=machine.code,
                machine_name=machine.name,
                started_at=session.started_at,
                hourly_rate=session.hourly_rate,
                status=session.status,
            ),
            ended_at=session.ended_at,
            # SES-07: tính lại từ started_at/ended_at, cùng công thức với checkout.
            billed_minutes=session.calculate_billed_minutes(session.ended_at),
        )

    def daily_revenue(
        self,
        store_id: int,
        date_from: date,
        date_to: date,
    ) -> list[DailyRevenue]:
        _validate_store_id(store_id)
        _validate_date_range(date_from, date_to, required=True)
        start, end = local_dates_to_utc_range(date_from, date_to)

        with self._database() as conn:
            self._require_store(conn, store_id)
            # Repository chỉ cộng usage_cost của hóa đơn PAID (số nguyên VND), gom
            # theo ngày giờ Việt Nam và chỉ trả những ngày có hóa đơn.
            return self._invoices.daily_revenue_by_store(
                conn,
                store_id,
                created_from_utc=start,
                created_before_utc=end,
            )

    def _require_actor(self, conn: Any) -> EmployeeSession:
        """Đọc lại người đang đăng nhập từ DB; không tin role/store từ UI."""

        actor = self._actor_provider() if self._actor_provider else None
        if (
            not isinstance(actor, EmployeeSession)
            or not _is_positive_id(actor.employee_id)
            or not _is_positive_id(actor.store_id)
        ):
            raise PermissionDeniedError()

        # Repository chỉ trả nhân viên ACTIVE thuộc cửa hàng ACTIVE.
        current = self._auth.get_active_session_by_id(conn, actor.employee_id)
        if (
            current is None
            or current.store_id != actor.store_id
            or current.role != actor.role
            or current.role not in REPORT_ROLES
        ):
            raise PermissionDeniedError()
        return current

    def _require_store(self, conn: Any, store_id: int) -> EmployeeSession:
        current = self._require_actor(conn)
        if store_id != current.store_id:
            raise PermissionDeniedError(WRONG_STORE)
        return current

    @contextmanager
    def _database(self) -> Iterator[Any]:
        """Mở transaction và đổi lỗi MySQL thành lỗi nghiệp vụ theo contract."""

        with translate_db_errors():
            with self._transaction() as conn:
                yield conn
