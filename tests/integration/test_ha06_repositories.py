"""Integration tests for HA-06 repositories."""

from uuid import uuid4
from datetime import timezone

import pytest

from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    PaymentMethod,
    TransactionType,
)
from mysql.connector.errors import IntegrityError
from cyberhub_manager.database import connection
from cyberhub_manager.repositories.account_repository import AccountRepository
from cyberhub_manager.repositories.customer_repository import CustomerRepository
from cyberhub_manager.security import hash_password


def test_create_customer_and_account_can_roll_back(monkeypatch):
    monkeypatch.setenv(
        "MYSQL_DATABASE", "cyberhub_manager_migration_test"
    )
    monkeypatch.setattr(connection, "_pool", None)

    token = uuid4().hex
    customer_code = "CUS-" + token[:16]
    account_code = "ACC-" + token[:16]
    username = "ha06." + token[:12]
    phone = "09" + str(int(token[:12], 16) % 100000000).zfill(8)

    conn = connection.get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute("SELECT DATABASE()")
        assert cursor.fetchone()[0] == "cyberhub_manager_migration_test"

        conn.start_transaction()
        customer_id = CustomerRepository().create(
            conn,
            code = customer_code,
            full_name = "Test HA06",
            phone = phone,
        )
        account_id = AccountRepository().create(
            conn,
            code = account_code,
            customer_id = customer_id,
            username = username,
            password_hash = hash_password("temporary-test-password"),
        )

        customer = CustomerRepository().get_by_id(conn, customer_id)
        assert customer is not None
        assert customer.account.id == account_id
        assert customer.account.username == username

        conn.rollback()

        cursor.execute(
            "SELECT COUNT(*) FROM customers WHERE code = %s",
            (customer_code,),
        )
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            "SELECT COUNT(*) FROM accounts WHERE code = %s",
            (account_code,),
        )
        assert cursor.fetchone()[0] == 0
    finally:
        conn.rollback()
        cursor.close()
        conn.close()

@pytest.fixture
def wallet_context(monkeypatch):
    monkeypatch.setenv(
        "MYSQL_DATABASE", "cyberhub_manager_migration_test"
    )
    monkeypatch.setattr(connection, "_pool", None)

    token = uuid4().hex
    password_hash = hash_password("temporary-test-password")
    conn = connection.get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        conn.start_transaction()
        cursor.execute("SELECT DATABASE()")
        assert cursor.fetchone()[0] == "cyberhub_manager_migration_test"

        cursor.execute(
            """
            INSERT INTO stores (code, name, address)
            VALUES (%s, %s, %s)
            """,
            ("ST-" + token[:16], "HA06 Test Store", "Test address"),
        )
        store_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO employees
                (code, store_id, full_name, username, password_hash, role)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                "EMP-" + token[:16],
                store_id,
                "HA06 Test Employee",
                "ha06e." + token[:12],
                password_hash,
                "STAFF",
            ),
        )
        employee_id = cursor.lastrowid

        customer_id = CustomerRepository().create(
            conn,
            code="CUS-" + token[:16],
            full_name="HA06 Test Customer",
            phone="09" + str(int(token[:12], 16) % 100000000).zfill(8),
        )
        account_id = AccountRepository().create(
            conn,
            code="ACC-" + token[:16],
            customer_id=customer_id,
            username="ha06c." + token[:12],
            password_hash=password_hash,
        )

        yield conn, account_id, employee_id
    finally:
        conn.rollback()
        cursor.close()
        conn.close()

def test_top_up_balance_and_history_roll_back_together(wallet_context):
    conn, account_id, employee_id = wallet_context
    repo = AccountRepository()
    code = "TX-" + uuid4().hex[:17]

    cursor = conn.cursor()
    cursor.execute("SAVEPOINT ha06_top_up")
    try:
        assert repo.get_by_id(conn, account_id, for_update=True).balance == 0
        assert repo.credit_balance(conn, account_id, 10000)

        transaction_id = repo.insert_top_up_transaction(
            conn,
            code = code,
            account_id = account_id,
            employee_id = employee_id,
            amount = 10000,
            method = PaymentMethod.CASH,
        )

        assert repo.get_by_id(conn, account_id).balance == 10000
        history = repo.list_transactions(conn, account_id)
        assert len(history) == 1

        entry = history[0]
        assert entry.transaction_id == transaction_id
        assert entry.type == TransactionType.TOP_UP
        assert entry.amount == 10000
        assert entry.method == PaymentMethod.CASH
        assert entry.employee_id == employee_id
        assert entry.created_at.tzinfo == timezone.utc
    finally:
        cursor.execute("ROLLBACK TO SAVEPOINT ha06_top_up")
        cursor.close()

    assert repo.get_by_id(conn, account_id).balance == 0
    assert repo.list_transactions(conn, account_id) == []

def test_customer_profile_search_and_status_can_roll_back(wallet_context):
    conn, account_id, _employee_id = wallet_context
    customer_repo = CustomerRepository()
    account_repo = AccountRepository()

    account = account_repo.get_by_id(conn, account_id)
    customer_id = account.customer_id
    original = customer_repo.get_by_id(conn, customer_id)
    assert original is not None

    cursor = conn.cursor()
    cursor.execute("SAVEPOINT ha06_customer")
    try:
        assert customer_repo.update_profile(
            conn,
            customer_id,
            full_name = "HA06 Renamed Customer",
            phone = original.phone,
        )
        assert customer_repo.set_status(
            conn, customer_id, CustomerStatus.INACTIVE
        )
        assert account_repo.set_status(
            conn, account_id, AccountStatus.LOCKED
        )

        updated = customer_repo.get_by_id(conn, customer_id)
        assert updated.full_name == "HA06 Renamed Customer"
        assert updated.status == CustomerStatus.INACTIVE
        assert updated.account.status == AccountStatus.LOCKED

        for keyword in (
            updated.code,
            updated.full_name,
            updated.phone,
            updated.account.username,
        ):
            assert any(
                item.customer_id == customer_id
                for item in customer_repo.search(conn, keyword)
            )
    finally:
        cursor.execute("ROLLBACK TO SAVEPOINT ha06_customer")
        cursor.close()

    restored = customer_repo.get_by_id(conn, customer_id)
    assert restored.full_name == original.full_name
    assert restored.status == CustomerStatus.ACTIVE
    assert restored.account.status == AccountStatus.ACTIVE

def test_duplicate_customer_phone_is_rejected(wallet_context):
    conn, account_id, _employee_id = wallet_context
    customer_repo = CustomerRepository()

    account = AccountRepository().get_by_id(conn, account_id)
    existing = customer_repo.get_by_id(conn, account.customer_id)
    duplicate_code = "CUS-" + uuid4().hex[:16]

    cursor = conn.cursor()
    cursor.execute("SAVEPOINT ha06_duplicate_phone")
    try:
        with pytest.raises(IntegrityError):
            customer_repo.create(
                conn,
                code=duplicate_code,
                full_name="Another Test Customer",
                phone=existing.phone,
            )
    finally:
        cursor.execute("ROLLBACK TO SAVEPOINT ha06_duplicate_phone")

    cursor.execute(
        "SELECT COUNT(*) FROM customers WHERE code = %s",
        (duplicate_code,),
    )
    assert cursor.fetchone()[0] == 0
    cursor.close()

def test_duplicate_account_username_is_rejected(wallet_context):
    conn, account_id, _employee_id = wallet_context
    account_repo = AccountRepository()
    existing = account_repo.get_by_id(conn, account_id)

    token = uuid4().hex
    customer_code = "CUS-" + token[:16]
    cursor = conn.cursor(buffered=True)

    try:
        cursor.execute("SAVEPOINT ha06_duplicate_username")
        try:
            customer_id = CustomerRepository().create(
                conn,
                code = customer_code,
                full_name = "Another Test Customer",
                phone = "08" + str(int(token[:12], 16) % 100000000).zfill(8),
            )

            with pytest.raises(IntegrityError):
                account_repo.create(
                    conn,
                    code = "ACC-" + token[:16],
                    customer_id = customer_id,
                    username = existing.username,
                    password_hash = hash_password("temporary-test-password"),
                )
        finally:
            cursor.execute("ROLLBACK TO SAVEPOINT ha06_duplicate_username")

        cursor.execute(
            "SELECT COUNT(*) FROM customers WHERE code = %s",
            (customer_code,),
        )
        assert cursor.fetchone()[0] == 0

    finally:
        cursor.close()

def test_rejects_invalid_top_up_inputs(wallet_context):
    conn, account_id, employee_id = wallet_context
    repo = AccountRepository()

    for amount in (0, -1, True, 1.5):
        with pytest.raises(ValueError):
            repo.credit_balance(conn, account_id, amount)

        with pytest.raises(ValueError):
            repo.insert_top_up_transaction(
                conn,
                code = "TX-" + uuid4().hex[:17],
                account_id = account_id,
                employee_id = employee_id,
                amount = amount,
                method = PaymentMethod.CASH,
            )

    with pytest.raises(ValueError):
        repo.insert_top_up_transaction(
            conn,
            code = "TX-" + uuid4().hex[:17],
            account_id = account_id,
            employee_id = employee_id,
            amount = 10000,
            method = PaymentMethod.ACCOUNT_BALANCE,
        )

    assert repo.get_by_id(conn, account_id).balance == 0
    assert repo.list_transactions(conn, account_id) == []