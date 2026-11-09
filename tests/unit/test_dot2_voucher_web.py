"""Đợt 2 — API voucher qua Flask (chế độ demo): phân quyền, CSRF, dùng một lần."""

import pytest

pytest.importorskip("flask")

from cyberhub_manager.web import create_app  # noqa: E402


@pytest.fixture
def app():
    return create_app({"TESTING": True, "WEB_MODE": "demo", "SECRET_KEY": "dot2-voucher-web-test"})


def sign_in(client, username, kind=None):
    csrf = client.get("/api/session").json["csrf_token"]
    payload = dict(username=username, password="demo123")
    if kind:
        payload["kind"] = kind
    result = client.post("/api/login", json=payload, headers={"X-CSRF-Token": csrf})
    assert result.status_code == 200, result.json
    return {"X-CSRF-Token": result.json["csrf_token"]}


def test_customer_lists_own_vouchers(app):
    c = app.test_client()
    sign_in(c, "nguyenvanan", "customer")

    data = c.get("/api/portal/vouchers").json

    assert data["active"] == 2
    assert {v["state"] for v in data["items"]} == {"ACTIVE", "EXPIRED"}


def test_customer_cannot_use_staff_voucher_api(app):
    c = app.test_client()
    sign_in(c, "nguyenvanan", "customer")
    assert c.get("/api/vouchers").status_code in (401, 403)
    assert c.get("/api/vouchers/lookup?code=CHDEMO0001").status_code in (401, 403)


def test_staff_redeems_once_and_second_attempt_conflicts(app):
    c = app.test_client()
    headers = sign_in(c, "nhanvien01")
    found = c.get("/api/vouchers/lookup?code=CHDEMO0001").json
    body = {"code": "CHDEMO0001", "customer_id": found["voucher"]["customer_id"]}

    assert c.post("/api/vouchers/redeem", json=body).status_code == 403  # thiếu CSRF
    first = c.post("/api/vouchers/redeem", json=body, headers=headers)
    assert first.status_code == 200, first.json
    assert first.json["bonus_credited"] == 10000
    second = c.post("/api/vouchers/redeem", json=body, headers=headers)
    assert second.status_code == 409
    assert "code" in second.json["error"]["field_errors"]
    events = c.get("/api/vouchers").json["events"]
    assert [e["action"] for e in events[:2]] == ["REJECT", "REDEEM"]


def test_staff_cannot_manage_rewards(app):
    c = app.test_client()
    headers = sign_in(c, "nhanvien01")

    assert c.get("/api/vouchers").json["can_manage"] is False
    reward = dict(code="X1", name="x", reward_type="MEMBER_POINTS", value=1, valid_days=1)
    assert c.post("/api/rewards", json=reward, headers=headers).status_code == 403
    assert c.post("/api/vouchers/issue", json={"catalog_id": 1, "customer_id": 1}, headers=headers).status_code == 403


def test_manager_creates_reward_and_issues_voucher(app):
    c = app.test_client()
    headers = sign_in(c, "quanly01")
    reward = dict(code="TRANUOC", name="Tặng trà đá", reward_type="FREE_DRINK", value=10000,
                  min_order_amount=0, valid_days=7, coin_cost=50, is_active=True)

    created = c.post("/api/rewards", json=reward, headers=headers)
    assert created.status_code == 200, created.json
    customer_id = c.get("/api/customers").json[0]["customer_id"]
    issued = c.post("/api/vouchers/issue", json={"catalog_id": created.json["id"], "customer_id": customer_id},
                    headers=headers)
    assert issued.status_code == 201, issued.json
    assert issued.json["status"] == "ISSUED" and issued.json["code"].startswith("CH")


def test_invalid_code_returns_field_error(app):
    c = app.test_client()
    sign_in(c, "nhanvien01")
    result = c.get("/api/vouchers/lookup?code=%21%21")
    assert result.status_code == 422
    assert "code" in result.json["error"]["field_errors"]
