"""LI-09 — Kiểm tra chính bộ test harness trong tests/conftest.py.

Các test này chứng minh integration test chỉ chạy trên cyberhub_manager_test và
không thể vô tình trỏ sang database development.
"""

import pytest

from cyberhub_manager.database import connection
from cyberhub_manager.database.transaction import transaction

TEST_DATABASE = "cyberhub_manager_test"
REFUSED = "Refusing to run integration tests outside cyberhub_manager_test"


def _scalar(conn, sql, params=()):
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        return cursor.fetchone()[0]
    finally:
        cursor.close()


def test_integration_tests_run_on_test_database(db_conn):
    assert _scalar(db_conn, "SELECT DATABASE()") == TEST_DATABASE


def test_transaction_manager_uses_test_database():
    with transaction() as conn:
        assert _scalar(conn, "SELECT DATABASE()") == TEST_DATABASE


@pytest.mark.parametrize(
    "database",
    [
        "cyberhub_manager",  # database development
        "cyberhub_manager_migration_test",  # có hậu tố _test nhưng không được chốt
        "cyberhub_manager_test2",
    ],
)
def test_pool_refuses_any_other_database(monkeypatch, database):
    monkeypatch.setenv("MYSQL_DATABASE", database)
    monkeypatch.setattr(connection, "_pool", None)

    with pytest.raises(RuntimeError, match=REFUSED):
        connection.get_connection()
    with pytest.raises(RuntimeError, match=REFUSED):
        with transaction():
            pass
    assert connection._pool is None


def test_db_conn_changes_stay_inside_its_transaction(db_conn, test_scenario):
    rows = test_scenario(db_conn)
    sql = "SELECT COUNT(*) FROM stores WHERE id = %s"

    assert _scalar(db_conn, sql, (rows.store_id,)) == 1
    # Connection khác không thấy dữ liệu chưa commit.
    with transaction() as other:
        assert _scalar(other, sql, (rows.store_id,)) == 0


def test_test_scenario_creates_unique_rows(db_conn, test_scenario):
    first, second = test_scenario(db_conn), test_scenario(db_conn)

    assert first.token != second.token
    assert first.store_id != second.store_id
    assert first.machine_id != second.machine_id
    assert first.customer_id != second.customer_id
