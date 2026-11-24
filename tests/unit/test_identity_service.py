from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.exceptions import PermissionDeniedError
from cyberhub_manager.application.services.identity_service import IdentityService


def actor(*, role=Role.MANAGER, store_id=1, auth_version=3):
    return EmployeeSession(
        7,
        "NV-07",
        "Test User",
        "test.user",
        store_id,
        f"STORE-{store_id}",
        f"Store {store_id}",
        role,
        auth_version,
    )


class AuthRepo:
    def __init__(self, current):
        self.current = current

    def get_active_session_by_id(self, conn, employee_id):
        assert conn is CONNECTION
        return self.current if employee_id == self.current.employee_id else None


class StoreRepo:
    def __init__(self, stores, assignments=()):
        self.stores = stores
        self.assignments = set(assignments)

    def store(self, conn, store_id, lock=False):
        assert conn is CONNECTION
        assert lock == "share"
        return self.stores.get(store_id)

    def assigned_store_ids(self, conn, employee_id):
        assert conn is CONNECTION
        assert employee_id == 7
        return self.assignments


CONNECTION = object()


@contextmanager
def transaction():
    yield CONNECTION


def service(current, stores=None, assignments=()):
    return IdentityService(
        auth_repo=AuthRepo(current),
        store_repo=StoreRepo(stores or {}, assignments),
        transaction_factory=transaction,
    )


def test_resolve_returns_current_active_employee():
    current = actor()
    assert service(current).resolve(7, 3, 1) == current


@pytest.mark.parametrize(
    "employee_id,auth_version,store_id",
    [("7", 3, 1), (7, 3, "1"), (None, 3, 1), (0, 3, 1), (7, -1, 1)],
)
def test_resolve_rejects_invalid_session_identifiers(employee_id, auth_version, store_id):
    assert service(actor()).resolve(employee_id, auth_version, store_id) is None


def test_resolve_rejects_boolean_auth_version():
    assert service(actor(auth_version=1)).resolve(7, True, 1) is None


def test_resolve_rejects_stale_auth_version():
    assert service(actor()).resolve(7, 2, 1) is None


def test_admin_can_switch_to_an_active_store():
    current = actor(role=Role.ADMIN)
    stores = {2: SimpleNamespace(id=2, code="STORE-2", name="Store 2", status="ACTIVE")}
    resolved = service(current, stores).resolve(7, 3, 2)
    assert resolved.store_id == 2
    assert resolved.store_code == "STORE-2"


def test_non_admin_cannot_switch_store():
    with pytest.raises(PermissionDeniedError):
        service(actor(role=Role.MANAGER)).resolve(7, 3, 2)


def test_manager_can_switch_only_to_an_explicitly_assigned_store():
    stores = {2: SimpleNamespace(id=2, code="STORE-2", name="Store 2", status="ACTIVE")}
    resolved = service(actor(role=Role.MANAGER), stores, assignments={2}).resolve(7, 3, 2)
    assert resolved.store_id == 2
