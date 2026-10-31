"""LI-05 — Integration test MachineService trên MySQL test database.

Service tự mở transaction() trên connection riêng, nên dữ liệu chuẩn bị
phải được commit trước; fixture tự xóa mọi dòng thuộc hai cửa hàng test
sau mỗi test.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cyberhub_manager.database import connection
from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.enums import MachineArchiveAction, MachineStatus, Role
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.repositories.machine_repository import MachineRepository
from cyberhub_manager.services.machine_service import MachineService

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


def _actor(employee_id, store_id, role):
    return EmployeeSession(
        employee_id=employee_id,
        employee_code="EMP",
        full_name="LI05 Actor",
        username="li05.actor",
        store_id=store_id,
        store_code="ST",
        store_name="LI05 Test Store",
        role=role,
    )


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", TEST_DATABASE)
    monkeypatch.setattr(connection, "_pool", None)

    token = uuid4().hex[:8]

    with transaction() as conn:
        assert _execute(conn, "SELECT DATABASE()") == (TEST_DATABASE,)
        store_ids = [
            _execute(
                conn,
                "INSERT INTO stores (code, name, address) VALUES (%s, %s, %s)",
                (f"ST{index}-{token}", "LI05 Test Store", "Test address"),
            )
            for index in (1, 2)
        ]

        store_id, other_store_id = store_ids
        employees = {}

        for key, employee_store_id, role, status in (
            ("manager", store_id, Role.MANAGER, "ACTIVE"),
            ("admin", store_id, Role.ADMIN, "ACTIVE"),
            ("staff", store_id, Role.STAFF, "ACTIVE"),
            ("locked", store_id, Role.MANAGER, "LOCKED"),
            (
                "other_manager",
                other_store_id,
                Role.MANAGER,
                "ACTIVE",
            ),
        ):
            code_suffix = {
                "manager": "MGR",
                "admin": "ADM",
                "staff": "STF",
                "locked": "LCK",
                "other_manager": "OMR",
            }[key]

            employee_id = _execute(
                conn,
                """
                INSERT INTO employees
                    (
                        code,
                        store_id,
                        full_name,
                        username,
                        password_hash,
                        role,
                        status
                    )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    f"EMP-{code_suffix}-{token}",
                    employee_store_id,
                    f"LI05 {key}",
                    f"li05.{key}.{token}",
                    "x",
                    role.value,
                    status,
                ),
            )

            employees[key] = SimpleNamespace(
                id=employee_id,
                store_id=employee_store_id,
                role=role,
            )

        customer_id = _execute(
            conn,
            "INSERT INTO customers (code, full_name, phone) VALUES (%s, %s, %s)",
            (f"CUS-{token}", "LI05 Khách", "08" + str(uuid4().int % 100_000_000).zfill(8)),
        )
        _execute(
            conn,
            """
            INSERT INTO accounts (code, customer_id, username, password_hash, balance)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (f"ACC-{token}", customer_id, f"li05c.{token}", "x", 50_000),
        )

    counter = iter(range(1, 1_000))

    def make_machine(*, store=store_id, status="AVAILABLE", hourly_rate=6_000):
        with transaction() as conn:
            return _execute(
                conn,
                """
                INSERT INTO machines (code, store_id, name, status, hourly_rate)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (f"LI05-{token}-{next(counter)}", store, "LI05 Máy", status, hourly_rate),
            )

    def start_session(
        machine_id,
        *,
        minutes_ago=10,
        hourly_rate=6_000,
        completed=False,
    ):
        # MySQL DATETIME does not preserve fractional seconds consistently.
        started_at = (
            datetime.now(timezone.utc).replace(
                tzinfo=None,
                microsecond=0,
            )
            - timedelta(minutes=minutes_ago)
        )
        with transaction() as conn:
            session_id = _execute(
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
                    employees["manager"].id,
                    started_at,
                    hourly_rate,
                ),
            )
            if completed:
                _execute(
                    conn,
                    """
                    UPDATE usage_sessions
                    SET closed_by = %s, ended_at = %s, cost = %s, status = 'COMPLETED'
                    WHERE id = %s
                    """,
                    (
                        employees["manager"].id,
                        started_at + timedelta(minutes=5),
                        500,
                        session_id,
                    ),
                )
            else:
                _execute(
                    conn,
                    "UPDATE machines SET status = 'IN_USE' WHERE id = %s",
                    (machine_id,),
                )
        return session_id

    try:
        yield SimpleNamespace(
            token=token,
            store_id=store_id,
            other_store_id=other_store_id,
            customer_id=customer_id,
            employees=employees,
            manager=_actor(
                employees["manager"].id,
                store_id,
                Role.MANAGER,
            ),
            admin=_actor(
                employees["admin"].id,
                store_id,
                Role.ADMIN,
            ),
            staff=_actor(
                employees["staff"].id,
                store_id,
                Role.STAFF,
            ),
            locked=_actor(
                employees["locked"].id,
                store_id,
                Role.MANAGER,
            ),
            other_manager=_actor(
                employees["other_manager"].id,
                other_store_id,
                Role.MANAGER,
            ),
            make_machine=make_machine,
            start_session=start_session,
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
            _execute(conn, "DELETE FROM accounts WHERE customer_id = %s", (customer_id,))
            _execute(conn, "DELETE FROM customers WHERE id = %s", (customer_id,))
            for sid in store_ids:
                _execute(
                    conn,
                    "DELETE FROM employees WHERE store_id = %s",
                    (sid,),
                )
                _execute(
                    conn,
                    "DELETE FROM stores WHERE id = %s",
                    (sid,),
                )


def _machine_service(db, actor=None) -> MachineService:
    """Build MachineService with a trusted logged-in actor."""

    current_actor = db.manager if actor is None else actor

    return MachineService(
        actor_provider=lambda: current_actor,
    )


# ----- list_machines ---------------------------------------------------------


def test_list_machines_includes_active_session_for_dashboard(db):
    idle_id = db.make_machine()
    busy_id = db.make_machine(hourly_rate=6_000)
    db.start_session(busy_id, minutes_ago=10, hourly_rate=6_000)
    archived_id = db.make_machine()
    with transaction() as conn:
        _execute(conn, "UPDATE machines SET is_active = FALSE WHERE id = %s", (archived_id,))

    summaries = {
        item.machine_id: item
        for item in _machine_service(db).list_machines(db.store_id)
    }

    assert set(summaries) == {idle_id, busy_id}
    assert summaries[idle_id].status == MachineStatus.AVAILABLE
    assert summaries[idle_id].active_session is None

    busy = summaries[busy_id]
    assert busy.status == MachineStatus.IN_USE
    active = busy.active_session
    assert active.session.customer_id == db.customer_id
    assert active.session.customer_name == "LI05 Khách"
    assert active.session.machine_code == busy.machine_code
    assert active.account_balance == 50_000
    assert 600 <= active.elapsed_seconds < 700
    # 6.000đ/giờ = 100đ/phút; phiên đã chạy khoảng 10-11 phút.
    assert 1_000 <= active.estimated_cost <= 1_100
    assert active.projected_balance == 50_000 - active.estimated_cost
    assert active.as_of.tzinfo is not None


def test_list_machines_rejects_available_machine_with_active_session(db):
    machine_id = db.make_machine()
    db.start_session(machine_id)

    with transaction() as conn:
        _execute(
            conn,
            "UPDATE machines SET status = 'AVAILABLE' WHERE id = %s",
            (machine_id,),
        )

    with pytest.raises(ConflictError):
        _machine_service(db).list_machines(db.store_id)


def test_list_machines_only_returns_requested_store(db):
    db.make_machine(store=db.other_store_id)

    assert _machine_service(db).list_machines(db.store_id) == []


def test_list_machines_allows_staff_in_own_store(db):
    machine_id = db.make_machine()

    result = _machine_service(db, db.staff).list_machines(db.store_id)

    assert [machine.machine_id for machine in result] == [machine_id]


def test_list_machines_rejects_other_store(db):
    with pytest.raises(PermissionDeniedError):
        _machine_service(db).list_machines(db.other_store_id)


def test_list_machines_rejects_missing_actor_provider(db):
    with pytest.raises(PermissionDeniedError):
        MachineService().list_machines(db.store_id)


def test_list_machines_rejects_locked_employee(db):
    with pytest.raises(PermissionDeniedError):
        _machine_service(db, db.locked).list_machines(db.store_id)

# ----- create_machine --------------------------------------------------------


def test_create_machine_succeeds_for_manager_and_admin(db):
    for actor, suffix in (
        (db.manager, "M"),
        (db.admin, "A"),
    ):
        service = _machine_service(db, actor)

        machine = service.create_machine(
            f"  LI05-{db.token}-{suffix}  ",
            db.store_id,
            "  Máy VIP  ",
            12_000,
            actor,
        )

        assert machine.code == f"LI05-{db.token}-{suffix}"
        assert machine.name == "Máy VIP"
        assert machine.status == MachineStatus.AVAILABLE
        assert machine.is_active is True


def test_create_machine_rejects_staff(db):
    with pytest.raises(PermissionDeniedError):
        _machine_service(db, db.staff).create_machine(
            f"LI05-{db.token}-S",
            db.store_id,
            "Máy",
            5_000,
            db.staff,
        )


def test_create_machine_rejects_forged_manager_role(db):
    forged_actor = _actor(
        db.employees["staff"].id,
        db.store_id,
        Role.MANAGER,
    )

    with pytest.raises(PermissionDeniedError):
        _machine_service(db, forged_actor).create_machine(
            f"LI05-{db.token}-FORGED",
            db.store_id,
            "Forged machine",
            5_000,
            forged_actor,
        )

    assert _fetch_one(
        "SELECT COUNT(*) FROM machines WHERE code = %s",
        (f"LI05-{db.token}-FORGED",),
    ) == (0,)


def test_create_machine_rejects_other_store(db):
    with pytest.raises(PermissionDeniedError):
        _machine_service(db).create_machine(
            f"LI05-{db.token}-O", db.other_store_id, "Máy", 5_000, db.manager
        )


def test_create_machine_rejects_invalid_input(db):
    with pytest.raises(ValidationError) as exc_info:
        _machine_service(db).create_machine("   ", db.store_id, "", True, db.manager)

    assert set(exc_info.value.field_errors) == {"code", "name", "hourly_rate"}


def test_create_machine_duplicate_code_raises_conflict(db):
    service = _machine_service(db)
    service.create_machine(f"LI05-{db.token}-D", db.store_id, "Máy", 5_000, db.manager)

    with pytest.raises(ConflictError) as exc_info:
        service.create_machine(f"LI05-{db.token}-D", db.store_id, "Máy khác", 5_000, db.manager)

    assert exc_info.value.field_errors == {"code": "Mã máy đã tồn tại"}


def test_create_machine_rolls_back_when_reading_back_fails(db, monkeypatch):
    code = f"LI05-{db.token}-R"

    def fail_get_by_id(self, conn, machine_id, *, for_update=False):
        raise RuntimeError("đọc lại máy lỗi")

    monkeypatch.setattr(MachineRepository, "get_by_id", fail_get_by_id)

    with pytest.raises(RuntimeError):
        _machine_service(db).create_machine(code, db.store_id, "Máy", 5_000, db.manager)

    assert _fetch_one("SELECT COUNT(*) FROM machines WHERE code = %s", (code,)) == (0,)


# ----- update_machine --------------------------------------------------------


def test_update_machine_changes_name_and_rate(db):
    machine_id = db.make_machine()

    machine = _machine_service(db).update_machine(machine_id, "  Tên mới  ", 9_000, db.manager)

    assert machine.name == "Tên mới"
    assert machine.hourly_rate == 9_000


def test_update_machine_in_use_keeps_session_snapshot_rate(db):
    machine_id = db.make_machine(hourly_rate=6_000)
    session_id = db.start_session(machine_id, hourly_rate=6_000)

    machine = _machine_service(db).update_machine(
        machine_id,
        "Máy đang chơi",
        9_000,
        db.manager
    )

    assert machine.hourly_rate == 9_000
    assert machine.status == MachineStatus.IN_USE
    assert _fetch_one(
        "SELECT hourly_rate FROM usage_sessions WHERE id = %s", (session_id,)
    ) == (6_000,)


def test_update_machine_rejects_archived_machine(db):
    machine_id = db.make_machine()
    with transaction() as conn:
        _execute(conn, "UPDATE machines SET is_active = FALSE WHERE id = %s", (machine_id,))

    with pytest.raises(ConflictError):
        _machine_service(db).update_machine(machine_id, "Tên", 5_000, db.manager)


def test_update_machine_rejects_staff_and_other_store(db):
    machine_id = db.make_machine()

    with pytest.raises(PermissionDeniedError):
        _machine_service(db, db.staff).update_machine(
            machine_id,
            "Tên",
            5_000,
            db.staff,
        )

    with pytest.raises(PermissionDeniedError):
        _machine_service(db, db.other_manager).update_machine(
            machine_id,
            "Tên",
            5_000,
            db.other_manager,
        )


def test_update_machine_unknown_raises_not_found(db):
    with pytest.raises(NotFoundError):
        _machine_service(db).update_machine(UNKNOWN_ID, "Tên", 5_000, db.manager)


# ----- set_maintenance -------------------------------------------------------


def test_set_maintenance_toggles_status(db):
    machine_id = db.make_machine()
    service = _machine_service(db)

    enabled = service.set_maintenance(machine_id, True, db.manager)
    assert enabled.status == MachineStatus.MAINTENANCE

    disabled = service.set_maintenance(machine_id, False, db.manager)
    assert disabled.status == MachineStatus.AVAILABLE


def test_set_maintenance_rejects_machine_in_use(db):
    machine_id = db.make_machine()
    db.start_session(machine_id)

    with pytest.raises(ConflictError):
        _machine_service(db).set_maintenance(machine_id, True, db.manager)

    assert _fetch_one("SELECT status FROM machines WHERE id = %s", (machine_id,)) == ("IN_USE",)


def test_set_maintenance_rejects_staff_and_other_store(db):
    machine_id = db.make_machine()

    with pytest.raises(PermissionDeniedError):
        _machine_service(db, db.staff).set_maintenance(
            machine_id,
            True,
            db.staff,
        )

    with pytest.raises(PermissionDeniedError):
        _machine_service(db, db.other_manager).set_maintenance(
            machine_id,
            True,
            db.other_manager,
        )

# ----- archive_machine -------------------------------------------------------


def test_archive_machine_without_history_deletes_it(db):
    machine_id = db.make_machine()

    result = _machine_service(db).archive_machine(machine_id, db.manager)

    assert result.machine_id == machine_id
    assert result.action == MachineArchiveAction.DELETED
    assert _fetch_one("SELECT COUNT(*) FROM machines WHERE id = %s", (machine_id,)) == (0,)


def test_archive_machine_with_history_only_archives_it(db):
    machine_id = db.make_machine()
    db.start_session(machine_id, completed=True)

    result = _machine_service(db).archive_machine(machine_id, db.manager)

    assert result.action == MachineArchiveAction.ARCHIVED
    assert _fetch_one("SELECT is_active FROM machines WHERE id = %s", (machine_id,)) == (0,)
    visible_ids = {
        item.machine_id
        for item in _machine_service(db).list_machines(db.store_id)
    }
    assert machine_id not in visible_ids


def test_archive_machine_rejects_machine_in_use(db):
    machine_id = db.make_machine()
    db.start_session(machine_id)

    with pytest.raises(ConflictError) as exc_info:
        _machine_service(db).archive_machine(machine_id, db.manager)

    assert exc_info.value.message == "Không thể ngừng sử dụng máy đang có phiên"
    assert _fetch_one("SELECT is_active FROM machines WHERE id = %s", (machine_id,)) == (1,)


def test_archive_machine_rejects_staff_and_other_store(db):
    machine_id = db.make_machine()

    with pytest.raises(PermissionDeniedError):
        _machine_service(db, db.staff).archive_machine(
            machine_id,
            db.staff,
        )

    with pytest.raises(PermissionDeniedError):
        _machine_service(db, db.other_manager).archive_machine(
            machine_id,
            db.other_manager,
        )

    assert _fetch_one("SELECT COUNT(*) FROM machines WHERE id = %s", (machine_id,)) == (1,)
