"""LI-03 — Integration test AuthService và CustomerService trên MySQL test database.

Service tự mở transaction() trên connection riêng, nên dữ liệu chuẩn bị phải
được commit trước; fixture ghi lại mọi dòng đã tạo và tự xóa sau mỗi test.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from cyberhub_manager.database import connection
from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.enums import AccountStatus, CustomerStatus, Role
from cyberhub_manager.domain.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.repositories.account_repository import AccountRepository
from cyberhub_manager.security import hash_password
from cyberhub_manager.services.auth_service import AuthService
from cyberhub_manager.services.customer_service import CustomerService

TEST_DATABASE = "cyberhub_manager_migration_test"
PASSWORD = "secret123"
UNKNOWN_ID = 999_999_999_999


def _execute(conn, sql, params=()):
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone() if cursor.with_rows else cursor.lastrowid
    finally:
        cursor.close()


def _unique_phone():
    return "09" + str(uuid4().int % 100_000_000).zfill(8)


def _unique_username():
    return "li03c." + uuid4().hex[:12]


def _actor(employee, role):
    return EmployeeSession(
        employee_id=employee.id,
        employee_code="EMP",
        full_name="LI03 Actor",
        username=employee.username,
        store_id=employee.store_id,
        store_code="ST",
        store_name="LI03 Test Store",
        role=role,
    )


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", TEST_DATABASE)
    monkeypatch.setattr(connection, "_pool", None)

    token = uuid4().hex[:10]
    password_hash = hash_password(PASSWORD)
    employees = {}

    with transaction() as conn:
        assert _execute(conn, "SELECT DATABASE()") == (TEST_DATABASE,)
        store_id = _execute(
            conn,
            "INSERT INTO stores (code, name, address) VALUES (%s, %s, %s)",
            ("ST-" + token, "LI03 Test Store", "Test address"),
        )
        for key, role, status in (
            ("manager", Role.MANAGER, "ACTIVE"),
            ("staff", Role.STAFF, "ACTIVE"),
            ("locked", Role.STAFF, "LOCKED"),
        ):
            username = f"li03{key[:3]}.{token}"
            employee_id = _execute(
                conn,
                """
                INSERT INTO employees
                    (code, store_id, full_name, username, password_hash, role, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    f"EMP{key[:3]}-{token}",
                    store_id,
                    f"LI03 {key}",
                    username,
                    password_hash,
                    role.value,
                    status,
                ),
            )
            employees[key] = SimpleNamespace(
                id=employee_id, username=username, store_id=store_id
            )

    customer_ids = []

    try:
        yield SimpleNamespace(
            store_id=store_id,
            employees=employees,
            customer_ids=customer_ids,
            manager=_actor(employees["manager"], Role.MANAGER),
            staff=_actor(employees["staff"], Role.STAFF),
        )
    finally:
        # Xóa bảng con trước bảng cha để không vướng khóa ngoại.
        with transaction() as conn:
            for customer_id in customer_ids:
                _execute(conn, "DELETE FROM accounts WHERE customer_id = %s", (customer_id,))
                _execute(conn, "DELETE FROM customers WHERE id = %s", (customer_id,))
            _execute(conn, "DELETE FROM employees WHERE store_id = %s", (store_id,))
            _execute(conn, "DELETE FROM stores WHERE id = %s", (store_id,))


def _create(db, **overrides):
    values = {
        "full_name": "LI03 Test Customer",
        "phone": _unique_phone(),
        "username": _unique_username(),
        "password": PASSWORD,
    }
    values.update(overrides)
    customer = CustomerService().create_customer(**values)
    db.customer_ids.append(customer.id)
    return customer


def _fetch_one(sql, params):
    with transaction() as conn:
        return _execute(conn, sql, params)[0]


# ----- AuthService -----------------------------------------------------------


def test_login_returns_session_for_active_employee(db):
    manager = db.employees["manager"]

    session = AuthService().login(f"  {manager.username}  ", PASSWORD)

    assert session.employee_id == manager.id
    assert session.store_id == db.store_id
    assert session.store_name == "LI03 Test Store"
    assert session.role == Role.MANAGER
    assert not hasattr(session, "password_hash")


@pytest.mark.parametrize(
    "employee_key, password",
    [("manager", "wrong-password"), ("locked", PASSWORD), (None, PASSWORD)],
)
def test_login_rejects_invalid_credentials(db, employee_key, password):
    username = db.employees[employee_key].username if employee_key else "li03.nobody"

    with pytest.raises(AuthenticationError):
        AuthService().login(username, password)


# ----- CustomerService -------------------------------------------------------


def test_create_customer_creates_customer_and_account_together(db):
    phone = _unique_phone()
    username = _unique_username()

    customer = _create(db, full_name="  Nguyễn Văn A  ", phone=phone, username=username)

    assert customer.code.startswith("CUS-") and len(customer.code) == 20
    assert customer.full_name == "Nguyễn Văn A"
    assert customer.phone == phone
    assert customer.status == CustomerStatus.ACTIVE
    assert customer.account.code.startswith("ACC-") and len(customer.account.code) == 20
    assert customer.account.username == username
    assert customer.account.balance == 0
    assert customer.account.status == AccountStatus.ACTIVE

    stored_hash = _fetch_one(
        "SELECT password_hash FROM accounts WHERE customer_id = %s", (customer.id,)
    )
    assert stored_hash != PASSWORD
    assert stored_hash.startswith("$2")


def test_create_customer_rejects_invalid_input(db):
    with pytest.raises(ValidationError) as exc_info:
        CustomerService().create_customer("A", "123", "ab", "123")

    assert set(exc_info.value.field_errors) == {"full_name", "phone", "username", "password"}


def test_create_customer_duplicate_phone_raises_conflict(db):
    existing = _create(db)

    with pytest.raises(ConflictError) as exc_info:
        _create(db, phone=existing.phone)

    assert exc_info.value.field_errors == {"phone": "Số điện thoại đã được sử dụng"}


def test_create_customer_duplicate_username_rolls_back_customer(db):
    existing = _create(db)
    new_phone = _unique_phone()

    with pytest.raises(ConflictError) as exc_info:
        _create(db, phone=new_phone, username=existing.account.username)

    assert exc_info.value.field_errors == {"username": "Tên đăng nhập đã được sử dụng"}
    # Account lỗi nên customer vừa insert trong cùng transaction cũng phải biến mất.
    assert _fetch_one("SELECT COUNT(*) FROM customers WHERE phone = %s", (new_phone,)) == 0


def test_get_customer_returns_customer_with_account(db):
    created = _create(db)

    customer = CustomerService().get_customer(created.id)

    assert customer.id == created.id
    assert customer.account.id == created.account.id


def test_get_customer_unknown_raises_not_found(db):
    with pytest.raises(NotFoundError):
        CustomerService().get_customer(UNKNOWN_ID)


def test_search_customers_matches_code_name_phone_and_username(db):
    created = _create(db, full_name="LI03 Tìm Kiếm")
    service = CustomerService()

    for keyword in (
        created.code,
        "LI03 Tìm",
        created.phone,
        created.account.username,
        f"  {created.phone}  ",
    ):
        results = service.search_customers(keyword)
        assert any(item.customer_id == created.id for item in results), keyword


def test_search_customers_without_match_returns_empty_list(db):
    assert CustomerService().search_customers("li03-khong-co-" + uuid4().hex) == []


def test_update_customer_changes_profile(db):
    created = _create(db)
    new_phone = _unique_phone()

    updated = CustomerService().update_customer(created.id, "  Tên Mới  ", new_phone)

    assert updated.full_name == "Tên Mới"
    assert updated.phone == new_phone


def test_update_customer_with_same_values_succeeds(db):
    created = _create(db)

    updated = CustomerService().update_customer(created.id, created.full_name, created.phone)

    assert updated.full_name == created.full_name


def test_update_customer_duplicate_phone_raises_conflict(db):
    first = _create(db)
    second = _create(db)

    with pytest.raises(ConflictError) as exc_info:
        CustomerService().update_customer(second.id, second.full_name, first.phone)

    assert set(exc_info.value.field_errors) == {"phone"}


def test_update_customer_unknown_raises_not_found(db):
    with pytest.raises(NotFoundError):
        CustomerService().update_customer(UNKNOWN_ID, "Tên Hợp Lệ", _unique_phone())


def test_set_customer_status_locks_and_unlocks_account_together(db):
    created = _create(db)
    service = CustomerService()

    inactive = service.set_customer_status(created.id, CustomerStatus.INACTIVE, db.manager)
    assert inactive.status == CustomerStatus.INACTIVE
    assert inactive.account.status == AccountStatus.LOCKED

    active = service.set_customer_status(created.id, CustomerStatus.ACTIVE, db.manager)
    assert active.status == CustomerStatus.ACTIVE
    assert active.account.status == AccountStatus.ACTIVE


def test_set_customer_status_rejects_staff(db):
    created = _create(db)

    with pytest.raises(PermissionDeniedError):
        CustomerService().set_customer_status(created.id, CustomerStatus.INACTIVE, db.staff)

    assert CustomerService().get_customer(created.id).status == CustomerStatus.ACTIVE


def test_set_customer_status_rolls_back_when_account_update_fails(db, monkeypatch):
    created = _create(db)

    def fail_set_status(self, conn, account_id, status):
        raise RuntimeError("khóa account lỗi")

    monkeypatch.setattr(AccountRepository, "set_status", fail_set_status)

    with pytest.raises(RuntimeError):
        CustomerService().set_customer_status(created.id, CustomerStatus.INACTIVE, db.manager)

    assert CustomerService().get_customer(created.id).status == CustomerStatus.ACTIVE


def test_set_customer_status_unknown_raises_not_found(db):
    with pytest.raises(NotFoundError):
        CustomerService().set_customer_status(UNKNOWN_ID, CustomerStatus.INACTIVE, db.manager)
