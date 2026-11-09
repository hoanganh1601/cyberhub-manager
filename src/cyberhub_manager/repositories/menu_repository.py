"""Đợt 1 — Truy cập dữ liệu menu và yêu cầu gọi món (MySQL). Không tự commit."""

from __future__ import annotations

from datetime import timezone
from typing import Any

from cyberhub_manager.domain.menu import (
    MenuCategory,
    MenuChangeField,
    MenuItem,
    MenuItemChange,
    MenuOrder,
    MenuOrderLine,
    MenuOrderStatus,
    MenuPage,
)
from cyberhub_manager.repositories.p1_repository import execute, rows

_ITEM_SELECT = """
    SELECT i.id, i.store_id, i.category_id, i.name, i.description, i.price, i.sort_order,
           i.is_visible, i.is_available, i.updated_at, LEFT(img.digest, 12) AS image_version
    FROM menu_items AS i
    LEFT JOIN menu_item_images AS img ON img.item_id = i.id
"""

_ORDER_SELECT = """
    SELECT o.id, o.code, o.store_id, o.account_id, c.full_name AS customer_name,
           m.code AS machine_code, o.status, o.total_amount, o.note, o.created_at, o.handled_by
    FROM menu_orders AS o
    JOIN accounts AS a ON a.id = o.account_id
    JOIN customers AS c ON c.id = a.customer_id
    JOIN machines AS m ON m.id = o.machine_id
"""


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def _category(row: dict) -> MenuCategory:
    return MenuCategory(
        id=int(row["id"]),
        store_id=int(row["store_id"]),
        page=MenuPage(row["page"]),
        name=row["name"],
        sort_order=int(row["sort_order"]),
        is_active=bool(row["is_active"]),
    )


def _item(row: dict) -> MenuItem:
    return MenuItem(
        id=int(row["id"]),
        store_id=int(row["store_id"]),
        category_id=int(row["category_id"]),
        name=row["name"],
        description=row["description"],
        price=int(row["price"]),
        sort_order=int(row["sort_order"]),
        is_visible=bool(row["is_visible"]),
        is_available=bool(row["is_available"]),
        image_version=row["image_version"],
        updated_at=_utc(row["updated_at"]),
    )


class MenuRepository:
    # ----- Nhóm món --------------------------------------------------------
    def list_categories(self, conn: Any, store_id: int) -> list[MenuCategory]:
        return [
            _category(r)
            for r in rows(
                conn,
                "SELECT id, store_id, page, name, sort_order, is_active FROM menu_categories"
                " WHERE store_id = %s ORDER BY page, sort_order, id",
                (store_id,),
            )
        ]

    def get_category(self, conn: Any, category_id: int, *, lock: bool = False) -> MenuCategory | None:
        result = rows(
            conn,
            "SELECT id, store_id, page, name, sort_order, is_active FROM menu_categories WHERE id = %s"
            + (" FOR UPDATE" if lock else ""),
            (category_id,),
        )
        return _category(result[0]) if result else None

    def insert_category(self, conn: Any, *, store_id, page, name, sort_order, is_active) -> int:
        return int(
            execute(
                conn,
                "INSERT INTO menu_categories (store_id, page, name, sort_order, is_active)"
                " VALUES (%s, %s, %s, %s, %s)",
                (store_id, page.value, name, sort_order, is_active),
            )
        )

    def update_category(self, conn: Any, category_id: int, *, page, name, sort_order, is_active) -> None:
        execute(
            conn,
            "UPDATE menu_categories SET page = %s, name = %s, sort_order = %s, is_active = %s WHERE id = %s",
            (page.value, name, sort_order, is_active, category_id),
        )

    # ----- Món ---------------------------------------------------------------
    def list_items(self, conn: Any, store_id: int) -> list[MenuItem]:
        return [
            _item(r)
            for r in rows(
                conn,
                _ITEM_SELECT + " WHERE i.store_id = %s ORDER BY i.category_id, i.sort_order, i.id",
                (store_id,),
            )
        ]

    def get_item(self, conn: Any, item_id: int, *, lock: bool | str = False) -> MenuItem | None:
        suffix = " FOR UPDATE" if lock is True else " FOR SHARE" if lock == "share" else ""
        result = rows(conn, _ITEM_SELECT + " WHERE i.id = %s" + suffix, (item_id,))
        return _item(result[0]) if result else None

    def insert_item(self, conn: Any, *, store_id, category_id, name, description, price,
                    sort_order, is_visible, is_available) -> int:
        return int(
            execute(
                conn,
                "INSERT INTO menu_items (store_id, category_id, name, description, price, sort_order,"
                " is_visible, is_available) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (store_id, category_id, name, description, price, sort_order, is_visible, is_available),
            )
        )

    def update_item(self, conn: Any, item_id: int, *, category_id, name, description, price,
                    sort_order, is_visible, is_available) -> None:
        execute(
            conn,
            "UPDATE menu_items SET category_id = %s, name = %s, description = %s, price = %s,"
            " sort_order = %s, is_visible = %s, is_available = %s WHERE id = %s",
            (category_id, name, description, price, sort_order, is_visible, is_available, item_id),
        )

    def set_item_available(self, conn: Any, item_id: int, available: bool) -> None:
        execute(conn, "UPDATE menu_items SET is_available = %s WHERE id = %s", (available, item_id))

    # ----- Ảnh ---------------------------------------------------------------
    def save_image(self, conn: Any, item_id: int, data: bytes, digest: str) -> None:
        execute(
            conn,
            "INSERT INTO menu_item_images (item_id, image_data, digest) VALUES (%s, %s, %s)"
            " ON DUPLICATE KEY UPDATE image_data = VALUES(image_data), digest = VALUES(digest)",
            (item_id, data, digest),
        )

    def get_image(self, conn: Any, item_id: int) -> bytes | None:
        result = rows(conn, "SELECT image_data FROM menu_item_images WHERE item_id = %s", (item_id,))
        return bytes(result[0]["image_data"]) if result else None

    # ----- Lịch sử thay đổi -----------------------------------------------------
    def record_change(self, conn: Any, *, item_id, employee_id, field: MenuChangeField,
                      old_value, new_value) -> None:
        execute(
            conn,
            "INSERT INTO menu_item_changes (item_id, employee_id, field, old_value, new_value)"
            " VALUES (%s, %s, %s, %s, %s)",
            (item_id, employee_id, field.value, old_value, new_value),
        )

    def item_changes(self, conn: Any, item_id: int, limit: int = 50) -> list[MenuItemChange]:
        return [
            MenuItemChange(
                item_id=int(r["item_id"]),
                employee_id=int(r["employee_id"]),
                employee_name=r["employee_name"],
                field=MenuChangeField(r["field"]),
                old_value=r["old_value"],
                new_value=r["new_value"],
                created_at=_utc(r["created_at"]),
            )
            for r in rows(
                conn,
                "SELECT h.item_id, h.employee_id, e.full_name AS employee_name, h.field, h.old_value,"
                " h.new_value, h.created_at FROM menu_item_changes AS h"
                " JOIN employees AS e ON e.id = h.employee_id"
                " WHERE h.item_id = %s ORDER BY h.created_at DESC, h.id DESC LIMIT %s",
                (item_id, limit),
            )
        ]

    # ----- Phiên đang chơi của khách --------------------------------------------
    def active_session(self, conn: Any, customer_id: int) -> dict | None:
        """Phiên ACTIVE (cột sinh active_customer_id) và cửa hàng của máy đang dùng."""
        result = rows(
            conn,
            "SELECT s.id AS session_id, m.id AS machine_id, m.code AS machine_code, m.store_id"
            " FROM usage_sessions AS s JOIN machines AS m ON m.id = s.machine_id"
            " WHERE s.active_customer_id = %s",
            (customer_id,),
        )
        return dict(result[0]) if result else None

    # ----- Yêu cầu gọi món --------------------------------------------------------
    def count_open_orders(self, conn: Any, account_id: int) -> int:
        result = rows(
            conn,
            "SELECT COUNT(*) AS total FROM menu_orders WHERE account_id = %s AND status = 'NEW'",
            (account_id,),
        )
        return int(result[0]["total"])

    def insert_order(self, conn: Any, *, code, store_id, account_id, session_id, machine_id, note,
                     lines: list[MenuOrderLine]) -> int:
        order_id = int(
            execute(
                conn,
                "INSERT INTO menu_orders (code, store_id, account_id, session_id, machine_id, note, total_amount)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (code, store_id, account_id, session_id, machine_id, note,
                 sum(line.amount for line in lines)),
            )
        )
        for line in lines:
            execute(
                conn,
                "INSERT INTO menu_order_items (order_id, item_id, item_name, unit_price, quantity)"
                " VALUES (%s, %s, %s, %s, %s)",
                (order_id, line.item_id, line.item_name, line.unit_price, line.quantity),
            )
        return order_id

    def _orders(self, conn: Any, where: str, params: tuple) -> list[MenuOrder]:
        heads = rows(conn, _ORDER_SELECT + where, params)
        if not heads:
            return []
        ids = [int(h["id"]) for h in heads]
        placeholders = ", ".join(["%s"] * len(ids))
        line_rows = rows(
            conn,
            "SELECT order_id, item_id, item_name, unit_price, quantity FROM menu_order_items"
            f" WHERE order_id IN ({placeholders}) ORDER BY order_id, item_name",
            tuple(ids),
        )
        lines: dict[int, list[MenuOrderLine]] = {order_id: [] for order_id in ids}
        for r in line_rows:
            lines[int(r["order_id"])].append(
                MenuOrderLine(int(r["item_id"]), r["item_name"], int(r["unit_price"]), int(r["quantity"]))
            )
        return [
            MenuOrder(
                id=int(h["id"]),
                code=h["code"],
                store_id=int(h["store_id"]),
                account_id=int(h["account_id"]),
                customer_name=h["customer_name"],
                machine_code=h["machine_code"],
                status=MenuOrderStatus(h["status"]),
                total_amount=int(h["total_amount"]),
                note=h["note"],
                lines=tuple(lines[int(h["id"])]),
                created_at=_utc(h["created_at"]),
                handled_by=None if h["handled_by"] is None else int(h["handled_by"]),
            )
            for h in heads
        ]

    def list_orders(self, conn: Any, store_id: int, status: MenuOrderStatus | None, limit: int = 100) -> list[MenuOrder]:
        if status is None:
            return self._orders(conn, " WHERE o.store_id = %s ORDER BY o.created_at DESC, o.id DESC LIMIT %s",
                                (store_id, limit))
        return self._orders(
            conn,
            " WHERE o.store_id = %s AND o.status = %s ORDER BY o.created_at, o.id LIMIT %s",
            (store_id, status.value, limit),
        )

    def account_orders(self, conn: Any, account_id: int, limit: int = 5) -> list[MenuOrder]:
        return self._orders(conn, " WHERE o.account_id = %s ORDER BY o.created_at DESC, o.id DESC LIMIT %s",
                            (account_id, limit))

    def get_order(self, conn: Any, order_id: int, *, lock: bool = False) -> MenuOrder | None:
        result = self._orders(conn, " WHERE o.id = %s" + (" FOR UPDATE" if lock else ""), (order_id,))
        return result[0] if result else None

    def finish_order(self, conn: Any, order_id: int, status: MenuOrderStatus, employee_id: int) -> bool:
        """Chỉ đổi được yêu cầu còn NEW; trả False nếu đã có người xử lý trước."""
        return bool(
            execute(
                conn,
                "UPDATE menu_orders SET status = %s, handled_by = %s WHERE id = %s AND status = 'NEW'",
                (status.value, employee_id, order_id),
            )
        )
