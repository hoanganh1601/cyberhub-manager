"""Integration tests for HA-05 authentication repository."""
from uuid import uuid4

import pytest
from cyberhub_manager.database import connection
from cyberhub_manager.domain.enums import Role
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.security import hash_password

@pytest.fixture
def auth_context(monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", "cyberhub_manager_migration_test")
    monkeypatch.setattr(connection, "_pool", None)

    conn = connection.get_connection()
    cursor = conn.cursor()
    token = uuid4().hex[:12]
    username = f"ha05.{token}"
    password_hash = hash_password("temporary-test-password")

    try:
        conn.start_transaction()
        cursor.execute("SELECT DATABASE()")
        assert cursor.fetchone()[0] == "cyberhub_manager_migration_test"

        cursor.execute(
            "INSERT INTO stores (code, name, address) VALUES (%s, %s, %s)",
            (f"ST-{token}", "HA05 Test Store", "Test address"),
        )
        store_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO employees
                (code, store_id, full_name, username, password_hash, role)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                f"EM-{token}",
                store_id,
                "HA05 Test Manager",
                username,
                password_hash,
                "MANAGER",
            ),
        )
        employee_id = cursor.lastrowid

        yield conn, username, store_id, employee_id, password_hash
    finally:
        conn.rollback()
        cursor.close()
        conn.close()

def test_active_employee_is_found_and_unknown_username_is_not(auth_context):
    conn, username, store_id, employee_id, password_hash = auth_context
    repo = AuthRepository()

    record = repo.get_active_by_username(conn, username)

    session = repo.get_active_session_by_id(conn, employee_id)
    assert session is not None
    assert session.employee_id == employee_id
    assert session.store_id == store_id
    assert session.role == Role.MANAGER
    assert not hasattr(session, "password_hash")
    assert repo.get_active_session_by_id(conn, 0) is None

    assert record is not None
    assert record.session.employee_id == employee_id
    assert record.session.store_id == store_id
    assert record.session.role == Role.MANAGER
    assert record.password_hash == password_hash
    assert password_hash not in repr(record)
    assert repo.get_active_by_username(conn, f"missing.{username}") is None

@pytest.mark.parametrize("status", ["INACTIVE", "LOCKED"])
def test_inactive_or_locked_employee_is_not_found(auth_context, status):
    conn, username, store_id, employee_id, _ = auth_context

    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE employees SET status = %s WHERE id = %s",
            (status, employee_id),
        )
        assert cursor.rowcount == 1
    finally:
        cursor.close()

    assert AuthRepository().get_active_by_username(conn, username) is None
    assert AuthRepository().get_active_session_by_id(conn, employee_id) is None

def test_employee_of_inactive_store_is_not_found(auth_context):
    conn, username, store_id, employee_id, _ = auth_context

    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE stores SET status = %s WHERE id = %s",
            ("INACTIVE", store_id),
        )
        assert cursor.rowcount == 1
    finally:
        cursor.close()

    assert AuthRepository().get_active_by_username(conn, username) is None
    assert AuthRepository().get_active_session_by_id(conn, employee_id) is None