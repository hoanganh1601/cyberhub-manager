"""Đợt 1 — Nghiệp vụ menu và gọi món (MenuService trên repository bộ nhớ, không cần MySQL).

Dữ liệu demo: `lethibinh` đang có phiên ACTIVE trên máy 2 của cơ sở 1; `nguyenvanan` không chơi.
"""

from datetime import datetime, timezone

import pytest

from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.menu import MAX_OPEN_ORDERS, MenuChangeField, MenuOrderStatus, MenuPage
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
    with pytest.raises(PermissionDeniedError):
        menu.save_item(staff, item.id, category_id=item.category_id, name=item.name, description="",
                       price=1_000, sort_order=0, is_visible=True, is_available=True)
    with pytest.raises(PermissionDeniedError):
        menu.save_category(staff, None, page="FOOD", name="Mới", sort_order=0, is_active=True)


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
