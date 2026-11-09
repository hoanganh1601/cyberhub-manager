"""LI-08 — Integration test ReportService trên MySQL test database.

ReportService tự mở transaction() trên connection riêng, nên dữ liệu chuẩn bị
phải được commit trước; fixture tự xóa mọi dòng thuộc hai cửa hàng test sau
mỗi test. Giờ tạo hóa đơn được đặt thẳng bằng UTC để thử ranh giới ngày
Asia/Ho_Chi_Minh (UTC+7): 00:00 giờ Việt Nam = 17:00 UTC ngày hôm trước.
"""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cyberhub_manager.database import connection
from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.domain.dtos import DailyRevenue, InvoiceFilters
from cyberhub_manager.domain.enums import InvoiceStatus, Role, SessionStatus
from cyberhub_manager.domain.exceptions import NotFoundError, PermissionDeniedError
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.repositories.invoice_repository import InvoiceRepository
from cyberhub_manager.services.report_service import ReportService

TEST_DATABASE = "cyberhub_manager_test"
UNKNOWN_ID = 999_999_999_999
RATE = 6_000


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def _execute(conn, sql, params=()):
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone() if cursor.with_rows else cursor.lastrowid
    finally:
        cursor.close()


@pytest.fixture
def db():
    # monkeypatch.setenv("MYSQL_DATABASE", TEST_DATABASE)
    # monkeypatch.setattr(connection, "_pool", None)

    token = uuid4().hex[:8]
    counter = iter(range(1, 1_000))

    with transaction() as conn:
        assert _execute(conn, "SELECT DATABASE()") == (TEST_DATABASE,)
        store_ids = [
            _execute(
                conn,
                "INSERT INTO stores (code, name, address) VALUES (%s, %s, %s)",
                (f"ST{index}-{token}", f"LI08 Cửa hàng {index}", "Test address"),
            )
            for index in (1, 2)
        ]
        store_id, other_store_id = store_ids

        employee_ids = {}
        for key, sid, role in (
            ("staff", store_id, Role.MANAGER),  # Đợt 0: doanh thu chỉ cho MANAGER/ADMIN
            ("other", other_store_id, Role.MANAGER),
        ):
            employee_ids[key] = _execute(
                conn,
                """
                INSERT INTO employees
                    (code, store_id, full_name, username, password_hash, role)
                VALUES (%s, %s, %s, %s, 'x', %s)
                """,
                (
                    f"EMP-{key[:3]}-{token}",
                    sid,
                    f"LI08 {key}",
                    f"li08.{key}.{token}",
                    role.value,
                ),
            )

        customer_id = _execute(
            conn,
            "INSERT INTO customers (code, full_name, phone) VALUES (%s, %s, %s)",
            (
                f"CUS-{token}",
                "LI08 Khách",
                "03" + str(uuid4().int % 100_000_000).zfill(8),
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

    # Phiên đăng nhập thật đọc từ DB, đóng vai actor của UI.
    with transaction() as conn:
        staff = AuthRepository().get_active_session_by_id(conn, employee_ids["staff"])

    def make_invoice(created_at, *, store=store_id, status="PAID", cost=200):
        """Một phiên COMPLETED 61 giây trên máy mới, hóa đơn tạo lúc created_at."""

        employee_id = employee_ids["staff" if store == store_id else "other"]
        number = next(counter)
        started_at = (created_at - timedelta(seconds=61)).replace(tzinfo=None)
        ended_at = created_at.replace(tzinfo=None)
        with transaction() as conn:
            machine_id = _execute(
                conn,
                """
                INSERT INTO machines (code, store_id, name, hourly_rate)
                VALUES (%s, %s, %s, %s)
                """,
                (f"LI08-{token}-{number}", store, f"LI08 Máy {number}", RATE),
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
                    f"SS-{token}-{number}",
                    customer_id,
                    machine_id,
                    employee_id,
                    employee_id,
                    started_at,
                    ended_at,
                    RATE,
                    cost,
                ),
            )
            invoice_id = InvoiceRepository().create(
                conn,
                code=f"INV-{token}-{number}",
                session_id=session_id,
                customer_id=customer_id,
                employee_id=employee_id,
                store_id=store,
                usage_cost=cost,
                settlement_amount=0,
            )
            # MySQL tự ghi created_at = lúc INSERT; đặt lại để thử ranh giới ngày.
            _execute(
                conn,
                "UPDATE invoices SET created_at = %s, status = %s WHERE id = %s",
                (ended_at, status, invoice_id),
            )
        return SimpleNamespace(
            invoice_id=invoice_id,
            code=f"INV-{token}-{number}",
            session_id=session_id,
            machine_id=machine_id,
            machine_code=f"LI08-{token}-{number}",
        )

    try:
        yield SimpleNamespace(
            token=token,
            store_id=store_id,
            other_store_id=other_store_id,
            employee_ids=employee_ids,
            customer_id=customer_id,
            staff=staff,
            service=ReportService(actor_provider=lambda: staff),
            make_invoice=make_invoice,
        )
    finally:
        # Xóa bảng con trước bảng cha để không vướng khóa ngoại.
        with transaction() as conn:
            for sid in store_ids:
                _execute(conn, "DELETE FROM invoices WHERE store_id = %s", (sid,))
                _execute(
                    conn,
                    """
                    DELETE s FROM usage_sessions AS s
                    JOIN machines AS m ON m.id = s.machine_id
                    WHERE m.store_id = %s
                    """,
                    (sid,),
                )
                _execute(conn, "DELETE FROM machines WHERE store_id = %s", (sid,))
            _execute(
                conn, "DELETE FROM accounts WHERE customer_id = %s", (customer_id,)
            )
            _execute(conn, "DELETE FROM customers WHERE id = %s", (customer_id,))
            for sid in store_ids:
                # Xem doanh thu ghi management_audit (FK RESTRICT tới employees): xóa trước.
                _execute(conn, "DELETE FROM management_audit WHERE store_id = %s", (sid,))
                _execute(conn, "DELETE FROM employees WHERE store_id = %s", (sid,))
                _execute(conn, "DELETE FROM stores WHERE id = %s", (sid,))


# ----- list_invoices ----------------------------------------------------------
def test_list_invoices_only_returns_current_store_newest_first(db):
    older = db.make_invoice(utc(2026, 11, 1, 3))
    newer = db.make_invoice(utc(2026, 11, 1, 5))
    db.make_invoice(utc(2026, 11, 1, 4), store=db.other_store_id)

    result = db.service.list_invoices(db.store_id, InvoiceFilters())

    assert [i.invoice_id for i in result] == [newer.invoice_id, older.invoice_id]
    assert {i.store_id for i in result} == {db.store_id}
    first = result[0]
    assert (first.customer_name, first.employee_name, first.store_name) == (
        "LI08 Khách",
        "LI08 staff",
        "LI08 Cửa hàng 1",
    )
    assert first.created_at == utc(2026, 11, 1, 5)


def test_list_invoices_date_filter_uses_vietnam_day_boundaries(db):
    db.make_invoice(utc(2026, 10, 31, 16, 59, 59))  # 23:59:59 ngày 31/10 VN
    first = db.make_invoice(utc(2026, 10, 31, 17, 0, 0))  # 00:00:00 ngày 01/11 VN
    last = db.make_invoice(utc(2026, 11, 1, 16, 59, 59))  # 23:59:59 ngày 01/11 VN
    db.make_invoice(utc(2026, 11, 1, 17, 0, 0))  # 00:00:00 ngày 02/11 VN
    filters = InvoiceFilters(date_from=date(2026, 11, 1), date_to=date(2026, 11, 1))

    result = db.service.list_invoices(db.store_id, filters)

    assert [i.invoice_id for i in result] == [last.invoice_id, first.invoice_id]


def test_list_invoices_filters_by_status_and_keyword(db):
    paid = db.make_invoice(utc(2026, 11, 1, 3))
    void = db.make_invoice(utc(2026, 11, 1, 4), status="VOID")

    by_status = db.service.list_invoices(
        db.store_id, InvoiceFilters(status=InvoiceStatus.VOID)
    )
    by_code = db.service.list_invoices(db.store_id, InvoiceFilters(keyword=paid.code))

    assert [i.invoice_id for i in by_status] == [void.invoice_id]
    assert [i.invoice_id for i in by_code] == [paid.invoice_id]


def test_list_invoices_of_other_store_is_denied(db):
    db.make_invoice(utc(2026, 11, 1, 3), store=db.other_store_id)

    with pytest.raises(PermissionDeniedError):
        db.service.list_invoices(db.other_store_id, InvoiceFilters())


# ----- get_invoice ------------------------------------------------------------
def test_get_invoice_returns_detail(db):
    created = db.make_invoice(utc(2026, 11, 1, 3))

    detail = db.service.get_invoice(created.invoice_id)

    assert detail.invoice.invoice_id == created.invoice_id
    assert detail.invoice.invoice_code == created.code
    assert detail.invoice.usage_cost == 200
    assert detail.invoice.status == InvoiceStatus.PAID
    session = detail.session
    assert (session.session_id, session.status) == (
        created.session_id,
        SessionStatus.COMPLETED,
    )
    assert (session.machine_id, session.machine_code) == (
        created.machine_id,
        created.machine_code,
    )
    assert (session.customer_id, session.customer_name) == (
        db.customer_id,
        "LI08 Khách",
    )
    assert session.hourly_rate == RATE
    assert session.started_at == utc(2026, 11, 1, 2, 58, 59)
    assert detail.ended_at == utc(2026, 11, 1, 3)
    assert detail.billed_minutes == 2


def test_get_invoice_of_other_store_is_denied(db):
    foreign = db.make_invoice(utc(2026, 11, 1, 3), store=db.other_store_id)

    with pytest.raises(PermissionDeniedError):
        db.service.get_invoice(foreign.invoice_id)


def test_get_unknown_invoice_is_not_found(db):
    with pytest.raises(NotFoundError):
        db.service.get_invoice(UNKNOWN_ID)


# ----- daily_revenue ----------------------------------------------------------
def test_daily_revenue_counts_paid_invoices_by_vietnam_day(db):
    db.make_invoice(utc(2026, 10, 31, 16, 59, 59), cost=1)  # 31/10 VN: ngoài khoảng
    db.make_invoice(utc(2026, 10, 31, 17, 0, 0), cost=100)  # 00:00 ngày 01/11 VN
    db.make_invoice(utc(2026, 11, 1, 5), cost=200)  # trưa 01/11 VN
    db.make_invoice(utc(2026, 11, 1, 6), cost=5_000, status="VOID")  # không tính
    db.make_invoice(utc(2026, 11, 2, 16, 59, 59), cost=300)  # 23:59:59 ngày 02/11 VN
    db.make_invoice(utc(2026, 11, 2, 17, 0, 0), cost=7)  # 03/11 VN: ngoài khoảng
    db.make_invoice(utc(2026, 11, 1, 5), cost=9_000, store=db.other_store_id)

    result = db.service.daily_revenue(db.store_id, date(2026, 11, 1), date(2026, 11, 2))

    # Cả ngày đầu và ngày cuối đều được tính; VOID và cửa hàng khác bị loại.
    assert result == [
        DailyRevenue(date=date(2026, 11, 1), invoice_count=2, revenue=300),
        DailyRevenue(date=date(2026, 11, 2), invoice_count=1, revenue=300),
    ]
    assert all(type(row.revenue) is int for row in result)


def test_daily_revenue_skips_days_without_paid_invoices(db):
    db.make_invoice(utc(2026, 11, 1, 3), cost=100)
    db.make_invoice(utc(2026, 11, 2, 3), status="VOID")  # 02/11 chỉ có VOID
    db.make_invoice(utc(2026, 11, 3, 3), cost=300)

    result = db.service.daily_revenue(db.store_id, date(2026, 11, 1), date(2026, 11, 3))

    assert [row.date for row in result] == [date(2026, 11, 1), date(2026, 11, 3)]


def test_daily_revenue_of_other_store_is_denied(db):
    with pytest.raises(PermissionDeniedError):
        db.service.daily_revenue(
            db.other_store_id, date(2026, 11, 1), date(2026, 11, 1)
        )


# ----- Actor ------------------------------------------------------------------
@pytest.mark.parametrize(
    ("table", "status"),
    [("employees", "LOCKED"), ("employees", "INACTIVE"), ("stores", "INACTIVE")],
)
def test_inactive_actor_or_store_is_denied(db, table, status):
    db.make_invoice(utc(2026, 11, 1, 3))
    row_id = db.employee_ids["staff"] if table == "employees" else db.store_id
    with transaction() as conn:
        _execute(
            conn, f"UPDATE {table} SET status = %s WHERE id = %s", (status, row_id)
        )

    with pytest.raises(PermissionDeniedError):
        db.service.list_invoices(db.store_id, InvoiceFilters())
    with pytest.raises(PermissionDeniedError):
        db.service.daily_revenue(db.store_id, date(2026, 11, 1), date(2026, 11, 1))
