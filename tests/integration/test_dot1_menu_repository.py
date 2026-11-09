"""Đợt 1 — MenuRepository và ràng buộc của migration 007 trên MySQL thật.

Mọi dữ liệu nằm trong transaction của `db_conn` và bị rollback sau test.
"""

import pytest
from mysql.connector import Error as MySQLError

from cyberhub_manager.domain.menu import MenuChangeField, MenuOrderLine, MenuOrderStatus, MenuPage
from cyberhub_manager.repositories.menu_repository import MenuRepository


def _execute(conn, sql, params=()):
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        return cursor.lastrowid
    finally:
        cursor.close()


@pytest.fixture
def menu_db(db_conn, test_scenario):
    rows = test_scenario(db_conn)
    repo = MenuRepository()
    category_id = repo.insert_category(db_conn, store_id=rows.store_id, page=MenuPage.DRINK, name="Trà",
                                       sort_order=0, is_active=True)
    item_id = repo.insert_item(db_conn, store_id=rows.store_id, category_id=category_id, name="Trà đào",
                               description="Size L", price=35_000, sort_order=0, is_visible=True,
                               is_available=True)
    session_id = _execute(
        db_conn,
        "INSERT INTO usage_sessions (code, customer_id, machine_id, opened_by, hourly_rate)"
        " VALUES (%s, %s, %s, %s, %s)",
        (f"SS-{rows.token}", rows.customer_id, rows.machine_id, rows.employee_id, rows.hourly_rate),
    )
    return db_conn, repo, rows, category_id, item_id, session_id


def test_active_session_points_to_store_of_machine(menu_db):
    conn, repo, rows, _, _, session_id = menu_db

    session = repo.active_session(conn, rows.customer_id)

    assert session["session_id"] == session_id
    assert session["store_id"] == rows.store_id
    assert session["machine_id"] == rows.machine_id


def test_order_snapshot_and_single_finish(menu_db):
    conn, repo, rows, _, item_id, session_id = menu_db
    order_id = repo.insert_order(
        conn, code=f"ORD-{rows.token}", store_id=rows.store_id, account_id=rows.account_id,
        session_id=session_id, machine_id=rows.machine_id, note="ít đá",
        lines=[MenuOrderLine(item_id, "Trà đào", 35_000, 2)],
    )

    assert repo.count_open_orders(conn, rows.account_id) == 1
    order = repo.get_order(conn, order_id)
    assert order.total_amount == 70_000 and order.lines[0].quantity == 2
    assert [o.id for o in repo.list_orders(conn, rows.store_id, MenuOrderStatus.NEW)] == [order_id]

    assert repo.finish_order(conn, order_id, MenuOrderStatus.SERVED, rows.employee_id) is True
    assert repo.finish_order(conn, order_id, MenuOrderStatus.CANCELLED, rows.employee_id) is False
    assert repo.get_order(conn, order_id).status == MenuOrderStatus.SERVED


def test_change_history_joins_employee_name(menu_db):
    conn, repo, rows, _, item_id, _ = menu_db
    repo.record_change(conn, item_id=item_id, employee_id=rows.employee_id, field=MenuChangeField.PRICE,
                       old_value="35000", new_value="38000")

    [change] = repo.item_changes(conn, item_id)

    assert change.field == MenuChangeField.PRICE
    assert change.employee_name == "Test employee"


def test_image_is_stored_and_versioned(menu_db):
    conn, repo, _, _, item_id, _ = menu_db
    repo.save_image(conn, item_id, b"webp-bytes", "a" * 64)
    repo.save_image(conn, item_id, b"webp-bytes-2", "b" * 64)  # upsert, không tạo dòng thứ hai

    assert repo.get_image(conn, item_id) == b"webp-bytes-2"
    assert repo.get_item(conn, item_id).image_version == "b" * 12


@pytest.mark.parametrize(
    ("sql", "params"),
    [
        # Giá ngoài khoảng 1.000–10.000.000 bị CHECK chặn.
        ("UPDATE menu_items SET price = %s WHERE id = %s", (999, "{item}")),
        # Trang menu chỉ FOOD/DRINK.
        ("UPDATE menu_categories SET page = %s WHERE id = %s", ("SNACK", "{category}")),
    ],
)
def test_check_constraints_reject_invalid_values(menu_db, sql, params):
    conn, _, _, category_id, item_id, _ = menu_db
    values = tuple(item_id if p == "{item}" else category_id if p == "{category}" else p for p in params)

    with pytest.raises(MySQLError):
        _execute(conn, sql, values)


def test_quantity_above_limit_is_rejected(menu_db):
    conn, repo, rows, _, item_id, session_id = menu_db

    with pytest.raises(MySQLError):
        repo.insert_order(
            conn, code=f"ORD-Q{rows.token}", store_id=rows.store_id, account_id=rows.account_id,
            session_id=session_id, machine_id=rows.machine_id, note="",
            lines=[MenuOrderLine(item_id, "Trà đào", 35_000, 21)],
        )
