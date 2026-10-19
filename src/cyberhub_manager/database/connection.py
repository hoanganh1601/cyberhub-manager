"""MySQL connection pool for CyberHub Manager."""

import logging
from contextlib import contextmanager
from threading import Lock
from typing import Generator

import mysql.connector
from mysql.connector import Error as MySQLError
from mysql.connector.cursor import MySQLCursor
from mysql.connector.pooling import (
    MySQLConnectionPool,
    PooledMySQLConnection,
)

from cyberhub_manager.config import load_settings

logger = logging.getLogger(__name__)

POOL_NAME = "cyberhub_pool"
POOL_SIZE = 5
CONNECTION_TIMEOUT = 5

_pool: MySQLConnectionPool | None = None
_pool_lock = Lock()


def init_pool() -> MySQLConnectionPool:
    """Khởi tạo pool một lần và trả về pool dùng chung."""
    global _pool

    with _pool_lock:
        if _pool is None:
            settings = load_settings()

            try:
                _pool = MySQLConnectionPool(
                    pool_name=POOL_NAME,
                    pool_size=POOL_SIZE,
                    pool_reset_session=True,
                    host=settings.mysql_host,
                    port=settings.mysql_port,
                    user=settings.mysql_user,
                    password=settings.mysql_password,
                    database=settings.mysql_database,
                    charset="utf8mb4",
                    collation="utf8mb4_0900_ai_ci",
                    time_zone="+00:00",
                    connection_timeout=CONNECTION_TIMEOUT,
                    autocommit=False,
                )
            except MySQLError:
                logger.exception(
                    "Không thể khởi tạo MySQL connection pool."
                )
                raise

            logger.info(
                "Đã khởi tạo pool '%s' với %d kết nối.",
                POOL_NAME,
                POOL_SIZE,
            )

        return _pool


def get_connection() -> PooledMySQLConnection:
    """Mượn một kết nối từ pool dùng chung."""
    pool = init_pool()

    try:
        return pool.get_connection()
    except MySQLError:
        logger.exception(
            "Không thể mượn kết nối từ MySQL connection pool."
        )
        raise

@contextmanager
def get_db_connection() -> Generator[PooledMySQLConnection, None, None]:
    """Context Manager quản lý mượn/trả kết nối và commit/rollback transaction.
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM accounts WHERE id = %s", (account_id,))
            result = cursor.fetchone()
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("Transaction bị hủy (rollback) do phát sinh ngoại lệ: %s", exc)
        raise
    finally:
        # conn.close() đối với PooledMySQLConnection sẽ trả kết nối lại pool, không đóng TCP socket
        conn.close()


@contextmanager
def get_db_cursor(dictionary: bool = True) -> Generator[MySQLCursor, None, None]:
    """Context Manager tiện ích quản lý trực tiếp cursor và kết nối.
    
    Usage:
        with get_db_cursor() as cursor:
            cursor.execute("UPDATE machines SET status = 'IN_USE' WHERE id = %s", (machine_id,))
    """
    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=dictionary)
        try:
            yield cursor
        finally:
            cursor.close()