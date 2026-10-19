"""Integration tests for the transaction manager."""

from uuid import uuid4

import pytest

from cyberhub_manager.database import connection
from cyberhub_manager.database.transaction import transaction


def _execute(conn, sql, params=()):
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone() if cursor.with_rows else None


@pytest.fixture
def probe_ids(monkeypatch):
    # Chỉ đổi cấu hình trong phạm vi kiểm thử.
    monkeypatch.setenv("MYSQL_DATABASE", "cyberhub_manager_test")
    monkeypatch.setattr(connection, "_pool", None)

    conn = connection.get_connection()

    try:
        assert _execute(conn, "SELECT DATABASE()") == (
            "cyberhub_manager_test",
        )

        _execute(
            conn,
            """
            CREATE TABLE IF NOT EXISTS ha04_transaction_probe (
                id CHAR(32) PRIMARY KEY,
                amount BIGINT NOT NULL
            ) ENGINE=InnoDB
            """,
        )
    finally:
        conn.close()

    ids = (uuid4().hex, uuid4().hex)

    try:
        yield ids
    finally:
        # Chỉ dọn các dòng do lần kiểm thử này tạo ra.
        with transaction() as conn:
            _execute(
                conn,
                """
                DELETE FROM ha04_transaction_probe
                WHERE id IN (%s, %s)
                """,
                ids,
            )


def _count_rows(ids):
    conn = connection.get_connection()

    try:
        result = _execute(
            conn,
            """
            SELECT COUNT(*)
            FROM ha04_transaction_probe
            WHERE id IN (%s, %s)
            """,
            ids,
        )
        return result[0]
    finally:
        conn.close()


def _insert_rows(conn, ids):
    for row_id in ids:
        _execute(
            conn,
            """
            INSERT INTO ha04_transaction_probe (id, amount)
            VALUES (%s, %s)
            """,
            (row_id, 10000),
        )


def test_success_commits_all_rows(probe_ids):
    with transaction() as conn:
        _insert_rows(conn, probe_ids)

    assert _count_rows(probe_ids) == 2


def test_exception_rolls_back_all_rows(probe_ids):
    with pytest.raises(RuntimeError, match="forced rollback"):
        with transaction() as conn:
            _insert_rows(conn, probe_ids)
            raise RuntimeError("forced rollback")

    assert _count_rows(probe_ids) == 0

def test_transactions_return_connections_to_pool(probe_ids):
    # Chạy nhiều lượt hơn số connection trong pool để phát hiện rò rỉ.
    for _ in range(connection.POOL_SIZE + 1):
        with transaction() as conn:
            assert _execute(conn, "SELECT 1") == (1,)

        with pytest.raises(RuntimeError, match="forced rollback"):
            with transaction() as conn:
                assert _execute(conn, "SELECT 1") == (1,)
                raise RuntimeError("forced rollback")