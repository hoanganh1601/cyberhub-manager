"""HTTP contract tests: real service adapters, isolated demo and browser security."""

import os
import subprocess
import sys

import pytest

pytest.importorskip("flask")

from cyberhub_manager.web import create_app


@pytest.fixture
def app():
    return create_app(
        {"TESTING": True, "WEB_MODE": "demo", "SECRET_KEY": "test-secret-for-web-only"}
    )


def bootstrap(client):
    result = client.get("/api/session")
    assert result.status_code == 200
    return result.json["csrf_token"]


def login(client, username="quanly01"):
    token = bootstrap(client)
    result = client.post(
        "/api/login",
        json=dict(username=username, password="demo123"),
        headers={"X-CSRF-Token": token},
    )
    assert result.status_code == 200, result.json
    return result.json["csrf_token"]


def post(client, path, token, data=None, method="POST"):
    return client.open(
        path, method=method, json=data or {}, headers={"X-CSRF-Token": token}
    )


def test_web_starts_without_tk_or_display():
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("DISPLAY", "WAYLAND_DISPLAY")
    }
    code = """
import sys
from cyberhub_manager.web import create_app
app = create_app({'WEB_MODE': 'demo'})
assert app.test_client().get('/').status_code == 200
assert 'tkinter' not in sys.modules
assert 'customtkinter' not in sys.modules
print('headless web OK')
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_index_assets_health_and_response_headers(app):
    client = app.test_client()
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/app.css").status_code == 200
    assert client.get("/assets/cyberhub_logo_dark.png").mimetype == "image/png"
    assert client.get("/assets/fonts/Inter-400.ttf").status_code == 200
    assert client.get("/assets/../../.env").status_code == 404
    response = client.get("/healthz")
    assert response.json == {"status": "ok", "mode": "demo"}
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/machines",
        "/api/customers",
        "/api/customers/1",
        "/api/invoices",
        "/api/revenue",
    ],
)
def test_requires_login(app, path):
    assert app.test_client().get(path).status_code == 401


def test_csrf_required_before_login_and_after_rotation(app):
    c = app.test_client()
    assert c.post("/api/login", json={}).status_code == 403
    old_token = bootstrap(c)
    token = login(c)
    assert old_token != token
    assert (
        post(
            c, "/api/customers/1/topup", old_token, {"amount": 10000, "method": "CASH"}
        ).status_code
        == 403
    )
    assert (
        post(
            c, "/api/customers/1/topup", token, {"amount": 10000, "method": "CASH"}
        ).status_code
        == 200
    )


def test_login_error_and_rate_limiting(app):
    c = app.test_client()
    token = bootstrap(c)
    for _ in range(10):
        result = post(
            c, "/api/login", token, {"username": "quanly01", "password": "wrong"}
        )
        assert result.status_code == 401
    result = post(c, "/api/login", token, {"username": "quanly01", "password": "wrong"})
    assert result.status_code == 429
    assert result.headers["Retry-After"] == "600"


def test_unicode_wrong_password_returns_authentication_error(app):
    c = app.test_client()
    token = bootstrap(c)
    response = post(
        c, "/api/login", token, dict(username="quanly01", password="mật khẩu sai")
    )
    assert response.status_code == 401


def test_demo_workspaces_are_independent_and_logout_revokes_cookie(app):
    a, b = app.test_client(), app.test_client()
    token_a = login(a)
    login(b)
    before = a.get("/api/customers/1").json["customer"]["balance"]
    assert (
        post(
            a, "/api/customers/1/topup", token_a, {"amount": 12345, "method": "CASH"}
        ).status_code
        == 200
    )
    assert a.get("/api/customers/1").json["customer"]["balance"] == before + 12345
    assert b.get("/api/customers/1").json["customer"]["balance"] == before
    old_cookie = a.get_cookie(app.config["SESSION_COOKIE_NAME"]).value
    assert post(a, "/api/logout", token_a).status_code == 200
    a.set_cookie(app.config["SESSION_COOKIE_NAME"], old_cookie)
    assert a.get("/api/customers").status_code == 401


@pytest.mark.parametrize(
    "path,data",
    [
        ("/api/machines", {"code": "PC99", "name": "New", "hourly_rate": 5000}),
        ("/api/machines/1/maintenance", {"enabled": True}),
        ("/api/machines/1/archive", {}),
        ("/api/customers/1/status", {"status": "INACTIVE", "actor": {"role": "ADMIN"}}),
    ],
)
def test_staff_cannot_elevate_permissions(app, path, data):
    c = app.test_client()
    token = login(c, "nhanvien01")
    assert post(c, path, token, data).status_code == 403


def test_staff_can_read_current_store_reports_but_cannot_choose_store(app):
    c = app.test_client()
    login(c, "nhanvien01")
    machines = c.get("/api/machines?store_id=999").json
    assert len(machines) == 20
    assert {item["store_id"] for item in machines} == {1}
    assert c.get("/api/invoices").status_code == 200
    assert c.get("/api/revenue").status_code == 200


@pytest.mark.parametrize("value", [True, 1.5, "50000", [], {}, -1, 0, 100_000_001])
def test_invalid_money_never_changes_balance(app, value):
    c = app.test_client()
    token = login(c)
    before = c.get("/api/customers/1").json
    response = post(
        c, "/api/customers/1/topup", token, {"amount": value, "method": "CASH"}
    )
    assert response.status_code == 422
    assert c.get("/api/customers/1").json == before


@pytest.mark.parametrize("method", [[], {}, "MOMO", None, True, "ACCOUNT_BALANCE"])
def test_invalid_method_returns_validation_error_not_500(app, method):
    c = app.test_client()
    token = login(c)
    response = post(
        c, "/api/customers/1/topup", token, {"amount": 10000, "method": method}
    )
    assert response.status_code == 422
    assert "method" in response.json["error"]["field_errors"]


def test_create_edit_lock_unlock_customer(app):
    c = app.test_client()
    token = login(c)
    payload = dict(
        full_name="Khách Web",
        phone="0987654321",
        username="web.customer",
        password="abcdef123",
    )
    result = post(c, "/api/customers", token, payload)
    assert result.status_code == 201, result.json
    customer_id = result.json["customer_id"]
    assert "password" not in result.get_data(as_text=True)
    assert result.json["balance"] == 0
    duplicate = post(c, "/api/customers", token, payload)
    assert duplicate.status_code == 409
    result = post(
        c,
        f"/api/customers/{customer_id}",
        token,
        dict(full_name="Khách Web Đã Sửa", phone="0987654322"),
        "PATCH",
    )
    assert result.status_code == 200
    assert result.json["full_name"] == "Khách Web Đã Sửa"
    result = post(
        c, f"/api/customers/{customer_id}/status", token, dict(status="INACTIVE")
    )
    assert result.json["account_status"] == "LOCKED"
    result = post(
        c, f"/api/customers/{customer_id}/status", token, dict(status="ACTIVE")
    )
    assert result.json["account_status"] == "ACTIVE"


def test_machine_management_and_session_checkout(app):
    c = app.test_client()
    token = login(c)
    result = post(
        c,
        "/api/machines",
        token,
        dict(code="WEB-PC", name="Máy Web", hourly_rate=6000, store_id=999),
    )
    assert result.status_code == 201, result.json
    mid = result.json["machine_id"]
    assert result.json["store_id"] == 1
    result = post(
        c,
        f"/api/machines/{mid}",
        token,
        dict(name="Máy Web Mới", hourly_rate=7000),
        "PATCH",
    )
    assert result.status_code == 200
    assert (
        post(c, f"/api/machines/{mid}/maintenance", token, dict(enabled=True)).json[
            "status"
        ]
        == "MAINTENANCE"
    )
    assert (
        post(c, f"/api/machines/{mid}/maintenance", token, dict(enabled=False)).json[
            "status"
        ]
        == "AVAILABLE"
    )
    assert (
        post(c, f"/api/machines/{mid}/open-preview", token, dict(customer_id=1)).json[
            "can_open"
        ]
        is True
    )
    opened = post(
        c,
        f"/api/machines/{mid}/open",
        token,
        dict(customer_id=1, actor={"employee_id": 999}),
    )
    assert opened.status_code == 201, opened.json
    assert (
        post(c, f"/api/machines/{mid}/open", token, dict(customer_id=1)).status_code
        == 409
    )
    preview = c.get(f"/api/machines/{mid}/checkout-preview").json
    assert preview["settlement_required"] == 0
    paid = post(
        c,
        f"/api/machines/{mid}/checkout",
        token,
        dict(settlement_amount=0, method=None),
    )
    assert paid.status_code == 200, paid.json
    assert paid.json["invoice"]["invoice"]["status"] == "PAID"
    assert (
        post(
            c,
            f"/api/machines/{mid}/checkout",
            token,
            dict(settlement_amount=0, method=None),
        ).status_code
        == 409
    )
    assert post(c, f"/api/machines/{mid}/archive", token).json["action"] == "ARCHIVED"


def test_checkout_settlement_is_exact_and_not_cash_received(app):
    c = app.test_client()
    token = login(c)
    preview = c.get("/api/machines/2/checkout-preview").json
    required = preview["settlement_required"]
    assert required > 0
    before = c.get("/api/customers/2").json
    assert (
        post(
            c,
            "/api/machines/2/checkout",
            token,
            dict(settlement_amount=required + 10000, method="CASH"),
        ).status_code
        == 422
    )
    assert c.get("/api/customers/2").json == before
    paid = post(
        c,
        "/api/machines/2/checkout",
        token,
        dict(settlement_amount=required, method="TRANSFER", cash_received=999999),
    )
    assert paid.status_code == 200, paid.json
    assert paid.json["balance_after"] == 0
    assert paid.json["invoice"]["invoice"]["settlement_amount"] == required


def test_reports_exclude_void_and_topups(app):
    c = app.test_client()
    token = login(c)
    invoices = c.get("/api/invoices").json
    revenue = c.get("/api/revenue?date_from=2000-01-01&date_to=2000-01-02")
    assert revenue.json["total_revenue"] == 0
    current = c.get("/api/revenue").json
    assert current["total_revenue"] == sum(
        item["usage_cost"] for item in invoices if item["status"] == "PAID"
    )
    post(c, "/api/customers/1/topup", token, dict(amount=100000, method="TRANSFER"))
    assert c.get("/api/revenue").json == current
    assert (
        c.get("/api/revenue?date_from=2030-01-01&date_to=2020-01-01").status_code == 422
    )
    assert (
        c.get("/api/revenue?date_from=2000-01-01&date_to=2030-01-01").status_code == 422
    )
    assert c.get("/api/invoices?status=invalid").status_code == 422


def test_demo_expiry_is_recoverable_and_sessions_are_bounded(app):
    c = app.test_client()
    token = login(c)
    registry = app.extensions["cyberhub_demo"]
    registry.limit = 1
    other = app.test_client()
    other_token = bootstrap(other)
    assert (
        post(
            other,
            "/api/login",
            other_token,
            dict(username="quanly01", password="demo123"),
        ).status_code
        == 503
    )
    for workspace in registry.entries.values():
        workspace.expires = 0
    assert c.get("/api/customers").status_code == 401
    assert c.get("/api/session").json["actor"] is None
    assert (
        post(
            c, "/api/login", token, dict(username="quanly01", password="demo123")
        ).status_code
        == 200
    )


def test_web_english_errors_and_http_only_cookie(app):
    c = app.test_client()
    token = login(c)
    result = c.post(
        "/api/customers",
        json=dict(full_name="", phone="", username="", password=""),
        headers={"X-CSRF-Token": token, "X-Language": "en"},
    )
    assert result.status_code == 422
    assert result.json["error"]["message"] == "Please check the highlighted fields."
    cookie = c.get_cookie(app.config["SESSION_COOKIE_NAME"])
    assert cookie.http_only is True
    assert cookie.same_site == "Lax"
    assert c.get("/api/customers").headers["Cache-Control"] == "no-store"


def test_locked_customer_can_top_up_to_repay_debt_without_unlocking(app):
    c = app.test_client()
    token = login(c)
    before = c.get("/api/customers/3").json["customer"]
    assert before["account_status"] == "LOCKED"
    result = post(c, "/api/customers/3/topup", token, dict(amount=10000, method="CASH"))
    assert result.status_code == 200, result.json
    after = c.get("/api/customers/3").json["customer"]
    assert after["balance"] == before["balance"] + 10000
    assert after["account_status"] == "LOCKED"
    assert post(c, "/api/machines/1/open", token, dict(customer_id=3)).status_code == 409


@pytest.mark.parametrize("raw_mysql", [False, True])
def test_li10_error_mapping_never_exposes_database_diagnostics(app, monkeypatch, caplog, raw_mysql):
    from mysql.connector import OperationalError
    from cyberhub_manager.domain.exceptions import ServiceUnavailableError

    c = app.test_client()
    token = login(c)
    workspace = next(iter(app.extensions["cyberhub_demo"].entries.values()))
    failure = (
        OperationalError("secret_sql_host", errno=2013)
        if raw_mysql else ServiceUnavailableError(details={"errno": 2013, "db_error": "connection"})
    )

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(workspace.services.wallet, "top_up", fail)
    result = post(c, "/api/customers/1/topup", token, dict(amount=10000, method="CASH"))
    assert result.status_code == 503
    assert result.json["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert result.json["error"]["details"] == {}
    assert "secret_sql_host" not in result.get_data(as_text=True)
    if raw_mysql:
        assert "errno=2013" in caplog.text
