"""LI-04 — Integration test WalletService trên MySQL test database.

WalletService tự mở transaction() trên connection riêng, nên dữ liệu chuẩn bị
phải được commit trước; fixture tự xóa đúng các dòng mình tạo sau mỗi test.
"""

from datetime import timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cyberhub_manager.database import connection
from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.domain.enums import (
    AccountStatus,
    PaymentMethod,
    TransactionType,
)
from cyberhub_manager.domain.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.repositories.account_repository import AccountRepository
from cyberhub_manager.repositories.customer_repository import CustomerRepository
from cyberhub_manager.security import hash_password
from cyberhub_manager.services.wallet_service import WalletService

TEST_DATABASE = "cyberhub_manager_migration_test"
EMPLOYEE_NAME = "LI04 Test Employee"
UNKNOWN_ID = 999_999_999_999


def _execute(conn, sql, params=()):
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone() if cursor.with_rows else cursor.lastrowid
    finally:
        cursor.close()


@pytest.fixture
def wallet_db(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", TEST_DATABASE)
    monkeypatch.setattr(connection, "_pool", None)

    token = uuid4().hex
    password_hash = hash_password("temporary-test-password")

    with transaction() as conn:
        assert _execute(conn, "SELECT DATABASE()") == (TEST_DATABASE,)

        store_id = _execute(
            conn,
            "INSERT INTO stores (code, name, address) VALUES (%s, %s, %s)",
            ("ST-" + token[:16], "LI04 Test Store", "Test address"),
        )
        employee_id = _execute(
            conn,
            """
            INSERT INTO employees
                (code, store_id, full_name, username, password_hash, role)
            VALUES (%s, %s, %s, %s, %s, 'STAFF')
            """,
            (
                "EMP-" + token[:16],
                store_id,
                EMPLOYEE_NAME,
                "li04e." + token[:12],
                password_hash,
            ),
        )
        customer_id = CustomerRepository().create(
            conn,
            code="CUS-" + token[:16],
            full_name="LI04 Test Customer",
            phone="09" + str(int(token[:12], 16) % 100000000).zfill(8),
        )
        account_id = AccountRepository().create(
            conn,
            code="ACC-" + token[:16],
            customer_id=customer_id,
            username="li04c." + token[:12],
            password_hash=password_hash,
        )

    try:
        yield SimpleNamespace(
            employee_id=employee_id,
            customer_id=customer_id,
            account_id=account_id,
        )
    finally:
        # Xóa bảng con trước bảng cha để không vướng khóa ngoại.
        with transaction() as conn:
            _execute(
                conn,
                "DELETE FROM account_transactions WHERE account_id = %s",
                (account_id,),
            )
            _execute(conn, "DELETE FROM accounts WHERE id = %s", (account_id,))
            _execute(conn, "DELETE FROM customers WHERE id = %s", (customer_id,))
            _execute(conn, "DELETE FROM employees WHERE id = %s", (employee_id,))
            _execute(conn, "DELETE FROM stores WHERE id = %s", (store_id,))


def _balance(account_id):
    with transaction() as conn:
        return AccountRepository().get_by_id(conn, account_id).balance


def _transaction_count(account_id):
    with transaction() as conn:
        return _execute(
            conn,
            "SELECT COUNT(*) FROM account_transactions WHERE account_id = %s",
            (account_id,),
        )[0]


def test_top_up_credits_balance_and_records_transaction(wallet_db):
    result = WalletService().top_up(
        wallet_db.customer_id, 50_000, PaymentMethod.CASH, wallet_db.employee_id
    )

    assert result.customer_id == wallet_db.customer_id
    assert result.account_id == wallet_db.account_id
    assert result.balance_before == 0
    assert result.balance_after == 50_000
    assert _balance(wallet_db.account_id) == 50_000

    entry = result.transaction
    assert entry.transaction_code.startswith("TX-")
    assert len(entry.transaction_code) == 20
    assert entry.type == TransactionType.TOP_UP
    assert entry.amount == 50_000
    assert entry.method == PaymentMethod.CASH
    assert entry.employee_id == wallet_db.employee_id
    assert entry.employee_name == EMPLOYEE_NAME
    assert entry.session_id is None
    assert entry.created_at.tzinfo == timezone.utc


def test_get_history_returns_newest_first(wallet_db):
    service = WalletService()
    first = service.top_up(
        wallet_db.customer_id, 10_000, PaymentMethod.CASH, wallet_db.employee_id
    )
    second = service.top_up(
        wallet_db.customer_id, 20_000, PaymentMethod.TRANSFER, wallet_db.employee_id
    )

    history = service.get_history(wallet_db.customer_id)

    assert [item.transaction_id for item in history] == [
        second.transaction.transaction_id,
        first.transaction.transaction_id,
    ]
    assert second.balance_before == 10_000
    assert second.balance_after == 30_000
    assert all(item.created_at.tzinfo == timezone.utc for item in history)


def test_get_history_returns_empty_list_without_transactions(wallet_db):
    assert WalletService().get_history(wallet_db.customer_id) == []


def test_top_up_allows_locked_account(wallet_db):
    with transaction() as conn:
        AccountRepository().set_status(
            conn, wallet_db.account_id, AccountStatus.LOCKED
        )

    result = WalletService().top_up(
        wallet_db.customer_id, 15_000, PaymentMethod.CASH, wallet_db.employee_id
    )

    assert result.balance_after == 15_000
    assert _balance(wallet_db.account_id) == 15_000


def test_top_up_rolls_back_balance_when_transaction_insert_fails(
    wallet_db, monkeypatch
):
    def fail_insert(self, conn, **kwargs):
        raise RuntimeError("ghi giao dịch lỗi")

    monkeypatch.setattr(AccountRepository, "insert_top_up_transaction", fail_insert)

    with pytest.raises(RuntimeError):
        WalletService().top_up(
            wallet_db.customer_id, 10_000, PaymentMethod.CASH, wallet_db.employee_id
        )

    assert _balance(wallet_db.account_id) == 0
    assert _transaction_count(wallet_db.account_id) == 0


def test_top_up_unknown_employee_is_denied_and_rolled_back(wallet_db):
    with pytest.raises(PermissionDeniedError):
        WalletService().top_up(
            wallet_db.customer_id, 10_000, PaymentMethod.CASH, UNKNOWN_ID
        )

    assert _balance(wallet_db.account_id) == 0
    assert _transaction_count(wallet_db.account_id) == 0


def test_top_up_unknown_customer_raises_not_found(wallet_db):
    with pytest.raises(NotFoundError):
        WalletService().top_up(
            UNKNOWN_ID, 10_000, PaymentMethod.CASH, wallet_db.employee_id
        )


def test_get_history_unknown_customer_raises_not_found(wallet_db):
    with pytest.raises(NotFoundError):
        WalletService().get_history(UNKNOWN_ID)


def test_top_up_invalid_amount_leaves_data_unchanged(wallet_db):
    with pytest.raises(ValidationError):
        WalletService().top_up(
            wallet_db.customer_id, 0, PaymentMethod.CASH, wallet_db.employee_id
        )

    assert _balance(wallet_db.account_id) == 0
    assert _transaction_count(wallet_db.account_id) == 0
