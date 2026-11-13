"""Lịch sử khuyến mãi POS (migration 020) và thống kê giảm giá trên MySQL thật; rollback sau mỗi test."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from mysql.connector import Error as MySQLError

from cyberhub_manager.domain.menu import MenuOrderLine, MenuOrderStatus, MenuPage
from cyberhub_manager.repositories.menu_repository import MenuRepository
from cyberhub_manager.services.pos_pricing import price_order

NOW = datetime.now(timezone.utc).replace(microsecond=0)


def _execute(conn, sql, params=()):
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        return cursor.lastrowid
    finally:
        cursor.close()


@pytest.fixture
def promo_db(db_conn, test_scenario):
    rows = test_scenario(db_conn)
    repo = MenuRepository()
    promo_id = repo.save_promotion(db_conn, rows.store_id, None, f"P{rows.token}".upper(), "TIER_PERCENT", None,
                                   10, "BRONZE", NOW - timedelta(hours=1), NOW + timedelta(days=30), True)
    return db_conn, repo, rows, promo_id


def test_changes_are_stored_as_json_and_listed_newest_first(promo_db):
    conn, repo, rows, promo_id = promo_db
    repo.record_promotion_change(conn, promo_id, rows.employee_id, "CREATE", {"value": [None, 10]})
    repo.record_promotion_change(conn, promo_id, rows.employee_id, "UPDATE", {"value": [10, 15]})

    history = repo.promotion_changes(conn, promo_id)

    assert [h["action"] for h in history] == ["UPDATE", "CREATE"]
    assert history[0]["changes"] == {"value": [10, 15]}
    assert history[0]["employee_name"] == "Test employee" and history[0]["created_at"].tzinfo is not None


def test_history_rejects_unknown_action_and_missing_promotion(promo_db):
    conn, repo, rows, promo_id = promo_db
    with pytest.raises(MySQLError):
        repo.record_promotion_change(conn, promo_id, rows.employee_id, "DELETE", {})
    with pytest.raises(MySQLError):
        repo.record_promotion_change(conn, promo_id + 10_000_000, rows.employee_id, "CREATE", {})


def test_switch_updates_only_the_owning_store(promo_db):
    conn, repo, rows, promo_id = promo_db

    repo.set_promotion_active(conn, rows.store_id + 10_000_000, promo_id, False)  # sai cơ sở: không đổi
    assert repo.get_promotion(conn, promo_id)["is_active"] == 1
    repo.set_promotion_active(conn, rows.store_id, promo_id, False)
    assert repo.get_promotion(conn, promo_id)["is_active"] == 0


def test_usage_counts_discount_except_cancelled_orders(promo_db):
    conn, repo, rows, promo_id = promo_db
    category = repo.insert_category(conn, store_id=rows.store_id, page=MenuPage.DRINK, name="Nước", sort_order=0,
                                    is_active=True)
    item = repo.insert_item(conn, store_id=rows.store_id, category_id=category, name="Coca", description="",
                            price=10_000, sort_order=0, is_visible=True, is_available=True)
    session_id = _execute(
        conn,
        "INSERT INTO usage_sessions (code, customer_id, machine_id, opened_by, hourly_rate)"
        " VALUES (%s, %s, %s, %s, %s)",
        (f"SS-{rows.token}", rows.customer_id, rows.machine_id, rows.employee_id, rows.hourly_rate),
    )
    rule = repo.get_promotion(conn, promo_id)
    order_ids = []
    for index in range(2):
        lines = [MenuOrderLine(item, "Coca", 10_000, 2)]
        order_id = repo.insert_order(
            conn, code=f"ORD-{rows.token}{index}", store_id=rows.store_id, account_id=rows.account_id,
            session_id=session_id, machine_id=rows.machine_id, note="", lines=lines)
        repo.save_order_pricing(conn, order_id, price_order(lines, [rule], "BRONZE"))
        order_ids.append(order_id)

    assert repo.promotion_usage(conn, rows.store_id) == {promo_id: dict(orders=2, discount=4_000)}
    repo.finish_order(conn, order_ids[0], MenuOrderStatus.CANCELLED, rows.employee_id)
    assert repo.promotion_usage(conn, rows.store_id) == {promo_id: dict(orders=1, discount=2_000)}
    assert repo.promotion_usage(conn, rows.store_id + 10_000_000) == {}


def test_json_column_round_trip_keeps_vietnamese_text(promo_db):
    conn, repo, rows, promo_id = promo_db
    repo.record_promotion_change(conn, promo_id, rows.employee_id, "UPDATE", {"code": ["ƯU_ĐÃI", "ƯU_ĐÃI_MỚI"]})

    [entry] = repo.promotion_changes(conn, promo_id)

    assert entry["changes"]["code"] == ["ƯU_ĐÃI", "ƯU_ĐÃI_MỚI"]
    assert json.dumps(entry["changes"], ensure_ascii=False).count("Ư") == 2
