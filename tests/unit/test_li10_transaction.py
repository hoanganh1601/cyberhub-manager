"""LI-10 — transaction() rollback đúng và mỗi lỗi chỉ ghi log một lần, ở mức phù hợp (không cần MySQL)."""

from __future__ import annotations

import logging

import pytest
from mysql.connector import errorcode
from mysql.connector.errors import DatabaseError, InterfaceError

from cyberhub_manager.database import transaction as transaction_module
from cyberhub_manager.database.transaction import transaction
from cyberhub_manager.domain.exceptions import (
    AuthenticationError,
    InsufficientBalanceError,
    ServiceUnavailableError,
)
from cyberhub_manager.services.auth_service import AuthService

def server_lost() -> InterfaceError:
    """Mỗi lần một exception mới để traceback của test này không dính sang test khác."""
    return InterfaceError(msg="Lost connection to MySQL server", errno=errorcode.CR_SERVER_LOST)


class FakeConnection:
    def __init__(self, *, rollback_error: Exception | None = None) -> None:
        self.calls: list[str] = []
        self.rollback_error = rollback_error

    def start_transaction(self) -> None:
        self.calls.append("start")

    def commit(self) -> None:
        self.calls.append("commit")

    def rollback(self) -> None:
        self.calls.append("rollback")
        if self.rollback_error is not None:
            raise self.rollback_error

    def close(self) -> None:
        self.calls.append("close")


@pytest.fixture
def conn(monkeypatch: pytest.MonkeyPatch) -> FakeConnection:
    fake = FakeConnection()
    monkeypatch.setattr(transaction_module, "get_connection", lambda: fake)
    return fake


@pytest.fixture
def logs(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    caplog.set_level(logging.DEBUG)
    return caplog


def _noisy(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Bản ghi người vận hành sẽ thấy với LOG_LEVEL=INFO trở lên."""
    return [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_commit_and_return_connection(conn: FakeConnection, logs) -> None:
    with transaction() as current:
        assert current is conn
    assert conn.calls == ["start", "commit", "close"]
    assert _noisy(logs) == []


def test_business_error_rolls_back_silently(conn: FakeConnection, logs) -> None:
    with pytest.raises(InsufficientBalanceError):
        with transaction():
            raise InsufficientBalanceError()
    assert conn.calls == ["start", "rollback", "close"]
    assert _noisy(logs) == []  # trước LI-10: traceback dài cho cả lỗi nghiệp vụ


def test_mysql_error_is_left_for_db_errors_to_log(conn: FakeConnection, logs) -> None:
    with pytest.raises(InterfaceError):
        with transaction():
            raise server_lost()
    assert conn.calls == ["start", "rollback", "close"]
    assert _noisy(logs) == []


def test_unexpected_bug_is_logged_with_traceback(conn: FakeConnection, logs) -> None:
    with pytest.raises(KeyError):
        with transaction():
            raise KeyError("secret_column")
    [record] = _noisy(logs)
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None and "secret_column" in logs.text


def test_failed_rollback_keeps_original_error_and_still_closes(monkeypatch, logs) -> None:
    fake = FakeConnection(rollback_error=server_lost())
    monkeypatch.setattr(transaction_module, "get_connection", lambda: fake)
    deadlock = DatabaseError(msg="Deadlock found", errno=errorcode.ER_LOCK_DEADLOCK)

    with pytest.raises(DatabaseError) as info:
        with transaction():
            raise deadlock
    assert info.value is deadlock  # lỗi rollback không che lỗi gốc
    assert fake.calls == ["start", "rollback", "close"]
    [record] = _noisy(logs)
    assert record.levelno == logging.WARNING and record.exc_info is None


# ----------------------------------------------------------------------
# Từ service đi xuống: mỗi sự cố đúng một dòng log
# ----------------------------------------------------------------------
class _LostConnectionAuthRepo:
    def get_active_by_username(self, conn, username):
        raise server_lost()


class _NoUserAuthRepo:
    def get_active_by_username(self, conn, username):
        return None


def test_mysql_down_during_login_logs_one_warning_without_traceback(conn, logs) -> None:
    with pytest.raises(ServiceUnavailableError):
        AuthService(auth_repo=_LostConnectionAuthRepo()).login("demo.manager", "demo123")
    [record] = _noisy(logs)
    assert record.levelno == logging.WARNING
    assert record.name == "cyberhub_manager.services.db_errors"
    assert all(r.exc_info is None for r in logs.records)


def test_wrong_password_writes_no_warning(conn, logs) -> None:
    with pytest.raises(AuthenticationError):
        AuthService(auth_repo=_NoUserAuthRepo()).login("demo.manager", "sai")
    assert _noisy(logs) == []
