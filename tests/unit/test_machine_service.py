"""LI-05 — Unit test cho MachineService, dùng repository giả nên không cần MySQL."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from mysql.connector import errorcode
from mysql.connector.errors import IntegrityError, InterfaceError

from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    MachineArchiveAction,
    MachineStatus,
    Role,
    SessionStatus,
)
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationError,
)
from cyberhub_manager.domain.models import Account, Customer, Machine, UsageSession
from cyberhub_manager.services.contracts import MachineServiceProtocol
from cyberhub_manager.services.machine_service import MachineService

STORE_ID = 1
OTHER_STORE_ID = 2
NOW = datetime(2026, 10, 23, 8, 0, tzinfo=timezone.utc)

ROLE_EMPLOYEE_IDS = {
    Role.MANAGER: 1,
    Role.ADMIN: 2,
    Role.STAFF: 3,
}

def make_actor(
    role=Role.MANAGER,
    store_id=STORE_ID,
    *,
    employee_id=None,
):
    resolved_employee_id = (
        ROLE_EMPLOYEE_IDS[role]
        if employee_id is None
        else employee_id
    )

    return EmployeeSession(
        employee_id=resolved_employee_id,
        employee_code="NV001",
        full_name="LI05 Actor",
        username="li05.actor",
        store_id=store_id,
        store_code="CH001",
        store_name="Cửa hàng test",
        role=role,
    )


def make_machine(machine_id=1, *, store_id=STORE_ID, status=MachineStatus.AVAILABLE,
                 is_active=True, hourly_rate=6_000):
    return Machine(
        id=machine_id,
        code=f"PC{machine_id:02d}",
        store_id=store_id,
        name=f"Máy {machine_id}",
        status=status,
        hourly_rate=hourly_rate,
        is_active=is_active,
        updated_at=NOW,
    )


def make_customer(balance=50_000):
    account = Account(
        id=10,
        code="ACC001",
        customer_id=5,
        username="khach01",
        balance=balance,
        status=AccountStatus.ACTIVE,
    )
    return Customer(
        id=5,
        code="KH001",
        full_name="Nguyễn Văn A",
        phone="0900000001",
        status=CustomerStatus.ACTIVE,
        account=account,
    )


def make_session(machine_id, *, minutes=10, hourly_rate=6_000):
    return UsageSession(
        id=100,
        code="SS001",
        customer_id=5,
        machine_id=machine_id,
        opened_by=1,
        closed_by=None,
        started_at=NOW - timedelta(minutes=minutes),
        ended_at=None,
        hourly_rate=hourly_rate,
        cost=None,
        status=SessionStatus.ACTIVE,
    )


class FakeAuthRepository:
    def __init__(self, actor, *, active=True):
        self.actor = actor
        self.active = active

    def get_active_session_by_id(
        self,
        conn,
        employee_id,
    ):
        if (
            not self.active
            or self.actor is None
            or self.actor.employee_id != employee_id
        ):
            return None

        return self.actor

# ----- Đồ giả ----------------------------------------------------------------
class FakeMachineRepository:
    def __init__(self, machines=()):
        self.machines = {machine.id: machine for machine in machines}
        self.calls = []
        self.create_error = None
        self.archive_error = None
        self.archive_result = MachineArchiveAction.DELETED

    def get_by_id(self, conn, machine_id, *, for_update=False):
        self.calls.append(("get_by_id", machine_id, for_update))
        return self.machines.get(machine_id)

    def list_by_store(self, conn, store_id):
        return [m for m in self.machines.values() if m.store_id == store_id and m.is_active]

    def create(self, conn, *, code, store_id, name, hourly_rate):
        if self.create_error is not None:
            raise self.create_error
        machine_id = max(self.machines, default=0) + 1
        self.machines[machine_id] = Machine(
            id=machine_id, code=code, store_id=store_id, name=name,
            status=MachineStatus.AVAILABLE, hourly_rate=hourly_rate,
            is_active=True, updated_at=NOW,
        )
        self.calls.append(("create", code))
        return machine_id

    def update_info(self, conn, machine_id, *, name, hourly_rate):
        old = self.machines[machine_id]
        self.machines[machine_id] = Machine(
            id=old.id, code=old.code, store_id=old.store_id, name=name,
            status=old.status, hourly_rate=hourly_rate,
            is_active=old.is_active, updated_at=NOW,
        )
        self.calls.append(("update_info", machine_id))
        return True

    def set_maintenance(self, conn, machine_id, enabled):
        old = self.machines[machine_id]
        self.machines[machine_id] = Machine(
            id=old.id, code=old.code, store_id=old.store_id, name=old.name,
            status=MachineStatus.MAINTENANCE if enabled else MachineStatus.AVAILABLE,
            hourly_rate=old.hourly_rate, is_active=old.is_active, updated_at=NOW,
        )
        self.calls.append(("set_maintenance", machine_id))
        return True

    def archive_or_delete(self, conn, machine_id):
        if self.archive_error is not None:
            raise self.archive_error
        self.calls.append(("archive_or_delete", machine_id))
        return self.archive_result

    def wrote(self):
        return [call for call in self.calls if call[0] != "get_by_id"]


class FakeSessionRepository:
    def __init__(self, sessions=()):
        self.sessions = list(sessions)

    def list_active_by_store(self, conn, store_id):
        return self.sessions


class FakeCustomerRepository:
    def __init__(self, customer=None):
        self.customer = customer

    def get_by_id(self, conn, customer_id):
        return self.customer


class FakeTransaction:
    def __init__(self):
        self.calls = 0
        self.rolled_back = False

    @contextmanager
    def __call__(self):
        self.calls += 1
        try:
            yield object()
        except BaseException:
            self.rolled_back = True
            raise


def build_service(
    machines=(),
    sessions=(),
    customer=None,
    *,
    actor=None,
    database_actor=None,
    actor_is_active=True,
):
    repo = FakeMachineRepository(machines)
    tx = FakeTransaction()

    trusted_actor = actor or make_actor()
    current_actor = (
        trusted_actor
        if database_actor is None
        else database_actor
    )

    service = MachineService(
        machine_repo=repo,
        session_repo=FakeSessionRepository(sessions),
        customer_repo=FakeCustomerRepository(customer),
        auth_repo=FakeAuthRepository(
            current_actor,
            active=actor_is_active,
        ),
        actor_provider=lambda: trusted_actor,
        transaction_factory=tx,
        clock=lambda: NOW,
    )

    return service, repo, tx


# ----- Contract --------------------------------------------------------------


def test_machine_service_matches_protocol():
    assert isinstance(MachineService(), MachineServiceProtocol)


# ----- list_machines ---------------------------------------------------------


def test_list_machines_builds_active_session_summary():
    busy = make_machine(1, status=MachineStatus.IN_USE, hourly_rate=6_000)
    idle = make_machine(2)
    service, _repo, _tx = build_service(
        machines=[busy, idle],
        sessions=[make_session(1, minutes=10, hourly_rate=6_000)],
        customer=make_customer(balance=50_000),
    )

    summaries = {item.machine_id: item for item in service.list_machines(STORE_ID)}

    assert summaries[2].active_session is None
    active = summaries[1].active_session
    assert active.session.customer_name == "Nguyễn Văn A"
    assert active.session.machine_code == "PC01"
    assert active.elapsed_seconds == 600
    # 10 phút x 6.000đ/giờ = 1.000đ.
    assert active.estimated_cost == 1_000
    assert active.account_balance == 50_000
    assert active.projected_balance == 49_000
    assert active.as_of == NOW


def test_list_machines_rejects_in_use_machine_without_session():
    service, _repo, _tx = build_service(
        machines=[make_machine(1, status=MachineStatus.IN_USE)]
    )

    with pytest.raises(ConflictError):
        service.list_machines(STORE_ID)


# ----- Quyền và phạm vi cửa hàng ---------------------------------------------


@pytest.mark.parametrize(
    "operation",
    [
        lambda s, actor: s.create_machine("PC09", STORE_ID, "Máy", 5_000, actor),
        lambda s, actor: s.update_machine(1, "Máy", 5_000, actor),
        lambda s, actor: s.set_maintenance(1, True, actor),
        lambda s, actor: s.archive_machine(1, actor),
    ],
    ids=["create", "update", "maintenance", "archive"],
)
def test_staff_cannot_manage_machines(operation):
    actor = make_actor(role=Role.STAFF)
    service, repo, _tx = build_service(
        machines=[make_machine(1)],
        actor=actor,
    )
    with pytest.raises(PermissionDeniedError):
        operation(service, actor)
    assert repo.wrote() == []


@pytest.mark.parametrize("role", [Role.MANAGER, Role.ADMIN])
def test_manager_and_admin_share_machine_permissions(role):
    actor = make_actor(role)
    service, _repo, _tx = build_service(actor=actor)

    machine = service.create_machine(
        "PC09",
        STORE_ID,
        "Máy",
        5_000,
        actor,
    )

    assert machine.code == "PC09"


def test_create_machine_rejects_other_store_before_write():
    service, repo, tx = build_service()

    with pytest.raises(PermissionDeniedError):
        service.create_machine("PC09", OTHER_STORE_ID, "Máy", 5_000, make_actor())

    assert tx.calls == 1
    assert tx.rolled_back is True
    assert repo.wrote() == []


@pytest.mark.parametrize(
    "operation",
    [
        lambda s, actor: s.update_machine(1, "Máy", 5_000, actor),
        lambda s, actor: s.set_maintenance(1, True, actor),
        lambda s, actor: s.archive_machine(1, actor),
    ],
    ids=["update", "maintenance", "archive"],
)
def test_machine_of_other_store_is_denied(operation):
    service, repo, _tx = build_service(machines=[make_machine(1, store_id=OTHER_STORE_ID)])

    with pytest.raises(PermissionDeniedError):
        operation(service, make_actor())

    assert repo.wrote() == []


@pytest.mark.parametrize(
    "operation",
    [
        lambda s, actor: s.update_machine(99, "Máy", 5_000, actor),
        lambda s, actor: s.set_maintenance(99, True, actor),
        lambda s, actor: s.archive_machine(99, actor),
    ],
    ids=["update", "maintenance", "archive"],
)
def test_unknown_machine_raises_not_found(operation):
    service, _repo, _tx = build_service()

    with pytest.raises(NotFoundError):
        operation(service, make_actor())


# ----- Validation và xung đột ------------------------------------------------


def test_create_machine_reports_all_invalid_fields():
    service, _repo, tx = build_service()

    with pytest.raises(ValidationError) as exc_info:
        service.create_machine("   ", STORE_ID, "", True, make_actor())

    assert set(exc_info.value.field_errors) == {"code", "name", "hourly_rate"}
    assert tx.calls == 0


@pytest.mark.parametrize("hourly_rate", [0, -1, 1.5, "5000", None, True])
def test_update_machine_rejects_invalid_hourly_rate(hourly_rate):
    service, repo, _tx = build_service(machines=[make_machine(1)])

    with pytest.raises(ValidationError) as exc_info:
        service.update_machine(1, "Máy", hourly_rate, make_actor())

    assert set(exc_info.value.field_errors) == {"hourly_rate"}
    assert repo.wrote() == []


def test_create_machine_maps_duplicate_code_to_conflict():
    service, repo, _tx = build_service()
    repo.create_error = IntegrityError(
        msg="Duplicate entry 'PC01' for key 'machines.uq_machines_code'",
        errno=errorcode.ER_DUP_ENTRY,
    )

    with pytest.raises(ConflictError) as exc_info:
        service.create_machine("PC01", STORE_ID, "Máy", 5_000, make_actor())

    assert exc_info.value.field_errors == {"code": "Mã máy đã tồn tại"}


def test_database_error_becomes_service_unavailable():
    service, repo, _tx = build_service()
    repo.create_error = InterfaceError(msg="mất kết nối")

    with pytest.raises(ServiceUnavailableError):
        service.create_machine("PC01", STORE_ID, "Máy", 5_000, make_actor())


def test_update_machine_allows_in_use_machine():
    service, _repo, _tx = build_service(
        machines=[make_machine(1, status=MachineStatus.IN_USE)]
    )

    machine = service.update_machine(1, "Tên mới", 9_000, make_actor())

    assert machine.hourly_rate == 9_000


def test_update_machine_rejects_archived_machine():
    service, repo, tx = build_service(machines=[make_machine(1, is_active=False)])

    with pytest.raises(ConflictError):
        service.update_machine(1, "Tên mới", 9_000, make_actor())

    assert repo.wrote() == []
    assert tx.rolled_back is True


def test_set_maintenance_locks_row_and_rejects_machine_in_use():
    service, repo, _tx = build_service(
        machines=[make_machine(1, status=MachineStatus.IN_USE)]
    )

    with pytest.raises(ConflictError):
        service.set_maintenance(1, True, make_actor())

    assert ("get_by_id", 1, True) in repo.calls
    assert repo.wrote() == []


def test_set_maintenance_rejects_non_bool_flag():
    service, _repo, _tx = build_service(machines=[make_machine(1)])

    with pytest.raises(ValidationError):
        service.set_maintenance(1, "yes", make_actor())


def test_archive_machine_rejects_machine_in_use():
    service, repo, _tx = build_service(
        machines=[make_machine(1, status=MachineStatus.IN_USE)]
    )

    with pytest.raises(ConflictError) as exc_info:
        service.archive_machine(1, make_actor())

    assert exc_info.value.message == "Không thể ngừng sử dụng máy đang có phiên"
    assert repo.wrote() == []


def test_archive_machine_translates_repository_conflict():
    service, repo, tx = build_service(machines=[make_machine(1)])
    repo.archive_error = ConflictError("Machine has an active session")

    with pytest.raises(ConflictError) as exc_info:
        service.archive_machine(1, make_actor())

    assert exc_info.value.message == "Không thể ngừng sử dụng máy đang có phiên"
    assert tx.rolled_back is True


@pytest.mark.parametrize(
    "action", [MachineArchiveAction.DELETED, MachineArchiveAction.ARCHIVED]
)
def test_archive_machine_returns_repository_action(action):
    service, repo, _tx = build_service(machines=[make_machine(1)])
    repo.archive_result = action

    result = service.archive_machine(1, make_actor())

    assert result.machine_id == 1
    assert result.action == action
