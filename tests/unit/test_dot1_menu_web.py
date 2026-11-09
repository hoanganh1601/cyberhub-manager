"""Đợt 1 — API menu qua Flask (chế độ demo): phân quyền, CSRF, giá do server quyết định."""

import pytest

pytest.importorskip("flask")

from cyberhub_manager.web import create_app  # noqa: E402


@pytest.fixture
def app():
    return create_app({"TESTING": True, "WEB_MODE": "demo", "SECRET_KEY": "dot1-menu-web-test"})


def sign_in(client, username, kind=None):
    csrf = client.get("/api/session").json["csrf_token"]
    payload = dict(username=username, password="demo123")
    if kind:
        payload["kind"] = kind
    result = client.post("/api/login", json=payload, headers={"X-CSRF-Token": csrf})
    assert result.status_code == 200, result.json
    return {"X-CSRF-Token": result.json["csrf_token"]}


def all_items(menu):
    return [i for p in menu["pages"] for g in p["categories"] for i in g["items"]]


def test_customer_reads_flipbook_menu_with_food_then_drink(app):
    c = app.test_client()
    sign_in(c, "nguyenvanan", "customer")

    menu = c.get("/api/portal/menu").json

    assert [p["page"] for p in menu["pages"]] == ["FOOD", "DRINK"]
    assert menu["can_order"] is False
    assert any(i["is_available"] is False for i in all_items(menu))


def test_customer_order_ignores_client_price_and_requires_csrf(app):
    c = app.test_client()
    headers = sign_in(c, "lethibinh", "customer")
    item = next(i for i in all_items(c.get("/api/portal/menu").json) if i["is_available"])
    body = {"lines": [{"item_id": item["id"], "quantity": 2, "unit_price": 1}], "note": ""}

    assert c.post("/api/portal/menu/orders", json=body).status_code == 403  # thiếu CSRF
    result = c.post("/api/portal/menu/orders", json=body, headers=headers)

    assert result.status_code == 201, result.json
    assert result.json["total_amount"] == item["price"] * 2  # giá lấy từ server, bỏ qua unit_price
    assert result.json["status"] == "NEW"


def test_sold_out_item_order_returns_conflict(app):
    c = app.test_client()
    headers = sign_in(c, "lethibinh", "customer")
    sold_out = next(i for i in all_items(c.get("/api/portal/menu").json) if not i["is_available"])

    result = c.post("/api/portal/menu/orders", json={"lines": [{"item_id": sold_out["id"], "quantity": 1}]},
                    headers=headers)

    assert result.status_code == 409
    assert "lines" in result.json["error"]["field_errors"]


def test_customer_cannot_use_staff_menu_api(app):
    c = app.test_client()
    sign_in(c, "nguyenvanan", "customer")
    assert c.get("/api/menu").status_code in (401, 403)


def test_staff_handles_menu_but_cannot_edit_items(app):
    c = app.test_client()
    headers = sign_in(c, "nhanvien01")
    data = c.get("/api/menu").json
    item = data["items"][0]

    assert data["can_manage"] is False
    assert c.get("/api/menu/orders").status_code == 200
    edit = c.patch(f"/api/menu/items/{item['id']}", json={**item, "price": 1000}, headers=headers)
    assert edit.status_code == 403
    toggle = c.post(f"/api/menu/items/{item['id']}/availability", json={"available": False}, headers=headers)
    assert toggle.status_code == 200 and toggle.json["is_available"] is False


def test_manager_creates_item_and_history_is_kept(app):
    c = app.test_client()
    headers = sign_in(c, "quanly01")
    category = c.get("/api/menu").json["categories"][0]
    body = dict(category_id=category["id"], name="Trà tắc mật ong", description="Ly lớn", price=20000,
                sort_order=5, is_visible=True, is_available=True)

    created = c.post("/api/menu/items", json=body, headers=headers)
    assert created.status_code == 200, created.json
    item_id = created.json["id"]
    updated = c.patch(f"/api/menu/items/{item_id}", json={**body, "price": 22000}, headers=headers)
    assert updated.json["price"] == 22000
    history = c.get(f"/api/menu/items/{item_id}/history").json
    assert [h["field"] for h in history] == ["PRICE", "CREATE"]


def test_invalid_price_returns_field_error(app):
    c = app.test_client()
    headers = sign_in(c, "quanly01")
    category = c.get("/api/menu").json["categories"][0]
    result = c.post("/api/menu/items", json=dict(category_id=category["id"], name="Sai giá", price="abc"),
                    headers=headers)
    assert result.status_code == 422
    assert "price" in result.json["error"]["field_errors"]


def test_item_without_image_returns_not_found(app):
    c = app.test_client()
    sign_in(c, "nguyenvanan", "customer")
    item = all_items(c.get("/api/portal/menu").json)[0]
    assert c.get(f"/api/portal/menu/items/{item['id']}/image").status_code == 404
