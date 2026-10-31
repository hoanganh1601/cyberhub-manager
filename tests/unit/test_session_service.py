"""LI-06 — Unit test cho SessionService (xem trước/mở phiên), dùng repository giả.

Đánh số TC theo 15 test case bắt buộc của task LI-06. TC14 (live estimate tại các
mốc biên) nằm trong tests/unit/test_domain_models.py vì phần tính nằm ở domain.
"""

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from mysql.connector import errorcode
from mysql.connector.errors import IntegrityError, InterfaceError

from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    MachineStatus,
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
from cyberhub_manager.domain.models import Account, Customer, Machine, UsageSession
from cyberhub_manager.services.contracts import SessionServiceProtocol
from cyberhub_manager.services.session_service import (
    ACCOUNT_LOCKED,
    CUSTOMER_BUSY,
    CUSTOMER_INACTIVE,
    MACHINE_ARCHIVED,
    MACHINE_BUSY,
    MACHINE_MAINTENANCE,
    NOT_ENOUGH_BALANCE,
    SessionService,
)

STORE_ID = 1
OTHER_STORE_ID = 2
NOW = datetime(2026, 10, 31, 8, 0, tzinfo=timezone.utc)
# Đơn giá 6_000đ/giờ => tối thiểu 30 phút = 3_000đ.
RATE = 6_000
MINIMUM = 3_000

ROLE_EMPLOYEE_IDS = {Role.ADMIN: 1, Role.MANAGER: 2, Role.STAFF: 3}


def make_actor(role=Role.STAFF, store_id=STORE_ID, *, employee_id=None):
    return EmployeeSession(
        employee_id=ROLE_EMPLOYEE_IDS[role] if employee_id is None else employee_id,
        employee_code="NV001",
        full_name="LI06 Actor",
        username="li06.actor",
        store_id=store_id,
        store_code="CH001",
        store_name="Cửa hàng test",
        role=role,
    )


def make_machine(
    machine_id=1,
    *,
    store_id=STORE_ID,
    status=MachineStatus.AVAILABLE,
    is_active=True,
    hourly_rate=RATE,
):
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


def make_customer(
    customer_id=5,
    *,
    balance=50_000,
    status=CustomerStatus.ACTIVE,
    account_status=AccountStatus.ACTIVE,
):
    account = Account(
        id=customer_id + 5,
        code=f"ACC{customer_id:03d}",
        customer_id=customer_id,
        username=f"khach{customer_id:02d}",
        balance=balance,
        status=account_status,
    )
    return Customer(
        id=customer_id,
        code=f"KH{customer_id:03d}",
        full_name="Nguyễn Văn A",
        phone="0900000001",
        status=status,
        account=account,
    )


def make_session(session_id=100, *, customer_id=5, machine_id=1):
    return UsageSession(
        id=session_id,
        code=f"SS-{session_id}",
        customer_id=customer_id,
        machine_id=machine_id,
        opened_by=3,
        closed_by=None,
        started_at=NOW,
        ended_at=None,
        hourly_rate=RATE,
        cost=None,
        status=SessionStatus.ACTIVE,
    )


# ----- Đồ giả ----------------------------------------------------------------
class FakeDatabase:
    """Kho dữ liệu chung của các repository giả; lỗi trong transaction thì rollback."""

    def __init__(self, *, machines, customers, sessions, employees):
        self.machines = {machine.id: machine for machine in machines}
        self.customers = {customer.id: customer for customer in customers}
        self.sessions = {session.id: session for session in sessions}
        self.employees = {employee.employee_id: employee for employee in employees}
        self.writes = []
        self.locks = []
        self.commits = 0
        self.rollbacks = 0
        self.create_error = None
        self.fail_mark_in_use = False

    @contextmanager
    def transaction(self):
        machines, sessions = dict(self.machines), dict(self.sessions)
        try:
            yield object()
        except BaseException:
            self.machines, self.sessions = machines, sessions
            self.rollbacks += 1
            raise
        self.commits += 1


class FakeAuthRepository:
    def __init__(self, db):
        self.db = db

    def get_active_session_by_id(self, conn, employee_id):
        # Employee/store không ACTIVE thì repository thật trả None.
        return self.db.employees.get(employee_id)


class FakeMachineRepository:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, conn, machine_id, *, for_update=False):
        if for_update:
            self.db.locks.append(("machine", machine_id))
        return self.db.machines.get(machine_id)

    def mark_in_use(self, conn, machine_id):
        self.db.writes.append(("mark_in_use", machine_id))
        old = self.db.machines[machine_id]
        if self.db.fail_mark_in_use or old.status != MachineStatus.AVAILABLE:
            return False
        self.db.machines[machine_id] = make_machine(
            machine_id,
            store_id=old.store_id,
            status=MachineStatus.IN_USE,
            is_active=old.is_active,
            hourly_rate=old.hourly_rate,
        )
        return True


class FakeSessionRepository:
    def __init__(self, db):
        self.db = db

    def get_active_by_machine(self, conn, machine_id, *, for_update=False):
        if for_update:
            self.db.locks.append(("session_machine", machine_id))
        return self._find_active(machine_id=machine_id)

    def get_active_by_customer(self, conn, customer_id, *, for_update=False):
        if for_update:
            self.db.locks.append(("session_customer", customer_id))
        return self._find_active(customer_id=customer_id)

    def create(
        self, conn, *, code, customer_id, machine_id, opened_by, started_at, hourly_rate
    ):
        self.db.writes.append(("create_session", machine_id))
        if self.db.create_error is not None:
            raise self.db.create_error
        session_id = max(self.db.sessions, default=0) + 1
        self.db.sessions[session_id] = UsageSession(
            id=session_id,
            code=code,
            customer_id=customer_id,
            machine_id=machine_id,
            opened_by=opened_by,
            closed_by=None,
            started_at=started_at,
            ended_at=None,
            hourly_rate=hourly_rate,
            cost=None,
            status=SessionStatus.ACTIVE,
        )
        return session_id

    def _find_active(self, *, machine_id=None, customer_id=None):
        for session in self.db.sessions.values():
            if session.is_active() and (
                session.machine_id == machine_id or session.customer_id == customer_id
            ):
                return session
        return None


class FakeCustomerRepository:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, conn, customer_id):
        return self.db.customers.get(customer_id)


class FakeAccountRepository:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, conn, account_id, *, for_update=False):
        if for_update:
            self.db.locks.append(("account", account_id))
        for customer in self.db.customers.values():
            if customer.account.id == account_id:
                return customer.account
        return None


def build_service(
    actor=None,
    *,
    machines=None,
    customers=None,
    sessions=(),
    employees=None,
    clock=lambda: NOW,
):
    """actor là người đang đăng nhập; employees là bản ghi ACTIVE trong DB."""

    actor = actor or make_actor()
    db = FakeDatabase(
        machines=[make_machine()] if machines is None else machines,
        customers=[make_customer()] if customers is None else customers,
        sessions=sessions,
        employees=[actor] if employees is None else employees,
    )
    service = SessionService(
        machine_repo=FakeMachineRepository(db),
        session_repo=FakeSessionRepository(db),
        customer_repo=FakeCustomerRepository(db),
        account_repo=FakeAccountRepository(db),
        auth_repo=FakeAuthRepository(db),
        actor_provider=lambda: actor,
        transaction_factory=db.transaction,
        clock=clock,
    )
    return service, db


def call(service, method, actor, customer_id=5, machine_id=1):
    return getattr(service, method)(customer_id, machine_id, actor)


# Các điều kiện chặn phải giống nhau ở preview và open.
BOTH = pytest.mark.parametrize("method", ["preview_open", "open_session"])


def test_session_service_satisfies_protocol():
    assert isinstance(SessionService(), SessionServiceProtocol)


# ----- TC1, TC2: thành công ---------------------------------------------------
def test_preview_then_open_session_success():  # TC1
    actor = make_actor()
    service, db = build_service(actor)

    preview = service.preview_open(5, 1, actor)

    assert preview.balance == 50_000
    assert preview.hourly_rate == RATE
    assert preview.minimum_balance == MINIMUM
    assert preview.estimated_minutes == 500  # floor(50_000 * 60 / 6_000)
    assert preview.can_open is True
    assert preview.blocked_reason is None
    assert preview.as_of == NOW

    summary = service.open_session(5, 1, actor)

    assert summary.session_code.startswith("SS-")
    assert len(summary.session_code) == 20
    assert (summary.customer_id, summary.machine_id) == (5, 1)
    assert (summary.customer_code, summary.machine_code) == ("KH005", "PC01")
    assert summary.started_at == NOW
    assert summary.hourly_rate == RATE
    assert summary.status == SessionStatus.ACTIVE

    saved = db.sessions[summary.session_id]
    assert saved.opened_by == actor.employee_id
    assert saved.hourly_rate == RATE
    assert db.machines[1].status == MachineStatus.IN_USE
    # Chỉ insert phiên và đổi máy: không trừ tiền, không tạo hóa đơn.
    assert db.writes == [("create_session", 1), ("mark_in_use", 1)]
    assert db.customers[5].account.balance == 50_000
    assert db.commits == 2


@pytest.mark.parametrize("role", [Role.STAFF, Role.MANAGER, Role.ADMIN])
def test_every_store_role_can_open_session(role):  # TC2
    actor = make_actor(role)
    service, db = build_service(actor)

    summary = service.open_session(5, 1, actor)

    assert db.sessions[summary.session_id].opened_by == actor.employee_id


def test_open_session_drops_microseconds_to_match_datetime_column():
    service, _ = build_service(clock=lambda: NOW.replace(microsecond=700_000))

    summary = service.open_session(5, 1, make_actor())

    assert summary.started_at == NOW


# ----- TC3, TC4: actor --------------------------------------------------------
@BOTH
def test_inactive_or_locked_actor_is_denied(method):  # TC3
    # Employee LOCKED/INACTIVE hoặc store INACTIVE: AuthRepository trả None.
    actor = make_actor()
    service, db = build_service(actor, employees=[])

    with pytest.raises(PermissionDeniedError):
        call(service, method, actor)
    assert db.writes == []


@BOTH
def test_actor_moved_to_other_store_is_denied(method):
    actor = make_actor()
    service, db = build_service(
        actor, employees=[make_actor(store_id=OTHER_STORE_ID)]
    )

    with pytest.raises(PermissionDeniedError):
        call(service, method, actor)
    assert db.writes == []


@BOTH
def test_missing_actor_provider_is_denied(method):
    db = FakeDatabase(machines=[], customers=[], sessions=[], employees=[])
    service = SessionService(transaction_factory=db.transaction)

    with pytest.raises(PermissionDeniedError):
        call(service, method, make_actor())


@BOTH
@pytest.mark.parametrize(
    "forged",
    [
        make_actor(Role.MANAGER, employee_id=3),  # tự nhận MANAGER bằng id STAFF
        make_actor(Role.STAFF, store_id=OTHER_STORE_ID),  # tự đổi store
        make_actor(Role.ADMIN),  # mượn employee_id của người khác
    ],
)
def test_forged_actor_is_denied(method, forged):  # TC4
    service, db = build_service(make_actor(Role.STAFF))

    with pytest.raises(PermissionDeniedError):
        call(service, method, forged)
    assert db.writes == []


# ----- TC5 - TC7: máy, khách --------------------------------------------------
@BOTH
def test_machine_of_other_store_is_denied(method):  # TC5
    service, db = build_service(machines=[make_machine(store_id=OTHER_STORE_ID)])

    with pytest.raises(PermissionDeniedError):
        call(service, method, make_actor())
    assert db.writes == []


@BOTH
@pytest.mark.parametrize(
    ("machine", "message"),
    [
        (make_machine(status=MachineStatus.MAINTENANCE), MACHINE_MAINTENANCE),
        (make_machine(status=MachineStatus.IN_USE), MACHINE_BUSY),
        (make_machine(is_active=False), MACHINE_ARCHIVED),
    ],
)
def test_unavailable_machine_is_rejected(method, machine, message):  # TC6
    service, db = build_service(machines=[machine])

    with pytest.raises(ConflictError) as exc_info:
        call(service, method, make_actor())

    assert exc_info.value.field_errors == {"machine_id": message}
    assert db.writes == []


@BOTH
@pytest.mark.parametrize(
    ("customer", "message"),
    [
        (make_customer(status=CustomerStatus.INACTIVE), CUSTOMER_INACTIVE),
        (make_customer(account_status=AccountStatus.LOCKED), ACCOUNT_LOCKED),
    ],
)
def test_invalid_customer_or_account_is_rejected(method, customer, message):  # TC7
    service, db = build_service(customers=[customer])

    with pytest.raises(ConflictError) as exc_info:
        call(service, method, make_actor())

    assert exc_info.value.field_errors == {"customer_id": message}
    assert db.writes == []


@BOTH
@pytest.mark.parametrize(
    ("customer_id", "machine_id"), [(5, 99), (99, 1), (5, 0), (True, 1)]
)
def test_missing_or_invalid_ids_are_not_found(method, customer_id, machine_id):
    service, db = build_service()

    with pytest.raises(NotFoundError):
        call(service, method, make_actor(), customer_id, machine_id)
    assert db.writes == []


# ----- TC8: số dư tối thiểu ---------------------------------------------------
def test_balance_below_minimum_is_rejected():  # TC8
    actor = make_actor()
    service, db = build_service(customers=[make_customer(balance=MINIMUM - 1)])

    preview = service.preview_open(5, 1, actor)
    assert preview.can_open is False
    assert preview.blocked_reason == NOT_ENOUGH_BALANCE

    with pytest.raises(InsufficientBalanceError) as exc_info:
        service.open_session(5, 1, actor)

    assert exc_info.value.details == {
        "balance": MINIMUM - 1,
        "minimum_balance": MINIMUM,
        "required_top_up": 1,
    }
    assert db.writes == []
    assert db.machines[1].status == MachineStatus.AVAILABLE


def test_balance_exactly_minimum_can_open():
    service, db = build_service(customers=[make_customer(balance=MINIMUM)])

    service.open_session(5, 1, make_actor())

    assert db.machines[1].status == MachineStatus.IN_USE


# ----- TC9 - TC11: phiên trùng ------------------------------------------------
@BOTH
def test_machine_with_active_session_conflicts(method):  # TC9
    # Dữ liệu lệch: máy vẫn AVAILABLE nhưng đã có phiên ACTIVE của khách khác.
    service, db = build_service(
        customers=[make_customer(), make_customer(6)],
        sessions=[make_session(customer_id=6, machine_id=1)],
    )

    with pytest.raises(ConflictError) as exc_info:
        call(service, method, make_actor())

    assert exc_info.value.field_errors == {"machine_id": MACHINE_BUSY}
    assert db.writes == []


@BOTH
def test_customer_with_active_session_conflicts(method):  # TC10
    service, db = build_service(
        machines=[make_machine(), make_machine(2, status=MachineStatus.IN_USE)],
        sessions=[make_session(customer_id=5, machine_id=2)],
    )

    with pytest.raises(ConflictError) as exc_info:
        call(service, method, make_actor())

    assert exc_info.value.field_errors == {"customer_id": CUSTOMER_BUSY}
    assert db.writes == []


def test_double_click_creates_only_one_session():  # TC11
    actor = make_actor()
    service, db = build_service(actor)
    service.open_session(5, 1, actor)

    with pytest.raises(ConflictError):
        service.open_session(5, 1, actor)

    assert len(db.sessions) == 1


@pytest.mark.parametrize(
    ("index", "field", "message"),
    [
        ("uq_usage_sessions_active_machine", "machine_id", MACHINE_BUSY),
        ("uq_usage_sessions_active_customer", "customer_id", CUSTOMER_BUSY),
    ],
)
def test_concurrent_open_duplicate_index_maps_to_conflict(index, field, message):
    # Request kia commit trước: unique index trong DB chặn insert thứ hai.
    service, db = build_service()
    db.create_error = IntegrityError(
        msg=f"Duplicate entry '1' for key 'usage_sessions.{index}'",
        errno=errorcode.ER_DUP_ENTRY,
    )

    with pytest.raises(ConflictError) as exc_info:
        service.open_session(5, 1, make_actor())

    assert exc_info.value.field_errors == {field: message}
    assert db.rollbacks == 1


@pytest.mark.parametrize(
    "error",
    [
        IntegrityError(
            msg="Cannot add a foreign key", errno=errorcode.ER_NO_REFERENCED_ROW_2
        ),
        InterfaceError(msg="mất kết nối"),
    ],
)
def test_other_database_errors_map_to_service_unavailable(error):
    service, db = build_service()
    db.create_error = error

    with pytest.raises(ServiceUnavailableError):
        service.open_session(5, 1, make_actor())
    assert db.rollbacks == 1


# ----- TC12, TC13: transaction và snapshot ------------------------------------
def test_failure_after_insert_rolls_back_session_and_machine():  # TC12
    service, db = build_service()
    db.fail_mark_in_use = True

    with pytest.raises(ConflictError):
        service.open_session(5, 1, make_actor())

    assert db.writes == [("create_session", 1), ("mark_in_use", 1)]
    assert db.sessions == {}
    assert db.machines[1].status == MachineStatus.AVAILABLE
    assert (db.commits, db.rollbacks) == (0, 1)


def test_changing_machine_rate_keeps_session_snapshot():  # TC13
    service, db = build_service()
    summary = service.open_session(5, 1, make_actor())

    db.machines[1] = make_machine(status=MachineStatus.IN_USE, hourly_rate=12_000)

    assert summary.hourly_rate == RATE
    assert db.sessions[summary.session_id].hourly_rate == RATE


# ----- TC15: preview chỉ đọc --------------------------------------------------
def test_preview_does_not_write_or_lock():  # TC15
    service, db = build_service()

    service.preview_open(5, 1, make_actor())

    assert db.writes == []
    assert db.locks == []
    assert db.sessions == {}
    assert db.machines[1].status == MachineStatus.AVAILABLE


def test_open_session_locks_rows_in_order():
    service, db = build_service()

    service.open_session(5, 1, make_actor())

    # Khóa máy -> account -> phiên, giống thứ tự LI-07 để tránh deadlock.
    assert db.locks == [
        ("machine", 1),
        ("account", 10),
        ("session_machine", 1),
        ("session_customer", 5),
    ]
