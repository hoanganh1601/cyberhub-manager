"""LI-06 — Linh: SessionService xem trước và mở phiên sử dụng máy.

Service chỉ làm việc qua repository và database.transaction.transaction();
UI không gọi repository hay SQL trực tiếp. Checkout và hóa đơn thuộc LI-07.
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
)
from cyberhub_manager.domain.models import (
    Account,
    Customer,
    Machine,
    estimate_play_minutes,
    minimum_balance,
    MINIMUM_SESSION_MINUTES,
)
from cyberhub_manager.repositories.account_repository import AccountRepository
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.repositories.customer_repository import CustomerRepository
from cyberhub_manager.repositories.machine_repository import MachineRepository
from cyberhub_manager.repositories.session_repository import SessionRepository

ActorProvider = Callable[[], EmployeeSession | None]

# STAFF, MANAGER và ADMIN đều được mở phiên trong cửa hàng của mình.
OPEN_SESSION_ROLES = frozenset({Role.STAFF, Role.MANAGER, Role.ADMIN})

# "SS-" + 17 ký tự hex = 20 ký tự, vừa cột usage_sessions.code VARCHAR(20).
SESSION_CODE_PREFIX = "SS-"
SESSION_CODE_HEX_LENGTH = 17

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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_positive_id(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _conflict(field: str, message: str) -> ConflictError:
    """field_errors giúp UI biết đánh dấu ô khách hay ô máy."""

    return ConflictError(message, field_errors={field: message})


def new_session_code() -> str:
    return SESSION_CODE_PREFIX + uuid4().hex[:SESSION_CODE_HEX_LENGTH]


class SessionService:
    """Triển khai SessionServiceProtocol trên MySQL (phần mở phiên)."""

    def __init__(
        self,
        machine_repo: MachineRepository | None = None,
        session_repo: SessionRepository | None = None,
        customer_repo: CustomerRepository | None = None,
        account_repo: AccountRepository | None = None,
        auth_repo: AuthRepository | None = None,
        actor_provider: ActorProvider | None = None,
        transaction_factory: Callable[[], AbstractContextManager[Any]] = transaction,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._machines = machine_repo or MachineRepository()
        self._sessions = session_repo or SessionRepository()
        self._customers = customer_repo or CustomerRepository()
        self._accounts = account_repo or AccountRepository()
        self._auth = auth_repo or AuthRepository()
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
        raise NotImplementedError("Checkout thuộc LI-07")

    def complete_checkout(
        self,
        machine_id: int,
        actor: EmployeeSession,
        settlement_amount: int,
        method: PaymentMethod | None,
    ) -> CheckoutResult:
        raise NotImplementedError("Checkout thuộc LI-07")

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
        if requested_actor.role != current.role or current.role not in OPEN_SESSION_ROLES:
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
            raise ServiceUnavailableError() from exc
        except MySQLError as exc:
            raise ServiceUnavailableError() from exc
