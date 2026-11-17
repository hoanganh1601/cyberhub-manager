"""Transactional MySQL checks for RBAC scope and customer activation."""

from contextlib import contextmanager
from dataclasses import replace
from uuid import uuid4

import pytest

from cyberhub_manager.domain.exceptions import ConflictError, PermissionDeniedError
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.repositories.customer_email_repository import CustomerEmailRepository
from cyberhub_manager.repositories.management_repository import ManagementRepositoryMixin
from cyberhub_manager.services.access import operating_actor
from cyberhub_manager.services.customer_email_service import CustomerEmailService, token_from_nonce


@pytest.fixture
def same_transaction(db_conn):
    @contextmanager
    def use():
        yield db_conn
    return use


def _one(conn, sql, params=()):
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone()
    finally:
        cursor.close()


def test_counter_registration_never_exposes_password_and_activation_is_one_time(
        db_conn, test_scenario, same_transaction, monkeypatch):
    scenario = test_scenario(db_conn)
    monkeypatch.setenv("CYBERHUB_SECRET_KEY", "integration-test-secret-32-characters-long")
    monkeypatch.setenv("CYBERHUB_RBAC_POLICY", "separated")

    class Counter:
        def _require_actor(self, conn, permission):
            return type("Actor", (), {"employee_id": scenario.employee_id,
                                       "store_id": scenario.store_id})()

    service = CustomerEmailService(Counter(), transaction_factory=same_transaction)
    email = f"test-{uuid4().hex[:12]}@example.test"
    registered = service.register_at_counter("Khách kiểm thử", "09" + str(uuid4().int % 100_000_000).zfill(8),
                                             email, "account." + uuid4().hex[:10])
    account_id = registered["account_id"]
    account = _one(db_conn, "SELECT balance,password_hash,web_login_enabled FROM accounts WHERE id=%s", (account_id,))
    assert account == {"balance": 0, "password_hash": None, "web_login_enabled": 0}
    assert _one(db_conn, "SELECT customer_id FROM customer_store_links WHERE customer_id=%s AND store_id=%s",
                (registered["customer_id"], scenario.store_id))
    token = _one(db_conn, "SELECT nonce,token_hash FROM customer_email_tokens WHERE account_id=%s", (account_id,))
    raw = token_from_nonce(token["nonce"])
    assert raw != token["token_hash"]
    assert service.activate(raw, "secure-pass-123") == {"activated": True}
    with pytest.raises(ConflictError):
        service.activate(raw, "secure-pass-456")
    activated = _one(db_conn, "SELECT balance,web_login_enabled,email_verified_at FROM accounts WHERE id=%s", (account_id,))
    assert activated["balance"] == 0 and activated["web_login_enabled"] == 1
    assert activated["email_verified_at"] is not None
    assert service.request_reset(email) == {"accepted": True}
    reset = _one(db_conn, "SELECT nonce FROM customer_email_tokens WHERE account_id=%s AND purpose='RESET'", (account_id,))
    assert service.reset_password(token_from_nonce(reset["nonce"]), "new-pass-123") == {"reset": True}
    with pytest.raises(ConflictError):
        service.reset_password(token_from_nonce(reset["nonce"]), "new-pass-456")
    assert _one(db_conn, "SELECT balance FROM accounts WHERE id=%s", (account_id,))["balance"] == 0


def test_manager_can_only_switch_to_explicitly_assigned_store(db_conn, test_scenario, monkeypatch):
    scenario = test_scenario(db_conn)
    monkeypatch.setenv("CYBERHUB_RBAC_POLICY", "separated")
    cursor = db_conn.cursor()
    other_code = "S-" + uuid4().hex[:12]
    try:
        cursor.execute("UPDATE employees SET role='MANAGER' WHERE id=%s", (scenario.employee_id,))
        cursor.execute("INSERT INTO stores(code,name,address) VALUES(%s,'Assigned store','Test address')", (other_code,))
        other_store = cursor.lastrowid
    finally:
        cursor.close()
    auth = AuthRepository()
    current = auth.get_active_session_by_id(db_conn, scenario.employee_id)
    target = replace(current, store_id=other_store)
    with pytest.raises(PermissionDeniedError):
        operating_actor(db_conn, auth, target)
    repo = ManagementRepositoryMixin()
    repo.set_store_assignment(db_conn, scenario.employee_id, other_store, scenario.employee_id, True)
    assert operating_actor(db_conn, auth, target).store_id == other_store
    repo.set_store_assignment(db_conn, scenario.employee_id, other_store, scenario.employee_id, False)
    with pytest.raises(PermissionDeniedError):
        operating_actor(db_conn, auth, target)
