"""LI-03 — Unit test cho AuthService, dùng repository giả nên không cần MySQL."""

from contextlib import contextmanager

import pytest
from mysql.connector.errors import InterfaceError

from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.exceptions import (
    AuthenticationError,
    ServiceUnavailableError,
)
from cyberhub_manager.repositories.auth_repository import AuthRecord
from cyberhub_manager.security import hash_password
from cyberhub_manager.services.auth_service import AuthService
from cyberhub_manager.services.contracts import AuthServiceProtocol

USERNAME = "staff01"
PASSWORD = "secret123"
# bcrypt chậm có chủ đích nên chỉ hash một lần cho cả file.
PASSWORD_HASH = hash_password(PASSWORD)

SESSION = EmployeeSession(
    employee_id=1,
    employee_code="NV001",
    full_name="Nhân viên test",
    username=USERNAME,
    store_id=1,
    store_code="CH001",
    store_name="Cửa hàng test",
    role=Role.STAFF,
)


# ----- Đồ giả ----------------------------------------------------------------


class FakeAuthRepository:
    def __init__(self, record=None, error=None):
        self.record = record
        self.error = error
        self.usernames = []

    def get_active_by_username(self, conn, username):
        self.usernames.append(username)
        if self.error is not None:
            raise self.error
        if self.record is not None and self.record.session.username == username:
            return self.record
        return None


class FakeTransaction:
    def __init__(self):
        self.calls = 0

    @contextmanager
    def __call__(self):
        self.calls += 1
        yield object()


def build_auth(record=None, error=None):
    repo = FakeAuthRepository(record=record, error=error)
    tx = FakeTransaction()
    return AuthService(auth_repo=repo, transaction_factory=tx), repo, tx


@pytest.fixture
def auth():
    return build_auth(AuthRecord(session=SESSION, password_hash=PASSWORD_HASH))


# ----- Test ------------------------------------------------------------------


def test_auth_service_matches_protocol():
    assert isinstance(AuthService(), AuthServiceProtocol)


def test_login_returns_employee_session(auth):
    service, _repo, _tx = auth

    session = service.login(USERNAME, PASSWORD)

    assert session == SESSION
    assert not hasattr(session, "password_hash")


def test_login_trims_username(auth):
    service, repo, _tx = auth

    assert service.login(f"  {USERNAME}  ", PASSWORD) == SESSION
    assert repo.usernames == [USERNAME]


def test_login_does_not_trim_password(auth):
    service, _repo, _tx = auth

    with pytest.raises(AuthenticationError):
        service.login(USERNAME, f" {PASSWORD} ")


def test_login_rejects_wrong_password(auth):
    service, _repo, _tx = auth

    with pytest.raises(AuthenticationError):
        service.login(USERNAME, "wrong-password")


def test_login_rejects_unknown_or_inactive_employee(auth):
    # Repository trả None cho cả username không tồn tại lẫn nhân viên/cửa hàng không ACTIVE.
    service, _repo, _tx = auth

    with pytest.raises(AuthenticationError):
        service.login("nobody", PASSWORD)


@pytest.mark.parametrize(
    "username, password",
    [("", PASSWORD), ("   ", PASSWORD), (USERNAME, ""), (None, PASSWORD), (USERNAME, None)],
)
def test_login_rejects_blank_input_without_touching_database(auth, username, password):
    service, _repo, tx = auth

    with pytest.raises(AuthenticationError):
        service.login(username, password)

    assert tx.calls == 0


def test_login_errors_share_one_message(auth):
    service, _repo, _tx = auth
    errors = []
    for username, password in [(USERNAME, "wrong-password"), ("nobody", PASSWORD), ("", "")]:
        with pytest.raises(AuthenticationError) as exc_info:
            service.login(username, password)
        errors.append((exc_info.value.code, exc_info.value.message))

    assert len(set(errors)) == 1
    assert errors[0][0] == "AUTH_INVALID_CREDENTIALS"


def test_login_maps_database_error_to_service_unavailable():
    service, _repo, _tx = build_auth(error=InterfaceError(msg="mất kết nối"))

    with pytest.raises(ServiceUnavailableError):
        service.login(USERNAME, PASSWORD)
