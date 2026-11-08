"""HTTP isolation, CSRF and pagination for customer self-service."""

import pytest
from cyberhub_manager.web import create_app


@pytest.fixture
def client():
    return create_app(
        {"TESTING": True, "WEB_MODE": "demo", "SECRET_KEY": "customer-phase1-test"}
    ).test_client()


def sign_in(client, username="nguyenvanan", kind="customer"):
    csrf = client.get("/api/session").json["csrf_token"]
    result = client.post(
        "/api/login",
        json=dict(username=username, password="demo123", kind=kind),
        headers={"X-CSRF-Token": csrf},
    )
    assert result.status_code == 200
    return {"X-CSRF-Token": result.json["csrf_token"]}


def test_customer_dashboard_history_and_persistent_reads(client):
    headers = sign_in(client)
    result = client.get("/api/portal/dashboard?days=7")
    assert result.status_code == 200, result.json
    assert result.json["totals"]["spent"] == 50000
    assert len(result.json["chart"]) == 7
    history = client.get(
        "/api/portal/history?kind=invoices&status=PAID&page_size=10"
    ).json
    assert history["total"] == 2 and len(history["items"]) == 2
    notices = client.get("/api/portal/notifications").json
    keys = [n["key"] for n in notices["items"]]
    assert (
        client.post("/api/portal/notifications/read", json={"keys": keys}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/portal/notifications/read", json={"keys": keys}, headers=headers
        ).status_code
        == 200
    )
    assert client.get("/api/portal/notifications").json["unread"] == 0
    # A fresh HTTP request sees the stored read receipts.
    assert client.get("/api/portal/notifications").json["unread"] == 0


def test_customer_quote_does_not_modify_wallet_or_employee_data(client):
    headers = sign_in(client)
    before = client.get("/api/portal/snapshot").json
    result = client.post(
        "/api/portal/topup-preview",
        json={"store_id": 1, "amount": 100000},
        headers=headers,
    )
    assert result.status_code == 200, result.json
    assert result.json["credited_total"] >= 100000
    assert client.get("/api/portal/snapshot").json == before
    assert client.get("/api/employees").status_code == 401
    assert (
        client.post(
            "/api/portal/notifications/read",
            json={"keys": ["invoice:4:PAID"]},
            headers=headers,
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "path",
    [
        "dashboard?days=NaN",
        "dashboard?days=365",
        "dashboard?store_id=999",
        "history?kind=stores",
        "history?page=-1",
        "history?date_from=invalid",
    ],
)
def test_malformed_customer_queries_return_validation_error(client, path):
    sign_in(client)
    response = client.get("/api/portal/" + path, headers={"X-Language": "en"})
    assert response.status_code == 422
    assert response.json["error"]["code"] == "VALIDATION_ERROR"


def test_employee_cannot_use_customer_apis(client):
    headers = sign_in(client, "admin01", "employee")
    for path in ("dashboard", "history", "notifications"):
        assert client.get("/api/portal/" + path).status_code == 403
    assert (
        client.post(
            "/api/portal/topup-preview",
            json={"amount": 100000, "store_id": 1},
            headers=headers,
        ).status_code
        == 403
    )
