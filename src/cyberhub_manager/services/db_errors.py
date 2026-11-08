"""LI-10 — Phân loại lỗi MySQL và đổi sang lỗi nghiệp vụ, dùng chung cho mọi service.

- `classify(exc)`: đọc errno để biết lỗi thuộc loại nào (trùng UNIQUE, FK, deadlock, mất kết nối...).
- `translate_db_errors(...)`: context manager bọc transaction; lỗi MySQL ra khỏi khối sẽ thành
  ConflictError (trùng dữ liệu đã khai báo), lỗi do service chỉ định (FK) hoặc ServiceUnavailableError.
  Chi tiết kỹ thuật chỉ nằm trong log, UI chỉ thấy lỗi nghiệp vụ.
- `retry_on_transient`: chạy lại cả thao tác khi MySQL báo deadlock (1213). Mỗi lần chạy là một
  transaction mới vì `transaction()` đã rollback toàn bộ lần trước.
"""

from __future__ import annotations

import functools
import logging
import re
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from enum import Enum
from typing import Final, TypeVar

from mysql.connector import Error as MySQLError
from mysql.connector import errorcode
from mysql.connector.errors import PoolError

from cyberhub_manager.domain.exceptions import (
    ApplicationError,
    ConflictError,
    ServiceUnavailableError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DbErrorKind(str, Enum):
    DUPLICATE = "duplicate"
    FOREIGN_KEY = "foreign_key"
    DEADLOCK = "deadlock"
    LOCK_TIMEOUT = "lock_timeout"
    CONNECTION = "connection"
    OTHER = "other"


_KIND_BY_ERRNO: Final[dict[int, DbErrorKind]] = {
    errorcode.ER_DUP_ENTRY: DbErrorKind.DUPLICATE,  # 1062
    errorcode.ER_NO_REFERENCED_ROW_2: DbErrorKind.FOREIGN_KEY,  # 1452: tham chiếu tới dòng không tồn tại
    errorcode.ER_ROW_IS_REFERENCED_2: DbErrorKind.FOREIGN_KEY,  # 1451: xóa dòng đang được tham chiếu
    errorcode.ER_LOCK_DEADLOCK: DbErrorKind.DEADLOCK,  # 1213
    errorcode.ER_LOCK_WAIT_TIMEOUT: DbErrorKind.LOCK_TIMEOUT,  # 1205
    errorcode.CR_CONNECTION_ERROR: DbErrorKind.CONNECTION,  # 2002
    errorcode.CR_CONN_HOST_ERROR: DbErrorKind.CONNECTION,  # 2003: MySQL không chạy / sai host-port
    errorcode.CR_SERVER_GONE_ERROR: DbErrorKind.CONNECTION,  # 2006
    errorcode.CR_SERVER_LOST: DbErrorKind.CONNECTION,  # 2013
    errorcode.CR_SERVER_LOST_EXTENDED: DbErrorKind.CONNECTION,  # 2055
    errorcode.ER_CON_COUNT_ERROR: DbErrorKind.CONNECTION,  # 1040: quá nhiều kết nối
}

# Chỉ deadlock được chạy lại mặc định: MySQL đã rollback cả transaction và lần sau thường thành công.
# Lock-wait timeout không chạy lại vì người dùng đã chờ innodb_lock_wait_timeout (mặc định 50 giây).
DEFAULT_RETRY_ON: Final[frozenset[DbErrorKind]] = frozenset({DbErrorKind.DEADLOCK})
RETRY_DELAYS: Final[tuple[float, ...]] = (0.05, 0.2)  # tối đa 3 lần chạy

# "Duplicate entry 'x' for key 'customers.uq_customers_phone'" (MySQL 8 có tiền tố tên bảng)
_DUPLICATE_KEY = re.compile(r"for key '(?:[^'.]+\.)?([^']+)'")
# "... CONSTRAINT `fk_account_transactions_employee` FOREIGN KEY ..."
_FOREIGN_KEY = re.compile(r"CONSTRAINT `([^`]+)`")

_sleep = time.sleep  # tách ra để test thay thế, không phải chờ thật


def classify(exc: BaseException) -> DbErrorKind:
    """Loại lỗi theo errno; pool hết kết nối cũng tính là lỗi kết nối."""

    if isinstance(exc, PoolError):
        return DbErrorKind.CONNECTION
    errno = getattr(exc, "errno", None)
    if isinstance(errno, int):
        return _KIND_BY_ERRNO.get(errno, DbErrorKind.OTHER)
    return DbErrorKind.OTHER


def constraint_name(exc: BaseException) -> str | None:
    """Tên UNIQUE key / FK constraint trong thông báo của MySQL, nếu có."""

    message = str(getattr(exc, "msg", None) or exc)
    for pattern in (_DUPLICATE_KEY, _FOREIGN_KEY):
        match = pattern.search(message)
        if match:
            return match.group(1)
    return None


def to_application_error(
    exc: MySQLError,
    *,
    duplicates: Mapping[str, tuple[str, str]] | None = None,
    on_foreign_key: Callable[[], ApplicationError] | None = None,
) -> ApplicationError:
    """Đổi một lỗi MySQL sang lỗi nghiệp vụ và ghi log ở mức phù hợp.

    duplicates: tên UNIQUE key -> (field, message) để UI hiện lỗi ngay dưới ô nhập.
    on_foreign_key: service tự quyết FK hỏng nghĩa là gì (vd. nhân viên không còn -> PermissionDenied).
    """

    kind = classify(exc)
    name = constraint_name(exc)

    if kind is DbErrorKind.DUPLICATE and duplicates and name in duplicates:
        field, message = duplicates[name]
        logger.info("Trùng dữ liệu theo %s", name)
        return ConflictError(message, field_errors={field: message})
    if kind is DbErrorKind.FOREIGN_KEY and on_foreign_key is not None:
        logger.info("Vi phạm khóa ngoại %s", name or "(không rõ tên)")
        return on_foreign_key()

    details: dict[str, object] = {"db_error": kind.value, "errno": getattr(exc, "errno", None)}
    if kind in (DbErrorKind.CONNECTION, DbErrorKind.DEADLOCK, DbErrorKind.LOCK_TIMEOUT):
        # Sự cố vận hành có thể tự hết: một dòng cảnh báo, không cần traceback.
        logger.warning("MySQL tạm thời lỗi (%s, errno=%s): %s", kind.value, details["errno"], exc)
    else:
        # Lỗi không lường trước (sai SQL, thiếu bảng, trùng key chưa khai báo...): cần traceback để sửa.
        logger.error("Lỗi MySQL không mong đợi (errno=%s)", details["errno"], exc_info=exc)
    return ServiceUnavailableError(details=details)


@contextmanager
def translate_db_errors(
    *,
    duplicates: Mapping[str, tuple[str, str]] | None = None,
    on_foreign_key: Callable[[], ApplicationError] | None = None,
) -> Iterator[None]:
    """Bọc ngoài `transaction()`: lỗi nghiệp vụ đi qua nguyên vẹn, lỗi MySQL được đổi kiểu."""

    try:
        yield
    except MySQLError as exc:
        raise to_application_error(exc, duplicates=duplicates, on_foreign_key=on_foreign_key) from exc


def transient_kind(
    exc: BaseException, retry_on: frozenset[DbErrorKind] = DEFAULT_RETRY_ON
) -> DbErrorKind | None:
    """Tìm lỗi MySQL đáng chạy lại trong chính exc hoặc chuỗi `raise ... from` của nó."""

    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, MySQLError):
            kind = classify(current)
            return kind if kind in retry_on else None
        current = current.__cause__
    return None


def retry_on_transient(
    func: Callable[..., T] | None = None,
    *,
    retry_on: frozenset[DbErrorKind] = DEFAULT_RETRY_ON,
    delays: tuple[float, ...] = RETRY_DELAYS,
) -> Callable[..., T] | Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator cho method public của service: chạy lại cả thao tác khi gặp lỗi tạm thời.

    Chỉ dùng cho thao tác mà mỗi lần chạy nằm trọn trong MỘT transaction, để lần chạy lỗi đã
    rollback sạch trước khi chạy lại. Không thêm CONNECTION vào retry_on cho thao tác ghi: mất
    kết nối lúc COMMIT thì không biết dữ liệu đã lưu hay chưa.
    """

    def decorate(target: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(target)
        def wrapper(*args: object, **kwargs: object) -> T:
            total = len(delays) + 1
            for attempt in range(1, total + 1):
                try:
                    return target(*args, **kwargs)
                except Exception as exc:
                    kind = transient_kind(exc, retry_on)
                    if kind is None or attempt == total:
                        raise
                    delay = delays[attempt - 1]
                    logger.warning(
                        "%s gặp %s, chạy lại lần %d/%d sau %.2fs",
                        target.__qualname__, kind.value, attempt + 1, total, delay,
                    )
                    _sleep(delay)
            raise AssertionError("unreachable")  # pragma: no cover

        return wrapper

    return decorate if func is None else decorate(func)
