"""LI-07 — Integration test cho hai thao tác repository dùng khi checkout.

Mỗi test tự mở transaction() và dọn dữ liệu của mình; repository không được
tự commit nên lỗi trong transaction phải làm mọi thay đổi biến mất.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from cyberhub_manager.database import connection
from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.repositories.account_repository import AccountRepository
from cyberhub_manager.repositories.machine_repository import MachineRepository

TEST_DATABASE = "cyberhub_manager_migration_test"
UNKNOWN_ID = 999_999_999_999


def _execute(conn, sql, params=()):
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone() if cursor.with_rows else cursor.lastrowid
    finally:
        cursor.close()


def _fetch_one(sql, params):
    with transaction() as conn:
        return _execute(conn, sql, params)


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", TEST_DATABASE)
    monkeypatch.setattr(connection, "_pool", None)

    token = uuid4().hex[:8]
    counter = iter(range(1, 100))

    with transaction() as conn:
        assert _execute(conn, "SELECT DATABASE()") == (TEST_DATABASE,)
        store_id = _execute(
            conn,
            "INSERT INTO stores (code, name, address) VALUES (%s, %s, %s)",
            (f"ST-{token}", "LI07 Test Store", "Test address"),
        )
        customer_id = _execute(
            conn,
            "INSERT INTO customers (code, full_name, phone) VALUES (%s, %s, %s)",
            (
                f"CUS-{token}",
                "LI07 Khách",
                "06" + str(uuid4().int % 100_000_000).zfill(8),
            ),
        )
        account_id = _execute(
            conn,
            """
            INSERT INTO accounts
                (code, customer_id, username, password_hash, balance)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (f"ACC-{token}", customer_id, f"li07c.{token}", "x", 5_000),
        )

    def make_machine(status):
        with transaction() as conn:
            return _execute(
                conn,
                """
                INSERT INTO machines (code, store_id, name, status, hourly_rate)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    f"LI07-{token}-{next(counter)}",
                    store_id,
                    "LI07 Máy",
                    status,
                    6_000,
                ),
            )

    try:
        yield SimpleNamespace(account_id=account_id, make_machine=make_machine)
    finally:
        with transaction() as conn:
            _execute(conn, "DELETE FROM machines WHERE store_id = %s", (store_id,))
            _execute(conn, "DELETE FROM accounts WHERE id = %s", (account_id,))
            _execute(conn, "DELETE FROM customers WHERE id = %s", (customer_id,))
            _execute(conn, "DELETE FROM stores WHERE id = %s", (store_id,))


def _balance(account_id):
    return _fetch_one("SELECT balance FROM accounts WHERE id = %s", (account_id,))[0]


def _machine_status(machine_id):
    return _fetch_one("SELECT status FROM machines WHERE id = %s", (machine_id,))[0]


# ----- AccountRepository.debit_balance ----------------------------------------
@pytest.mark.parametrize(
    ("amount", "expected", "balance_after"),
    [
        (3_000, True, 2_000),
        (5_000, True, 0),  # trừ về đúng 0 vẫn hợp lệ
        (5_001, False, 5_000),  # không bao giờ làm số dư âm
    ],
)
def test_debit_balance_never_goes_negative(db, amount, expected, balance_after):
    with transaction() as conn:
        debited = AccountRepository().debit_balance(conn, db.account_id, amount)

    assert debited is expected

    assert _balance(db.account_id) == balance_after


def test_debit_balance_unknown_account_returns_false(db):
    with transaction() as conn:
        assert AccountRepository().debit_balance(conn, UNKNOWN_ID, 1_000) is False


@pytest.mark.parametrize("amount", [0, -1, True, 1.5])
def test_debit_balance_rejects_invalid_amount(db, amount):
    with transaction() as conn:
        with pytest.raises(ValueError):
            AccountRepository().debit_balance(conn, db.account_id, amount)

    assert _balance(db.account_id) == 5_000


def test_debit_balance_does_not_commit(db):
    with pytest.raises(RuntimeError):
        with transaction() as conn:
            assert AccountRepository().debit_balance(conn, db.account_id, 1_000)
            raise RuntimeError("rollback")

    assert _balance(db.account_id) == 5_000


# ----- MachineRepository.mark_available ---------------------------------------
@pytest.mark.parametrize(
    ("status", "expected", "status_after"),
    [
        ("IN_USE", True, "AVAILABLE"),
        ("AVAILABLE", False, "AVAILABLE"),
        ("MAINTENANCE", False, "MAINTENANCE"),  # không được kéo máy ra khỏi bảo trì
    ],
)
def test_mark_available_only_releases_in_use_machine(
    db, status, expected, status_after
):
    machine_id = db.make_machine(status)

    with transaction() as conn:
        assert MachineRepository().mark_available(conn, machine_id) is expected

    assert _machine_status(machine_id) == status_after


def test_mark_available_does_not_commit(db):
    machine_id = db.make_machine("IN_USE")

    with pytest.raises(RuntimeError):
        with transaction() as conn:
            assert MachineRepository().mark_available(conn, machine_id) is True
            raise RuntimeError("rollback")

    assert _machine_status(machine_id) == "IN_USE"
