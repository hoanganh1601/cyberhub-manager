"""LI-09 — Linh: cấu hình và fixture dùng chung cho automated test.

- tests/unit: không cần MySQL; conftest không đụng tới database.
- tests/integration: luôn chạy trên cyberhub_manager_test. Trước mỗi test,
  conftest ép MYSQL_DATABASE, reset connection pool và chỉ cho tạo pool trỏ
  vào đúng database này. MySQL chưa chạy hoặc chưa migrate thì test báo lỗi
  kèm hướng dẫn; không bao giờ chuyển sang database development.

Không seed dữ liệu demo: test tự tạo dữ liệu với mã duy nhất (uuid4).
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

_ROOT = str(Path(__file__).resolve().parent.parent)
_SRC = str(Path(__file__).resolve().parent.parent / "src")
_TESTS = str(Path(__file__).resolve().parent)
for _p in (_ROOT, _SRC, _TESTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from mysql.connector import Error as MySQLError

from cyberhub_manager.config import load_settings
from cyberhub_manager.database import connection

TEST_DATABASE = "cyberhub_manager_test"
INTEGRATION_DIR = Path(__file__).resolve().parent / "integration"

WRONG_DATABASE_MESSAGE = (
    "Refusing to run integration tests outside cyberhub_manager_test"
)
UNAVAILABLE_MESSAGE = """\
MySQL test database is unavailable.
Run:
  docker compose up -d mysql
  python scripts/prepare_test_db.py"""
NOT_MIGRATED_MESSAGE = """\
cyberhub_manager_test has no schema yet (migrations not applied).
Run:
  python scripts/prepare_test_db.py"""

# Bảng phải có sau khi chạy migration; thiếu là chưa chuẩn bị database test.
_REQUIRED_TABLES = ("schema_migrations", "invoices")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: cần MySQL cyberhub_manager_test (tự gắn cho tests/integration)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    for item in items:
        if INTEGRATION_DIR in Path(str(item.fspath)).resolve().parents:
            item.add_marker(pytest.mark.integration)


def require_test_database(conn: Any) -> None:
    """Dừng ngay nếu connection không trỏ vào đúng cyberhub_manager_test."""

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DATABASE()")
        (current,) = cursor.fetchone()
    finally:
        cursor.close()
    if current != TEST_DATABASE:
        raise RuntimeError(WRONG_DATABASE_MESSAGE)


def _guarded_load_settings():
    """Pool chỉ được tạo cho cyberhub_manager_test, kể cả khi test đổi env."""

    settings = load_settings()
    if settings.mysql_database != TEST_DATABASE:
        raise RuntimeError(WRONG_DATABASE_MESSAGE)
    return settings


def _point_to_test_database(patch: pytest.MonkeyPatch) -> None:
    patch.setenv("MYSQL_DATABASE", TEST_DATABASE)
    # Pool cũ có thể đang trỏ vào database khác hoặc giữ kết nối của test trước.
    patch.setattr(connection, "_pool", None)
    patch.setattr(connection, "load_settings", _guarded_load_settings)


@pytest.fixture(scope="session")
def test_database_ready() -> None:
    """Kiểm tra một lần mỗi phiên pytest: MySQL chạy, đúng database, đã migrate."""

    with pytest.MonkeyPatch.context() as patch:
        _point_to_test_database(patch)
        # connection.py ghi traceback khi không kết nối được; ở đây chỉ cần hướng dẫn.
        logging.disable(logging.CRITICAL)
        try:
            conn = connection.get_connection()
        except MySQLError:
            conn = None
        finally:
            logging.disable(logging.NOTSET)
        if conn is None:
            pytest.fail(UNAVAILABLE_MESSAGE, pytrace=False)
        try:
            require_test_database(conn)
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = DATABASE() AND table_name IN (%s, %s)
                    """,
                    _REQUIRED_TABLES,
                )
                (found,) = cursor.fetchone()
            finally:
                cursor.close()
        finally:
            conn.close()
    if found != len(_REQUIRED_TABLES):
        pytest.fail(NOT_MIGRATED_MESSAGE, pytrace=False)


@pytest.fixture(autouse=True)
def _integration_database(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mọi integration test dùng cyberhub_manager_test với pool mới."""

    if request.node.get_closest_marker("integration") is None:
        return
    request.getfixturevalue("test_database_ready")
    _point_to_test_database(monkeypatch)


@pytest.fixture
def db_conn() -> Iterator[Any]:
    """Connection trong một transaction, luôn rollback sau test.

    Dùng cho test repository không cần commit thật. Cursor do test tự mở phải
    được đóng; connection luôn được trả về pool kể cả khi assert thất bại.
    """

    conn = connection.get_connection()
    try:
        require_test_database(conn)
        conn.start_transaction()
        yield conn
    finally:
        conn.rollback()
        conn.close()


def _insert(conn: Any, sql: str, params: tuple) -> int:
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        return int(cursor.lastrowid)
    finally:
        cursor.close()


@pytest.fixture
def test_scenario() -> Callable[..., SimpleNamespace]:
    """Tạo store, nhân viên, khách, account và máy riêng cho test trên `conn`.

    Mọi mã đều duy nhất (TEST-...-token) nên không đụng dữ liệu khác. Dữ liệu
    nằm trong transaction của `conn`: rollback là dọn sạch.
    """

    def make(conn: Any, *, hourly_rate: int = 5_000) -> SimpleNamespace:
        require_test_database(conn)
        token = uuid4().hex[:8]
        store_id = _insert(
            conn,
            "INSERT INTO stores (code, name, address) VALUES (%s, %s, %s)",
            (f"TEST-ST-{token}", "Test store", "Test address"),
        )
        employee_id = _insert(
            conn,
            """
            INSERT INTO employees
                (code, store_id, full_name, username, password_hash, role)
            VALUES (%s, %s, %s, %s, 'x', 'STAFF')
            """,
            (f"TEST-EMP-{token}", store_id, "Test employee", f"test.e.{token}"),
        )
        customer_id = _insert(
            conn,
            "INSERT INTO customers (code, full_name, phone) VALUES (%s, %s, %s)",
            (
                f"TEST-CUS-{token}",
                "Test customer",
                "02" + str(uuid4().int % 100_000_000).zfill(8),
            ),
        )
        account_id = _insert(
            conn,
            """
            INSERT INTO accounts (code, customer_id, username, password_hash)
            VALUES (%s, %s, %s, 'x')
            """,
            (f"TEST-ACC-{token}", customer_id, f"test.c.{token}"),
        )
        machine_id = _insert(
            conn,
            """
            INSERT INTO machines (code, store_id, name, hourly_rate)
            VALUES (%s, %s, %s, %s)
            """,
            (f"TEST-PC-{token}", store_id, "Test machine", hourly_rate),
        )
        return SimpleNamespace(
            token=token,
            store_id=store_id,
            employee_id=employee_id,
            customer_id=customer_id,
            account_id=account_id,
            machine_id=machine_id,
            hourly_rate=hourly_rate,
        )

    return make


_SHARED_TK_ROOT = None


def get_shared_tk_root():
    """Retrieve or lazily create the shared root without destroying it."""
    global _SHARED_TK_ROOT
    import os
    import sys
    import customtkinter as ctk


    root = getattr(ctk, "_SHARED_TEST_ROOT", None)
    if root is not None:
        try:
            if root.winfo_exists():
                _SHARED_TK_ROOT = root
                return root
        except Exception:
            pass

    if _SHARED_TK_ROOT is not None:
        try:
            if _SHARED_TK_ROOT.winfo_exists():
                ctk._SHARED_TEST_ROOT = _SHARED_TK_ROOT
                return _SHARED_TK_ROOT
        except Exception:
            pass

    try:
        ctk.CTk._windows_set_titlebar_color = lambda self, color: None
        ctk.CTkToplevel._windows_set_titlebar_color = lambda self, color: None
    except Exception:
        pass

    _SHARED_TK_ROOT = ctk.CTk()
    _SHARED_TK_ROOT.geometry("1280x720")
    _SHARED_TK_ROOT.withdraw()
    ctk._SHARED_TEST_ROOT = _SHARED_TK_ROOT
    return _SHARED_TK_ROOT


@pytest.fixture(scope="session")
def tk_root():
    """Single session-scoped CTk root for all UI unit tests on Windows."""
    root = get_shared_tk_root()
    yield root
    # Không destroy root giữa các fixture để tránh lỗi Tcl re-init trên Windows



@pytest.fixture(autouse=True)
def _cleanup_tk_widgets():
    """Cleanup child widgets from the shared root after each test."""
    yield
    if _SHARED_TK_ROOT is not None:
        for child in list(_SHARED_TK_ROOT.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

