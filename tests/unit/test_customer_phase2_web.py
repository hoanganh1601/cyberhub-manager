"""Phase 2 HTTP ownership, password session revocation and classification permissions."""

import pytest
from cyberhub_manager.web import create_app


@pytest.fixture
def app():
    return create_app(
        {"TESTING": True, "WEB_MODE": "demo", "SECRET_KEY": "phase2-tests-only"}
    )


def login(client, username="nguyenvanan", kind="customer"):
    token = client.get("/api/session").json["csrf_token"]
    result = client.post(
        "/api/login",
        json=dict(username=username, password="demo123", kind=kind),
        headers={"X-CSRF-Token": token},
    )
    assert result.status_code == 200
    return {"X-CSRF-Token": result.json["csrf_token"]}


def test_customer_counts_are_private_and_usage_is_consistent(app):
    client = app.test_client()
    login(client)
    available = client.get("/api/portal/availability?store_id=1")
    assert available.status_code == 200 and available.json["refresh_seconds"] == 300
    assert [(room["room_type"], room["total"], room["available"]) for room in available.json["rooms"]] == [
        ("STANDARD", 8, 5), ("VIP", 8, 8), ("COUPLE", 2, 2), ("SUPER_VIP", 2, 2),
    ]
    assert [room["min_hourly_rate"] for room in available.json["rooms"]] == [10000, 20000, 25000, 35000]
    assert [room["max_hourly_rate"] for room in available.json["rooms"]] == [10000, 20000, 25000, 35000]
    assert "machine_code" not in available.text and "customer_id" not in available.text
    usage = client.get("/api/portal/usage?days=7")
    assert usage.status_code == 200 and usage.json["usage_seconds"] == 18000
    assert len(usage.json["daily"]) == 7
    assert client.get("/api/portal/availability?store_id=999").status_code == 422


def test_owned_profile_and_password_changes_keep_current_session_and_revoke_old_cookie(
    app,
):
    client = app.test_client()
    headers = login(client)
    cookie_name = app.config["SESSION_COOKIE_NAME"]
    old_cookie = client.get_cookie(cookie_name)
    old = app.test_client()
    old.set_cookie(cookie_name, old_cookie.value)
    result = client.patch(
        "/api/portal/profile",
        json=dict(
            full_name="New Customer Name",
            phone="0912345678",
            current_password="demo123",
            customer_id=2,
            balance=999999,
            role="ADMIN",
        ),
        headers=headers,
    )
    assert result.status_code == 200 and result.json["username"] == "nguyenvanan"
    assert client.get("/api/portal/dashboard").json["wallet"]["balance"] == 50000
    result = client.post(
        "/api/portal/password",
        json=dict(
            current_password="demo123",
            new_password="new-password123",
            confirmation="new-password123",
        ),
        headers=headers,
    )
    assert result.status_code == 200
    assert result.json["csrf_token"] != headers["X-CSRF-Token"]
    assert client.get("/api/portal/profile").status_code == 200
    assert old.get("/api/portal/profile").status_code == 403
    assert old.get("/api/portal/invoices/1/export").status_code == 403
    assert client.get("/api/customers").status_code == 401


def test_profile_changes_require_csrf_and_correct_current_password(app):
    client = app.test_client()
    headers = login(client)
    data = dict(
        full_name="New Customer Name", phone="0912345678", current_password="wrong"
    )
    assert client.patch("/api/portal/profile", json=data).status_code == 403
    result = client.patch("/api/portal/profile", json=data, headers=headers)
    assert (
        result.status_code == 422
        and "current_password" in result.json["error"]["field_errors"]
    )
    assert client.get("/api/portal/profile").json["full_name"] == "Nguyễn Văn An"


def test_room_classification_roles_and_occupied_machine(app):
    client = app.test_client()
    headers = login(client, "admin01", "employee")
    assert (
        client.patch(
            "/api/machines/1/room-type", json={"room_type": "VIP"}, headers=headers
        ).status_code
        == 200
    )
    assert client.get("/api/machine-rooms").json[0]["room_type"] == "VIP"
    assert client.get("/api/machines").json[0]["room_type"] == "VIP"
    for room_type in ("COUPLE", "SUPER_VIP"):
        assert client.patch(
            "/api/machines/1/room-type", json={"room_type": room_type}, headers=headers
        ).status_code == 200
        assert client.get("/api/machines").json[0]["room_type"] == room_type
    assert (
        client.patch(
            "/api/machines/2/room-type", json={"room_type": "VIP"}, headers=headers
        ).status_code
        == 409
    )
    other = app.test_client()
    other_headers = login(other, "nhanvien01", "employee")
    assert (
        other.patch(
            "/api/machines/1/room-type",
            json={"room_type": "VIP"},
            headers=other_headers,
        ).status_code
        == 403
    )
    customer = app.test_client()
    customer_headers = login(customer)
    assert customer.get("/api/machine-rooms").status_code == 401
    assert (
        customer.patch(
            "/api/machines/1/room-type",
            json={"room_type": "VIP"},
            headers=customer_headers,
        ).status_code
        == 401
    )
