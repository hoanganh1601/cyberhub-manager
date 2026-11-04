"""LI-06/LI-07 — Unit test cho SessionService (mở phiên, checkout), dùng repository giả.

Đánh số TC theo 15 test case bắt buộc của task LI-06. TC14 (live estimate tại các
mốc biên) nằm trong tests/unit/test_domain_models.py vì phần tính nằm ở domain.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from mysql.connector import errorcode
from mysql.connector.errors import IntegrityError, InterfaceError

from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    InvoiceStatus,
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
    Invoice,
    Machine,
    UsageSession,
)
from cyberhub_manager.services.contracts import SessionServiceProtocol
from cyberhub_manager.services.session_service import (
    ACCOUNT_LOCKED,
    ALREADY_CHECKED_OUT,
    BALANCE_CHANGED,
    CUSTOMER_BUSY,
    CUSTOMER_INACTIVE,
    MACHINE_ARCHIVED,
    MACHINE_BUSY,
    MACHINE_MAINTENANCE,
    METHOD_INVALID,
    METHOD_NOT_ALLOWED,
    NO_ACTIVE_SESSION,
    NOT_ENOUGH_BALANCE,
    SETTLEMENT_INVALID,
    SETTLEMENT_NOT_ENOUGH,
    SETTLEMENT_EXCESS,
    SessionService,
)

STORE_ID = 1
OTHER_STORE_ID = 2
NOW = datetime(2026, 10, 31, 8, 0, tzinfo=timezone.utc)
# Đơn giá 6_000đ/giờ => tối thiểu 30 phút = 3_000đ.
RATE = 6_000
MINIMUM = 3_000
# Giờ MySQL ghi invoices.created_at trong test checkout.
INVOICE_CREATED_AT = datetime(2026, 10, 31, 8, 1, 2, tzinfo=timezone.utc)

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


def copy_customer(customer, *, balance=None):
    account = customer.account
    return Customer(
        id=customer.id,
        code=customer.code,
        full_name=customer.full_name,
        phone=customer.phone,
        status=customer.status,
        account=Account(
            id=account.id,
            code=account.code,
            customer_id=account.customer_id,
            username=account.username,
            balance=account.balance if balance is None else balance,
            status=account.status,
        ),
    )


def copy_session(session):
    return UsageSession(
        id=session.id,
        code=session.code,
        customer_id=session.customer_id,
        machine_id=session.machine_id,
        opened_by=session.opened_by,
        closed_by=session.closed_by,
        started_at=session.started_at,
        ended_at=session.ended_at,
        hourly_rate=session.hourly_rate,
        cost=session.cost,
        status=session.status,
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
        self.transactions = []
        self.invoices = {}
        # (tên bước, exception): bước đó ném lỗi để thử rollback.
        self.fail_at = None

    def write(self, step, *args):
        self.writes.append((step, *args))
        if self.fail_at is not None and self.fail_at[0] == step:
            raise self.fail_at[1]

    @contextmanager
    def transaction(self):
        snapshot = (
            dict(self.machines),
            dict(self.sessions),
            dict(self.customers),
            list(self.transactions),
            dict(self.invoices),
        )
        try:
            yield object()
        except BaseException:
            (
                self.machines,
                self.sessions,
                self.customers,
                self.transactions,
                self.invoices,
            ) = snapshot
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

    def mark_available(self, conn, machine_id):
        self.db.write("mark_available", machine_id)
        old = self.db.machines[machine_id]
        if old.status != MachineStatus.IN_USE:
            return False
        self.db.machines[machine_id] = make_machine(
            machine_id,
            store_id=old.store_id,
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

    def complete(self, conn, session):
        self.db.write("complete_session", session.id)
        stored = self.db.sessions.get(session.id)
        if stored is None or not stored.is_active():
            return False
        self.db.sessions[session.id] = copy_session(session)
        return True

    def _find_active(self, *, machine_id=None, customer_id=None):
        for session in self.db.sessions.values():
            if session.is_active() and (
                session.machine_id == machine_id or session.customer_id == customer_id
            ):
                return copy_session(session)
        return None


class FakeCustomerRepository:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, conn, customer_id):
        customer = self.db.customers.get(customer_id)
        return None if customer is None else copy_customer(customer)


class FakeAccountRepository:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, conn, account_id, *, for_update=False):
        if for_update:
            self.db.locks.append(("account", account_id))
        customer = self._owner(account_id)
        return None if customer is None else copy_customer(customer).account

    def credit_balance(self, conn, account_id, amount):
        self.db.write("credit_balance", amount)
        customer = self._owner(account_id)
        self.db.customers[customer.id] = copy_customer(
            customer, balance=customer.account.balance + amount
        )
        return True

    def debit_balance(self, conn, account_id, amount):
        self.db.write("debit_balance", amount)
        customer = self._owner(account_id)
        if customer.account.balance < amount:
            return False
        self.db.customers[customer.id] = copy_customer(
            customer, balance=customer.account.balance - amount
        )
        return True

    def insert_debt_settlement_transaction(
        self, conn, *, code, account_id, employee_id, session_id, settlement_amount,
        method,
    ):
        self.db.write("settlement_transaction", settlement_amount)
        self.db.transactions.append(
            ("DEBT_SETTLEMENT", account_id, session_id, settlement_amount, method)
        )
        return len(self.db.transactions)

    def insert_usage_payment_transaction(
        self, conn, *, code, account_id, employee_id, session_id, usage_cost
    ):
        self.db.write("usage_transaction", usage_cost)
        self.db.transactions.append(
            (
                "USAGE_PAYMENT",
                account_id,
                session_id,
                -usage_cost,
                PaymentMethod.ACCOUNT_BALANCE,
            )
        )
        return len(self.db.transactions)

    def _owner(self, account_id):
        for customer in self.db.customers.values():
            if customer.account.id == account_id:
                return customer
        return None


class FakeInvoiceRepository:
    def __init__(self, db):
        self.db = db

    def create(
        self, conn, *, code, session_id, customer_id, employee_id, store_id,
        usage_cost, settlement_amount,
    ):
        self.db.write("create_invoice", session_id)
        if any(i.session_id == session_id for i in self.db.invoices.values()):
            raise IntegrityError(
                msg="Duplicate entry for key 'invoices.uq_invoices_session'",
                errno=errorcode.ER_DUP_ENTRY,
            )
        invoice_id = max(self.db.invoices, default=0) + 1
        self.db.invoices[invoice_id] = Invoice(
            id=invoice_id,
            code=code,
            session_id=session_id,
            customer_id=customer_id,
            employee_id=employee_id,
            store_id=store_id,
            usage_cost=usage_cost,
            settlement_amount=settlement_amount,
            total_amount=usage_cost,
            status=InvoiceStatus.PAID,
            created_at=INVOICE_CREATED_AT,
        )
        return invoice_id

    def get_by_id(self, conn, invoice_id):
        return self.db.invoices.get(invoice_id)


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
        invoice_repo=FakeInvoiceRepository(db),
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


# ===== LI-07: preview_checkout ===============================================
def build_checkout(*, balance=50_000, machine=None, sessions=None, **kwargs):
    """Máy 1 đang IN_USE với phiên 100 của khách 5, bắt đầu lúc NOW."""

    return build_service(
        machines=[machine or make_machine(status=MachineStatus.IN_USE)],
        customers=[make_customer(balance=balance)],
        sessions=[make_session()] if sessions is None else sessions,
        **kwargs,
    )


def test_preview_checkout_calculates_cost_and_balance():
    service, db = build_checkout()

    preview = service.preview_checkout(1, NOW + timedelta(seconds=61))

    assert preview.session.session_id == 100
    assert (preview.session.customer_code, preview.session.machine_code) == (
        "KH005",
        "PC01",
    )
    assert preview.calculated_at == NOW + timedelta(seconds=61)
    assert preview.elapsed_seconds == 61
    assert preview.billed_minutes == 2
    assert preview.usage_cost == 200  # 6_000đ/giờ = 100đ/phút
    assert preview.balance_before == 50_000
    assert preview.projected_balance == 49_800
    assert preview.settlement_required == 0


@pytest.mark.parametrize(
    ("offset_seconds", "minutes", "cost"),
    [(0, 1, 100), (1, 1, 100), (60, 1, 100), (61, 2, 200)],
)
def test_preview_checkout_rounds_minutes_at_boundaries(offset_seconds, minutes, cost):
    service, _ = build_checkout()

    preview = service.preview_checkout(1, NOW + timedelta(seconds=offset_seconds))

    assert (preview.billed_minutes, preview.usage_cost) == (minutes, cost)


def test_preview_checkout_uses_session_rate_snapshot():
    # Máy đã tăng giá lên 12_000đ/giờ sau khi mở phiên 6_000đ/giờ.
    service, _ = build_checkout(
        machine=make_machine(status=MachineStatus.IN_USE, hourly_rate=12_000)
    )

    preview = service.preview_checkout(1, NOW + timedelta(minutes=10))

    assert preview.session.hourly_rate == RATE
    assert preview.usage_cost == 1_000


def test_preview_checkout_reports_settlement_without_ending_session():
    service, db = build_checkout(balance=50)

    preview = service.preview_checkout(1, NOW + timedelta(seconds=61))

    assert preview.projected_balance == -150
    assert preview.settlement_required == 150
    # Số dư dự kiến âm không tự kết thúc phiên.
    assert db.sessions[100].is_active()
    assert db.machines[1].status == MachineStatus.IN_USE


def test_preview_checkout_does_not_write_or_lock():
    service, db = build_checkout()

    service.preview_checkout(1, NOW + timedelta(minutes=5))

    assert db.writes == []
    assert db.locks == []
    assert db.customers[5].account.balance == 50_000


def test_preview_checkout_returns_utc_time():
    service, _ = build_checkout()
    vietnam_time = (NOW + timedelta(minutes=5)).astimezone(
        timezone(timedelta(hours=7))
    )

    preview = service.preview_checkout(1, vietnam_time)

    assert preview.calculated_at == NOW + timedelta(minutes=5)
    assert preview.calculated_at.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "current_time", [NOW.replace(tzinfo=None), "2026-10-31 08:05", None]
)
def test_preview_checkout_rejects_time_without_timezone(current_time):
    service, _ = build_checkout()

    with pytest.raises(ValidationError) as exc_info:
        service.preview_checkout(1, current_time)

    assert "current_time" in exc_info.value.field_errors


def test_preview_checkout_rejects_time_before_session_start():
    service, _ = build_checkout()

    with pytest.raises(ValidationError):
        service.preview_checkout(1, NOW - timedelta(seconds=1))


@pytest.mark.parametrize("machine_id", [99, 0, True])
def test_preview_checkout_unknown_machine_is_not_found(machine_id):
    service, _ = build_checkout()

    with pytest.raises(NotFoundError):
        service.preview_checkout(machine_id, NOW)


def test_preview_checkout_machine_of_other_store_is_denied():
    service, _ = build_checkout(
        machine=make_machine(status=MachineStatus.IN_USE, store_id=OTHER_STORE_ID)
    )

    with pytest.raises(PermissionDeniedError):
        service.preview_checkout(1, NOW)


@pytest.mark.parametrize(
    ("machine", "sessions"),
    [
        (make_machine(), []),  # máy rảnh
        (make_machine(status=MachineStatus.IN_USE), []),  # IN_USE nhưng mất phiên
        (make_machine(), None),  # còn phiên nhưng máy đã AVAILABLE
    ],
)
def test_preview_checkout_without_active_session_conflicts(machine, sessions):
    service, _ = build_checkout(machine=machine, sessions=sessions)

    with pytest.raises(ConflictError) as exc_info:
        service.preview_checkout(1, NOW)

    assert exc_info.value.field_errors == {"machine_id": NO_ACTIVE_SESSION}


def test_preview_checkout_without_login_is_denied():
    db = FakeDatabase(machines=[], customers=[], sessions=[], employees=[])
    service = SessionService(transaction_factory=db.transaction)

    with pytest.raises(PermissionDeniedError):
        service.preview_checkout(1, NOW)


@pytest.mark.parametrize(
    ("actor", "employees"),
    [
        (make_actor(), []),  # employee hoặc store không còn ACTIVE
        (make_actor(Role.MANAGER, employee_id=3), [make_actor(Role.STAFF)]),
    ],
)
def test_preview_checkout_rechecks_actor_in_database(actor, employees):
    service, _ = build_checkout(actor=actor, employees=employees)

    with pytest.raises(PermissionDeniedError):
        service.preview_checkout(1, NOW)


# ===== LI-07: complete_checkout ==============================================
# Phiên 100 (khách 5, account 10) bắt đầu lúc NOW, giá 6_000đ/giờ = 100đ/phút;
# checkout lúc NOW + 61 giây => 2 phút => phí 200đ.
CHECKOUT_AT = NOW + timedelta(seconds=61)


def build_complete(*, balance=50_000, actor=None, **kwargs):
    actor = actor or make_actor(Role.MANAGER)
    service, db = build_checkout(
        balance=balance, actor=actor, clock=lambda: CHECKOUT_AT, **kwargs
    )
    return service, db, actor


def assert_unchanged(db, balance):
    """Năm nhóm dữ liệu checkout đều giữ nguyên như trước."""

    assert db.customers[5].account.balance == balance
    assert db.transactions == []
    assert db.sessions[100].is_active()
    assert db.machines[1].status == MachineStatus.IN_USE
    assert db.invoices == {}


def test_complete_checkout_without_settlement():
    service, db, actor = build_complete()

    result = service.complete_checkout(1, actor, 0, None)

    assert result.balance_after == 49_800
    invoice = result.invoice.invoice
    assert invoice.invoice_code.startswith("INV-")
    assert len(invoice.invoice_code) == 20
    assert (invoice.usage_cost, invoice.settlement_amount, invoice.total_amount) == (
        200,
        0,
        200,
    )
    assert invoice.status == InvoiceStatus.PAID
    assert (invoice.session_id, invoice.customer_id, invoice.store_id) == (100, 5, 1)
    assert (invoice.employee_id, invoice.employee_name) == (2, actor.full_name)
    assert invoice.customer_name == "Nguyễn Văn A"
    assert invoice.store_name == actor.store_name
    assert invoice.created_at == INVOICE_CREATED_AT
    assert result.invoice.ended_at == CHECKOUT_AT
    assert result.invoice.billed_minutes == 2
    assert result.invoice.session.status == SessionStatus.COMPLETED

    saved = db.sessions[100]
    assert saved.status == SessionStatus.COMPLETED
    # Người mở (STAFF id 3) và người checkout (MANAGER id 2) lưu riêng.
    assert (saved.opened_by, saved.closed_by) == (3, 2)
    assert (saved.ended_at, saved.cost) == (CHECKOUT_AT, 200)
    assert db.machines[1].status == MachineStatus.AVAILABLE
    assert db.customers[5].account.balance == 49_800
    assert db.transactions == [
        ("USAGE_PAYMENT", 10, 100, -200, PaymentMethod.ACCOUNT_BALANCE)
    ]
    assert db.writes == [
        ("debit_balance", 200),
        ("usage_transaction", 200),
        ("complete_session", 100),
        ("mark_available", 1),
        ("create_invoice", 100),
    ]
    assert (db.commits, db.rollbacks) == (1, 0)


@pytest.mark.parametrize(
    ("settlement", "method", "balance_after"),
    [
        (150, PaymentMethod.CASH, 0),
        (150, PaymentMethod.TRANSFER, 0),
    ],
)

def test_complete_checkout_with_settlement(settlement, method, balance_after):
    service, db, actor = build_complete(balance=50)

    result = service.complete_checkout(1, actor, settlement, method)

    assert result.balance_after == balance_after
    assert result.invoice.invoice.settlement_amount == settlement
    assert db.customers[5].account.balance == balance_after
    assert db.transactions == [
        ("DEBT_SETTLEMENT", 10, 100, settlement, method),
        ("USAGE_PAYMENT", 10, 100, -200, PaymentMethod.ACCOUNT_BALANCE),
    ]
    # Cộng tiền bù trước rồi mới trừ phí.
    assert [step for step, *_ in db.writes][:4] == [
        "credit_balance",
        "settlement_transaction",
        "debit_balance",
        "usage_transaction",
    ]


def test_complete_checkout_accepts_method_as_text():
    service, db, actor = build_complete(balance=50)

    service.complete_checkout(1, actor, 150, "CASH")

    assert db.transactions[0][-1] is PaymentMethod.CASH


def test_settlement_below_required_changes_nothing():
    service, db, actor = build_complete(balance=50)

    with pytest.raises(SettlementRequiredError) as exc_info:
        service.complete_checkout(1, actor, 149, PaymentMethod.CASH)

    assert exc_info.value.field_errors == {"settlement_amount": SETTLEMENT_NOT_ENOUGH}
    assert exc_info.value.details == {
        "settlement_required": 150,
        "usage_cost": 200,
        "balance_before": 50,
    }
    assert db.writes == []
    assert_unchanged(db, 50)


def test_missing_settlement_when_required_changes_nothing():
    service, db, actor = build_complete(balance=50)

    with pytest.raises(SettlementRequiredError):
        service.complete_checkout(1, actor, 0, None)

    assert_unchanged(db, 50)


def test_settlement_above_required_is_rejected():
    service, db, actor = build_complete(balance=50)

    with pytest.raises(ValidationError) as exc_info:
        service.complete_checkout(
            1,
            actor,
            151,
            PaymentMethod.CASH,
        )

    assert exc_info.value.field_errors == {
        "settlement_amount": SETTLEMENT_EXCESS,
    }
    assert db.writes == []
    assert_unchanged(db, 50)


@pytest.mark.parametrize(
    ("settlement", "method", "field", "message"),
    [
        (-1, PaymentMethod.CASH, "settlement_amount", SETTLEMENT_INVALID),
        (True, PaymentMethod.CASH, "settlement_amount", SETTLEMENT_INVALID),
        (1.5, PaymentMethod.CASH, "settlement_amount", SETTLEMENT_INVALID),
        ("150", PaymentMethod.CASH, "settlement_amount", SETTLEMENT_INVALID),
        (150, None, "method", METHOD_INVALID),
        (150, PaymentMethod.ACCOUNT_BALANCE, "method", METHOD_INVALID),
        (150, PaymentMethod.PROMOTION, "method", METHOD_INVALID),
        (0, PaymentMethod.CASH, "method", METHOD_NOT_ALLOWED),
    ],
)
def test_invalid_settlement_input_is_rejected_before_database(
    settlement, method, field, message
):
    service, db, actor = build_complete(balance=50)

    with pytest.raises(ValidationError) as exc_info:
        service.complete_checkout(1, actor, settlement, method)

    assert exc_info.value.field_errors == {field: message}
    assert (db.commits, db.rollbacks) == (0, 0)


def test_complete_checkout_uses_server_clock_and_rate_snapshot():
    # Máy đã tăng giá; giờ server có phần lẻ giây.
    service, db, actor = build_complete(
        machine=make_machine(status=MachineStatus.IN_USE, hourly_rate=12_000)
    )
    service._clock = lambda: CHECKOUT_AT.replace(microsecond=900_000)

    result = service.complete_checkout(1, actor, 0, None)

    assert result.invoice.ended_at == CHECKOUT_AT
    assert result.invoice.invoice.usage_cost == 200
    assert db.sessions[100].hourly_rate == RATE


def test_complete_checkout_clamps_clock_before_start():
    service, db, actor = build_complete()
    service._clock = lambda: NOW - timedelta(seconds=5)

    result = service.complete_checkout(1, actor, 0, None)

    assert result.invoice.ended_at == NOW
    assert result.invoice.invoice.usage_cost == 100  # tối thiểu 1 phút


def test_complete_checkout_locks_rows_in_order():
    service, db, actor = build_complete()

    service.complete_checkout(1, actor, 0, None)

    assert db.locks == [("machine", 1), ("account", 10), ("session_machine", 1)]


@pytest.mark.parametrize("machine_id", [99, 0, True])
def test_complete_checkout_unknown_machine_is_not_found(machine_id):
    service, db, actor = build_complete()

    with pytest.raises(NotFoundError):
        service.complete_checkout(machine_id, actor, 0, None)
    assert_unchanged(db, 50_000)


def test_complete_checkout_machine_of_other_store_is_denied():
    service, db, actor = build_complete(
        machine=make_machine(status=MachineStatus.IN_USE, store_id=OTHER_STORE_ID)
    )

    with pytest.raises(PermissionDeniedError):
        service.complete_checkout(1, actor, 0, None)
    assert_unchanged(db, 50_000)


def test_complete_checkout_without_active_session_conflicts():
    service, db, actor = build_complete(machine=make_machine(), sessions=[])

    with pytest.raises(ConflictError) as exc_info:
        service.complete_checkout(1, actor, 0, None)

    assert exc_info.value.field_errors == {"machine_id": NO_ACTIVE_SESSION}
    assert db.writes == []


@pytest.mark.parametrize(
    ("actor", "employees"),
    [
        (make_actor(Role.MANAGER), []),  # employee hoặc store không còn ACTIVE
        (make_actor(Role.MANAGER, employee_id=3), [make_actor(Role.STAFF)]),
        (make_actor(Role.MANAGER, store_id=OTHER_STORE_ID), None),
    ],
)
def test_complete_checkout_rejects_invalid_actor(actor, employees):
    service, db, _ = build_complete(actor=actor, employees=employees)

    with pytest.raises(PermissionDeniedError):
        service.complete_checkout(1, actor, 0, None)
    assert_unchanged(db, 50_000)


def test_complete_checkout_rejects_actor_other_than_logged_in():
    service, db, _ = build_complete()

    with pytest.raises(PermissionDeniedError):
        service.complete_checkout(1, make_actor(Role.ADMIN), 0, None)
    assert_unchanged(db, 50_000)


def test_double_click_checkout_creates_one_invoice():
    service, db, actor = build_complete()
    service.complete_checkout(1, actor, 0, None)

    with pytest.raises(ConflictError) as exc_info:
        service.complete_checkout(1, actor, 0, None)

    assert exc_info.value.field_errors == {"machine_id": NO_ACTIVE_SESSION}
    assert len(db.invoices) == 1
    assert len(db.transactions) == 1
    assert db.customers[5].account.balance == 49_800


@pytest.mark.parametrize(
    "step",
    [
        "credit_balance",
        "settlement_transaction",
        "debit_balance",
        "usage_transaction",
        "complete_session",
        "mark_available",
        "create_invoice",
    ],
)
def test_failure_at_any_step_rolls_back_everything(step):
    service, db, actor = build_complete(balance=50)
    db.fail_at = (step, RuntimeError(f"lỗi tại {step}"))

    with pytest.raises(RuntimeError):
        service.complete_checkout(1, actor, 150, PaymentMethod.CASH)

    assert_unchanged(db, 50)
    assert (db.commits, db.rollbacks) == (0, 1)


def test_database_error_maps_to_service_unavailable():
    service, db, actor = build_complete()
    db.fail_at = ("create_invoice", InterfaceError(msg="mất kết nối"))

    with pytest.raises(ServiceUnavailableError):
        service.complete_checkout(1, actor, 0, None)
    assert_unchanged(db, 50_000)


def test_existing_invoice_for_session_maps_to_conflict():
    service, db, actor = build_complete()
    db.invoices[7] = Invoice(
        id=7,
        code="INV-OLD",
        session_id=100,
        customer_id=5,
        employee_id=2,
        store_id=1,
        usage_cost=100,
        settlement_amount=0,
        total_amount=100,
        status=InvoiceStatus.PAID,
        created_at=NOW,
    )

    with pytest.raises(ConflictError) as exc_info:
        service.complete_checkout(1, actor, 0, None)

    assert exc_info.value.field_errors == {"machine_id": ALREADY_CHECKED_OUT}
    assert list(db.invoices) == [7]
    assert db.transactions == []
    assert db.sessions[100].is_active()


@pytest.mark.parametrize(
    ("repo", "method", "message"),
    [
        ("_accounts", "debit_balance", BALANCE_CHANGED),
        ("_sessions", "complete", ALREADY_CHECKED_OUT),
        ("_machines", "mark_available", NO_ACTIVE_SESSION),
    ],
)
def test_guarded_update_not_applied_rolls_back(monkeypatch, repo, method, message):
    service, db, actor = build_complete()
    monkeypatch.setattr(getattr(service, repo), method, lambda *args: False)

    with pytest.raises(ConflictError) as exc_info:
        service.complete_checkout(1, actor, 0, None)

    assert exc_info.value.message == message
    assert_unchanged(db, 50_000)
