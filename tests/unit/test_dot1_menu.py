"""Đợt 1 — Nghiệp vụ menu và gọi món (MenuService trên repository bộ nhớ, không cần MySQL).

Dữ liệu demo: `lethibinh` đang có phiên ACTIVE trên máy 2 của cơ sở 1; `nguyenvanan` không chơi.
"""

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.menu import MAX_OPEN_ORDERS, MenuChangeField, MenuOrderStatus, MenuPage
from cyberhub_manager.domain.p1 import Permission, ROLE_PERMISSIONS
from cyberhub_manager.services.menu_service import NEED_ACTIVE_SESSION
from cyberhub_manager.services.mocks.clock import MockClock
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD

NOW = datetime(2026, 10, 18, 9, tzinfo=timezone.utc)


@pytest.fixture
def ctx():
    bundle = build_mock_services(p1=True, clock=MockClock(NOW))
    return dict(
        bundle=bundle,
        menu=bundle.menu,
        player=bundle.portal.login("lethibinh", DEMO_PASSWORD),
        visitor=bundle.portal.login("nguyenvanan", DEMO_PASSWORD),
        manager=bundle.auth.login("quanly01", DEMO_PASSWORD),
        staff=bundle.auth.login("nhanvien01", DEMO_PASSWORD),
    )


def items_of(menu_data):
    return [i for p in menu_data["pages"] for g in p["categories"] for i in g["items"]]


def find(menu_data, name):
    return next(i for i in items_of(menu_data) if i.name == name)


def test_paid_pos_revenue_uses_payment_day_in_vietnam():
    clock = MockClock(NOW)
    bundle = build_mock_services(p1=True, clock=clock)
    customer = bundle.portal.login("lethibinh", DEMO_PASSWORD)
    manager = bundle.auth.login("quanly01", DEMO_PASSWORD)
    coca = find(bundle.menu.portal_menu(customer), "Coca")
    clock.set(datetime(2026, 10, 18, 16, 59, tzinfo=timezone.utc))
    order = bundle.menu.place_order(customer, [{"item_id": coca.id, "quantity": 2}])
    bundle.menu.finish_order(manager, order.id, "SERVED")
    assert bundle.menu.paid_revenue(manager, date(2026, 10, 18), date(2026, 10, 18))["days"] == []

    clock.advance(minutes=2)
    bundle.menu.pay_order(manager, order.id, "CASH")
    assert bundle.menu.paid_revenue(manager, date(2026, 10, 18), date(2026, 10, 18))["days"] == []
    report = bundle.menu.paid_revenue(manager, date(2026, 10, 19), date(2026, 10, 19))
    assert report["days"] == [{"date": date(2026, 10, 19), "order_count": 1,
                               "revenue": 2 * coca.price}]
    assert report["top_items"][0]["quantity"] == 2


# ----- Xem menu -----------------------------------------------------------------
def test_menu_has_food_page_then_drink_page(ctx):
    data = ctx["menu"].portal_menu(ctx["visitor"])

    assert [p["page"] for p in data["pages"]] == [MenuPage.FOOD, MenuPage.DRINK]
    assert data["session"] is None and data["can_order"] is False
    assert find(data, "Xúc xích chiên").is_available is False  # demo có sẵn một món hết


def test_player_menu_defaults_to_store_of_current_machine(ctx):
    data = ctx["menu"].portal_menu(ctx["player"])

    assert data["can_order"] is True
    assert data["session"]["store_id"] == data["store_id"]


def test_menu_differs_per_store(ctx):
    store_id = ctx["manager"].store_id
    category = next(c for c in ctx["menu"].manage_menu(ctx["manager"])["categories"] if c.page == MenuPage.FOOD)
    ctx["menu"].save_item(ctx["manager"], None, category_id=category.id, name="Bánh flan", description="",
                          price=15_000, sort_order=0, is_visible=True, is_available=True)

    own = ctx["menu"].portal_menu(ctx["visitor"], store_id)
    other_store = next(s["id"] for s in own["stores"] if s["id"] != store_id)
    other = ctx["menu"].portal_menu(ctx["visitor"], other_store)

    assert "Bánh flan" in [i.name for i in items_of(own)]
    assert "Bánh flan" not in [i.name for i in items_of(other)]


def test_hidden_item_and_disabled_category_are_not_shown(ctx):
    menu, manager = ctx["menu"], ctx["manager"]
    coca = find(menu.portal_menu(ctx["visitor"]), "Coca")
    menu.save_item(manager, coca.id, category_id=coca.category_id, name=coca.name, description=coca.description,
                   price=coca.price, sort_order=coca.sort_order, is_visible=False, is_available=True)
    snack = find(menu.portal_menu(ctx["visitor"]), "Cá viên chiên")
    category = next(c for c in menu.manage_menu(manager)["categories"] if c.id == snack.category_id)
    menu.save_category(manager, category.id, page=category.page, name=category.name,
                       sort_order=category.sort_order, is_active=False)

    names = [i.name for i in items_of(menu.portal_menu(ctx["visitor"]))]
    assert "Coca" not in names and "Cá viên chiên" not in names


# ----- Gọi món ------------------------------------------------------------------
def test_order_uses_database_price_and_current_machine(ctx):
    menu = ctx["menu"]
    item = find(menu.portal_menu(ctx["player"]), "Cà phê sữa đá/nóng")

    order = menu.place_order(ctx["player"], [{"item_id": item.id, "quantity": 2}], "  ít đá ")

    assert order.status == MenuOrderStatus.NEW
    assert order.total_amount == item.price * 2
    assert order.lines[0].unit_price == item.price
    assert order.note == "ít đá"
    assert order.machine_code == menu.portal_menu(ctx["player"])["session"]["machine_code"]


def test_sold_out_item_cannot_be_ordered(ctx):
    menu = ctx["menu"]
    sold_out = find(menu.portal_menu(ctx["player"]), "Xúc xích chiên")

    with pytest.raises(ConflictError) as info:
        menu.place_order(ctx["player"], [{"item_id": sold_out.id, "quantity": 1}])

    assert "Xúc xích chiên" in info.value.field_errors["lines"]
    assert menu.portal_menu(ctx["player"])["orders"] == []


def test_staff_marks_item_sold_out_then_order_is_rejected(ctx):
    menu = ctx["menu"]
    item = find(menu.portal_menu(ctx["player"]), "Redbull Thái")
    menu.set_item_available(ctx["staff"], item.id, False)

    assert find(menu.portal_menu(ctx["player"]), "Redbull Thái").is_available is False
    with pytest.raises(ConflictError):
        menu.place_order(ctx["player"], [{"item_id": item.id, "quantity": 1}])


def test_customer_without_active_session_cannot_order(ctx):
    menu = ctx["menu"]
    item = find(menu.portal_menu(ctx["visitor"]), "Nước suối")

    with pytest.raises(ValidationError) as info:
        menu.place_order(ctx["visitor"], [{"item_id": item.id, "quantity": 1}])

    assert info.value.field_errors == {"session": NEED_ACTIVE_SESSION}


def test_item_of_another_store_cannot_be_ordered(ctx):
    menu = ctx["menu"]
    data = menu.portal_menu(ctx["visitor"])
    player_store = menu.portal_menu(ctx["player"])["store_id"]
    other_store = next(s["id"] for s in data["stores"] if s["id"] != player_store)
    foreign = items_of(menu.portal_menu(ctx["visitor"], other_store))[0]

    with pytest.raises(NotFoundError):
        menu.place_order(ctx["player"], [{"item_id": foreign.id, "quantity": 1}])


@pytest.mark.parametrize(
    "lines",
    [
        [],
        "1",
        [{"item_id": 1, "quantity": 0}],
        [{"item_id": 1, "quantity": 21}],
        [{"item_id": 1, "quantity": True}],
        [{"item_id": "1", "quantity": 1}],
        [{"item_id": 1, "quantity": 1}, {"item_id": 1, "quantity": 2}],
        [{"item_id": i, "quantity": 1} for i in range(1, 22)],
    ],
)
def test_invalid_order_lines_are_rejected_before_database(ctx, lines):
    with pytest.raises(ValidationError):
        ctx["menu"].place_order(ctx["player"], lines)


def test_open_order_limit_prevents_spam(ctx):
    menu = ctx["menu"]
    item = find(menu.portal_menu(ctx["player"]), "Nước suối")
    for _ in range(MAX_OPEN_ORDERS):
        menu.place_order(ctx["player"], [{"item_id": item.id, "quantity": 1}])

    with pytest.raises(ConflictError):
        menu.place_order(ctx["player"], [{"item_id": item.id, "quantity": 1}])


def test_forged_customer_principal_is_denied(ctx):
    from dataclasses import replace

    forged = replace(ctx["player"], customer_id=ctx["visitor"].customer_id)
    with pytest.raises(PermissionDeniedError):
        ctx["menu"].portal_menu(forged)


# ----- Quản trị -----------------------------------------------------------------
def test_staff_sees_menu_but_cannot_manage_it(ctx):
    menu, staff = ctx["menu"], ctx["staff"]
    data = menu.manage_menu(staff)
    item = data["items"][0]

    assert data["can_manage"] is False
    assert data["can_prepare"] is True
    assert data["can_collect_payment"] is True
    with pytest.raises(PermissionDeniedError):
        menu.save_item(staff, item.id, category_id=item.category_id, name=item.name, description="",
                       price=1_000, sort_order=0, is_visible=True, is_available=True)
    with pytest.raises(PermissionDeniedError):
        menu.save_category(staff, None, page="FOOD", name="Mới", sort_order=0, is_active=True)


def test_staff_inventory_overview_hides_recipes(ctx):
    class Inventory:
        def __init__(self):
            self.recipe_reads = 0

        def list_ingredients(self, conn, store_id):
            return [{"id": 1, "available": 5}]

        def list_counts(self, conn, store_id):
            return []

        def item_tracking(self, conn, store_id):
            return [{"item_id": 1, "is_stock_tracked": True}]

        def get_recipe(self, conn, item_id):
            self.recipe_reads += 1
            return [{"ingredient_id": 1, "quantity": 2}]

    inventory = Inventory()
    ctx["menu"]._inventory = inventory

    staff_view = ctx["menu"].inventory_overview(ctx["staff"])
    assert staff_view["actor_id"] == ctx["staff"].employee_id
    assert staff_view["ingredients"] == [{"id": 1, "available": 5}]
    assert staff_view["can_manage"] is False
    assert staff_view["can_configure"] is False
    assert staff_view["can_receive"] is False
    assert staff_view["can_count"] is True
    assert staff_view["recipes"] == []
    assert staff_view["tracking"] == {}
    assert inventory.recipe_reads == 0

    manager_view = ctx["menu"].inventory_overview(ctx["manager"])
    assert manager_view["actor_id"] == ctx["manager"].employee_id
    assert manager_view["can_manage"] is True
    assert manager_view["can_configure"] is True
    assert manager_view["can_receive"] is True
    assert manager_view["can_issue"] is True
    assert manager_view["can_approve"] is True
    assert manager_view["recipes"]
    assert inventory.recipe_reads > 0


@pytest.mark.parametrize(
    "permission,operation",
    [
        (Permission.INVENTORY_CONFIGURE, "add"),
        (Permission.INVENTORY_CONFIGURE, "recipe"),
        (Permission.INVENTORY_RECEIVE, "receive"),
    ],
)
def test_inventory_writes_require_their_specific_permission(ctx, monkeypatch,
                                                             permission, operation):
    menu, manager = ctx["menu"], ctx["manager"]
    monkeypatch.setitem(
        ROLE_PERMISSIONS, Role.MANAGER,
        ROLE_PERMISSIONS[Role.MANAGER] - {permission},
    )

    with pytest.raises(PermissionDeniedError):
        if operation == "add":
            menu.add_ingredient(manager, name="Đường", unit="g")
        elif operation == "recipe":
            menu.set_item_recipe(manager, 1, parts=[{"ingredient_id": 1,
                                                     "quantity_per_unit": 1}])
        else:
            menu.receive_ingredient(manager, 1, quantity=1,
                                    reference_code="RC-1", request_id=str(uuid4()))


def test_inventory_overview_reports_independent_capabilities(ctx, monkeypatch):
    monkeypatch.setitem(
        ROLE_PERMISSIONS, Role.MANAGER,
        ROLE_PERMISSIONS[Role.MANAGER] - {Permission.INVENTORY_RECEIVE},
    )
    view = ctx["menu"].inventory_overview(ctx["manager"])

    assert view["can_configure"] is True
    assert view["can_receive"] is False
    assert view["can_manage"] is False


def test_inventory_count_and_manual_movement_permissions(ctx):
    menu = ctx["menu"]
    request_id = str(uuid4())
    with pytest.raises(PermissionDeniedError):
        menu.move_ingredient(ctx["staff"], 1, kind="ISSUE", quantity=1,
                             reference_code="ISS-1", request_id=request_id,
                             note="Hỏng trong kho")
    with pytest.raises(PermissionDeniedError):
        menu.decide_inventory_count(ctx["staff"], 1, approve=True)
    with pytest.raises(ConflictError):
        menu.propose_inventory_count(ctx["staff"], 1, counted_on_hand=1,
                                     reason="Kiểm kê cuối ca", request_id=request_id)


def test_menu_overview_reports_independent_pos_capabilities(ctx, monkeypatch):
    monkeypatch.setitem(
        ROLE_PERMISSIONS, Role.STAFF,
        ROLE_PERMISSIONS[Role.STAFF] - {Permission.POS_PREPARE_ORDERS},
    )
    view = ctx["menu"].manage_menu(ctx["staff"])

    assert view["can_prepare"] is False
    assert view["can_serve"] is True
    assert view["can_collect_payment"] is True


def test_menu_overview_requires_view_permission(ctx, monkeypatch):
    monkeypatch.setitem(
        ROLE_PERMISSIONS, Role.STAFF,
        ROLE_PERMISSIONS[Role.STAFF] - {Permission.POS_VIEW_ORDERS},
    )
    with pytest.raises(PermissionDeniedError):
        ctx["menu"].manage_menu(ctx["staff"])


def test_price_change_is_recorded_in_history_and_audit(ctx):
    menu, manager = ctx["menu"], ctx["manager"]
    item = menu.manage_menu(manager)["items"][0]

    menu.save_item(manager, item.id, category_id=item.category_id, name=item.name, description=item.description,
                   price=item.price + 5_000, sort_order=item.sort_order, is_visible=True, is_available=item.is_available)

    history = menu.item_history(manager, item.id)
    assert history[0].field == MenuChangeField.PRICE
    assert (history[0].old_value, history[0].new_value) == (str(item.price), str(item.price + 5_000))
    audit = ctx["bundle"].menu._p1.data.management_audit
    assert audit[-1][2:] == ("MENU_ITEM_SAVE", item.id)


@pytest.mark.parametrize("price", [999, 10_000_001, 25_000.5, "25000", True])
def test_invalid_price_is_rejected(ctx, price):
    item = ctx["menu"].manage_menu(ctx["manager"])["items"][0]
    with pytest.raises(ValidationError):
        ctx["menu"].save_item(ctx["manager"], item.id, category_id=item.category_id, name=item.name,
                              description="", price=price, sort_order=0, is_visible=True, is_available=True)


def test_duplicate_item_name_in_same_store_is_rejected(ctx):
    menu, manager = ctx["menu"], ctx["manager"]
    first, second = menu.manage_menu(manager)["items"][:2]

    with pytest.raises(ConflictError):
        menu.save_item(manager, second.id, category_id=second.category_id, name=first.name.upper(),
                       description="", price=second.price, sort_order=0, is_visible=True, is_available=True)


def test_staff_serves_order_only_once(ctx):
    menu = ctx["menu"]
    item = find(menu.portal_menu(ctx["player"]), "Mì xào trứng")
    order = menu.place_order(ctx["player"], [{"item_id": item.id, "quantity": 1}])

    assert [o.id for o in menu.list_orders(ctx["staff"])] == [order.id]
    served = menu.finish_order(ctx["staff"], order.id, "SERVED")
    assert served.status == MenuOrderStatus.SERVED and served.handled_by == ctx["staff"].employee_id
    with pytest.raises(ConflictError):
        menu.finish_order(ctx["manager"], order.id, "CANCELLED")
    assert menu.list_orders(ctx["staff"]) == []


def test_pos_order_moves_through_preparing_served_and_paid(ctx):
    menu = ctx["menu"]
    item = find(menu.portal_menu(ctx["player"]), "Mì xào trứng")
    order = menu.place_order(ctx["player"], [{"item_id": item.id, "quantity": 1}])

    preparing = menu.finish_order(ctx["staff"], order.id, "PREPARING")
    assert preparing.status == MenuOrderStatus.PREPARING
    served = menu.finish_order(ctx["staff"], order.id, "SERVED")
    assert served.status == MenuOrderStatus.SERVED
    paid = menu.pay_order(ctx["staff"], order.id, "CASH")
    assert paid.status == MenuOrderStatus.PAID
    assert paid.payment_method.value == "CASH" and paid.paid_by == ctx["staff"].employee_id
    with pytest.raises(ConflictError):
        menu.pay_order(ctx["manager"], order.id, "TRANSFER")


def test_order_lifecycle_creates_idempotent_customer_notifications(ctx):
    menu = ctx["menu"]
    item = find(menu.portal_menu(ctx["player"]), "Mì xào trứng")
    order = menu.place_order(ctx["player"], [{"item_id": item.id, "quantity": 1}])
    menu.finish_order(ctx["staff"], order.id, "PREPARING")
    menu.finish_order(ctx["staff"], order.id, "SERVED")
    menu.pay_order(ctx["staff"], order.id, "CASH")

    notices = ctx["bundle"].portal.notifications(ctx["player"])
    lifecycle = [
        notice for notice in notices["items"]
        if notice["key"].startswith(f"menu-order:{order.id}:")
    ]
    assert {notice["kind"] for notice in lifecycle} == {
        "MENU_ORDER_NEW",
        "MENU_ORDER_PREPARING",
        "MENU_ORDER_SERVED",
        "MENU_ORDER_PAID",
    }
    assert len({notice["key"] for notice in lifecycle}) == 4
    assert all(not notice["read"] for notice in lifecycle)

    key = next(notice["key"] for notice in lifecycle if notice["kind"] == "MENU_ORDER_PAID")
    ctx["bundle"].portal.mark_notifications_read(ctx["player"], [key])
    refreshed = ctx["bundle"].portal.notifications(ctx["player"])["items"]
    assert next(notice for notice in refreshed if notice["key"] == key)["read"] is True


def test_cancelled_order_creates_warning_notification(ctx):
    menu = ctx["menu"]
    item = find(menu.portal_menu(ctx["player"]), "Mì xào trứng")
    order = menu.place_order(ctx["player"], [{"item_id": item.id, "quantity": 1}])
    menu.finish_order(ctx["staff"], order.id, "CANCELLED", reason="Khách đổi ý")

    notice = next(
        item for item in ctx["bundle"].portal.notifications(ctx["player"])["items"]
        if item["key"] == f"menu-order:{order.id}:CANCELLED"
    )
    assert notice["kind"] == "MENU_ORDER_CANCELLED"
    assert notice["severity"] == "warning"


def test_order_notification_repository_is_idempotent(ctx):
    menu = ctx["menu"]
    item = find(menu.portal_menu(ctx["player"]), "Mì xào trứng")
    order = menu.place_order(ctx["player"], [{"item_id": item.id, "quantity": 1}])
    repository = menu._repo

    with repository.transaction() as conn:
        repository.record_order_notification(
            conn, order, MenuOrderStatus.NEW, order.created_at,
        )

    matching = [
        event for event in ctx["bundle"].portal._repo.order_notifications
        if event["notification_key"] == f"menu-order:{order.id}:NEW"
    ]
    assert len(matching) == 1


def test_cancel_preparing_requires_reason(ctx):
    menu = ctx["menu"]
    item = find(menu.portal_menu(ctx["player"]), "Mì xào trứng")
    order = menu.place_order(ctx["player"], [{"item_id": item.id, "quantity": 1}])
    menu.finish_order(ctx["staff"], order.id, "PREPARING")

    with pytest.raises(ValidationError) as exc:
        menu.finish_order(ctx["staff"], order.id, "CANCELLED")
    assert "reason" in exc.value.field_errors
    assert menu.list_orders(ctx["staff"], "PREPARING")[0].id == order.id

    cancelled = menu.finish_order(
        ctx["staff"], order.id, "CANCELLED", reason="Khách đổi ý",
    )
    assert cancelled.status is MenuOrderStatus.CANCELLED
    assert cancelled.cancel_reason == "Khách đổi ý"


def test_cancel_reason_only_applies_to_cancellation(ctx):
    menu = ctx["menu"]
    item = find(menu.portal_menu(ctx["player"]), "Mì xào trứng")
    order = menu.place_order(ctx["player"], [{"item_id": item.id, "quantity": 1}])

    preparing = menu.finish_order(ctx["staff"], order.id, "PREPARING", reason="Bỏ qua")
    assert preparing.cancel_reason is None

    cancelled = menu.finish_order(ctx["staff"], order.id, "CANCELLED", reason="  Khách đổi ý  ")
    assert cancelled.cancel_reason == "Khách đổi ý"


def test_pos_order_cannot_pay_before_served_or_cancel_after_served(ctx):
    menu = ctx["menu"]
    item = find(menu.portal_menu(ctx["player"]), "Mì xào trứng")
    order = menu.place_order(ctx["player"], [{"item_id": item.id, "quantity": 1}])
    with pytest.raises(ConflictError):
        menu.pay_order(ctx["staff"], order.id, "CASH")
    menu.finish_order(ctx["staff"], order.id, "SERVED")
    with pytest.raises(ConflictError):
        menu.finish_order(ctx["manager"], order.id, "CANCELLED")


@pytest.mark.parametrize(
    "status,permission",
    [
        ("PREPARING", Permission.POS_PREPARE_ORDERS),
        ("SERVED", Permission.POS_SERVE_ORDERS),
        ("CANCELLED", Permission.POS_CANCEL_ORDERS),
    ],
)
def test_pos_status_change_requires_its_own_permission(ctx, monkeypatch, status, permission):
    menu = ctx["menu"]
    item = find(menu.portal_menu(ctx["player"]), "Coca")
    order = menu.place_order(ctx["player"], [{"item_id": item.id, "quantity": 1}])
    monkeypatch.setitem(
        ROLE_PERMISSIONS, Role.STAFF, ROLE_PERMISSIONS[Role.STAFF] - {permission}
    )

    with pytest.raises(PermissionDeniedError):
        menu.finish_order(ctx["staff"], order.id, status)

    assert menu._repo.get_order(None, order.id).status == MenuOrderStatus.NEW


def test_pos_payment_requires_collect_permission(ctx, monkeypatch):
    menu = ctx["menu"]
    item = find(menu.portal_menu(ctx["player"]), "Coca")
    order = menu.place_order(ctx["player"], [{"item_id": item.id, "quantity": 1}])
    menu.finish_order(ctx["staff"], order.id, "SERVED")
    monkeypatch.setitem(
        ROLE_PERMISSIONS,
        Role.STAFF,
        ROLE_PERMISSIONS[Role.STAFF] - {Permission.POS_COLLECT_PAYMENT},
    )

    with pytest.raises(PermissionDeniedError):
        menu.pay_order(ctx["staff"], order.id, "CASH")

    assert menu._repo.get_order(None, order.id).status == MenuOrderStatus.SERVED


def test_failed_save_rolls_back_menu_changes(ctx, monkeypatch):
    menu, manager = ctx["menu"], ctx["manager"]
    item = menu.manage_menu(manager)["items"][0]

    def broken_audit(*_args):
        raise RuntimeError("audit lỗi")

    monkeypatch.setattr(menu._p1, "audit", broken_audit)
    with pytest.raises(RuntimeError):
        menu.save_item(manager, item.id, category_id=item.category_id, name=item.name, description="",
                       price=item.price + 1_000, sort_order=0, is_visible=True, is_available=True)

    monkeypatch.undo()
    assert next(i for i in menu.manage_menu(manager)["items"] if i.id == item.id).price == item.price
    assert menu.item_history(manager, item.id) == []
