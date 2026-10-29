import pytest
from mysql.connector.errors import IntegrityError

from datetime import datetime, timezone, timedelta, date
from uuid import uuid4


from cyberhub_manager.database import connection
from cyberhub_manager.repositories.account_repository import AccountRepository
from cyberhub_manager.repositories.session_repository import SessionRepository
from cyberhub_manager.repositories.invoice_repository import InvoiceRepository
from cyberhub_manager.domain.enums import PaymentMethod, InvoiceStatus

def test_insert_usage_payment_transaction_rolls_back(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", "cyberhub_manager_migration_test")
    monkeypatch.setattr(connection, "_pool", None)

    conn = connection.get_connection()
    cursor = conn.cursor(buffered=True)
    transaction_code = "HA08T_" + uuid4().hex[:12].upper()
    settlement_code = "HA08D_" + uuid4().hex[:12].upper()

    try:
        cursor.execute("SELECT DATABASE()")
        assert cursor.fetchone()[0] == "cyberhub_manager_migration_test"
        conn.start_transaction()

        cursor.execute(
            """
            SELECT a.id, c.id
            FROM accounts AS a
            JOIN customers AS c ON c.id = a.customer_id
            WHERE c.code = %s
            """,
            ("DEMO_CUS_01",),
        )
        account_id, customer_id = cursor.fetchone()

        cursor.execute(
            "SELECT id, store_id, hourly_rate FROM machines WHERE code = %s",
            ("DEMO_PC_01",),
        )
        machine_id, store_id, hourly_rate = cursor.fetchone()

        cursor.execute(
            """
            SELECT id FROM employees
            WHERE store_id = %s AND status = 'ACTIVE'
            ORDER BY id LIMIT 1
            """,
            (store_id,),
        )
        employee_id = cursor.fetchone()[0]

        cursor.execute("SELECT balance FROM accounts WHERE id = %s", (account_id,))
        balance_before = cursor.fetchone()[0]

        session_id = SessionRepository().create(
            conn,
            code = "HA08S_" + uuid4().hex[:12].upper(),
            customer_id = customer_id,
            machine_id = machine_id,
            opened_by = employee_id,
            started_at = datetime.now(timezone.utc),
            hourly_rate = hourly_rate,
        )

        transaction_id = AccountRepository().insert_usage_payment_transaction(
            conn,
            code = transaction_code,
            account_id = account_id,
            employee_id = employee_id,
            session_id = session_id,
            usage_cost = 1000,
        )

        cursor.execute(
            """
            SELECT type, amount, method, session_id
            FROM account_transactions WHERE id = %s
            """,
            (transaction_id,),
        )
        assert cursor.fetchone() == (
            "USAGE_PAYMENT", -1000, "ACCOUNT_BALANCE", session_id
        )

        settlement_id = AccountRepository().insert_debt_settlement_transaction(
            conn,
            code = settlement_code,
            account_id = account_id,
            employee_id = employee_id,
            session_id = session_id,
            settlement_amount = 1000,
            method = PaymentMethod.CASH,
        )
        cursor.execute(
            """
            SELECT type, amount, method, session_id
            FROM account_transactions WHERE id = %s
            """,
            (settlement_id,),
        )
        assert cursor.fetchone() == (
            "DEBT_SETTLEMENT", 1000, "CASH", session_id
        )
        
        cursor.execute("SELECT balance FROM accounts WHERE id = %s", (account_id,))
        assert cursor.fetchone()[0] == balance_before

        conn.rollback()
        cursor.execute(
            "SELECT COUNT(*) FROM account_transactions WHERE code IN (%s, %s)",
            (transaction_code, settlement_code),
        )
        assert cursor.fetchone()[0] == 0
    finally:
        conn.rollback()
        cursor.close()
        conn.close()
def test_create_invoice_rolls_back(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", "cyberhub_manager_migration_test")
    monkeypatch.setattr(connection, "_pool", None)

    conn = connection.get_connection()
    cursor = conn.cursor(buffered = True)
    session_repo = SessionRepository()
    invoice_repo = InvoiceRepository()
    invoice_code = "HA08I_" + uuid4().hex[:12].upper()

    try:
        cursor.execute("SELECT DATABASE()")
        assert cursor.fetchone()[0] == "cyberhub_manager_migration_test"
        conn.start_transaction()

        cursor.execute(
            "SELECT id FROM customers WHERE code = %s",
            ("DEMO_CUS_01",),
        )
        customer_id = cursor.fetchone()[0]
        cursor.execute(
            "SELECT id, store_id, hourly_rate FROM machines WHERE code = %s",
            ("DEMO_PC_01",),
        )
        machine_id, store_id, hourly_rate = cursor.fetchone()
        cursor.execute(
            """
            SELECT id FROM employees
            WHERE store_id = %s AND status = 'ACTIVE'
            ORDER BY id LIMIT 1
            """,
            (store_id,),
        )
        employee_id = cursor.fetchone()[0]

        session_id = session_repo.create(
            conn,
            code = "HA08S_" + uuid4().hex[:12].upper(),
            customer_id = customer_id,
            machine_id = machine_id,
            opened_by = employee_id,
            started_at = datetime.now(timezone.utc) - timedelta(minutes = 2),
            hourly_rate = hourly_rate,
        )
        session = session_repo.get_by_id(conn, session_id, for_update = True)
        assert session is not None
        cost = session.complete(employee_id, datetime.now(timezone.utc))
        assert session_repo.complete(conn, session) is True

        invoice_id = invoice_repo.create(
            conn,
            code = invoice_code,
            session_id = session_id,
            customer_id = customer_id,
            employee_id = employee_id,
            store_id = store_id,
            usage_cost = cost,
            settlement_amount=0,
        )

        cursor.execute(
            """
            SELECT code, session_id, usage_cost, settlement_amount,
                   total_amount, status
            FROM invoices WHERE id = %s
            """,
            (invoice_id,),
        )
        assert cursor.fetchone() == (
            invoice_code, session_id, cost, 0, cost, "PAID"
        )
        
        saved = invoice_repo.get_by_id(conn, invoice_id)
        assert saved is not None
        assert saved.id == invoice_id
        assert saved.session_id == session_id
        assert saved.total_amount == cost
        assert saved.status == InvoiceStatus.PAID
        assert saved.created_at.utcoffset() == timedelta(0)
        
        filtered = invoice_repo.list_by_store(
            conn,
            store_id,
            created_from_utc = saved.created_at,
            created_before_utc = saved.created_at + timedelta(days=1),
            keyword = invoice_code,
            customer_id = customer_id,
            status = InvoiceStatus.PAID,
        )
        assert [item.invoice_id for item in filtered] == [invoice_id]
        assert filtered[0].total_amount == cost
        assert invoice_repo.list_by_store(
            conn,
            store_id,
            created_before_utc = saved.created_at,
            keyword = invoice_code,
        ) == []
        
        with pytest.raises(IntegrityError):
            invoice_repo.create(
                conn,
                code = "HA08J_" + uuid4().hex[:12].upper(),
                session_id = session_id,
                customer_id = customer_id,
                employee_id = employee_id,
                store_id = store_id,
                usage_cost = cost,
                settlement_amount = 0,
            )
        cursor.execute(
            "SELECT COUNT(*) FROM invoices WHERE session_id = %s",
            (session_id,),
        )
        assert cursor.fetchone()[0] == 1

        # conn.rollback()
        day_start_utc = datetime(2035, 1, 1, 17, 0, tzinfo=timezone.utc)
        cursor.execute(
            "UPDATE invoices SET created_at = %s WHERE id = %s",
            (day_start_utc.replace(tzinfo=None), invoice_id),
        )
        
        cursor.execute(
        "SELECT id, store_id, status, created_at, usage_cost FROM invoices WHERE id = %s",
        (invoice_id,),
        )
        print("REVENUE DEBUG:", cursor.fetchone())
        
        revenue = invoice_repo.daily_revenue_by_store(
            conn,
            store_id,
            created_from_utc = day_start_utc,
            created_before_utc = day_start_utc + timedelta(days = 1),
        )
        assert [(r.date, r.invoice_count, r.revenue) for r in revenue] == [
            (date(2035, 1, 2), 1, cost)
        ]
        cursor.execute(
            "UPDATE invoices SET status = 'VOID' WHERE id = %s",
            (invoice_id,),
        )
        assert invoice_repo.daily_revenue_by_store (
            conn,
            store_id,
            created_from_utc = day_start_utc,
            created_before_utc = day_start_utc + timedelta(days = 1),
        ) == []
        
        conn.rollback()
        cursor.execute(
            "SELECT COUNT(*) FROM invoices WHERE code = %s",
            (invoice_code,),
        )
        assert cursor.fetchone()[0] == 0
    finally:
        conn.rollback()
        cursor.close()
        conn.close()