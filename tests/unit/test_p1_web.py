"""HTTP authorization and wallet/portal integration for P1."""

from datetime import datetime, timedelta, timezone
import pytest
from cyberhub_manager.web import create_app


@pytest.fixture
def client():
    return create_app(
        {"TESTING": True, "WEB_MODE": "demo", "SECRET_KEY": "p1-http-tests"}
    ).test_client()


def login(client, username="admin01", kind="employee"):
    token = client.get("/api/session").json["csrf_token"]
    result = client.post(
        "/api/login",
        json={"username": username, "password": "demo123", "kind": kind},
        headers={"X-CSRF-Token": token},
    )
    assert result.status_code == 200, result.json
    return {"X-CSRF-Token": result.json["csrf_token"]}


def test_management_create_switch_operate_and_export(client):
    headers = login(client)
    assert len(client.get("/api/stores").json) == 2
    now = datetime.now(timezone.utc)
    policy = dict(
        code="GLOBAL10",
        name="Global 10%",
        store_id=None,
        minimum_amount=100000,
        bonus_percent=10,
        starts_at=(now - timedelta(days=1)).isoformat(),
        ends_at=(now + timedelta(days=1)).isoformat(),
        is_active=True,
    )
    assert (
        client.post("/api/promotions", json=policy, headers=headers).status_code == 200
    )
    preview = client.post(
        "/api/customers/1/topup-preview", json={"amount": 100000}, headers=headers
    )
    assert preview.json["bonus_amount"] == 10000
    result = client.post(
        "/api/customers/1/topup",
        json={"amount": 100000, "method": "TRANSFER"},
        headers=headers,
    )
    assert result.status_code == 200, result.json
    customer = client.get("/api/customers/1").json["customer"]
    assert customer["cash_balance"] == 150000 and customer["bonus_balance"] == 10000
    switched = client.post("/api/store/switch", json={"store_id": 2}, headers=headers)
    assert switched.status_code == 200, switched.json
    assert client.get("/api/machines").json == []
    machine = client.post(
        "/api/machines",
        json={"code": "PC-H01", "name": "Ha Dong", "hourly_rate": 10000},
        headers=headers,
    )
    assert machine.status_code == 201, machine.json
    # A switched administrator cannot use invoices from another operating store.
    assert client.get("/api/invoices/1/export").status_code == 403


@pytest.mark.parametrize("username", ["nhanvien01", "quanly01"])
def test_store_privileges_cannot_be_forged(client, username):
    headers = login(client, username)
    assert (
        client.post(
            "/api/store/switch", json={"store_id": 2, "role": "ADMIN"}, headers=headers
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/stores",
            json={"code": "CH03", "name": "Unauthorized", "address": "Address"},
            headers=headers,
        ).status_code
        == 403
    )
    if username == "nhanvien01":
        assert client.get("/api/employees").status_code == 403


def test_customer_cannot_call_employee_apis_or_export_another_invoice(client):
    headers = login(client, "nguyenvanan", "customer")
    snapshot = client.get("/api/portal/snapshot")
    assert snapshot.status_code == 200, snapshot.json
    assert snapshot.json["profile"]["username"] == "nguyenvanan"
    assert "password" not in str(snapshot.json)
    assert client.get("/api/customers").status_code == 401
    assert (
        client.post(
            "/api/customers/1/topup",
            json={"amount": 100000, "method": "CASH"},
            headers=headers,
        ).status_code
        == 401
    )
    assert client.get("/api/portal/invoices/4/export").status_code == 404
    own = client.get("/api/portal/invoices/1/export", headers={"X-Language": "en"})
    assert own.status_code == 200
    assert b"SERVICE RECEIPT" in own.data
    assert client.get("/customer").status_code == 200


def test_printable_and_csv_exports_scoped_and_localized(client):
    login(client, "nhanvien01")
    html = client.get("/api/invoices/1/export", headers={"X-Language": "en"})
    assert html.status_code == 200 and b"Paid from bonus" in html.data
    csv = client.get("/api/invoices/1/export?format=csv")
    assert csv.status_code == 200 and "attachment" in csv.headers["Content-Disposition"]
    assert csv.data.startswith(b"\xef\xbb\xbf")
    assert client.get("/api/portal/snapshot").status_code == 403
