"""Integration tests for HA-07 repositories."""

import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from cyberhub_manager.repositories.session_repository import SessionRepository
from cyberhub_manager.database import connection
from cyberhub_manager.domain.enums import MachineStatus, MachineArchiveAction, SessionStatus
from cyberhub_manager.repositories.machine_repository import MachineRepository
from cyberhub_manager.domain.exceptions import ConflictError

def test_create_and_get_machine_can_roll_back(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", "cyberhub_manager_migration_test")
    monkeypatch.setattr(connection, "_pool", None)

    conn = connection.get_connection()
    cursor = conn.cursor(buffered=True)
    code = "HA07_" + uuid4().hex[:12].upper()
    repo = MachineRepository()

    try:
        cursor.execute("SELECT DATABASE()")
        assert cursor.fetchone()[0] == "cyberhub_manager_migration_test"

        conn.start_transaction()
        cursor.execute("SELECT store_id FROM machines ORDER BY id LIMIT 1")
        store_id = cursor.fetchone()[0]

        machine_id = repo.create(
            conn,
            code = code,
            store_id = store_id,
            name = "HA07 test machine",
            hourly_rate = 5000,
        )
        machine = repo.get_by_id(conn, machine_id)

        assert machine is not None
        assert machine.code == code
        assert machine.status == MachineStatus.AVAILABLE
        assert machine.is_active is True
        assert machine.updated_at.tzinfo is not None

        conn.rollback()
        cursor.execute("SELECT COUNT(*) FROM machines WHERE code = %s", (code,))
        assert cursor.fetchone()[0] == 0
    finally:
        conn.rollback()
        cursor.close()
        conn.close()
def test_session_creation_adds_history_then_rolls_back(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", "cyberhub_manager_migration_test")
    monkeypatch.setattr(connection, "_pool", None)

    conn = connection.get_connection()
    cursor = conn.cursor(buffered = True)
    code = "HA07S_" + uuid4().hex[:12].upper()
    machine_repo = MachineRepository()

    try:
        cursor.execute("SELECT DATABASE()")
        assert cursor.fetchone()[0] == "cyberhub_manager_migration_test"

        conn.start_transaction()
        cursor.execute(
            "SELECT id, store_id, hourly_rate FROM machines WHERE code = %s",
            ("DEMO_PC_01",),
        )
        machine_id, store_id, hourly_rate = cursor.fetchone()
        cursor.execute(
            "SELECT id FROM customers WHERE code = %s",
            ("DEMO_CUS_01",),
        )
        customer_id = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT id FROM employees
            WHERE store_id = %s AND status = 'ACTIVE'
            ORDER BY id LIMIT 1
            """,
            (store_id,),
        )
        employee_id = cursor.fetchone()[0]

        history_before = machine_repo.has_session_history(conn, machine_id)
        session_id = SessionRepository().create(
            conn,
            code = code,
            customer_id = customer_id,
            machine_id = machine_id,
            opened_by = employee_id,
            started_at = datetime.now(timezone.utc),
            hourly_rate = hourly_rate,
        )
        assert session_id > 0
        assert machine_repo.has_session_history(conn, machine_id)

        conn.rollback()
        cursor.execute(
            "SELECT COUNT(*) FROM usage_sessions WHERE code = %s",
            (code,),
        )
        assert cursor.fetchone()[0] == 0
        assert machine_repo.has_session_history(conn, machine_id) == history_before
    finally:
        conn.rollback()
        cursor.close()
        conn.close()
def test_archive_or_delete_removes_machine_without_history(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", "cyberhub_manager_migration_test")
    monkeypatch.setattr(connection, "_pool", None)

    conn = connection.get_connection()
    cursor = conn.cursor(buffered=True)
    code = "HA07D_" + uuid4().hex[:12].upper()
    repo = MachineRepository()

    try:
        cursor.execute("SELECT DATABASE()")
        assert cursor.fetchone()[0] == "cyberhub_manager_migration_test"

        conn.start_transaction()
        cursor.execute(
            "SELECT store_id FROM machines WHERE code = %s",
            ("DEMO_PC_01",),
        )
        store_id = cursor.fetchone()[0]

        machine_id = repo.create(
            conn,
            code = code,
            store_id = store_id,
            name = "Temporary machine",
            hourly_rate = 5000,
        )
        assert not repo.has_session_history(conn, machine_id)

        action = repo.archive_or_delete(conn, machine_id)
        assert action == MachineArchiveAction.DELETED
        assert repo.get_by_id(conn, machine_id) is None

        conn.rollback()
        cursor.execute(
            "SELECT COUNT(*) FROM machines WHERE code = %s",
            (code,),
        )
        assert cursor.fetchone()[0] == 0
    finally:
        conn.rollback()
        cursor.close()
        conn.close()
def test_archive_or_delete_preserves_machine_with_history(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", "cyberhub_manager_migration_test")
    monkeypatch.setattr(connection, "_pool", None)

    conn = connection.get_connection()
    cursor = conn.cursor(buffered = True)
    session_code = "HA07H_" + uuid4().hex[:12].upper()
    machine_repo = MachineRepository()

    try:
        cursor.execute("SELECT DATABASE()")
        assert cursor.fetchone()[0] == "cyberhub_manager_migration_test"

        conn.start_transaction()
        cursor.execute(
            """
            SELECT id, store_id, hourly_rate
            FROM machines WHERE code = %s
            """,
            ("DEMO_PC_01",),
        )
        machine_id, store_id, hourly_rate = cursor.fetchone()
        cursor.execute(
            "SELECT id FROM customers WHERE code = %s",
            ("DEMO_CUS_01",),
        )
        customer_id = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT id FROM employees
            WHERE store_id = %s AND status = 'ACTIVE'
            ORDER BY id LIMIT 1
            """,
            (store_id,),
        )
        employee_id = cursor.fetchone()[0]

        started_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        session_id = SessionRepository().create(
            conn,
            code = session_code,
            customer_id = customer_id,
            machine_id = machine_id,
            opened_by = employee_id,
            started_at = started_at,
            hourly_rate = hourly_rate,
        )
        cursor.execute(
            """
            UPDATE usage_sessions
            SET status = 'COMPLETED', ended_at = %s,
                cost = %s, closed_by = %s
            WHERE id = %s
            """,
            (
                datetime.now(timezone.utc).replace(tzinfo=None),
                1000,
                employee_id,
                session_id,
            ),
        )

        action = machine_repo.archive_or_delete(conn, machine_id)
        assert action == MachineArchiveAction.ARCHIVED
        archived = machine_repo.get_by_id(conn, machine_id)
        assert archived is not None
        assert archived.is_active is False

        conn.rollback()
        restored = machine_repo.get_by_id(conn, machine_id)
        assert restored is not None
        assert restored.is_active is True
        cursor.execute(
            "SELECT COUNT(*) FROM usage_sessions WHERE code = %s",
            (session_code,),
        )
        assert cursor.fetchone()[0] == 0
    finally:
        conn.rollback()
        cursor.close()
        conn.close()
def test_archive_or_delete_rejects_active_session(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", "cyberhub_manager_migration_test")
    monkeypatch.setattr(connection, "_pool", None)

    conn = connection.get_connection()
    cursor = conn.cursor(buffered=True)
    session_code = "HA07A_" + uuid4().hex[:12].upper()
    machine_repo = MachineRepository()

    try:
        cursor.execute("SELECT DATABASE()")
        assert cursor.fetchone()[0] == "cyberhub_manager_migration_test"

        conn.start_transaction()
        cursor.execute(
            "SELECT id, store_id, hourly_rate FROM machines WHERE code = %s",
            ("DEMO_PC_01",),
        )
        machine_id, store_id, hourly_rate = cursor.fetchone()

        cursor.execute(
            "SELECT id FROM customers WHERE code = %s",
            ("DEMO_CUS_01",),
        )
        customer_id = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT id FROM employees
            WHERE store_id = %s AND status = 'ACTIVE'
            ORDER BY id LIMIT 1
            """,
            (store_id,),
        )
        employee_id = cursor.fetchone()[0]

        SessionRepository().create(
            conn,
            code = session_code,
            customer_id = customer_id,
            machine_id = machine_id,
            opened_by = employee_id,
            started_at = datetime.now(timezone.utc) - timedelta(minutes=2),
            hourly_rate = hourly_rate,
        )

        with pytest.raises(ConflictError):
            machine_repo.archive_or_delete(conn, machine_id)

        machine = machine_repo.get_by_id(conn, machine_id)
        assert machine is not None
        assert machine.is_active is True
    finally:
        conn.rollback()
        cursor.close()
        conn.close()
def test_get_session_by_id_maps_active_and_completed(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", "cyberhub_manager_migration_test")
    monkeypatch.setattr(connection, "_pool", None)

    conn = connection.get_connection()
    cursor = conn.cursor(buffered = True)
    repo = SessionRepository()

    try:
        cursor.execute("SELECT DATABASE()")
        assert cursor.fetchone()[0] == "cyberhub_manager_migration_test"
        conn.start_transaction()

        cursor.execute(
            "SELECT id, store_id, hourly_rate FROM machines WHERE code = %s",
            ("DEMO_PC_01",),
        )
        machine_id, store_id, hourly_rate = cursor.fetchone()
        cursor.execute(
            "SELECT id FROM customers WHERE code = %s",
            ("DEMO_CUS_01",),
        )
        customer_id = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT id FROM employees
            WHERE store_id = %s AND status = 'ACTIVE'
            ORDER BY id LIMIT 1
            """,
            (store_id,),
        )
        employee_id = cursor.fetchone()[0]

        session_id = repo.create(
            conn,
            code = "HA07G_" + uuid4().hex[:12].upper(),
            customer_id = customer_id,
            machine_id = machine_id,
            opened_by = employee_id,
            started_at = datetime.now(timezone.utc) - timedelta(minutes=2),
            hourly_rate = hourly_rate,
        )

        active = repo.get_by_id(conn, session_id, for_update = True)
        assert active is not None
        assert active.status == SessionStatus.ACTIVE
        assert active.started_at.utcoffset() == timedelta(0)
        assert active.ended_at is None
        assert active.cost is None

        active_by_machine = repo.get_active_by_machine(
            conn, machine_id, for_update = True
        )
        assert active_by_machine is not None
        assert active_by_machine.id == session_id

        store_sessions = repo.list_active_by_store(conn, store_id)
        matching = [s for s in store_sessions if s.id == session_id]
        assert len(matching) == 1
        assert matching[0].machine_id == machine_id
        assert matching[0].status == SessionStatus.ACTIVE
        assert repo.list_active_by_store(conn, store_id + 10_000_000) == []

        active_by_customer = repo.get_active_by_customer(
            conn, customer_id, for_update = True
        )
        assert active_by_customer is not None
        assert active_by_customer.id == session_id

        ended_at = datetime.now(timezone.utc)
        cost = active.complete(employee_id, ended_at)
        assert repo.complete(conn, active) is True
        assert repo.complete(conn, active) is False

        completed = repo.get_by_id(conn, session_id)
        assert completed is not None
        assert completed.status == SessionStatus.COMPLETED
        assert completed.ended_at is not None
        assert completed.ended_at.utcoffset() == timedelta(0)
        assert completed.cost == cost
        assert completed.closed_by == employee_id
        assert repo.get_active_by_machine(conn, machine_id) is None
        assert repo.get_active_by_customer(conn, customer_id) is None
        assert all (
            s.id != session_id
            for s in repo.list_active_by_store(conn, store_id)
        )

        conn.rollback()
        cursor.execute(
            "SELECT COUNT(*) FROM usage_sessions WHERE id = %s",
            (session_id,),
        )
        assert cursor.fetchone()[0] == 0

    finally:
        conn.rollback()
        cursor.close()
        conn.close()
def test_machine_list_update_and_maintenance_roll_back(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", "cyberhub_manager_migration_test")
    monkeypatch.setattr(connection, "_pool", None)

    conn = connection.get_connection()
    cursor = conn.cursor(buffered = True)
    repo = MachineRepository()

    try:
        cursor.execute("SELECT DATABASE()")
        assert cursor.fetchone()[0] == "cyberhub_manager_migration_test"
        conn.start_transaction()

        cursor.execute(
            "SELECT id, store_id FROM machines WHERE code = %s",
            ("DEMO_PC_01",),
        )
        machine_id, store_id = cursor.fetchone()
        original = repo.get_by_id(conn, machine_id)
        assert original is not None
        assert any(
            machine.id == machine_id
            for machine in repo.list_by_store(conn, store_id)
        )

        assert repo.update_info(
            conn,
            machine_id,
            name = "HA07 temporary name",
            hourly_rate = original.hourly_rate + 1000,
        )
        updated = repo.get_by_id(conn, machine_id)
        assert updated is not None
        assert updated.name == "HA07 temporary name"
        assert updated.hourly_rate == original.hourly_rate + 1000

        assert repo.set_maintenance(conn, machine_id, enabled=True)
        maintained = repo.get_by_id(conn, machine_id)
        assert maintained is not None
        assert maintained.status == MachineStatus.MAINTENANCE

        conn.rollback()
        restored = repo.get_by_id(conn, machine_id)
        assert restored is not None
        assert restored.name == original.name
        assert restored.hourly_rate == original.hourly_rate
        assert restored.status == original.status
    finally:
        conn.rollback()
        cursor.close()
        conn.close()