"""Cutover policy: HTTP guards and business/credential boundaries in demo mode."""

import pytest

from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.exceptions import PermissionDeniedError
from cyberhub_manager.domain.p1 import Permission, can
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.web import create_app
from cyberhub_manager.ui.navigation import NavKey, visible_nav_items


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("CYBERHUB_RBAC_POLICY", "separated")
    return create_app({"TESTING": True, "WEB_MODE": "demo", "ASSISTANT_ENABLED": False,
                       "SECRET_KEY": "rbac-test-secret"})


def login(app, username):
    client = app.test_client()
    csrf = client.get("/api/session").json["csrf_token"]
    response = client.post("/api/login", json={"username": username, "password": "demo123"},
                           headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200, response.json
    return client, response.json["csrf_token"], response.json


def send(client, method, path, csrf, body=None):
    return client.open(path, method=method, json=body or {}, headers={"X-CSRF-Token": csrf})


def test_matrix_does_not_inherit_business_grants(app):
    assert can(Role.ADMIN, Permission.MANAGE_EMPLOYEE_CREDENTIALS)
    for permission in (Permission.VIEW_REVENUE, Permission.MANAGE_MACHINES,
                       Permission.OPERATE_WALLET, Permission.MANAGE_PROMOTIONS,
                       Permission.SWITCH_STORE):
        assert not can(Role.ADMIN, permission)
    assert can(Role.DIRECTOR, Permission.VIEW_REVENUE)
    assert not can(Role.DIRECTOR, Permission.MANAGE_EMPLOYEE_CREDENTIALS)
    assert not can(Role.DIRECTOR, Permission.POS_COLLECT_PAYMENT)
    assert {item.key for item in visible_nav_items(Role.ADMIN)} == {NavKey.EMPLOYEES}
    director_pages = {item.key for item in visible_nav_items(Role.DIRECTOR)}
    assert NavKey.REPORTS in director_pages and NavKey.MACHINES not in director_pages


def test_admin_only_reaches_account_apis(app):
    client, csrf, data = login(app, "admin01")
    assert data["permissions"] == ["manage_employee_credentials"]
    assert client.get("/api/employees").status_code == 200
    for path in ("/api/revenue", "/api/forecasting", "/api/customers", "/api/machines",
                 "/api/promotions", "/api/menu/orders", "/api/assistant/messages"):
        assert client.get(path).status_code == 403, path
    assert send(client, "POST", "/api/machines", csrf,
                {"code": "PC99", "name": "PC 99", "hourly_rate": 10_000}).status_code == 403


def test_director_can_view_business_but_cannot_manage_credentials(app):
    client, csrf, data = login(app, "giamdoc01")
    assert "view_revenue" in data["permissions"]
    assert client.get("/api/revenue").status_code == 200
    assert client.get("/api/customers/1").status_code == 200
    for path in ("/api/vouchers", "/api/games", "/api/ads"):
        assert client.get(path).status_code == 200, path
    assert client.get("/api/employees").status_code == 200
    target = next(e for e in client.get("/api/employees").json if e["role"] == "STAFF")
    assert send(client, "POST", f"/api/employees/{target['id']}/reset-password", csrf,
                {"temporary_password": "temporary123", "confirm_password": "temporary123"}).status_code == 403
    changed = dict(store_id=target["store_id"], full_name="Updated Staff", username=target["username"],
                   role="DIRECTOR", status=target["status"])
    assert send(client, "PATCH", f"/api/employees/{target['id']}", csrf, changed).status_code == 403
    changed["role"] = target["role"]
    assert send(client, "PATCH", f"/api/employees/{target['id']}", csrf, changed).status_code == 200


def test_director_store_scope_and_manager_cannot_switch(app):
    director, csrf, _ = login(app, "giamdoc01")
    created = send(director, "POST", "/api/stores", csrf,
                   {"code": "RBAC02", "name": "Second store", "address": "Hanoi"})
    assert created.status_code == 200, created.json
    second = created.json["id"]
    switched = send(director, "POST", "/api/store/switch", csrf, {"store_id": second})
    assert switched.status_code == 200
    assert switched.json["actor"]["store_id"] == second
    manager, manager_csrf, _ = login(app, "quanly01")
    assert send(manager, "POST", "/api/store/switch", manager_csrf,
                {"store_id": second}).status_code == 403


def test_manager_cannot_provision_or_promote_staff(app):
    client, csrf, _ = login(app, "quanly01")
    employee = next(e for e in client.get("/api/employees").json if e["role"] == "STAFF")
    body = dict(store_id=employee["store_id"], full_name="Test Employee", username=employee["username"],
                role="STAFF", status="ACTIVE")
    assert send(client, "POST", "/api/employees", csrf,
                dict(body, username="another.employee", password="temporary123")).status_code == 403
    assert send(client, "PATCH", f"/api/employees/{employee['id']}", csrf,
                dict(body, role="MANAGER")).status_code == 403


def test_role_change_revokes_existing_session(app):
    services = build_mock_services(p1=True)
    admin = services.auth.login("admin01", "demo123")
    staff = services.auth.login("nhanvien01", "demo123")
    row = next(e for e in services.management.list_employees(admin) if e.id == staff.employee_id)
    services.management.save_employee(admin, row.id, row.store_id, row.full_name,
                                      row.username, "MANAGER", row.status)
    with pytest.raises(PermissionDeniedError):
        services.management.validate_actor(staff)


def test_personnel_profile_provisioning_and_manager_store_assignment(monkeypatch):
    """Desktop and Web share this staged HR -> identity -> store-access workflow."""

    monkeypatch.setenv("CYBERHUB_RBAC_POLICY", "separated")
    services = build_mock_services(p1=True)
    director = services.auth.login("giamdoc01", "demo123")
    admin = services.auth.login("admin01", "demo123")
    manager = services.auth.login("quanly01", "demo123")

    other_store = services.management.save_store(
        director, None, "RBAC-02", "CyberHub Secondary", "Hanoi", "ACTIVE"
    )
    profile = services.management.save_employee_profile(
        director, None, other_store.id, "New Inventory Employee"
    )
    assert profile["employee_id"] is None

    identity = services.management.save_employee(
        admin,
        None,
        other_store.id,
        profile["full_name"],
        "inventory.new",
        "INVENTORY",
        "ACTIVE",
        "Temporary!2026",
        profile["id"],
    )
    linked = next(
        item
        for item in services.management.list_employee_profiles(admin)
        if item["id"] == profile["id"]
    )
    assert linked["employee_id"] == identity.id

    services.management.set_manager_store_assignment(
        admin, manager.employee_id, other_store.id, True
    )
    assert services.management.list_manager_store_assignments(
        admin, manager.employee_id
    ) == [other_store.id]
    with pytest.raises(PermissionDeniedError):
        services.management.validate_actor(manager)
    manager = services.auth.login("quanly01", "demo123")
    switched = services.management.switch_store(manager, other_store.id)
    assert switched.store_id == other_store.id
    assert {store.id for store in services.management.list_stores(switched)} == {
        manager.store_id,
        other_store.id,
    }
    with pytest.raises(PermissionDeniedError):
        services.management.set_manager_store_assignment(
            director, manager.employee_id, other_store.id, False
        )
