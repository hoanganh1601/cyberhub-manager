"""LI-06/LI-07 — Linh: SessionService mở phiên và checkout máy.

Service chỉ làm việc qua repository và database.transaction.transaction();
UI không gọi repository hay SQL trực tiếp.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from mysql.connector import Error as MySQLError
from mysql.connector import errorcode
from mysql.connector.errors import IntegrityError

from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.domain.dtos import (
    CheckoutPreview,
    CheckoutResult,
    EmployeeSession,
    InvoiceDetail,
    InvoiceSummary,
    OpenSessionPreview,
    SessionSummary,
)
from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    MachineStatus,
    PaymentMethod,
    Role,
    SessionStatus,
)
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    InsufficientBalanceError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    SettlementRequiredError,
    ValidationError,
)
from cyberhub_manager.domain.models import (
    Account,
    Customer,
    Machine,
    UsageSession,
    estimate_play_minutes,
    minimum_balance,
    MINIMUM_SESSION_MINUTES,
)
from cyberhub_manager.repositories.account_repository import AccountRepository
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.repositories.customer_repository import CustomerRepository
from cyberhub_manager.repositories.invoice_repository import InvoiceRepository
from cyberhub_manager.repositories.machine_repository import MachineRepository
from cyberhub_manager.repositories.session_repository import SessionRepository
from cyberhub_manager.services.wallet_service import new_transaction_code

ActorProvider = Callable[[], EmployeeSession | None]

# STAFF, MANAGER và ADMIN đều được mở phiên và checkout trong cửa hàng của mình.
SESSION_ROLES = frozenset({Role.STAFF, Role.MANAGER, Role.ADMIN})

# "SS-" + 17 ký tự hex = 20 ký tự, vừa cột usage_sessions.code VARCHAR(20).
SESSION_CODE_PREFIX = "SS-"
SESSION_CODE_HEX_LENGTH = 17

# "INV-" + 16 ký tự hex = 20 ký tự, vừa cột invoices.code VARCHAR(20).
INVOICE_CODE_PREFIX = "INV-"
INVOICE_CODE_HEX_LENGTH = 16

# P0 chỉ nhận tiền bù bằng tiền mặt hoặc chuyển khoản.
SETTLEMENT_METHODS = frozenset({PaymentMethod.CASH, PaymentMethod.TRANSFER})

MACHINE_BUSY = "Máy đang được sử dụng"
CUSTOMER_BUSY = "Khách hàng đang có phiên khác"
WRONG_STORE = "Bạn chỉ được thao tác dữ liệu của cửa hàng hiện tại"
MACHINE_NOT_FOUND = "Không tìm thấy máy"
CUSTOMER_NOT_FOUND = "Không tìm thấy khách hàng"
MACHINE_ARCHIVED = "Máy đã ngừng sử dụng"
MACHINE_MAINTENANCE = "Máy đang bảo trì"
CUSTOMER_INACTIVE = "Khách hàng đã ngừng hoạt động"
ACCOUNT_LOCKED = "Tài khoản khách hàng đã bị khóa"
NOT_ENOUGH_BALANCE = f"Số dư chưa đủ cho {MINIMUM_SESSION_MINUTES} phút sử dụng"
NO_ACTIVE_SESSION = "Máy không có phiên đang hoạt động"
CURRENT_TIME_INVALID = "Thời gian tính phí phải có timezone"
ALREADY_CHECKED_OUT = "Phiên này đã được checkout"
BALANCE_CHANGED = "Số dư tài khoản vừa thay đổi, vui lòng xem lại"
SETTLEMENT_INVALID = "Tiền bù phải là số nguyên không âm"
SETTLEMENT_NOT_ENOUGH = "Tiền bù chưa đủ để số dư không âm"
SETTLEMENT_EXCESS = "Tiền bù phải bằng đúng số tiền còn thiếu"
METHOD_INVALID = "Phương thức chỉ được là tiền mặt hoặc chuyển khoản"
METHOD_NOT_ALLOWED = "Không chọn phương thức khi không có tiền bù"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_positive_id(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _conflict(field: str, message: str) -> ConflictError:
    """field_errors giúp UI biết đánh dấu ô khách hay ô máy."""

    return ConflictError(message, field_errors={field: message})


def new_session_code() -> str:
    return SESSION_CODE_PREFIX + uuid4().hex[:SESSION_CODE_HEX_LENGTH]


def new_invoice_code() -> str:
    return INVOICE_CODE_PREFIX + uuid4().hex[:INVOICE_CODE_HEX_LENGTH]


def _validate_settlement_input(
    settlement_amount: int, method: PaymentMethod | None
) -> PaymentMethod | None:
    """Kiểm tra dữ liệu UI gửi lên; đủ hay thiếu tiền bù xét sau khi tính phí."""

    if (
        isinstance(settlement_amount, bool)
        or not isinstance(settlement_amount, int)
        or settlement_amount < 0
    ):
        raise ValidationError(field_errors={"settlement_amount": SETTLEMENT_INVALID})
    if settlement_amount == 0:
        if method is not None:
            raise ValidationError(field_errors={"method": METHOD_NOT_ALLOWED})
        return None

    if (
        not isinstance(method, PaymentMethod)
        or method not in SETTLEMENT_METHODS
    ):
        raise ValidationError(
            field_errors={"method": METHOD_INVALID}
        )

    return method


def _check_settlement_amount(
    preview: CheckoutPreview,
    settlement_amount: int,
) -> None:
    """Require settlement to equal the current outstanding amount."""

    required = preview.settlement_required

    if settlement_amount < required:
        raise SettlementRequiredError(
            field_errors={
                "settlement_amount": SETTLEMENT_NOT_ENOUGH,
            },
            details={
                "settlement_required": required,
                "usage_cost": preview.usage_cost,
                "balance_before": preview.balance_before,
            },
        )

    if settlement_amount > required:
        raise ValidationError(
            field_errors={
                "settlement_amount": SETTLEMENT_EXCESS,
            }
        )


def _session_summary(
    session: UsageSession, customer: Customer, machine: Machine
) -> SessionSummary:
    return SessionSummary(
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
    )


def _build_checkout_preview(
    session: UsageSession,
    customer: Customer,
    machine: Machine,
    balance: int,
    at: datetime,
) -> CheckoutPreview:
    """SES-07, SES-08: tính theo đơn giá snapshot của phiên.

    preview_checkout và complete_checkout dùng chung để hai bên không lệch số.
    """

    cost = session.calculate_cost(at)
    projected = balance - cost
    return CheckoutPreview(
        session=_session_summary(session, customer, machine),
        calculated_at=at,
        elapsed_seconds=session.elapsed_seconds(at),
        billed_minutes=session.calculate_billed_minutes(at),
        usage_cost=cost,
        balance_before=balance,
        projected_balance=projected,
        # Số dư dự kiến âm chỉ báo số tiền cần bù; không tự kết thúc phiên.
        settlement_required=max(0, -projected),
    )


class SessionService:
    """Triển khai SessionServiceProtocol trên MySQL."""

    def __init__(
        self,
        machine_repo: MachineRepository | None = None,
        session_repo: SessionRepository | None = None,
        customer_repo: CustomerRepository | None = None,
        account_repo: AccountRepository | None = None,
        auth_repo: AuthRepository | None = None,
        invoice_repo: InvoiceRepository | None = None,
        actor_provider: ActorProvider | None = None,
        transaction_factory: Callable[[], AbstractContextManager[Any]] = transaction,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._machines = machine_repo or MachineRepository()
        self._sessions = session_repo or SessionRepository()
        self._customers = customer_repo or CustomerRepository()
        self._accounts = account_repo or AccountRepository()
        self._auth = auth_repo or AuthRepository()
        self._invoices = invoice_repo or InvoiceRepository()
        # Không có provider thì không có phiên đăng nhập, mọi thao tác bị từ chối.
        self._actor_provider = actor_provider
        self._transaction = transaction_factory
        self._clock = clock

    def preview_open(
        self,
        customer_id: int,
        machine_id: int,
        actor: EmployeeSession,
    ) -> OpenSessionPreview:
        with self._database() as conn:
            current = self._require_actor(conn, actor)
            customer, account, machine = self._check_can_open(
                conn, current, customer_id, machine_id
            )

        balance = account.balance
        rate = machine.hourly_rate
        required = minimum_balance(rate)
        can_open = balance >= required
        return OpenSessionPreview(
            customer_id=customer.id,
            machine_id=machine.id,
            balance=balance,
            hourly_rate=rate,
            minimum_balance=required,
            estimated_minutes=estimate_play_minutes(balance, rate),
            can_open=can_open,
            blocked_reason=None if can_open else NOT_ENOUGH_BALANCE,
            as_of=self._clock(),
        )

    def open_session(
        self,
        customer_id: int,
        machine_id: int,
        actor: EmployeeSession,
    ) -> SessionSummary:
        with self._database() as conn:
            current = self._require_actor(conn, actor)
            customer, account, machine = self._check_can_open(
                conn, current, customer_id, machine_id, lock=True
            )

            required = minimum_balance(machine.hourly_rate)
            if account.balance < required:
                raise InsufficientBalanceError(
                    NOT_ENOUGH_BALANCE,
                    details={
                        "balance": account.balance,
                        "minimum_balance": required,
                        "required_top_up": required - account.balance,
                    },
                )

            # Cột DATETIME không lưu phần giây lẻ; bỏ trước để giá trị trả về khớp DB.
            started_at = self._clock().replace(microsecond=0)
            code = new_session_code()
            session_id = self._sessions.create(
                conn,
                code=code,
                customer_id=customer.id,
                machine_id=machine.id,
                opened_by=current.employee_id,
                started_at=started_at,
                # SES-02: chụp đơn giá lúc mở; đổi giá máy sau đó không ảnh hưởng phiên.
                hourly_rate=machine.hourly_rate,
            )
            if not self._machines.mark_in_use(conn, machine.id):
                # Raise trong transaction để rollback cả phiên vừa insert.
                raise _conflict("machine_id", MACHINE_BUSY)

        return SessionSummary(
            session_id=session_id,
            session_code=code,
            customer_id=customer.id,
            customer_code=customer.code,
            customer_name=customer.full_name,
            machine_id=machine.id,
            machine_code=machine.code,
            machine_name=machine.name,
            started_at=started_at,
            hourly_rate=machine.hourly_rate,
            status=SessionStatus.ACTIVE,
        )

    def preview_checkout(
        self,
        machine_id: int,
        current_time: datetime,
    ) -> CheckoutPreview:
        if not isinstance(current_time, datetime) or current_time.utcoffset() is None:
            raise ValidationError(field_errors={"current_time": CURRENT_TIME_INVALID})
        at = current_time.astimezone(timezone.utc)

        with self._database() as conn:
            # Contract không nhận actor: dùng chính người đang đăng nhập.
            logged_in = self._actor_provider() if self._actor_provider else None
            current = self._require_actor(conn, logged_in)
            machine, session, customer = self._get_active_session(
                conn, current, machine_id
            )

        return _build_checkout_preview(
            session, customer, machine, customer.account.balance, at
        )

    def complete_checkout(
        self,
        machine_id: int,
        actor: EmployeeSession,
        settlement_amount: int,
        method: PaymentMethod | None,
    ) -> CheckoutResult:
        method = _validate_settlement_input(settlement_amount, method)

        with self._database() as conn:
            current = self._require_actor(conn, actor)
            machine, session, customer, account = self._lock_for_checkout(
                conn, current, machine_id
            )

            # Tính lại bằng giờ server và số dư đã khóa; không tin số liệu từ UI.
            ended_at = max(self._clock().replace(microsecond=0), session.started_at)
            preview = _build_checkout_preview(
                session, customer, machine, account.balance, ended_at
            )
            _check_settlement_amount(preview, settlement_amount)
            cost = session.complete(current.employee_id, ended_at)

            # Cộng tiền bù trước để lệnh trừ phí không bao giờ làm số dư âm.
            if settlement_amount:
                self._accounts.credit_balance(conn, account.id, settlement_amount)
                self._accounts.insert_debt_settlement_transaction(
                    conn,
                    code=new_transaction_code(),
                    account_id=account.id,
                    employee_id=current.employee_id,
                    session_id=session.id,
                    settlement_amount=settlement_amount,
                    method=method,
                )
                account.credit(settlement_amount)
            if not self._accounts.debit_balance(conn, account.id, cost):
                raise ConflictError(BALANCE_CHANGED)
            account.debit(cost)
            self._accounts.insert_usage_payment_transaction(
                conn,
                code=new_transaction_code(),
                account_id=account.id,
                employee_id=current.employee_id,
                session_id=session.id,
                usage_cost=cost,
            )

            if not self._sessions.complete(conn, session):
                raise _conflict("machine_id", ALREADY_CHECKED_OUT)
            if not self._machines.mark_available(conn, machine.id):
                raise _conflict("machine_id", NO_ACTIVE_SESSION)

            invoice_id = self._invoices.create(
                conn,
                code=new_invoice_code(),
                session_id=session.id,
                customer_id=customer.id,
                employee_id=current.employee_id,
                store_id=machine.store_id,
                usage_cost=cost,
                settlement_amount=settlement_amount,
            )
            # Đọc lại để created_at đúng giờ MySQL ghi.
            invoice = self._invoices.get_by_id(conn, invoice_id)
            if invoice is None:
                raise ServiceUnavailableError()

        summary = InvoiceSummary(
            invoice_id=invoice.id,
            invoice_code=invoice.code,
            session_id=session.id,
            customer_id=customer.id,
            customer_name=customer.full_name,
            employee_id=current.employee_id,
            employee_name=current.full_name,
            store_id=invoice.store_id,
            store_name=current.store_name,
            usage_cost=invoice.usage_cost,
            settlement_amount=invoice.settlement_amount,
            total_amount=invoice.total_amount,
            status=invoice.status,
            created_at=invoice.created_at,
        )
        return CheckoutResult(
            invoice=InvoiceDetail(
                invoice=summary,
                session=_session_summary(session, customer, machine),
                ended_at=ended_at,
                billed_minutes=preview.billed_minutes,
            ),
            balance_after=account.balance,
        )

    def _require_actor(
        self, conn: Any, requested_actor: EmployeeSession
    ) -> EmployeeSession:
        """Đọc lại actor từ DB; không tin role/store do caller truyền vào."""

        actor = self._actor_provider() if self._actor_provider else None
        if (
            not isinstance(actor, EmployeeSession)
            or not _is_positive_id(actor.employee_id)
            or not _is_positive_id(actor.store_id)
        ):
            raise PermissionDeniedError()

        # actor truyền vào phải đúng là người đang đăng nhập.
        if (
            not isinstance(requested_actor, EmployeeSession)
            or requested_actor.employee_id != actor.employee_id
            or requested_actor.store_id != actor.store_id
        ):
            raise PermissionDeniedError()

        current = self._auth.get_active_session_by_id(conn, actor.employee_id)
        if current is None or current.store_id != actor.store_id:
            raise PermissionDeniedError()
        # Role lấy từ DB; actor khai role khác DB (vd. STAFF tự nhận MANAGER) bị từ chối.
        if requested_actor.role != current.role or current.role not in SESSION_ROLES:
            raise PermissionDeniedError()
        return current

    def _check_can_open(
        self,
        conn: Any,
        current: EmployeeSession,
        customer_id: int,
        machine_id: int,
        *,
        lock: bool = False,
    ) -> tuple[Customer, Account, Machine]:
        """Mọi điều kiện mở phiên trừ số dư; vi phạm thì raise exception.

        lock=True (open_session) khóa máy, account và phiên bằng FOR UPDATE.
        """
        machine = self._get_machine(conn, machine_id, for_update=lock)
        if machine.store_id != current.store_id:
            raise PermissionDeniedError(WRONG_STORE)
        if not machine.is_active:
            raise _conflict("machine_id", MACHINE_ARCHIVED)
        if machine.status == MachineStatus.MAINTENANCE:
            raise _conflict("machine_id", MACHINE_MAINTENANCE)
        if machine.status != MachineStatus.AVAILABLE:
            raise _conflict("machine_id", MACHINE_BUSY)

        customer = self._get_customer(conn, customer_id)
        if customer.status != CustomerStatus.ACTIVE:
            raise _conflict("customer_id", CUSTOMER_INACTIVE)
        # Khi mở phiên, khóa dòng account để số dư không đổi giữa lúc kiểm tra và insert.
        account = (
            self._accounts.get_by_id(conn, customer.account.id, for_update=True)
            if lock
            else customer.account
        )
        if account is None:
            raise NotFoundError(CUSTOMER_NOT_FOUND)
        if account.status != AccountStatus.ACTIVE:
            raise _conflict("customer_id", ACCOUNT_LOCKED)

        if self._sessions.get_active_by_machine(conn, machine.id, for_update=lock) is not None:
            raise _conflict("machine_id", MACHINE_BUSY)
        if self._sessions.get_active_by_customer(conn, customer.id, for_update=lock) is not None:
            raise _conflict("customer_id", CUSTOMER_BUSY)
        return customer, account, machine

    def _get_active_session(
        self, conn: Any, current: EmployeeSession, machine_id: int
    ) -> tuple[Machine, UsageSession, Customer]:
        """Máy thuộc cửa hàng hiện tại và đang có phiên ACTIVE; không khóa dữ liệu."""

        machine = self._get_machine(conn, machine_id)
        if machine.store_id != current.store_id:
            raise PermissionDeniedError(WRONG_STORE)
        session = self._sessions.get_active_by_machine(conn, machine.id)
        if session is None or machine.status != MachineStatus.IN_USE:
            raise _conflict("machine_id", NO_ACTIVE_SESSION)
        return machine, session, self._get_customer(conn, session.customer_id)

    def _lock_for_checkout(
        self, conn: Any, current: EmployeeSession, machine_id: int
    ) -> tuple[Machine, UsageSession, Customer, Account]:
        """Khóa máy -> account -> phiên (cùng thứ tự mở phiên) rồi kiểm tra lại."""

        machine = self._get_machine(conn, machine_id, for_update=True)
        if machine.store_id != current.store_id:
            raise PermissionDeniedError(WRONG_STORE)
        # Đọc thường để biết cần khóa account của khách nào.
        session = self._sessions.get_active_by_machine(conn, machine.id)
        if session is None or machine.status != MachineStatus.IN_USE:
            raise _conflict("machine_id", NO_ACTIVE_SESSION)
        customer = self._get_customer(conn, session.customer_id)
        account = self._accounts.get_by_id(conn, customer.account.id, for_update=True)
        locked = self._sessions.get_active_by_machine(conn, machine.id, for_update=True)
        # Phiên đã bị checkout hoặc đổi giữa lúc đọc và lúc khóa thì dừng lại.
        if account is None or locked is None or locked.id != session.id:
            raise _conflict("machine_id", NO_ACTIVE_SESSION)
        return machine, locked, customer, account

    def _get_machine(
        self, conn: Any, machine_id: int, *, for_update: bool = False
    ) -> Machine:
        if _is_positive_id(machine_id):
            machine = self._machines.get_by_id(conn, machine_id, for_update=for_update)
            if machine is not None:
                return machine
        raise NotFoundError(MACHINE_NOT_FOUND)

    def _get_customer(self, conn: Any, customer_id: int) -> Customer:
        if _is_positive_id(customer_id):
            customer = self._customers.get_by_id(conn, customer_id)
            if customer is not None:
                return customer
        raise NotFoundError(CUSTOMER_NOT_FOUND)

    @contextmanager
    def _database(self) -> Iterator[Any]:
        """Mở transaction và đổi lỗi MySQL thành lỗi nghiệp vụ theo contract."""

        try:
            with self._transaction() as conn:
                yield conn
        except IntegrityError as exc:
            # Lưới an toàn cuối: unique index chặn hai phiên ACTIVE (SES-03).
            if exc.errno == errorcode.ER_DUP_ENTRY:
                message = str(exc)
                if "uq_usage_sessions_active_machine" in message:
                    raise ConflictError(
                        MACHINE_BUSY, field_errors={"machine_id": MACHINE_BUSY}
                    ) from exc
                if "uq_usage_sessions_active_customer" in message:
                    raise ConflictError(
                        CUSTOMER_BUSY, field_errors={"customer_id": CUSTOMER_BUSY}
                    ) from exc
                # Lưới an toàn cuối: mỗi phiên chỉ có một hóa đơn (INV-01).
                if "uq_invoices_session" in message:
                    raise _conflict("machine_id", ALREADY_CHECKED_OUT) from exc
            raise ServiceUnavailableError() from exc
        except MySQLError as exc:
            raise ServiceUnavailableError() from exc
