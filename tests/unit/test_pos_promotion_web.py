"""API khuyến mãi POS qua Flask (chế độ demo): bật/tắt, lịch sử, báo giá, phân quyền, CSRF."""

import pytest

pytest.importorskip("flask")

from cyberhub_manager.web import create_app  # noqa: E402


@pytest.fixture
def app():
    return create_app({"TESTING": True, "WEB_MODE": "demo", "SECRET_KEY": "pos-promotion-web-test"})


def sign_in(client, username, kind=None):
    csrf = client.get("/api/session").json["csrf_token"]
    payload = dict(username=username, password="demo123")
    if kind:
        payload["kind"] = kind
    result = client.post("/api/login", json=payload, headers={"X-CSRF-Token": csrf})
    assert result.status_code == 200, result.json
    return {"X-CSRF-Token": result.json["csrf_token"]}


def test_manager_sees_state_and_usage_and_switches_with_history(app):
    c = app.test_client()
    headers = sign_in(c, "quanly01")
    promotions = c.get("/api/menu/promotions").json
    target = next(p for p in promotions if p["code"] == "DEMO_VIP_10")
    assert target["state"] == "ACTIVE" and target["orders_count"] == 0 and target["discount_total"] == 0
    assert target["starts_at"].endswith("+00:00")  # có múi giờ: trình duyệt hiển thị đúng giờ

    url = f"/api/menu/promotions/{target['id']}/active"
    assert c.post(url, json={"is_active": False}).status_code == 403  # thiếu CSRF
    switched = c.post(url, json={"is_active": False}, headers=headers)
    assert switched.status_code == 200 and switched.json["state"] == "OFF"
    history = c.get(f"/api/menu/promotions/{target['id']}/history").json
    assert [h["action"] for h in history] == ["DISABLE"]


def test_invalid_switch_value_is_a_field_error(app):
    c = app.test_client()
    headers = sign_in(c, "quanly01")
    target = c.get("/api/menu/promotions").json[0]
    result = c.post(f"/api/menu/promotions/{target['id']}/active", json={"is_active": "yes"}, headers=headers)
    assert result.status_code == 422 and "is_active" in result.json["error"]["field_errors"]


def test_staff_cannot_switch_or_read_promotion_history(app):
    manager = app.test_client()
    sign_in(manager, "quanly01")
    target = manager.get("/api/menu/promotions").json[0]

    staff = app.test_client()
    headers = sign_in(staff, "nhanvien01")
    assert staff.post(f"/api/menu/promotions/{target['id']}/active", json={"is_active": False},
                      headers=headers).status_code == 403
    assert staff.get(f"/api/menu/promotions/{target['id']}/history").status_code == 403


def test_customer_quote_shows_discount_and_requires_csrf(app):
    c = app.test_client()
    headers = sign_in(c, "lethibinh", "customer")
    menu = c.get("/api/portal/menu").json
    coca = next(i for p in menu["pages"] for g in p["categories"] for i in g["items"] if i["name"] == "Coca")
    body = {"lines": [{"item_id": coca["id"], "quantity": 3}]}

    assert c.post("/api/portal/menu/quote", json=body).status_code == 403
    quote = c.post("/api/portal/menu/quote", json=body, headers=headers)
    assert quote.status_code == 200, quote.json
    assert quote.json["gross_amount"] == 30000 and quote.json["discount_amount"] == 15000
    assert quote.json["final_amount"] == 15000 and quote.json["promotion_code"] == "DEMO_NUOC_5000"
    assert c.get("/api/portal/menu").json["orders"] == []  # báo giá không tạo đơn


def test_customer_without_session_cannot_quote_and_cannot_use_staff_routes(app):
    c = app.test_client()
    headers = sign_in(c, "nguyenvanan", "customer")
    result = c.post("/api/portal/menu/quote", json={"lines": [{"item_id": 1, "quantity": 1}]}, headers=headers)
    assert result.status_code == 422 and "session" in result.json["error"]["field_errors"]
    assert c.get("/api/menu/promotions").status_code in (401, 403)
