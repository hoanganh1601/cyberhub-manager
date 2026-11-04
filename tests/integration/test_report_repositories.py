"""LI-08 — Integration test cho InvoiceRepository.get_summary_by_id.

Fixture tạo một hóa đơn thật (cửa hàng, nhân viên, khách, máy, phiên COMPLETED)
rồi xóa đúng các dòng mình tạo sau mỗi test.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cyberhub_manager.database import connection
from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.domain.enums import InvoiceStatus
from cyberhub_manager.repositories.invoice_repository import InvoiceRepository

TEST_DATABASE = "cyberhub_manager_migration_test"
UNKNOWN_ID = 999_999_999_999
STARTED_AT = datetime(2026, 11, 1, 1, 0)
ENDED_AT = datetime(2026, 11, 1, 2, 0)


def _execute(conn, sql, params=()):
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone() if cursor.with_rows else cursor.lastrowid
    finally:
        cursor.close()


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", TEST_DATABASE)
    monkeypatch.setattr(connection, "_pool", None)

    token = uuid4().hex[:8]

    with transaction() as conn:
        assert _execute(conn, "SELECT DATABASE()") == (TEST_DATABASE,)
        store_id = _execute(
            conn,
            "INSERT INTO stores (code, name, address) VALUES (%s, %s, %s)",
            (f"ST-{token}", "LI08 Cửa hàng", "Test address"),
        )
        employee_id = _execute(
            conn,
            """
            INSERT INTO employees
                (code, store_id, full_name, username, password_hash, role)
            VALUES (%s, %s, %s, %s, 'x', 'STAFF')
            """,
            (f"EMP-{token}", store_id, "LI08 Nhân viên", f"li08e.{token}"),
        )
        customer_id = _execute(
            conn,
            "INSERT INTO customers (code, full_name, phone) VALUES (%s, %s, %s)",
            (
                f"CUS-{token}",
                "LI08 Khách",
                "04" + str(uuid4().int % 100_000_000).zfill(8),
            ),
        )
        _execute(
            conn,
            """
            INSERT INTO accounts (code, customer_id, username, password_hash)
            VALUES (%s, %s, %s, 'x')
            """,
            (f"ACC-{token}", customer_id, f"li08c.{token}"),
        )
        machine_id = _execute(
            conn,
            """
            INSERT INTO machines (code, store_id, name, hourly_rate)
            VALUES (%s, %s, %s, %s)
            """,
            (f"LI08-{token}", store_id, "LI08 Máy", 6_000),
        )
        session_id = _execute(
            conn,
            """
            INSERT INTO usage_sessions
                (code, customer_id, machine_id, opened_by, closed_by,
                 started_at, ended_at, hourly_rate, cost, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'COMPLETED')
            """,
            (
                f"SS-{token}",
                customer_id,
                machine_id,
                employee_id,
                employee_id,
                STARTED_AT,
                ENDED_AT,
                6_000,
                6_000,
            ),
        )
        invoice_id = InvoiceRepository().create(
            conn,
            code=f"INV-{token}",
            session_id=session_id,
            customer_id=customer_id,
            employee_id=employee_id,
            store_id=store_id,
            usage_cost=6_000,
            settlement_amount=1_000,
        )

    try:
        yield SimpleNamespace(
            token=token,
            store_id=store_id,
            employee_id=employee_id,
            customer_id=customer_id,
            session_id=session_id,
            invoice_id=invoice_id,
        )
    finally:
        # Xóa bảng con trước bảng cha để không vướng khóa ngoại.
        with transaction() as conn:
            _execute(conn, "DELETE FROM invoices WHERE id = %s", (invoice_id,))
            _execute(conn, "DELETE FROM usage_sessions WHERE id = %s", (session_id,))
            _execute(conn, "DELETE FROM machines WHERE id = %s", (machine_id,))
            _execute(
                conn, "DELETE FROM accounts WHERE customer_id = %s", (customer_id,)
            )
            _execute(conn, "DELETE FROM customers WHERE id = %s", (customer_id,))
            _execute(conn, "DELETE FROM employees WHERE id = %s", (employee_id,))
            _execute(conn, "DELETE FROM stores WHERE id = %s", (store_id,))


def _summary(invoice_id):
    with transaction() as conn:
        return InvoiceRepository().get_summary_by_id(conn, invoice_id)


def test_get_summary_by_id_joins_names(db):
    summary = _summary(db.invoice_id)

    assert summary.invoice_id == db.invoice_id
    assert summary.invoice_code == f"INV-{db.token}"
    assert (summary.session_id, summary.customer_id, summary.store_id) == (
        db.session_id,
        db.customer_id,
        db.store_id,
    )
    assert (summary.customer_name, summary.employee_name, summary.store_name) == (
        "LI08 Khách",
        "LI08 Nhân viên",
        "LI08 Cửa hàng",
    )
    assert summary.employee_id == db.employee_id
    assert (summary.usage_cost, summary.settlement_amount, summary.total_amount) == (
        6_000,
        1_000,
        6_000,
    )
    assert summary.status == InvoiceStatus.PAID
    assert summary.created_at.tzinfo == timezone.utc


def test_get_summary_by_id_keeps_name_of_inactive_employee(db):
    # Nhân viên đã nghỉ việc vẫn phải hiện tên trên hóa đơn cũ.
    with transaction() as conn:
        _execute(
            conn,
            "UPDATE employees SET status = 'INACTIVE' WHERE id = %s",
            (db.employee_id,),
        )

    assert _summary(db.invoice_id).employee_name == "LI08 Nhân viên"


def test_get_summary_by_id_returns_void_status(db):
    with transaction() as conn:
        _execute(
            conn, "UPDATE invoices SET status = 'VOID' WHERE id = %s", (db.invoice_id,)
        )

    assert _summary(db.invoice_id).status == InvoiceStatus.VOID


def test_get_summary_by_id_unknown_returns_none(db):
    assert _summary(UNKNOWN_ID) is None


def test_list_by_store_matches_summary_after_refactor(db):
    with transaction() as conn:
        listed = InvoiceRepository().list_by_store(conn, db.store_id)

    assert listed == [_summary(db.invoice_id)]
