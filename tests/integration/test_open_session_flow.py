"""LI-06 — Integration test mở phiên và live estimate trên MySQL test database.

SessionService tự mở transaction() trên connection riêng, nên dữ liệu chuẩn bị
phải được commit trước; fixture tự xóa mọi dòng thuộc hai cửa hàng test sau
mỗi test. Đánh số TC theo 15 test case bắt buộc của task LI-06.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Barrier, Thread
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.domain.enums import MachineStatus, Role, SessionStatus
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    InsufficientBalanceError,
    PermissionDeniedError,
)
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.repositories.machine_repository import MachineRepository
from cyberhub_manager.repositories.session_repository import SessionRepository
from cyberhub_manager.services.machine_service import MachineService
from cyberhub_manager.services.session_service import (
    ACCOUNT_LOCKED,
    CUSTOMER_BUSY,
    CUSTOMER_INACTIVE,
    MACHINE_ARCHIVED,
    MACHINE_BUSY,
    MACHINE_MAINTENANCE,
    SessionService,
)

TEST_DATABASE = "cyberhub_manager_test"
NOW = datetime(2026, 10, 31, 8, 0, tzinfo=timezone.utc)
# Đơn giá 6_000đ/giờ => tối thiểu 30 phút = 3_000đ.
RATE = 6_000
MINIMUM = 3_000


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
def db():
    token = uuid4().hex[:8]
    counter = iter(range(1, 1_000))

    with transaction() as conn:
        assert _execute(conn, "SELECT DATABASE()") == (TEST_DATABASE,)
        store_ids = [
            _execute(
                conn,
                "INSERT INTO stores (code, name, address) VALUES (%s, %s, %s)",
                (f"ST{index}-{token}", "LI06 Test Store", "Test address"),
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
                    f"LI06 {role.value}",
                    f"li06.{role.value.lower()}.{token}",
                    "x",
                    role.value,
                ),
            )

        customer_ids = []
        for index in (1, 2):
            customer_id = _execute(
                conn,
                "INSERT INTO customers (code, full_name, phone) VALUES (%s, %s, %s)",
                (
                    f"CUS{index}-{token}",
                    f"LI06 Khách {index}",
                    "07" + str(uuid4().int % 100_000_000).zfill(8),
                ),
            )
            _execute(
                conn,
                """
                INSERT INTO accounts
                    (code, customer_id, username, password_hash, balance)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    f"ACC{index}-{token}",
                    customer_id,
                    f"li06c{index}.{token}",
                    "x",
                    50_000,
                ),
            )
            customer_ids.append(customer_id)

    # Phiên đăng nhập thật đọc từ DB, đóng vai actor của UI.
    with transaction() as conn:
        actors = {
            role: AuthRepository().get_active_session_by_id(conn, employee_id)
            for role, employee_id in employee_ids.items()
        }

    def make_machine(*, store=store_id, status="AVAILABLE", is_active=True):
        with transaction() as conn:
            return _execute(
                conn,
                """
                INSERT INTO machines
                    (code, store_id, name, status, hourly_rate, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    f"LI06-{token}-{next(counter)}",
                    store,
                    "LI06 Máy",
                    status,
                    RATE,
                    is_active,
                ),
            )

    def insert_active_session(customer_id, machine_id):
        with transaction() as conn:
            return _execute(
                conn,
                """
                INSERT INTO usage_sessions
                    (code, customer_id, machine_id, opened_by, started_at, hourly_rate)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    f"SS-{token}-{next(counter)}",
                    customer_id,
                    machine_id,
                    employee_ids[Role.STAFF],
                    NOW.replace(tzinfo=None),
                    RATE,
                ),
            )

    try:
        yield SimpleNamespace(
            store_id=store_id,
            other_store_id=other_store_id,
            employee_ids=employee_ids,
            actors=actors,
            staff=actors[Role.STAFF],
            customer_id=customer_ids[0],
            other_customer_id=customer_ids[1],
            make_machine=make_machine,
            insert_active_session=insert_active_session,
        )
    finally:
        # Xóa bảng con trước bảng cha để không vướng khóa ngoại.
        with transaction() as conn:
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
            for cid in customer_ids:
                _execute(conn, "DELETE FROM accounts WHERE customer_id = %s", (cid,))
                _execute(conn, "DELETE FROM customers WHERE id = %s", (cid,))
            for sid in store_ids:
                _execute(conn, "DELETE FROM employees WHERE store_id = %s", (sid,))
                _execute(conn, "DELETE FROM stores WHERE id = %s", (sid,))


def _service(actor, clock=lambda: NOW):
    return SessionService(actor_provider=lambda: actor, clock=clock)


def _machine_status(machine_id):
    return _fetch_one("SELECT status FROM machines WHERE id = %s", (machine_id,))[0]


def _session_count(machine_id):
    return _fetch_one(
        "SELECT COUNT(*) FROM usage_sessions WHERE machine_id = %s", (machine_id,)
    )[0]


def _balance(customer_id):
    return _fetch_one(
        "SELECT balance FROM accounts WHERE customer_id = %s", (customer_id,)
    )[0]


def _money_rows(customer_id):
    """Số giao dịch và hóa đơn của khách; mở phiên không được tạo dòng nào."""

    return _fetch_one(
        """
        SELECT
            (SELECT COUNT(*) FROM account_transactions AS t
             JOIN accounts AS a ON a.id = t.account_id
             WHERE a.customer_id = %s),
            (SELECT COUNT(*) FROM invoices WHERE customer_id = %s)
        """,
        (customer_id, customer_id),
    )


def _assert_nothing_opened(db, machine_id):
    assert _session_count(machine_id) == 0
    assert _machine_status(machine_id) == "AVAILABLE"


# ----- TC1, TC2: thành công ---------------------------------------------------
def test_preview_then_open_session_persists_session(db):  # TC1
    machine_id = db.make_machine()
    service = _service(db.staff)

    preview = service.preview_open(db.customer_id, machine_id, db.staff)
    assert preview.minimum_balance == MINIMUM
    assert preview.estimated_minutes == 500
    assert preview.can_open is True

    summary = service.open_session(db.customer_id, machine_id, db.staff)

    assert summary.status == SessionStatus.ACTIVE
    assert summary.started_at == NOW
    assert _machine_status(machine_id) == "IN_USE"
    with transaction() as conn:
        saved = SessionRepository().get_by_id(conn, summary.session_id)
    assert saved.code == summary.session_code
    assert saved.opened_by == db.staff.employee_id
    assert saved.hourly_rate == RATE
    assert saved.started_at == NOW
    assert saved.started_at.tzinfo == timezone.utc
    # Không trừ tiền, không ghi giao dịch, không tạo hóa đơn.
    assert _balance(db.customer_id) == 50_000
    assert _money_rows(db.customer_id) == (0, 0)


@pytest.mark.parametrize("role", [Role.STAFF, Role.MANAGER, Role.ADMIN])
def test_every_store_role_can_open_session(db, role):  # TC2
    actor = db.actors[role]
    machine_id = db.make_machine()

    summary = _service(actor).open_session(db.customer_id, machine_id, actor)

    with transaction() as conn:
        saved = SessionRepository().get_by_id(conn, summary.session_id)
    assert saved.opened_by == db.employee_ids[role]


# ----- TC3, TC4: actor --------------------------------------------------------
@pytest.mark.parametrize(
    ("table", "status"),
    [("employees", "LOCKED"), ("employees", "INACTIVE"), ("stores", "INACTIVE")],
)
def test_inactive_actor_or_store_is_denied(db, table, status):  # TC3
    machine_id = db.make_machine()
    row_id = db.staff.employee_id if table == "employees" else db.store_id
    _update(f"UPDATE {table} SET status = %s WHERE id = %s", (status, row_id))

    with pytest.raises(PermissionDeniedError):
        _service(db.staff).open_session(db.customer_id, machine_id, db.staff)
    _assert_nothing_opened(db, machine_id)


def test_staff_claiming_manager_role_is_denied(db):  # TC4
    machine_id = db.make_machine()
    forged = replace(db.staff, role=Role.MANAGER)

    # Cả actor đăng nhập lẫn actor truyền vào đều tự nhận MANAGER.
    with pytest.raises(PermissionDeniedError):
        _service(forged).open_session(db.customer_id, machine_id, forged)
    _assert_nothing_opened(db, machine_id)


# ----- TC5 - TC8: máy, khách, số dư -------------------------------------------
def test_machine_of_other_store_is_denied(db):  # TC5
    machine_id = db.make_machine(store=db.other_store_id)

    with pytest.raises(PermissionDeniedError):
        _service(db.staff).open_session(db.customer_id, machine_id, db.staff)
    assert _session_count(machine_id) == 0


@pytest.mark.parametrize(
    ("status", "is_active", "message"),
    [
        ("MAINTENANCE", True, MACHINE_MAINTENANCE),
        ("IN_USE", True, MACHINE_BUSY),
        ("AVAILABLE", False, MACHINE_ARCHIVED),
    ],
)
def test_unavailable_machine_is_rejected(db, status, is_active, message):  # TC6
    machine_id = db.make_machine(status=status, is_active=is_active)

    with pytest.raises(ConflictError) as exc_info:
        _service(db.staff).open_session(db.customer_id, machine_id, db.staff)

    assert exc_info.value.field_errors == {"machine_id": message}
    assert _session_count(machine_id) == 0
    assert _machine_status(machine_id) == status


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        (
            "UPDATE customers SET status = 'INACTIVE' WHERE id = %s",
            CUSTOMER_INACTIVE,
        ),
        (
            "UPDATE accounts SET status = 'LOCKED' WHERE customer_id = %s",
            ACCOUNT_LOCKED,
        ),
    ],
)
def test_invalid_customer_or_account_is_rejected(db, sql, message):  # TC7
    machine_id = db.make_machine()
    _update(sql, (db.customer_id,))

    with pytest.raises(ConflictError) as exc_info:
        _service(db.staff).open_session(db.customer_id, machine_id, db.staff)

    assert exc_info.value.field_errors == {"customer_id": message}
    _assert_nothing_opened(db, machine_id)


def test_balance_below_minimum_is_rejected(db):  # TC8
    machine_id = db.make_machine()
    _update(
        "UPDATE accounts SET balance = %s WHERE customer_id = %s",
        (MINIMUM - 1, db.customer_id),
    )

    with pytest.raises(InsufficientBalanceError) as exc_info:
        _service(db.staff).open_session(db.customer_id, machine_id, db.staff)

    assert exc_info.value.details["required_top_up"] == 1
    _assert_nothing_opened(db, machine_id)


# ----- TC9 - TC11: phiên trùng ------------------------------------------------
def test_machine_with_active_session_conflicts(db):  # TC9
    # Dữ liệu lệch: máy vẫn AVAILABLE nhưng đã có phiên ACTIVE.
    machine_id = db.make_machine()
    db.insert_active_session(db.other_customer_id, machine_id)

    with pytest.raises(ConflictError) as exc_info:
        _service(db.staff).open_session(db.customer_id, machine_id, db.staff)

    assert exc_info.value.field_errors == {"machine_id": MACHINE_BUSY}
    assert _session_count(machine_id) == 1


def test_customer_with_active_session_conflicts(db):  # TC10
    busy_machine_id = db.make_machine(status="IN_USE")
    db.insert_active_session(db.customer_id, busy_machine_id)
    machine_id = db.make_machine()

    with pytest.raises(ConflictError) as exc_info:
        _service(db.staff).open_session(db.customer_id, machine_id, db.staff)

    assert exc_info.value.field_errors == {"customer_id": CUSTOMER_BUSY}
    _assert_nothing_opened(db, machine_id)


def test_double_click_creates_only_one_session(db):  # TC11
    machine_id = db.make_machine()
    service = _service(db.staff)
    service.open_session(db.customer_id, machine_id, db.staff)

    with pytest.raises(ConflictError):
        service.open_session(db.customer_id, machine_id, db.staff)

    assert _session_count(machine_id) == 1


def _open_concurrently(db, requests):
    """Hai request cùng lúc; FOR UPDATE buộc request sau chờ request trước."""

    barrier = Barrier(len(requests))
    results = []

    def worker(customer_id, machine_id):
        service = _service(db.staff)
        barrier.wait()
        try:
            results.append(service.open_session(customer_id, machine_id, db.staff))
        except ConflictError as exc:
            results.append(exc)

    threads = [Thread(target=worker, args=request) for request in requests]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results


def test_concurrent_open_same_machine_creates_one_session(db):  # TC11
    machine_id = db.make_machine()

    results = _open_concurrently(
        db, [(db.customer_id, machine_id), (db.other_customer_id, machine_id)]
    )

    conflicts = [r for r in results if isinstance(r, ConflictError)]
    assert len(results) == 2
    assert len(conflicts) == 1
    assert conflicts[0].field_errors == {"machine_id": MACHINE_BUSY}
    assert _session_count(machine_id) == 1


def test_concurrent_open_same_customer_creates_one_session(db):  # TC11
    first, second = db.make_machine(), db.make_machine()

    results = _open_concurrently(
        db, [(db.customer_id, first), (db.customer_id, second)]
    )

    conflicts = [r for r in results if isinstance(r, ConflictError)]
    assert len(results) == 2
    assert len(conflicts) == 1
    assert conflicts[0].field_errors == {"customer_id": CUSTOMER_BUSY}
    assert _session_count(first) + _session_count(second) == 1


# ----- TC12, TC13: transaction và snapshot ------------------------------------
@pytest.mark.parametrize("failure", ["not_updated", "error"])
def test_failure_after_insert_rolls_back_session(db, monkeypatch, failure):  # TC12
    machine_id = db.make_machine()

    def fail_mark_in_use(self, conn, machine_id):
        if failure == "error":
            raise RuntimeError("lỗi giữa chừng")
        return False

    monkeypatch.setattr(MachineRepository, "mark_in_use", fail_mark_in_use)

    with pytest.raises((ConflictError, RuntimeError)):
        _service(db.staff).open_session(db.customer_id, machine_id, db.staff)
    _assert_nothing_opened(db, machine_id)


def test_changing_machine_rate_keeps_session_snapshot(db):  # TC13
    machine_id = db.make_machine()
    summary = _service(db.staff).open_session(db.customer_id, machine_id, db.staff)

    _update("UPDATE machines SET hourly_rate = 12000 WHERE id = %s", (machine_id,))

    with transaction() as conn:
        saved = SessionRepository().get_by_id(conn, summary.session_id)
    assert saved.hourly_rate == RATE


# ----- TC14: live estimate qua dashboard --------------------------------------
@pytest.mark.parametrize(
    ("offset_seconds", "elapsed", "cost"),
    [(0, 0, 100), (60, 60, 100), (61, 61, 200)],  # 6_000đ/giờ = 100đ/phút
)
def test_dashboard_live_estimate_uses_snapshot(db, offset_seconds, elapsed, cost):
    machine_id = db.make_machine()
    _service(db.staff).open_session(db.customer_id, machine_id, db.staff)
    # Đổi giá sau khi mở: estimate vẫn dùng đơn giá snapshot của phiên.
    _update("UPDATE machines SET hourly_rate = 12000 WHERE id = %s", (machine_id,))
    manager = db.actors[Role.MANAGER]
    machines = MachineService(
        actor_provider=lambda: manager,
        clock=lambda: NOW + timedelta(seconds=offset_seconds),
    )

    cards = machines.list_machines(db.store_id)

    [card] = [c for c in cards if c.machine_id == machine_id]
    estimate = card.active_session
    assert card.status == MachineStatus.IN_USE
    assert estimate.session.hourly_rate == RATE
    assert estimate.elapsed_seconds == elapsed
    assert estimate.estimated_cost == cost
    assert estimate.projected_balance == 50_000 - cost
    assert estimate.as_of.tzinfo is not None


# ----- TC15: preview chỉ đọc --------------------------------------------------
def test_preview_does_not_write(db):  # TC15
    machine_id = db.make_machine()
    sql = "SELECT status, updated_at FROM machines WHERE id = %s"
    before = _fetch_one(sql, (machine_id,))

    _service(db.staff).preview_open(db.customer_id, machine_id, db.staff)

    assert _fetch_one(sql, (machine_id,)) == before
    assert _session_count(machine_id) == 0
    assert _balance(db.customer_id) == 50_000


# ----- MachineRepository.mark_in_use ------------------------------------------
@pytest.mark.parametrize(
    ("status", "is_active", "expected"),
    [
        ("AVAILABLE", True, True),
        ("IN_USE", True, False),
        ("MAINTENANCE", True, False),
        ("AVAILABLE", False, False),
    ],
)
def test_mark_in_use_only_switches_available_machine(
    db, status, is_active, expected
):
    machine_id = db.make_machine(status=status, is_active=is_active)

    with transaction() as conn:
        assert MachineRepository().mark_in_use(conn, machine_id) is expected

    assert _machine_status(machine_id) == ("IN_USE" if expected else status)


def test_mark_in_use_does_not_commit(db):
    machine_id = db.make_machine()

    with pytest.raises(RuntimeError):
        with transaction() as conn:
            assert MachineRepository().mark_in_use(conn, machine_id) is True
            raise RuntimeError("rollback")

    assert _machine_status(machine_id) == "AVAILABLE"
