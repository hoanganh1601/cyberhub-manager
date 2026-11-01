"""LI-07 — Integration test preview và checkout trên MySQL test database.

SessionService tự mở transaction() trên connection riêng, nên dữ liệu chuẩn bị
phải được commit trước; fixture tự xóa mọi dòng thuộc hai cửa hàng test sau
mỗi test. Phiên được mở thật bằng SessionService lúc NOW với giá 6_000đ/giờ
(100đ/phút); checkout lúc NOW + 61 giây => 2 phút => phí 200đ.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Barrier, Thread
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cyberhub_manager.database import connection
from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.domain.enums import (
    InvoiceStatus,
    PaymentMethod,
    Role,
    SessionStatus,
)
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    PermissionDeniedError,
    SettlementRequiredError,
    ValidationError,
)
from cyberhub_manager.repositories.account_repository import AccountRepository
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.repositories.invoice_repository import InvoiceRepository
from cyberhub_manager.repositories.machine_repository import MachineRepository
from cyberhub_manager.repositories.session_repository import SessionRepository
from cyberhub_manager.services.session_service import (
    NO_ACTIVE_SESSION,
    SessionService,
)

TEST_DATABASE = "cyberhub_manager_migration_test"
NOW = datetime(2026, 10, 31, 8, 0, tzinfo=timezone.utc)
CHECKOUT_AT = NOW + timedelta(seconds=61)
RATE = 6_000
BALANCE = 50_000


def _execute(conn, sql, params=()):
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone() if cursor.with_rows else cursor.lastrowid
    finally:
        cursor.close()


def _fetch_one(sql, params=()):
    with transaction() as conn:
        return _execute(conn, sql, params)


def _update(sql, params):
    with transaction() as conn:
        _execute(conn, sql, params)


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", TEST_DATABASE)
    monkeypatch.setattr(connection, "_pool", None)

    token = uuid4().hex[:8]
    counter = iter(range(1, 1_000))

    with transaction() as conn:
        assert _execute(conn, "SELECT DATABASE()") == (TEST_DATABASE,)
        store_ids = [
            _execute(
                conn,
                "INSERT INTO stores (code, name, address) VALUES (%s, %s, %s)",
                (f"ST{index}-{token}", "LI07 Test Store", "Test address"),
            )
            for index in (1, 2)
        ]
        store_id, other_store_id = store_ids

        employee_ids = {}
        for role in Role:
            employee_ids[role] = _execute(
                conn,
                """
                INSERT INTO employees
                    (code, store_id, full_name, username, password_hash, role)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    f"EMP-{role.value[:3]}-{token}",
                    store_id,
                    f"LI07 {role.value}",
                    f"li07.{role.value.lower()}.{token}",
                    "x",
                    role.value,
                ),
            )

        customer_id = _execute(
            conn,
            "INSERT INTO customers (code, full_name, phone) VALUES (%s, %s, %s)",
            (
                f"CUS-{token}",
                "LI07 Khách",
                "05" + str(uuid4().int % 100_000_000).zfill(8),
            ),
        )
        account_id = _execute(
            conn,
            """
            INSERT INTO accounts
                (code, customer_id, username, password_hash, balance)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (f"ACC-{token}", customer_id, f"li07c.{token}", "x", BALANCE),
        )

    # Phiên đăng nhập thật đọc từ DB, đóng vai actor của UI.
    with transaction() as conn:
        actors = {
            role: AuthRepository().get_active_session_by_id(conn, employee_id)
            for role, employee_id in employee_ids.items()
        }

    def make_machine(*, store=store_id):
        with transaction() as conn:
            return _execute(
                conn,
                """
                INSERT INTO machines (code, store_id, name, hourly_rate)
                VALUES (%s, %s, %s, %s)
                """,
                (f"LI07-{token}-{next(counter)}", store, "LI07 Máy", RATE),
            )

    def open_session(machine_id):
        """STAFF mở phiên lúc NOW; trả về id phiên."""

        staff = actors[Role.STAFF]
        service = SessionService(actor_provider=lambda: staff, clock=lambda: NOW)
        return service.open_session(customer_id, machine_id, staff).session_id

    try:
        yield SimpleNamespace(
            store_id=store_id,
            other_store_id=other_store_id,
            employee_ids=employee_ids,
            actors=actors,
            manager=actors[Role.MANAGER],
            customer_id=customer_id,
            account_id=account_id,
            make_machine=make_machine,
            open_session=open_session,
        )
    finally:
        # Xóa bảng con trước bảng cha để không vướng khóa ngoại.
        with transaction() as conn:
            for sid in store_ids:
                _execute(conn, "DELETE FROM invoices WHERE store_id = %s", (sid,))
            _execute(
                conn,
                "DELETE FROM account_transactions WHERE account_id = %s",
                (account_id,),
            )
            for sid in store_ids:
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
            _execute(conn, "DELETE FROM accounts WHERE id = %s", (account_id,))
            _execute(conn, "DELETE FROM customers WHERE id = %s", (customer_id,))
            for sid in store_ids:
                _execute(conn, "DELETE FROM employees WHERE store_id = %s", (sid,))
                _execute(conn, "DELETE FROM stores WHERE id = %s", (sid,))


def _service(actor, clock=lambda: CHECKOUT_AT):
    return SessionService(actor_provider=lambda: actor, clock=clock)


def _set_balance(db, balance):
    _update(
        "UPDATE accounts SET balance = %s WHERE id = %s", (balance, db.account_id)
    )


def _state(db, session_id, machine_id):
    """Năm nhóm dữ liệu checkout: số dư, giao dịch, phiên, máy, hóa đơn."""

    return _fetch_one(
        """
        SELECT
            (SELECT balance FROM accounts WHERE id = %s),
            (SELECT COUNT(*) FROM account_transactions WHERE account_id = %s),
            (SELECT status FROM usage_sessions WHERE id = %s),
            (SELECT status FROM machines WHERE id = %s),
            (SELECT COUNT(*) FROM invoices WHERE session_id = %s)
        """,
        (db.account_id, db.account_id, session_id, machine_id, session_id),
    )


def _transactions(db):
    with transaction() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT type, amount, method, session_id, employee_id
                FROM account_transactions
                WHERE account_id = %s
                ORDER BY id
                """,
                (db.account_id,),
            )
            return cursor.fetchall()
        finally:
            cursor.close()


@pytest.fixture
def busy(db):
    """Một máy đang có phiên ACTIVE do STAFF mở lúc NOW."""

    machine_id = db.make_machine()
    session_id = db.open_session(machine_id)
    before = _state(db, session_id, machine_id)
    assert before == (BALANCE, 0, "ACTIVE", "IN_USE", 0)
    return SimpleNamespace(machine_id=machine_id, session_id=session_id)


# ----- preview_checkout -------------------------------------------------------
def test_preview_checkout_does_not_write(db, busy):
    sql = "SELECT updated_at FROM machines WHERE id = %s"
    machine_updated_at = _fetch_one(sql, (busy.machine_id,))

    preview = _service(db.manager).preview_checkout(busy.machine_id, CHECKOUT_AT)

    assert preview.usage_cost == 200
    assert preview.settlement_required == 0
    assert _state(db, busy.session_id, busy.machine_id) == (
        BALANCE,
        0,
        "ACTIVE",
        "IN_USE",
        0,
    )
    assert _fetch_one(sql, (busy.machine_id,)) == machine_updated_at


@pytest.mark.parametrize(
    ("offset_seconds", "minutes", "cost"),
    [(1, 1, 100), (60, 1, 100), (61, 2, 200)],
)
def test_preview_checkout_boundaries_use_rate_snapshot(
    db, busy, offset_seconds, minutes, cost
):
    # Tăng giá máy sau khi mở: phí vẫn theo usage_sessions.hourly_rate.
    _update(
        "UPDATE machines SET hourly_rate = 12000 WHERE id = %s", (busy.machine_id,)
    )

    preview = _service(db.manager).preview_checkout(
        busy.machine_id, NOW + timedelta(seconds=offset_seconds)
    )

    assert preview.session.hourly_rate == RATE
    assert (preview.billed_minutes, preview.usage_cost) == (minutes, cost)


# ----- complete_checkout thành công -------------------------------------------
def test_complete_checkout_persists_all_five_groups(db, busy):
    result = _service(db.manager).complete_checkout(
        busy.machine_id, db.manager, 0, None
    )

    assert result.balance_after == BALANCE - 200
    assert _state(db, busy.session_id, busy.machine_id) == (
        BALANCE - 200,
        1,
        "COMPLETED",
        "AVAILABLE",
        1,
    )

    with transaction() as conn:
        session = SessionRepository().get_by_id(conn, busy.session_id)
        invoice = InvoiceRepository().get_by_id(
            conn, result.invoice.invoice.invoice_id
        )
    assert session.status == SessionStatus.COMPLETED
    # Người mở và người checkout được lưu riêng.
    assert session.opened_by == db.employee_ids[Role.STAFF]
    assert session.closed_by == db.employee_ids[Role.MANAGER]
    assert (session.ended_at, session.cost) == (CHECKOUT_AT, 200)

    assert invoice.code == result.invoice.invoice.invoice_code
    assert (invoice.session_id, invoice.customer_id, invoice.store_id) == (
        busy.session_id,
        db.customer_id,
        db.store_id,
    )
    assert invoice.employee_id == db.employee_ids[Role.MANAGER]
    assert (invoice.usage_cost, invoice.settlement_amount, invoice.total_amount) == (
        200,
        0,
        200,
    )
    assert invoice.status == InvoiceStatus.PAID
    assert result.invoice.invoice.created_at == invoice.created_at
    assert result.invoice.invoice.created_at.tzinfo == timezone.utc

    assert _transactions(db) == [
        (
            "USAGE_PAYMENT",
            -200,
            "ACCOUNT_BALANCE",
            busy.session_id,
            db.employee_ids[Role.MANAGER],
        )
    ]


@pytest.mark.parametrize("role", [Role.STAFF, Role.MANAGER, Role.ADMIN])
def test_every_store_role_can_checkout(db, busy, role):
    actor = db.actors[role]

    result = _service(actor).complete_checkout(busy.machine_id, actor, 0, None)

    assert result.invoice.invoice.employee_id == db.employee_ids[role]


@pytest.mark.parametrize(
    ("settlement", "method", "balance_after"),
    [(150, PaymentMethod.CASH, 0), (200, PaymentMethod.TRANSFER, 50)],
)
def test_complete_checkout_with_settlement(db, busy, settlement, method, balance_after):
    _set_balance(db, 50)

    result = _service(db.manager).complete_checkout(
        busy.machine_id, db.manager, settlement, method
    )

    assert result.balance_after == balance_after
    assert result.invoice.invoice.settlement_amount == settlement
    assert _state(db, busy.session_id, busy.machine_id) == (
        balance_after,
        2,
        "COMPLETED",
        "AVAILABLE",
        1,
    )
    manager_id = db.employee_ids[Role.MANAGER]
    assert _transactions(db) == [
        ("DEBT_SETTLEMENT", settlement, method.value, busy.session_id, manager_id),
        ("USAGE_PAYMENT", -200, "ACCOUNT_BALANCE", busy.session_id, manager_id),
    ]


# ----- complete_checkout bị từ chối: dữ liệu giữ nguyên -----------------------
@pytest.mark.parametrize(
    ("settlement", "method", "error"),
    [
        (0, None, SettlementRequiredError),  # cần bù 150 mà không bù
        (149, PaymentMethod.CASH, SettlementRequiredError),
        (201, PaymentMethod.CASH, ValidationError),  # vượt phí phiên
        (150, PaymentMethod.ACCOUNT_BALANCE, ValidationError),
    ],
)
def test_rejected_settlement_changes_nothing(db, busy, settlement, method, error):
    _set_balance(db, 50)

    with pytest.raises(error):
        _service(db.manager).complete_checkout(
            busy.machine_id, db.manager, settlement, method
        )

    assert _state(db, busy.session_id, busy.machine_id) == (
        50,
        0,
        "ACTIVE",
        "IN_USE",
        0,
    )


@pytest.mark.parametrize(
    "target",
    [
        (AccountRepository, "insert_debt_settlement_transaction"),
        (AccountRepository, "debit_balance"),
        (AccountRepository, "insert_usage_payment_transaction"),
        (SessionRepository, "complete"),
        (MachineRepository, "mark_available"),
        (InvoiceRepository, "create"),
    ],
)
def test_failure_mid_checkout_rolls_back_all_five_groups(
    db, busy, monkeypatch, target
):
    _set_balance(db, 50)
    repo, method = target

    def fail(self, *args, **kwargs):
        raise RuntimeError("lỗi giữa chừng")

    monkeypatch.setattr(repo, method, fail)

    with pytest.raises(RuntimeError):
        _service(db.manager).complete_checkout(
            busy.machine_id, db.manager, 150, PaymentMethod.CASH
        )

    assert _state(db, busy.session_id, busy.machine_id) == (
        50,
        0,
        "ACTIVE",
        "IN_USE",
        0,
    )


def test_machine_of_other_store_is_denied(db):
    machine_id = db.make_machine(store=db.other_store_id)

    with pytest.raises(PermissionDeniedError):
        _service(db.manager).preview_checkout(machine_id, CHECKOUT_AT)
    with pytest.raises(PermissionDeniedError):
        _service(db.manager).complete_checkout(machine_id, db.manager, 0, None)


@pytest.mark.parametrize(
    ("table", "status"),
    [("employees", "LOCKED"), ("employees", "INACTIVE"), ("stores", "INACTIVE")],
)
def test_inactive_actor_or_store_is_denied(db, busy, table, status):
    row_id = db.manager.employee_id if table == "employees" else db.store_id
    _update(f"UPDATE {table} SET status = %s WHERE id = %s", (status, row_id))

    with pytest.raises(PermissionDeniedError):
        _service(db.manager).complete_checkout(busy.machine_id, db.manager, 0, None)

    assert _state(db, busy.session_id, busy.machine_id) == (
        BALANCE,
        0,
        "ACTIVE",
        "IN_USE",
        0,
    )


def test_staff_claiming_manager_role_is_denied(db, busy):
    forged = replace(db.actors[Role.STAFF], role=Role.MANAGER)

    with pytest.raises(PermissionDeniedError):
        _service(forged).complete_checkout(busy.machine_id, forged, 0, None)

    assert _state(db, busy.session_id, busy.machine_id) == (
        BALANCE,
        0,
        "ACTIVE",
        "IN_USE",
        0,
    )


def test_machine_without_active_session_conflicts(db):
    machine_id = db.make_machine()

    with pytest.raises(ConflictError) as exc_info:
        _service(db.manager).complete_checkout(machine_id, db.manager, 0, None)

    assert exc_info.value.field_errors == {"machine_id": NO_ACTIVE_SESSION}


# ----- double-click và checkout đồng thời --------------------------------------
def test_double_click_checkout_creates_one_invoice(db, busy):
    service = _service(db.manager)
    service.complete_checkout(busy.machine_id, db.manager, 0, None)

    with pytest.raises(ConflictError):
        service.complete_checkout(busy.machine_id, db.manager, 0, None)

    assert _state(db, busy.session_id, busy.machine_id) == (
        BALANCE - 200,
        1,
        "COMPLETED",
        "AVAILABLE",
        1,
    )


def test_concurrent_checkout_creates_one_invoice(db, busy):
    """Hai request cùng lúc; FOR UPDATE trên máy buộc request sau chờ request trước."""

    barrier = Barrier(2)
    results = []

    def worker():
        service = _service(db.manager)
        barrier.wait()
        try:
            results.append(
                service.complete_checkout(busy.machine_id, db.manager, 0, None)
            )
        except ConflictError as exc:
            results.append(exc)

    threads = [Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    conflicts = [r for r in results if isinstance(r, ConflictError)]
    assert len(results) == 2
    assert len(conflicts) == 1
    assert conflicts[0].field_errors == {"machine_id": NO_ACTIVE_SESSION}
    # Chỉ trừ tiền một lần và chỉ một hóa đơn.
    assert _state(db, busy.session_id, busy.machine_id) == (
        BALANCE - 200,
        1,
        "COMPLETED",
        "AVAILABLE",
        1,
    )
