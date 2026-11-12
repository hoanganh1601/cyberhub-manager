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
    assert data["can_set_availability"] is True
    assert all(data[key] is True for key in (
        "can_prepare", "can_serve", "can_cancel", "can_collect_payment",
    ))
    assert c.get("/api/menu/orders").status_code == 200
    edit = c.patch(f"/api/menu/items/{item['id']}", json={**item, "price": 1000}, headers=headers)
    assert edit.status_code == 403
    toggle = c.post(f"/api/menu/items/{item['id']}/availability", json={"available": False}, headers=headers)
    assert toggle.status_code == 200 and toggle.json["is_available"] is False


def test_inventory_api_rechecks_role_and_csrf(app):
    staff = app.test_client()
    staff_headers = sign_in(staff, "nhanvien01")
    overview = staff.get("/api/inventory")
    assert overview.status_code == 200
    assert overview.json["can_count"] is True
    assert overview.json["can_approve"] is False
    assert overview.json["can_issue"] is False

    decision = "/api/inventory/counts/1/decision"
    assert staff.post(decision, json={"approve": True}).status_code == 403
    assert staff.post(decision, json={"approve": True}, headers=staff_headers).status_code == 403

    manager = app.test_client()
    sign_in(manager, "quanly01")
    manager_overview = manager.get("/api/inventory")
    assert manager_overview.status_code == 200
    assert manager_overview.json["can_approve"] is True
    assert manager_overview.json["can_issue"] is True


def test_staff_can_advance_and_pay_menu_order(app):
    staff = app.test_client()
    staff_headers = sign_in(staff, "nhanvien01")
    with staff.session_transaction() as session:
        workspace = app.extensions["cyberhub_demo"].get(session["workspace"])
    customer = workspace.services.portal.login("lethibinh", "demo123")
    item = next(i for p in workspace.services.menu.portal_menu(customer)["pages"] for g in p["categories"] for i in g["items"] if i.is_available)
    order_id = workspace.services.menu.place_order(customer, [{"item_id": item.id, "quantity": 1}]).id
    assert staff.post(f"/api/menu/orders/{order_id}/status", json={"status": "PREPARING"}, headers=staff_headers).json["status"] == "PREPARING"
    assert staff.post(f"/api/menu/orders/{order_id}/status", json={"status": "SERVED"}, headers=staff_headers).json["status"] == "SERVED"
    paid = staff.post(f"/api/menu/orders/{order_id}/payment", json={"method": "TRANSFER"}, headers=staff_headers)
    assert paid.status_code == 200 and paid.json["status"] == "PAID" and paid.json["payment_method"] == "TRANSFER"


def test_demo_pos_samples_and_revenue_change_only_when_paid(app):
    client = app.test_client()
    headers = sign_in(client, "quanly01")
    orders = client.get("/api/menu/orders?status=ALL").json
    assert {o["status"] for o in orders} == {"NEW", "PREPARING", "SERVED", "PAID", "CANCELLED"}
    assert sum(o["status"] == "PAID" for o in orders) == 3

    before = client.get("/api/revenue").json
    assert before["menu_order_count"] >= 1
    assert before["total_revenue"] == before["machine_revenue"] + before["menu_revenue"]
    assert before["top_menu_items"][0]["name"] == "Coca"
    assert sum(day["menu_revenue"] for day in before["days"]) == before["menu_revenue"]

    served = next(o for o in orders if o["status"] == "SERVED")
    paid = client.post(f"/api/menu/orders/{served['id']}/payment",
                       json={"method": "CASH"}, headers=headers)
    assert paid.status_code == 200
    after = client.get("/api/revenue").json
    assert after["menu_order_count"] == before["menu_order_count"] + 1
    assert after["menu_revenue"] == before["menu_revenue"] + served["total_amount"]

    new_order = next(o for o in orders if o["status"] == "NEW")
    cancelled = client.post(f"/api/menu/orders/{new_order['id']}/status",
                            json={"status": "CANCELLED"}, headers=headers)
    assert cancelled.status_code == 200
    assert client.get("/api/revenue").json == after


def test_food_voucher_reduces_paid_revenue(app):
    client = app.test_client()
    headers = sign_in(client, "quanly01")
    with client.session_transaction() as session:
        workspace = app.extensions["cyberhub_demo"].get(session["workspace"])
    customer = workspace.services.portal.login("lethibinh", "demo123")
    item = next(i for i in workspace.services.menu.portal_menu(customer)["pages"][0]["categories"][0]["items"]
                if i.price >= 25_000)
    order = workspace.services.menu.place_order(customer, [{"item_id": item.id, "quantity": 2}])
    workspace.services.menu.finish_order(workspace.actor, order.id, "SERVED")
    baseline = client.get("/api/revenue").json
    discount = client.post("/api/vouchers/redeem",
                           json={"code": "CHDEMO0004", "customer_id": customer.customer_id,
                                 "order_id": order.id}, headers=headers)
    assert discount.status_code == 200, discount.json
    assert discount.json["discount"] == 20_000
    paid = client.post(f"/api/menu/orders/{order.id}/payment",
                       json={"method": "TRANSFER"}, headers=headers)
    assert paid.status_code == 200, paid.json
    assert paid.json["discount_amount"] == 20_000
    report = client.get("/api/revenue").json
    assert report["menu_revenue"] == baseline["menu_revenue"] + order.total_amount - 20_000
    assert client.post("/api/vouchers/redeem",
                       json={"code": "CHDEMO0005", "customer_id": customer.customer_id,
                             "order_id": order.id}, headers=headers).status_code == 409


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
