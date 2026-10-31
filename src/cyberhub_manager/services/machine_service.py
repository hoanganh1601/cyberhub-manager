"""LI-05 — Linh: MachineService quản lý và hiển thị máy theo cửa hàng.

Service chỉ làm việc qua MachineRepository, SessionRepository, CustomerRepository
và database.transaction.transaction(); UI không gọi repository hay SQL trực tiếp.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import datetime, timezone
from typing import Any

from mysql.connector import Error as MySQLError
from mysql.connector import errorcode
from mysql.connector.errors import IntegrityError

from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.domain.dtos import (
    ActiveSessionSummary,
    EmployeeSession,
    MachineArchiveResult,
    MachineSummary,
    SessionSummary,
)
from cyberhub_manager.domain.enums import MachineStatus, Role
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationError,
)
from cyberhub_manager.domain.models import Machine, UsageSession
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.repositories.customer_repository import CustomerRepository
from cyberhub_manager.repositories.machine_repository import MachineRepository
from cyberhub_manager.repositories.session_repository import SessionRepository

MANAGER_ROLES = frozenset({Role.MANAGER, Role.ADMIN})
ActorProvider = Callable[[], EmployeeSession | None]

CODE_TAKEN = "Mã máy đã tồn tại"
WRONG_STORE = "Bạn chỉ được thao tác dữ liệu của cửa hàng hiện tại"
MACHINE_NOT_FOUND = "Không tìm thấy máy"
UPDATE_ARCHIVED = "Không thể sửa máy đã ngừng sử dụng"
MAINTENANCE_IN_USE = "Không thể bảo trì máy đang được sử dụng"
MAINTENANCE_ARCHIVED = "Không thể thay đổi máy đã ngừng sử dụng"
ARCHIVE_IN_USE = "Không thể ngừng sử dụng máy đang có phiên"
INCONSISTENT_SESSION = "Dữ liệu máy và phiên không nhất quán"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ----- Validate từng trường, trả thông báo lỗi hoặc None --------------------

def _clean(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _code_error(code: str) -> str | None:
    if not 1 <= len(code) <= 20:
        return "Mã máy phải có từ 1 đến 20 ký tự"
    return None


def _name_error(name: str) -> str | None:
    if not 1 <= len(name) <= 100:
        return "Tên máy phải có từ 1 đến 100 ký tự"
    return None


def _hourly_rate_error(value: object) -> str | None:
    # bool là lớp con của int nên phải loại riêng.
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return "Đơn giá phải là số nguyên lớn hơn 0"
    return None


def _raise_if_errors(errors: dict[str, str | None]) -> None:
    """Gom mọi lỗi trường vào một ValidationError để UI đánh dấu cùng lúc."""

    field_errors = {field: message for field, message in errors.items() if message}
    if field_errors:
        raise ValidationError(field_errors=field_errors)


def _is_positive_id(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0

class MachineService:
    """Triển khai MachineServiceProtocol trên MySQL."""

    def __init__(
        self,
        machine_repo: MachineRepository | None = None,
        session_repo: SessionRepository | None = None,
        customer_repo: CustomerRepository | None = None,
        auth_repo: AuthRepository | None = None,
        actor_provider: ActorProvider | None = None,
        transaction_factory: Callable[[], AbstractContextManager[Any]] = transaction,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._machines = machine_repo or MachineRepository()
        self._sessions = session_repo or SessionRepository()
        self._customers = customer_repo or CustomerRepository()
        self._auth = auth_repo or AuthRepository()
        self._actor_provider = actor_provider
        self._transaction = transaction_factory
        self._clock = clock

    def list_machines(self, store_id: int) -> list[MachineSummary]:
        now = self._clock()

        with self._database() as conn:
            self._require_actor(
                conn,
                requested_store_id=store_id,
            )

            machines = self._machines.list_by_store(
                conn,
                store_id,
            )
            sessions = {
                session.machine_id: session
                for session in self._sessions.list_active_by_store(
                    conn,
                    store_id,
                )
            }

            return [
                self._to_summary(
                    conn,
                    machine,
                    sessions.get(machine.id),
                    now,
                )
                for machine in machines
            ]

    def create_machine(
        self,
        code: str,
        store_id: int,
        name: str,
        hourly_rate: int,
        actor: EmployeeSession,
    ) -> Machine:
        code = _clean(code)
        name = _clean(name)

        _raise_if_errors(
            {
                "code": _code_error(code),
                "name": _name_error(name),
                "hourly_rate": _hourly_rate_error(hourly_rate),
            }
        )

        with self._database() as conn:
            self._require_actor(
                conn,
                actor,
                requested_store_id=store_id,
                manager_only=True,
            )


            machine_id = self._machines.create(
                conn,
                code = code,
                store_id = store_id,
                name = name,
                hourly_rate = hourly_rate,
            )

            return self._get_machine(conn, machine_id)

    def update_machine(
        self,
        machine_id: int,
        name: str,
        hourly_rate: int,
        actor: EmployeeSession,
    ) -> Machine:
        name = _clean(name)

        with self._database() as conn:
            current_actor = self._require_actor(
                conn,
                actor,
                manager_only=True,
            )

            machine = self._get_machine(
                conn,
                machine_id,
                for_update=True,
            )

            if current_actor.store_id != machine.store_id:
                raise PermissionDeniedError(WRONG_STORE)

            _raise_if_errors(
                {
                    "name": _name_error(name),
                    "hourly_rate": _hourly_rate_error(hourly_rate),
                }
            )

            if not machine.is_active:
                raise ConflictError(UPDATE_ARCHIVED)

            # The active session keeps its hourly-rate snapshot.
            if not self._machines.update_info(
                conn,
                machine.id,
                name=name,
                hourly_rate=hourly_rate,
            ):
                raise ConflictError(UPDATE_ARCHIVED)

            return self._get_machine(conn, machine.id)

    def set_maintenance(
        self,
        machine_id: int,
        enabled: bool,
        actor: EmployeeSession,
    ) -> Machine:
        with self._database() as conn:
            current_actor = self._require_actor(
                conn,
                actor,
                manager_only=True,
            )

            machine = self._get_machine(
                conn,
                machine_id,
                for_update=True,
            )

            if current_actor.store_id != machine.store_id:
                raise PermissionDeniedError(WRONG_STORE)

            if not isinstance(enabled, bool):
                raise ValidationError(
                    field_errors={
                        "enabled": "Giá trị bảo trì không hợp lệ"
                    }
                )

            if machine.status == MachineStatus.IN_USE:
                raise ConflictError(MAINTENANCE_IN_USE)

            if not machine.is_active:
                raise ConflictError(MAINTENANCE_ARCHIVED)

            if not self._machines.set_maintenance(
                conn,
                machine.id,
                enabled,
            ):
                raise ConflictError(MAINTENANCE_IN_USE)

            return self._get_machine(conn, machine.id)

    def archive_machine(
        self,
        machine_id: int,
        actor: EmployeeSession,
    ) -> MachineArchiveResult:
        with self._database() as conn:
            current_actor = self._require_actor(
                conn,
                actor,
                manager_only=True,
            )

            machine = self._get_machine(
                conn,
                machine_id,
                for_update=True,
            )

            if current_actor.store_id != machine.store_id:
                raise PermissionDeniedError(WRONG_STORE)

            if machine.status == MachineStatus.IN_USE:
                raise ConflictError(ARCHIVE_IN_USE)

            try:
                action = self._machines.archive_or_delete(
                    conn,
                    machine.id,
                )
            except ConflictError as exc:
                raise ConflictError(ARCHIVE_IN_USE) from exc

            if action is None:
                raise NotFoundError(MACHINE_NOT_FOUND)

            return MachineArchiveResult(
                machine_id = machine.id,
                action = action,
            )

    def _require_actor(
        self,
        conn: Any,
        requested_actor: EmployeeSession | None = None,
        *,
        requested_store_id: int | None = None,
        manager_only: bool = False,
    ) -> EmployeeSession:
        """Validate actor identity, store scope, and current database role."""

        actor = (
            self._actor_provider()
            if self._actor_provider is not None
            else None
        )

        if (
            not isinstance(actor, EmployeeSession)
            or not _is_positive_id(actor.employee_id)
            or not _is_positive_id(actor.store_id)
        ):
            raise PermissionDeniedError()

        if requested_actor is not None and (
            not isinstance(requested_actor, EmployeeSession)
            or requested_actor.employee_id != actor.employee_id
            or requested_actor.store_id != actor.store_id
        ):
            raise PermissionDeniedError()

        current_actor = self._auth.get_active_session_by_id(
            conn,
            actor.employee_id,
        )

        if current_actor is None or current_actor.store_id != actor.store_id:
            raise PermissionDeniedError()

        if (
            requested_store_id is not None
            and current_actor.store_id != requested_store_id
        ):
            raise PermissionDeniedError(WRONG_STORE)

        if manager_only and current_actor.role not in MANAGER_ROLES:
            raise PermissionDeniedError()

        return current_actor


    @contextmanager
    def _database(self) -> Iterator[Any]:
        """Mở transaction và đổi lỗi MySQL thành lỗi nghiệp vụ theo contract."""

        try:
            with self._transaction() as conn:
                yield conn
        except IntegrityError as exc:
            if exc.errno == errorcode.ER_DUP_ENTRY and "uq_machines_code" in str(exc):
                raise ConflictError(CODE_TAKEN, field_errors={"code": CODE_TAKEN}) from exc
            raise ServiceUnavailableError() from exc
        except MySQLError as exc:
            raise ServiceUnavailableError() from exc

    def _get_machine(
        self, conn: Any, machine_id: int, *, for_update: bool = False
    ) -> Machine:
        if _is_positive_id(machine_id):
            machine = self._machines.get_by_id(conn, machine_id, for_update=for_update)
            if machine is not None:
                return machine
        raise NotFoundError(MACHINE_NOT_FOUND)

    def _to_summary(
        self,
        conn: Any,
        machine: Machine,
        session: UsageSession | None,
        now: datetime,
    ) -> MachineSummary:
        active_session = None
        if machine.status == MachineStatus.IN_USE:
            if session is None:
                raise ConflictError(INCONSISTENT_SESSION)
            active_session = self._to_active_session(conn, machine, session, now)

        elif session is not None:
                raise ConflictError(INCONSISTENT_SESSION)

        return MachineSummary(
            machine_id=machine.id,
            machine_code=machine.code,
            store_id=machine.store_id,
            name=machine.name,
            status=machine.status,
            hourly_rate=machine.hourly_rate,
            is_active=machine.is_active,
            updated_at=machine.updated_at,
            active_session=active_session,
        )

    def _to_active_session(
        self,
        conn: Any,
        machine: Machine,
        session: UsageSession,
        now: datetime,
    ) -> ActiveSessionSummary:
        customer = self._customers.get_by_id(conn, session.customer_id)
        if customer is None:
            raise ConflictError(INCONSISTENT_SESSION)

        # Đồng hồ máy app có thể lệch vài giây so với started_at; không để thời gian âm.
        at = max(now, session.started_at)
        estimated_cost = session.calculate_cost(at)
        balance = customer.account.balance
        return ActiveSessionSummary(
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
            account_balance=balance,
            elapsed_seconds=session.elapsed_seconds(at),
            estimated_cost=estimated_cost,
            projected_balance=balance - estimated_cost,
            as_of=at,
        )
