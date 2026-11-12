"""Inventory follows POS order transitions atomically on the isolated test DB."""

from uuid import uuid4

import pytest

from cyberhub_manager.domain.exceptions import ConflictError
from cyberhub_manager.domain.menu import MenuOrderLine, MenuOrderStatus, MenuPage
from cyberhub_manager.repositories.inventory_repository import InventoryRepository
from cyberhub_manager.repositories.menu_repository import MenuRepository
from cyberhub_manager.repositories.p1_repository import rows


@pytest.fixture
def stock_order(db_conn, test_scenario):
    scenario = test_scenario(db_conn)
    menu = MenuRepository()
    stock = InventoryRepository()
    category_id = menu.insert_category(
        db_conn, store_id=scenario.store_id, page=MenuPage.DRINK,
        name="Đồ uống kho", sort_order=0, is_active=True,
    )
    item_id = menu.insert_item(
        db_conn, store_id=scenario.store_id, category_id=category_id,
        name="Nước kho", description="", price=10_000,
        sort_order=0, is_visible=True, is_available=True,
    )
    cursor = db_conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO usage_sessions (code, customer_id, machine_id, opened_by, hourly_rate)"
            " VALUES (%s, %s, %s, %s, %s)",
            (f"STOCK-{scenario.token}", scenario.customer_id, scenario.machine_id,
             scenario.employee_id, scenario.hourly_rate),
        )
        session_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO inventory_ingredients"
            " (store_id, code, name, unit, on_hand, reorder_point)"
            " VALUES (%s, %s, %s, 'ml', 100, 20)",
            (scenario.store_id, f"ING-{scenario.token}", "Siro",),
        )
        ingredient_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO menu_item_recipes (item_id, ingredient_id, quantity_per_unit)"
            " VALUES (%s, %s, 30)",
            (item_id, ingredient_id),
        )
        cursor.execute("UPDATE menu_items SET is_stock_tracked = TRUE WHERE id = %s", (item_id,))
    finally:
        cursor.close()

    def create(suffix="1", quantity=2):
        line = MenuOrderLine(item_id, "Nước kho", 10_000, quantity)
        order_id = menu.insert_order(
            db_conn, code=f"ORD-STOCK-{scenario.token}-{suffix}",
            store_id=scenario.store_id, account_id=scenario.account_id,
            session_id=session_id, machine_id=scenario.machine_id, note="", lines=[line],
        )
        stock.reserve_order(db_conn, order_id, scenario.store_id, scenario.account_id, [line])
        return order_id

    def balance():
        return rows(
            db_conn,
            "SELECT on_hand, reserved FROM inventory_ingredients WHERE id = %s",
            (ingredient_id,),
        )[0]

    return db_conn, scenario, menu, stock, item_id, ingredient_id, create, balance


def test_reservation_snapshots_recipe_and_consumes_once(stock_order):
    conn, actor, menu, stock, item_id, ingredient_id, create, balance = stock_order
    order_id = create()
    assert balance() == {"on_hand": 100, "reserved": 60}

    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE menu_item_recipes SET quantity_per_unit = 10 WHERE item_id = %s",
            (item_id,),
        )
    finally:
        cursor.close()

    order = menu.get_order(conn, order_id, lock=True)
    assert menu.finish_order(conn, order_id, MenuOrderStatus.PREPARING, actor.employee_id)
    stock.transition_order(conn, order, MenuOrderStatus.PREPARING, actor.employee_id)
    assert balance() == {"on_hand": 40, "reserved": 0}

    order = menu.get_order(conn, order_id, lock=True)
    assert menu.finish_order(conn, order_id, MenuOrderStatus.SERVED, actor.employee_id)
    stock.transition_order(conn, order, MenuOrderStatus.SERVED, actor.employee_id)
    assert balance() == {"on_hand": 40, "reserved": 0}
    assert [r["kind"] for r in rows(
        conn, "SELECT kind FROM inventory_movements WHERE order_id = %s ORDER BY id", (order_id,),
    )] == ["RESERVE", "CONSUME"]
    assert rows(
        conn,
        "SELECT quantity FROM menu_order_recipe_snapshots WHERE order_id = %s"
        " AND ingredient_id = %s",
        (order_id, ingredient_id),
    )[0]["quantity"] == 60


def test_shortage_rejects_entire_new_order(stock_order):
    conn, actor, menu, stock, item_id, ingredient_id, create, balance = stock_order
    create()
    cursor = conn.cursor()
    try:
        cursor.execute("SAVEPOINT before_short_order")
        with pytest.raises(ConflictError):
            create(suffix="2")
        cursor.execute("ROLLBACK TO SAVEPOINT before_short_order")
    finally:
        cursor.close()
    assert balance() == {"on_hand": 100, "reserved": 60}
    assert len(rows(conn, "SELECT id FROM inventory_movements WHERE ingredient_id = %s", (ingredient_id,))) == 1


@pytest.mark.parametrize("target,expected,kind", [
    (MenuOrderStatus.CANCELLED, {"on_hand": 100, "reserved": 0}, "RELEASE"),
    (MenuOrderStatus.PREPARING, {"on_hand": 40, "reserved": 0}, "CONSUME"),
])
def test_new_order_stock_transition(stock_order, target, expected, kind):
    conn, actor, menu, stock, _, _, create, balance = stock_order
    order_id = create()
    order = menu.get_order(conn, order_id, lock=True)
    assert menu.finish_order(conn, order_id, target, actor.employee_id)
    stock.transition_order(conn, order, target, actor.employee_id)
    assert balance() == expected
    assert rows(conn, "SELECT kind FROM inventory_movements WHERE order_id = %s ORDER BY id", (order_id,))[-1]["kind"] == kind
    assert not menu.finish_order(conn, order_id, target, actor.employee_id)


def test_preparing_cancel_records_waste_without_second_debit(stock_order):
    conn, actor, menu, stock, _, _, create, balance = stock_order
    order_id = create()
    for target in (MenuOrderStatus.PREPARING, MenuOrderStatus.CANCELLED):
        order = menu.get_order(conn, order_id, lock=True)
        assert menu.finish_order(
            conn, order_id, target, actor.employee_id,
            reason="Khách hủy sau khi chuẩn bị" if target is MenuOrderStatus.CANCELLED else None,
        )
        stock.transition_order(
            conn, order, target, actor.employee_id,
            reason="Khách hủy sau khi chuẩn bị" if target is MenuOrderStatus.CANCELLED else None,
        )
    assert balance() == {"on_hand": 40, "reserved": 0}
    assert [r["kind"] for r in rows(
        conn, "SELECT kind FROM inventory_movements WHERE order_id = %s ORDER BY id", (order_id,),
    )] == ["RESERVE", "CONSUME", "WASTE"]
    assert rows(
        conn, "SELECT note FROM inventory_movements WHERE order_id = %s AND kind = 'WASTE'",
        (order_id,),
    )[0]["note"] == "Khách hủy sau khi chuẩn bị"
    assert menu.get_order(conn, order_id).cancel_reason == "Khách hủy sau khi chuẩn bị"


def test_manual_issue_respects_reservations_and_retry(stock_order):
    conn, actor, _menu, stock, _item_id, ingredient_id, create, balance = stock_order
    create()
    ingredient = stock.get_ingredient(conn, ingredient_id, lock=True)
    key = f"issue:{uuid4().hex}"
    args = dict(ingredient=ingredient, quantity=40, reference_code="ISS-1",
                note="Xuất cho quầy", employee_id=actor.employee_id,
                idempotency_key=key, kind="ISSUE")
    with pytest.raises(ConflictError):
        stock.manual_movement(conn, **{**args, "quantity": 41})
    assert balance() == {"on_hand": 100, "reserved": 60}
    assert stock.manual_movement(conn, **args) is True
    assert balance() == {"on_hand": 60, "reserved": 60}
    assert stock.manual_movement(conn, **args) is False
    with pytest.raises(ConflictError):
        stock.manual_movement(conn, **{**args, "quantity": 1})
    assert stock.manual_movement(
        conn, ingredient=stock.get_ingredient(conn, ingredient_id, lock=True),
        quantity=10, reference_code="RET-1", note="Trả hàng còn dùng được",
        employee_id=actor.employee_id, idempotency_key=f"return:{uuid4().hex}",
        kind="RETURN",
    ) is True
    assert balance() == {"on_hand": 70, "reserved": 60}


def test_count_approval_rejects_stale_movement_even_when_balance_matches(stock_order):
    conn, actor, _menu, stock, _item_id, ingredient_id, _create, balance = stock_order
    ingredient = stock.get_ingredient(conn, ingredient_id, lock=True)
    count, created = stock.propose_count(
        conn, ingredient=ingredient, counted_on_hand=95,
        reason="Kiểm kê cuối ca", employee_id=actor.employee_id,
        request_id=uuid4().hex,
    )
    assert created is True
    for kind in ("ISSUE", "RETURN"):
        stock.manual_movement(
            conn, ingredient=stock.get_ingredient(conn, ingredient_id, lock=True),
            quantity=1, reference_code=f"{kind}-1", note="Kiểm tra sổ",
            employee_id=actor.employee_id, idempotency_key=f"{kind}:{uuid4().hex}",
            kind=kind,
        )
    assert balance() == {"on_hand": 100, "reserved": 0}
    with pytest.raises(ConflictError):
        stock.decide_count(
            conn, count=stock.get_count(conn, count["id"], lock=True),
            ingredient=stock.get_ingredient(conn, ingredient_id, lock=True),
            employee_id=actor.employee_id, approve=True,
        )
    assert stock.get_count(conn, count["id"])["status"] == "PENDING"


def test_count_approval_records_adjustment_once(stock_order):
    conn, actor, _menu, stock, _item_id, ingredient_id, _create, balance = stock_order
    count, created = stock.propose_count(
        conn, ingredient=stock.get_ingredient(conn, ingredient_id, lock=True),
        counted_on_hand=80, reason="Kiểm kê cuối ca",
        employee_id=actor.employee_id, request_id=uuid4().hex,
    )
    assert created is True
    decided = stock.decide_count(
        conn, count=stock.get_count(conn, count["id"], lock=True),
        ingredient=stock.get_ingredient(conn, ingredient_id, lock=True),
        employee_id=actor.employee_id, approve=True,
    )
    assert decided["status"] == "APPROVED"
    assert balance() == {"on_hand": 80, "reserved": 0}
    assert rows(conn, "SELECT kind, on_hand_delta FROM inventory_movements"
                " WHERE idempotency_key = %s", (f"count:{count['id']}",)) == [
                    {"kind": "ADJUST", "on_hand_delta": -20}
                ]
    with pytest.raises(ConflictError):
        stock.decide_count(
            conn, count=stock.get_count(conn, count["id"], lock=True),
            ingredient=stock.get_ingredient(conn, ingredient_id, lock=True),
            employee_id=actor.employee_id, approve=True,
        )


def test_count_proposal_retry_uses_original_request(stock_order):
    conn, actor, _menu, stock, _item_id, ingredient_id, _create, balance = stock_order
    ingredient = stock.get_ingredient(conn, ingredient_id, lock=True)
    key = uuid4().hex
    args = dict(
        ingredient=ingredient, counted_on_hand=90,
        reason="Kiểm kê cuối ca", employee_id=actor.employee_id,
        request_id=key,
    )
    proposal, created = stock.propose_count(conn, **args)
    assert created is True
    retry, created = stock.propose_count(conn, **args)
    assert created is False
    assert retry["id"] == proposal["id"]
    assert balance() == {"on_hand": 100, "reserved": 0}

    with pytest.raises(ConflictError):
        stock.propose_count(conn, **{**args, "counted_on_hand": 80})
