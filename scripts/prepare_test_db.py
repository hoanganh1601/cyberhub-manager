"""LI-09 — Linh: chuẩn bị database cyberhub_manager_test cho automated test.

Chạy từ thư mục gốc repository, sau khi MySQL ở trạng thái healthy:

    python scripts/prepare_test_db.py

Script đọc MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD từ environment
hoặc .env, luôn nhắm vào cyberhub_manager_test, tạo database nếu chưa có rồi
áp dụng migration theo thứ tự. Chạy lại nhiều lần an toàn: migration đã áp dụng
được bỏ qua. Script không seed dữ liệu DEMO_* và không reset dữ liệu.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

import mysql.connector
from mysql.connector import Error as MySQLError
from mysql.connector import errorcode

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE = "cyberhub_manager_test"
# Đối chiếu đúng tên đã chốt, không chấp nhận mọi tên có hậu tố _test.
ALLOWED_DATABASES = frozenset({TEST_DATABASE})

UNAVAILABLE_MESSAGE = """\
MySQL test database is unavailable.
Run:
  docker compose up -d mysql
  docker compose ps        (wait until the container is healthy)
  python scripts/prepare_test_db.py"""

NO_PRIVILEGE_MESSAGE = """\
User '{user}' cannot create database '{database}'.
Create it once with the MySQL root account, then run this script again:
  docker compose exec mysql mysql -uroot -p
  CREATE DATABASE IF NOT EXISTS {database}
      CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
  GRANT ALL PRIVILEGES ON {database}.* TO '{user}'@'%';
  python scripts/prepare_test_db.py"""

# Lỗi kết nối: server chưa chạy hoặc sai host/port.
_CONNECTION_ERRORS = frozenset(
    {errorcode.CR_CONN_HOST_ERROR, errorcode.CR_CONNECTION_ERROR}
)
# Lỗi quyền khi CREATE DATABASE hoặc khi mở database.
_PRIVILEGE_ERRORS = frozenset(
    {errorcode.ER_DBACCESS_DENIED_ERROR, errorcode.ER_ACCESS_DENIED_ERROR}
)


EXIT_FAILED = 1
EXIT_REFUSED = 2


class PrepareError(RuntimeError):
    """Lỗi đã có thông báo rõ ràng cho người chạy script."""

    def __init__(self, message: str, exit_code: int = EXIT_FAILED) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def require_test_database(database: str) -> str:
    if database not in ALLOWED_DATABASES:
        raise PrepareError(
            f"Refusing to prepare database {database!r}: "
            f"only {TEST_DATABASE} is allowed.",
            EXIT_REFUSED,
        )
    return database


def _connect(settings, database: str | None = None):
    options = {
        "host": settings.mysql_host,
        "port": settings.mysql_port,
        "user": settings.mysql_user,
        "password": settings.mysql_password,
        "charset": "utf8mb4",
        "collation": "utf8mb4_0900_ai_ci",
        "connection_timeout": 5,
    }
    if database is not None:
        options["database"] = database
    return mysql.connector.connect(**options)


def _can_open(settings, database: str) -> bool:
    try:
        _connect(settings, database).close()
    except MySQLError:
        return False
    return True


def create_database_if_missing(settings, database: str) -> None:
    require_test_database(database)
    try:
        conn = _connect(settings)
    except MySQLError as exc:
        if exc.errno in _CONNECTION_ERRORS:
            raise PrepareError(UNAVAILABLE_MESSAGE) from exc
        raise

    try:
        cursor = conn.cursor()
        try:
            # Tên database đã qua allowlist nên ghép vào câu lệnh là an toàn.
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
        finally:
            cursor.close()
    except MySQLError as exc:
        if exc.errno not in _PRIVILEGE_ERRORS:
            raise
        # Không có quyền CREATE nhưng database đã được tạo sẵn và cấp quyền.
        if not _can_open(settings, database):
            message = NO_PRIVILEGE_MESSAGE.format(
                user=settings.mysql_user, database=database
            )
            raise PrepareError(message) from exc
    finally:
        conn.close()


def run_test_migrations(database: str) -> None:
    require_test_database(database)
    from cyberhub_manager.database import connection

    os.environ["MYSQL_DATABASE"] = database
    # Pool cũ có thể đang trỏ vào database khác.
    connection._pool = None

    conn = connection.get_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT DATABASE()")
            (current,) = cursor.fetchone()
        finally:
            cursor.close()
    finally:
        conn.close()
    if current != database:
        raise PrepareError(
            f"Refusing to run migrations on {current!r}; expected {database}.",
            EXIT_REFUSED,
        )

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from scripts.init_db import run_migrations

    run_migrations()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--database",
        default=TEST_DATABASE,
        help=f"database cần chuẩn bị; chỉ chấp nhận {TEST_DATABASE}",
    )
    args = parser.parse_args(argv)
    database = args.database

    try:
        require_test_database(database)
        # load_settings bắt buộc có MYSQL_DATABASE; luôn trỏ vào database test.
        os.environ["MYSQL_DATABASE"] = database
        from cyberhub_manager.config import load_settings

        settings = load_settings()
        print(
            f"MySQL: {settings.mysql_host}:{settings.mysql_port} "
            f"(user {settings.mysql_user})"
        )
        print(f"Target database: {database}")
        create_database_if_missing(settings, database)
        run_test_migrations(database)
    except PrepareError as exc:
        print(exc, file=sys.stderr)
        return exc.exit_code
    except MySQLError as exc:
        if exc.errno in _CONNECTION_ERRORS:
            print(UNAVAILABLE_MESSAGE, file=sys.stderr)
        else:
            print(f"MySQL error while preparing {database}: {exc}", file=sys.stderr)
        return EXIT_FAILED
    except RuntimeError as exc:
        # Thiếu biến môi trường hoặc migration lỗi (scripts/init_db.py).
        print(exc, file=sys.stderr)
        return EXIT_FAILED

    print(f"Test database {database} is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
