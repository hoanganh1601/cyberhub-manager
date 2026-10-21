"""Transaction boundary helpers for CyberHub Manager."""

import logging 
from collections.abc import Iterator
from contextlib import contextmanager

from mysql.connector.pooling import PooledMySQLConnection
from cyberhub_manager.database.connection import get_connection


logger = logging.getLogger(__name__)

@contextmanager
def transaction() -> Iterator[PooledMySQLConnection]:
    """Dùng một connection cho toàn bộ transaction."""
    conn = get_connection()
    
    try:
        conn.start_transaction()
        yield conn
        conn.commit()
    except BaseException:
        logger.exception("Giao dịch gặp lỗi; thực hiện roolback.")
        try:
            conn.rollback()
        except Exception:
            logger.exception("Không thể rollback giao dịch.")
        raise
    finally:
        try:
            conn.close()
        except Exception:
            logger.exception("Không thể trả connection về pool")