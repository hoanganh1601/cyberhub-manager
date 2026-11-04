"""LI-09 — Unit test CustomerService (LI-03), dùng repository giả nên không cần MySQL.

Customer không gắn với cửa hàng trong schema P0 (bảng customers không có store_id),
nên phạm vi cửa hàng chỉ áp dụng cho actor: session phải khớp cửa hàng trong DB.
"""

from contextlib import contextmanager

import pytest
from mysql.connector import errorcode
from mysql.connector.errors import IntegrityError, InterfaceError

from cyberhub_manager.domain.dtos import CustomerSummary, EmployeeSession
from cyberhub_manager.domain.enums import AccountStatus, CustomerStatus, Role
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationError,
)
from cyberhub_manager.domain.models import Account, Customer
from cyberhub_manager.services import customer_service as module
from cyberhub_manager.services.contracts import CustomerServiceProtocol
from cyberhub_manager.services.customer_service import (
    PHONE_TAKEN,
    USERNAME_TAKEN,
    CustomerService,
)

STORE_ID = 1
OTHER_STORE_ID = 2
PASSWORD = "secret123"
VALID = {
    "full_name": "Nguyễn Văn A",
    "phone": "0900000001",
    "username": "khach.a",
    "password": PASSWORD,
}
ROLE_EMPLOYEE_IDS = {Role.ADMIN: 1, Role.MANAGER: 2, Role.STAFF: 3}


def make_actor(role=Role.STAFF, store_id=STORE_ID, *, employee_id=None):
    return EmployeeSession(
        employee_id=ROLE_EMPLOYEE_IDS[role] if employee_id is None else employee_id,
        employee_code="NV001",
        full_name="LI03 Actor",
        username="li03.actor",
        store_id=store_id,
        store_code="CH001",
        store_name="Cửa hàng test",
        role=role,
    )


def duplicate(constraint):
    return IntegrityError(
        msg=f"Duplicate entry for key '{constraint}'", errno=errorcode.ER_DUP_ENTRY
    )


# ----- Đồ giả ----------------------------------------------------------------
class FakeDatabase:
    """Lưu bản ghi dạng dict; lỗi trong transaction thì trả về trạng thái cũ."""

    def __init__(self, employees):
        self.employees = {e.employee_id: e for e in employees}
        self.customers = {}
        self.accounts = {}
        self.writes = []
        self.searches = []
        self.transactions = 0
        self.commits = 0
        self.rollbacks = 0
        self.fail_at = None

    def write(self, step):
        self.writes.append(step)
        if self.fail_at is not None and self.fail_at[0] == step:
            raise self.fail_at[1]

    def add_customer(self, customer_id=5, *, phone="0900000099"):
        self.customers[customer_id] = {
            "code": f"CUS-{customer_id}",
            "full_name": "Khách có sẵn",
            "phone": phone,
            "status": CustomerStatus.ACTIVE,
        }
        self.accounts[customer_id] = {
            "id": customer_id + 5,
            "code": f"ACC-{customer_id}",
            "username": f"khach{customer_id}",
            "password_hash": "x",
            "status": AccountStatus.ACTIVE,
        }

    def build(self, customer_id):
        row = self.customers.get(customer_id)
        if row is None:
            return None
        account = self.accounts[customer_id]
        return Customer(
            id=customer_id,
            code=row["code"],
            full_name=row["full_name"],
            phone=row["phone"],
            status=row["status"],
            account=Account(
                id=account["id"],
                code=account["code"],
                customer_id=customer_id,
                username=account["username"],
                balance=0,
                status=account["status"],
            ),
        )

    @contextmanager
    def transaction(self):
        self.transactions += 1
        snapshot = (
            {k: dict(v) for k, v in self.customers.items()},
            {k: dict(v) for k, v in self.accounts.items()},
        )
        try:
            yield object()
        except BaseException:
            self.customers, self.accounts = snapshot
            self.rollbacks += 1
            raise
        self.commits += 1


class FakeAuthRepository:
    def __init__(self, db):
        self.db = db

    def get_active_session_by_id(self, conn, employee_id):
        # Employee/store không ACTIVE thì repository thật trả None.
        return self.db.employees.get(employee_id)


class FakeCustomerRepository:
    def __init__(self, db):
        self.db = db

    def create(self, conn, *, code, full_name, phone):
        self.db.write("create_customer")
        customer_id = max(self.db.customers, default=0) + 1
        self.db.customers[customer_id] = {
            "code": code,
            "full_name": full_name,
            "phone": phone,
            "status": CustomerStatus.ACTIVE,
        }
        return customer_id

    def get_by_id(self, conn, customer_id):
        return self.db.build(customer_id)

    def search(self, conn, keyword):
        self.db.searches.append(keyword)
        return [
            CustomerSummary(
                customer_id=customer_id,
                customer_code=row["code"],
                full_name=row["full_name"],
                phone=row["phone"],
                account_id=self.db.accounts[customer_id]["id"],
                username=self.db.accounts[customer_id]["username"],
                balance=0,
                customer_status=row["status"],
                account_status=self.db.accounts[customer_id]["status"],
            )
            for customer_id, row in self.db.customers.items()
        ]

    def update_profile(self, conn, customer_id, *, full_name, phone):
        self.db.write("update_profile")
        self.db.customers[customer_id].update(full_name=full_name, phone=phone)
        return True

    def set_status(self, conn, customer_id, status):
        self.db.write("set_customer_status")
        self.db.customers[customer_id]["status"] = status
        return True


class FakeAccountRepository:
    def __init__(self, db):
        self.db = db

    def create(self, conn, *, code, customer_id, username, password_hash):
        self.db.write("create_account")
        self.db.accounts[customer_id] = {
            "id": customer_id + 5,
            "code": code,
            "username": username,
            "password_hash": password_hash,
            "status": AccountStatus.ACTIVE,
        }
        return customer_id + 5

    def set_status(self, conn, account_id, status):
        self.db.write("set_account_status")
        for account in self.db.accounts.values():
            if account["id"] == account_id:
                account["status"] = status
        return True


@pytest.fixture(autouse=True)
def fast_hash(monkeypatch):
    # bcrypt chậm và không phải đối tượng của test này.
    monkeypatch.setattr(module, "hash_password", lambda password: f"hashed:{password}")


def build_service(actor=None, *, employees=None):
    """actor là người đang đăng nhập; employees là bản ghi ACTIVE trong DB."""

    actor = actor or make_actor()
    db = FakeDatabase([actor] if employees is None else employees)
    service = CustomerService(
        customer_repo=FakeCustomerRepository(db),
        account_repo=FakeAccountRepository(db),
        auth_repo=FakeAuthRepository(db),
        actor_provider=lambda: actor,
        transaction_factory=db.transaction,
    )
    return service, db


def test_customer_service_satisfies_protocol():
    assert isinstance(CustomerService(), CustomerServiceProtocol)


# ----- create_customer --------------------------------------------------------
def test_create_customer_creates_customer_and_account_together():
    service, db = build_service()

    customer = service.create_customer(
        "  Nguyễn Văn A  ", " 0900000001 ", " khach.a ", PASSWORD
    )

    assert customer.full_name == "Nguyễn Văn A"
    assert customer.phone == "0900000001"
    assert customer.status == CustomerStatus.ACTIVE
    assert customer.account.username == "khach.a"
    assert customer.account.status == AccountStatus.ACTIVE
    assert customer.code.startswith("CUS-") and len(customer.code) == 20
    assert customer.account.code.startswith("ACC-") and len(customer.account.code) == 20
    assert db.writes == ["create_customer", "create_account"]
    assert (db.transactions, db.commits) == (1, 1)


def test_create_customer_stores_hash_not_password():
    service, db = build_service()

    customer = service.create_customer(**VALID)

    assert db.accounts[customer.id]["password_hash"] == f"hashed:{PASSWORD}"


def test_create_customer_reports_every_invalid_field_before_database():
    service, db = build_service()

    with pytest.raises(ValidationError) as exc_info:
        service.create_customer("A", "123", "ab", "12345")

    assert set(exc_info.value.field_errors) == {
        "full_name",
        "phone",
        "username",
        "password",
    }
    assert db.transactions == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("full_name", "x" * 101),
        ("full_name", None),
        ("phone", "1900000001"),
        ("phone", "090000000"),
        ("username", "có dấu cách"),
        ("username", "x" * 31),
        ("password", "x" * 73),
        ("password", None),
    ],
)
def test_create_customer_rejects_invalid_field(field, value):
    service, db = build_service()

    with pytest.raises(ValidationError) as exc_info:
        service.create_customer(**{**VALID, field: value})

    assert list(exc_info.value.field_errors) == [field]
    assert db.transactions == 0


@pytest.mark.parametrize(
    ("step", "constraint", "field", "message"),
    [
        ("create_customer", "uq_customers_phone", "phone", PHONE_TAKEN),
        ("create_account", "uq_accounts_username", "username", USERNAME_TAKEN),
    ],
)
def test_create_customer_duplicate_maps_to_conflict_and_rolls_back(
    step, constraint, field, message
):
    service, db = build_service()
    db.fail_at = (step, duplicate(constraint))

    with pytest.raises(ConflictError) as exc_info:
        service.create_customer(**VALID)

    assert exc_info.value.field_errors == {field: message}
    assert db.customers == {}
    assert db.rollbacks == 1


@pytest.mark.parametrize(
    "error",
    [
        duplicate("uq_customers_code"),
        IntegrityError(msg="fk", errno=errorcode.ER_NO_REFERENCED_ROW_2),
        InterfaceError(msg="mất kết nối"),
    ],
)
def test_create_customer_other_database_errors_are_unavailable(error):
    service, db = build_service()
    db.fail_at = ("create_account", error)

    with pytest.raises(ServiceUnavailableError):
        service.create_customer(**VALID)

    assert db.customers == {}


def test_create_customer_rolls_back_customer_when_account_fails():
    service, db = build_service()
    db.fail_at = ("create_account", RuntimeError("lỗi giữa chừng"))

    with pytest.raises(RuntimeError):
        service.create_customer(**VALID)

    assert db.customers == {}
    assert (db.commits, db.rollbacks) == (0, 1)


# ----- Actor: áp dụng cho mọi thao tác ----------------------------------------
OPERATIONS = {
    "create": lambda s: s.create_customer(**VALID),
    "get": lambda s: s.get_customer(5),
    "search": lambda s: s.search_customers("khach"),
    "update": lambda s: s.update_customer(5, "Tên mới", "0900000002"),
}


@pytest.mark.parametrize("operation", OPERATIONS.values(), ids=OPERATIONS.keys())
@pytest.mark.parametrize(
    "employees",
    [
        [],  # employee LOCKED/INACTIVE hoặc store INACTIVE
        [make_actor(store_id=OTHER_STORE_ID)],  # đã chuyển sang cửa hàng khác
    ],
    ids=["inactive", "moved_store"],
)
def test_invalid_actor_is_denied_without_write(operation, employees):
    service, db = build_service(make_actor(), employees=employees)
    db.add_customer()

    with pytest.raises(PermissionDeniedError):
        operation(service)

    assert db.writes == []


@pytest.mark.parametrize("operation", OPERATIONS.values(), ids=OPERATIONS.keys())
def test_missing_login_is_denied(operation):
    service, db = build_service()
    service._actor_provider = None
    db.add_customer()

    with pytest.raises(PermissionDeniedError):
        operation(service)

    assert db.writes == []


# ----- get_customer / search_customers ----------------------------------------
def test_get_customer_returns_customer_with_account():
    service, db = build_service()
    db.add_customer()

    customer = service.get_customer(5)

    assert customer.id == 5
    assert customer.account.username == "khach5"


@pytest.mark.parametrize("customer_id", [99, 0, -1, True, "5", None])
def test_get_customer_unknown_or_invalid_id_is_not_found(customer_id):
    service, db = build_service()
    db.add_customer()

    with pytest.raises(NotFoundError):
        service.get_customer(customer_id)


def test_search_customers_trims_keyword_and_returns_summaries():
    service, db = build_service()
    db.add_customer()

    result = service.search_customers("  khach  ")

    assert db.searches == ["khach"]
    assert [item.customer_id for item in result] == [5]
    assert all(isinstance(item, CustomerSummary) for item in result)


def test_read_database_error_is_unavailable():
    service, db = build_service()

    @contextmanager
    def broken():
        raise InterfaceError(msg="mất kết nối")
        yield

    service._transaction = broken

    with pytest.raises(ServiceUnavailableError):
        service.get_customer(5)
    with pytest.raises(ServiceUnavailableError):
        service.search_customers("khach")


# ----- update_customer --------------------------------------------------------
def test_update_customer_changes_profile():
    service, db = build_service()
    db.add_customer()

    customer = service.update_customer(5, "  Tên mới  ", " 0900000002 ")

    assert (customer.full_name, customer.phone) == ("Tên mới", "0900000002")
    assert db.writes == ["update_profile"]


def test_update_customer_rejects_invalid_fields_before_database():
    service, db = build_service()
    db.add_customer()

    with pytest.raises(ValidationError) as exc_info:
        service.update_customer(5, "A", "123")

    assert set(exc_info.value.field_errors) == {"full_name", "phone"}
    assert db.transactions == 0


def test_update_customer_unknown_is_not_found_without_write():
    service, db = build_service()

    with pytest.raises(NotFoundError):
        service.update_customer(99, "Tên mới", "0900000002")

    assert db.writes == []


def test_update_customer_duplicate_phone_conflicts_and_rolls_back():
    service, db = build_service()
    db.add_customer()
    db.fail_at = ("update_profile", duplicate("uq_customers_phone"))

    with pytest.raises(ConflictError) as exc_info:
        service.update_customer(5, "Tên mới", "0900000002")

    assert exc_info.value.field_errors == {"phone": PHONE_TAKEN}
    assert db.customers[5]["full_name"] == "Khách có sẵn"


# ----- set_customer_status ----------------------------------------------------
@pytest.mark.parametrize("role", [Role.MANAGER, Role.ADMIN])
@pytest.mark.parametrize(
    ("status", "account_status"),
    [
        (CustomerStatus.INACTIVE, AccountStatus.LOCKED),
        (CustomerStatus.ACTIVE, AccountStatus.ACTIVE),
    ],
)
def test_set_customer_status_updates_customer_and_account(role, status, account_status):
    actor = make_actor(role)
    service, db = build_service(actor)
    db.add_customer()

    customer = service.set_customer_status(5, status, actor)

    assert customer.status == status
    assert customer.account.status == account_status
    assert db.writes == ["set_customer_status", "set_account_status"]


def test_set_customer_status_rejects_staff_without_write():
    actor = make_actor(Role.STAFF)
    service, db = build_service(actor)
    db.add_customer()

    with pytest.raises(PermissionDeniedError):
        service.set_customer_status(5, CustomerStatus.INACTIVE, actor)

    assert db.writes == []


def test_set_customer_status_uses_role_from_database():
    # Session tự nhận MANAGER nhưng DB ghi STAFF.
    forged = make_actor(Role.MANAGER, employee_id=3)
    service, db = build_service(forged, employees=[make_actor(Role.STAFF)])
    db.add_customer()

    with pytest.raises(PermissionDeniedError):
        service.set_customer_status(5, CustomerStatus.INACTIVE, forged)

    assert db.writes == []


@pytest.mark.parametrize(
    "requested",
    [
        make_actor(Role.ADMIN),  # mượn employee_id của người khác
        make_actor(Role.MANAGER, store_id=OTHER_STORE_ID),  # tự đổi cửa hàng
    ],
)
def test_set_customer_status_rejects_other_actor(requested):
    actor = make_actor(Role.MANAGER)
    service, db = build_service(actor)
    db.add_customer()

    with pytest.raises(PermissionDeniedError):
        service.set_customer_status(5, CustomerStatus.INACTIVE, requested)
    assert db.writes == []


@pytest.mark.parametrize("status", ["INACTIVE", None, AccountStatus.LOCKED])
def test_set_customer_status_rejects_invalid_status_before_database(status):
    actor = make_actor(Role.MANAGER)
    service, db = build_service(actor)

    with pytest.raises(ValidationError) as exc_info:
        service.set_customer_status(5, status, actor)

    assert "status" in exc_info.value.field_errors
    assert db.transactions == 0


def test_set_customer_status_unknown_is_not_found_without_write():
    actor = make_actor(Role.MANAGER)
    service, db = build_service(actor)

    with pytest.raises(NotFoundError):
        service.set_customer_status(99, CustomerStatus.INACTIVE, actor)

    assert db.writes == []


def test_set_customer_status_rolls_back_when_account_update_fails():
    actor = make_actor(Role.MANAGER)
    service, db = build_service(actor)
    db.add_customer()
    db.fail_at = ("set_account_status", RuntimeError("lỗi giữa chừng"))

    with pytest.raises(RuntimeError):
        service.set_customer_status(5, CustomerStatus.INACTIVE, actor)

    assert db.customers[5]["status"] == CustomerStatus.ACTIVE
    assert db.accounts[5]["status"] == AccountStatus.ACTIVE
    assert db.rollbacks == 1
