"""Transaction boundary helpers for CyberHub Manager.

LI-10: `transaction()` chỉ lo commit / rollback / trả connection; mỗi lỗi chỉ được ghi log MỘT lần,
ở tầng hiểu nó nhất:
- Lỗi nghiệp vụ (ApplicationError: sai mật khẩu, không đủ số dư...) là kết quả bình thường: không log.
- Lỗi MySQL: services/db_errors ghi log đúng mức (warning cho sự cố vận hành, error cho lỗi lạ).
- Lỗi khác (bug Python): ghi traceback tại đây để không bị nuốt mất.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from mysql.connector import Error as MySQLError
from mysql.connector.pooling import PooledMySQLConnection

from cyberhub_manager.database.connection import get_connection
from cyberhub_manager.domain.exceptions import ApplicationError

logger = logging.getLogger(__name__)


@contextmanager
def transaction() -> Iterator[PooledMySQLConnection]:
    """Dùng một connection cho toàn bộ transaction; lỗi thì rollback rồi ném lại nguyên vẹn."""
    conn = get_connection()

    try:
        conn.start_transaction()
        yield conn
        conn.commit()
    except BaseException as exc:
        _log_failure(exc)
        _rollback(conn)
        raise
    finally:
        try:
            conn.close()
        except Exception as close_error:  # noqa: BLE001 — trả pool lỗi không được che lỗi gốc
            logger.warning("Không thể trả connection về pool: %s", close_error)


def _log_failure(exc: BaseException) -> None:
    if isinstance(exc, ApplicationError):
        logger.debug("Rollback do lỗi nghiệp vụ %s", exc.code)
    elif isinstance(exc, MySQLError):
        logger.debug("Rollback do lỗi MySQL errno=%s", exc.errno)
    elif isinstance(exc, Exception):
        logger.error("Giao dịch gặp lỗi không mong đợi; thực hiện rollback.", exc_info=exc)
    # KeyboardInterrupt / SystemExit: chỉ rollback, không log.


def _rollback(conn: PooledMySQLConnection) -> None:
    try:
        conn.rollback()
    except Exception as rollback_error:  # noqa: BLE001 — giữ lỗi gốc cho tầng trên
        # Thường do đã mất kết nối; khi đó MySQL tự hủy transaction chưa commit.
        logger.warning("Không thể rollback giao dịch: %s", rollback_error)
