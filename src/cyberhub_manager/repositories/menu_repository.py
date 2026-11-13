"""Đợt 1 — Truy cập dữ liệu menu và yêu cầu gọi món (MySQL). Không tự commit."""

from __future__ import annotations

from datetime import timezone
import json
from uuid import uuid4
from typing import Any

from cyberhub_manager.domain.menu import (
    MenuCategory,
    MenuChangeField,
    MenuItem,
    MenuItemChange,
    MenuOrder,
    MenuOrderLine,
    MenuOrderStatus,
    MenuPaymentMethod,
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
           m.code AS machine_code, o.status, o.total_amount, o.note, o.created_at, o.handled_by,
           o.payment_method, o.paid_at, o.paid_by, o.cancel_reason, o.reservation_expires_at
    FROM menu_orders AS o
    JOIN accounts AS a ON a.id = o.account_id
    JOIN customers AS c ON c.id = a.customer_id
    JOIN machines AS m ON m.id = o.machine_id
"""


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def _db_time(value):
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


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
                     lines: list[MenuOrderLine], expires_at=None) -> int:
        order_id = int(
            execute(
                conn,
                "INSERT INTO menu_orders (code, store_id, account_id, session_id, machine_id, note, total_amount, reservation_expires_at)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (code, store_id, account_id, session_id, machine_id, note,
                 sum(line.amount for line in lines), _db_time(expires_at)),
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

    def list_promotions(self, conn, store_id):
        return rows(conn, "SELECT id,store_id,code,kind,item_id,value,minimum_tier,"
                    "starts_at,ends_at,is_active FROM menu_promotions"
                    " WHERE store_id=%s ORDER BY id DESC", (store_id,))

    def active_promotions(self, conn, store_id, now):
        return rows(conn, "SELECT id,store_id,code,kind,item_id,value,minimum_tier,"
                    "starts_at,ends_at,is_active FROM menu_promotions"
                    " WHERE store_id=%s AND is_active=1 AND starts_at<=%s AND ends_at>%s"
                    " ORDER BY id", (store_id, _db_time(now), _db_time(now)))

    def get_promotion(self, conn, promotion_id):
        found = rows(conn, "SELECT id,store_id,code,kind,item_id,value,minimum_tier,"
                     "starts_at,ends_at,is_active FROM menu_promotions WHERE id=%s", (promotion_id,))
        return found[0] if found else None

    def save_promotion(self, conn, store_id, promotion_id, code, kind, item_id,
                       value, minimum_tier, starts_at, ends_at, is_active):
        values = (code, kind, item_id, value, minimum_tier, _db_time(starts_at),
                  _db_time(ends_at), is_active)
        if promotion_id is None:
            return int(execute(conn, "INSERT INTO menu_promotions"
                " (store_id,code,kind,item_id,value,minimum_tier,starts_at,ends_at,is_active)"
                " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)", (store_id, *values)))
        execute(conn, "UPDATE menu_promotions SET code=%s,kind=%s,item_id=%s,value=%s,"
                "minimum_tier=%s,starts_at=%s,ends_at=%s,is_active=%s"
                " WHERE id=%s AND store_id=%s", (*values, promotion_id, store_id))
        return promotion_id

    def set_promotion_active(self, conn, store_id, promotion_id, is_active):
        execute(conn, "UPDATE menu_promotions SET is_active=%s WHERE id=%s AND store_id=%s",
                (is_active, promotion_id, store_id))

    def record_promotion_change(self, conn, promotion_id, employee_id, action, changes):
        """Ghi một dòng lịch sử; changes là {trường: [giá trị cũ, giá trị mới]}."""
        execute(conn, "INSERT INTO menu_promotion_changes (promotion_id,employee_id,action,changes_json)"
                " VALUES(%s,%s,%s,%s)",
                (promotion_id, employee_id, action, json.dumps(changes, ensure_ascii=False)))

    def promotion_changes(self, conn, promotion_id, limit=50):
        result = []
        for r in rows(conn, "SELECT h.id,h.employee_id,e.full_name AS employee_name,h.action,h.changes_json,"
                      "h.created_at FROM menu_promotion_changes AS h JOIN employees AS e ON e.id=h.employee_id"
                      " WHERE h.promotion_id=%s ORDER BY h.created_at DESC,h.id DESC LIMIT %s",
                      (promotion_id, limit)):
            changes = r["changes_json"]
            if isinstance(changes, (str, bytes, bytearray)):
                changes = json.loads(changes)
            result.append(dict(id=int(r["id"]), employee_id=int(r["employee_id"]),
                               employee_name=r["employee_name"], action=r["action"],
                               changes=changes, created_at=_utc(r["created_at"])))
        return result

    def promotion_usage(self, conn, store_id):
        """Số đơn và tổng tiền đã giảm theo từng ưu đãi (bỏ đơn hủy/hoàn; bỏ đơn mà voucher giảm nhiều hơn)."""
        return {int(r["promotion_id"]): dict(orders=int(r["orders"]), discount=int(r["discount"]))
                for r in rows(conn,
                    "SELECT p.promotion_id, COUNT(*) AS orders, COALESCE(SUM(p.discount_amount),0) AS discount"
                    " FROM menu_order_pricing AS p JOIN menu_orders AS o ON o.id=p.order_id"
                    " WHERE o.store_id=%s AND p.promotion_id IS NOT NULL AND p.discount_amount>0"
                    " AND o.status NOT IN ('CANCELLED','REFUNDED')"
                    " AND COALESCE(JSON_UNQUOTE(JSON_EXTRACT(p.snapshot_json,'$.applied_source')),'')<>'VOUCHER'"
                    " GROUP BY p.promotion_id", (store_id,))}

    def save_order_pricing(self, conn, order_id, pricing):
        execute(conn, "INSERT INTO menu_order_pricing"
                " (order_id,promotion_id,promotion_code,promotion_kind,discount_amount,final_amount,snapshot_json)"
                " VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (order_id, pricing["promotion_id"], pricing["promotion_code"],
                 pricing["promotion_kind"], pricing["discount_amount"],
                 pricing["final_amount"], json.dumps(pricing["snapshot"], default=str, ensure_ascii=False)))

    def apply_voucher_pricing(self, conn, order, voucher_code, discount):
        found = rows(conn, "SELECT snapshot_json FROM menu_order_pricing WHERE order_id=%s FOR UPDATE", (order.id,))
        if found:
            snapshot = found[0]["snapshot_json"]
            if isinstance(snapshot, str):
                snapshot = json.loads(snapshot)
        else:
            snapshot = {"gross_amount": order.total_amount,
                        "lines": [dict(item_id=l.item_id, name=l.item_name,
                                       unit_price=l.unit_price, quantity=l.quantity) for l in order.lines],
                        "rule": None}
        snapshot["voucher"] = {"code": voucher_code, "discount_amount": discount}
        snapshot["applied_source"] = "VOUCHER"
        snapshot["effective_discount_amount"] = discount
        snapshot["final_amount"] = max(0, order.total_amount-discount)
        encoded = json.dumps(snapshot, default=str, ensure_ascii=False)
        if found:
            execute(conn, "UPDATE menu_order_pricing SET final_amount=%s,snapshot_json=%s WHERE order_id=%s",
                    (snapshot["final_amount"], encoded, order.id))
        else:
            execute(conn, "INSERT INTO menu_order_pricing"
                    " (order_id,discount_amount,final_amount,snapshot_json) VALUES(%s,0,%s,%s)",
                    (order.id, snapshot["final_amount"], encoded))

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
        discount_rows = rows(
            conn, "SELECT used_order_id, value FROM customer_vouchers"
                  f" WHERE status = 'USED' AND used_order_id IN ({placeholders})", tuple(ids)
        )
        discounts = {int(r["used_order_id"]): int(r["value"]) for r in discount_rows}
        price_rows = rows(conn,
            "SELECT order_id,promotion_code,discount_amount FROM menu_order_pricing"
            f" WHERE order_id IN ({placeholders})", tuple(ids))
        pricing = {int(r["order_id"]): r for r in price_rows}
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
                payment_method=None if h["payment_method"] is None else MenuPaymentMethod(h["payment_method"]),
                paid_at=_utc(h["paid_at"]),
                paid_by=None if h["paid_by"] is None else int(h["paid_by"]),
                discount_amount=min(int(h["total_amount"]), max(
                    discounts.get(int(h["id"]), 0),
                    int(pricing.get(int(h["id"]), {}).get("discount_amount", 0)))),
                promotion_code=(pricing.get(int(h["id"]), {}).get("promotion_code")
                                if discounts.get(int(h["id"]), 0) <= int(pricing.get(int(h["id"]), {}).get("discount_amount", 0))
                                else None),
                cancel_reason=h["cancel_reason"],
                reservation_expires_at=_utc(h["reservation_expires_at"]),
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

    def pending_holds(self, conn: Any, before_utc, limit=100) -> list[int]:
        return [int(r["id"]) for r in rows(conn,
            "SELECT id FROM menu_orders WHERE status='NEW' AND reservation_expires_at IS NOT NULL"
            " AND reservation_expires_at <= %s ORDER BY reservation_expires_at,id LIMIT %s",
            (_db_time(before_utc), limit))]

    def record_hold_warning(self, conn: Any, order: MenuOrder, created_at) -> bool:
        return bool(execute(conn,
            "INSERT IGNORE INTO customer_notification_events"
            " (notification_key,account_id,store_id,kind,code,amount,created_at)"
            " VALUES(%s,%s,%s,'MENU_ORDER_EXPIRING',%s,%s,%s)",
            (f"menu-order:{order.id}:EXPIRING", order.account_id, order.store_id,
             order.code, max(0, order.total_amount - order.discount_amount), _db_time(created_at))))

    def record_unavailable_notification(self, conn, account_id, store_id, created_at):
        execute(conn, "INSERT INTO customer_notification_events"
            " (notification_key,account_id,store_id,kind,code,amount,created_at)"
            " VALUES(%s,%s,%s,'MENU_ITEM_UNAVAILABLE',%s,0,%s)",
            (f"menu-item-unavailable:{uuid4().hex}", account_id, store_id,
             "MENU", _db_time(created_at)))

    def record_order_notification(
        self,
        conn: Any,
        order: MenuOrder,
        status: MenuOrderStatus,
        created_at,
    ) -> None:
        """Append one idempotent customer event in the order transaction."""
        execute(
            conn,
            "INSERT IGNORE INTO customer_notification_events "
            "(notification_key,account_id,store_id,kind,code,amount,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (
                f"menu-order:{order.id}:{status.value}",
                order.account_id,
                order.store_id,
                f"MENU_ORDER_{status.value}",
                order.code,
                max(0, order.total_amount - order.discount_amount),
                _db_time(created_at),
            ),
        )

    def finish_order(self, conn: Any, order_id: int, status: MenuOrderStatus, employee_id: int,
                     *, reason: str | None = None) -> bool:
        """Đổi trạng thái chuẩn bị/phục vụ/hủy theo điều kiện hiện tại."""
        allowed = {
            MenuOrderStatus.PREPARING: (MenuOrderStatus.NEW,),
            MenuOrderStatus.SERVED: (MenuOrderStatus.NEW, MenuOrderStatus.PREPARING),
            MenuOrderStatus.CANCELLED: (MenuOrderStatus.NEW, MenuOrderStatus.PREPARING),
        }
        previous = allowed.get(status, ())
        placeholders = ",".join(["%s"] * len(previous))
        return bool(
            execute(
                conn,
                f"UPDATE menu_orders SET status = %s, handled_by = %s, cancel_reason = %s"
                f" WHERE id = %s AND status IN ({placeholders})",
                (status.value, employee_id, reason, order_id, *(s.value for s in previous)),
            )
        )

    def pay_order(self, conn: Any, order_id: int, method: MenuPaymentMethod, employee_id: int, paid_at) -> bool:
        return bool(execute(
            conn,
            "UPDATE menu_orders SET status='PAID', payment_method=%s, paid_at=%s, paid_by=%s, handled_by=%s "
            "WHERE id=%s AND status='SERVED' AND payment_method IS NULL",
            (method.value, paid_at, employee_id, employee_id, order_id),
        ))

    def get_reversal(self, conn, order_id, *, lock=False):
        found = rows(conn, "SELECT id,order_id,store_id,requested_by,reason,disposition,status,"
                     "refund_amount,refund_method,refund_reference,decided_by,decided_at"
                     " FROM pos_order_reversals WHERE order_id=%s"
                     + (" FOR UPDATE" if lock else ""), (order_id,))
        return found[0] if found else None

    def list_reversals(self, conn, store_id, status="PENDING"):
        return rows(conn,
            "SELECT id,order_id,store_id,requested_by,reason,disposition,status,refund_amount,"
            "refund_method,refund_reference,decided_by,decided_at FROM pos_order_reversals"
            " WHERE store_id=%s AND status=%s ORDER BY id DESC LIMIT 100", (store_id, status))

    def request_reversal(self, conn, order, actor_id, reason, disposition):
        return int(execute(conn,
            "INSERT INTO pos_order_reversals (order_id,store_id,requested_by,reason,disposition)"
            " VALUES(%s,%s,%s,%s,%s)",
            (order.id, order.store_id, actor_id, reason, disposition)))

    def decide_reversal(self, conn, reversal_id, actor_id, now, approved, refund_amount,
                        refund_method=None, refund_reference=None):
        return bool(execute(conn,
            "UPDATE pos_order_reversals SET status=%s,decided_by=%s,decided_at=%s,"
            "refund_amount=%s,refund_method=%s,refund_reference=%s"
            " WHERE id=%s AND status='PENDING'",
            ("APPROVED" if approved else "REJECTED", actor_id, _db_time(now),
             refund_amount if approved else 0, refund_method, refund_reference, reversal_id)))

    def set_reversed_status(self, conn, order, target, employee_id, reason):
        return bool(execute(conn,
            "UPDATE menu_orders SET status=%s,handled_by=%s,cancel_reason=%s WHERE id=%s AND status=%s",
            (target.value, employee_id, reason, order.id, order.status.value)))

    def paid_order_report(self, conn: Any, store_id: int, start_utc, before_utc):
        """Paid POS revenue by Vietnam date, net of redeemed food vouchers."""
        bounds = (store_id, start_utc.replace(tzinfo=None), before_utc.replace(tzinfo=None))
        days = rows(conn, """
            SELECT DATE(DATE_ADD(o.paid_at, INTERVAL 7 HOUR)) AS local_day,
                   COUNT(*) AS order_count,
                   SUM(o.total_amount - LEAST(o.total_amount,
                       GREATEST(COALESCE(v.value, 0), COALESCE(mp.discount_amount, 0)))) AS revenue
            FROM menu_orders AS o
            LEFT JOIN customer_vouchers AS v ON v.used_order_id = o.id AND v.status = 'USED'
            LEFT JOIN menu_order_pricing AS mp ON mp.order_id = o.id
            WHERE o.store_id = %s AND o.status IN ('PAID','REFUNDED')
              AND o.paid_at >= %s AND o.paid_at < %s
            GROUP BY local_day ORDER BY local_day
        """, bounds)
        refunds = rows(conn, """
            SELECT DATE(DATE_ADD(decided_at, INTERVAL 7 HOUR)) AS local_day,
                   COUNT(*) AS refund_count, SUM(refund_amount) AS refund_total
            FROM pos_order_reversals
            WHERE store_id=%s AND status='APPROVED' AND refund_amount>0
              AND decided_at >= %s AND decided_at < %s
            GROUP BY local_day ORDER BY local_day
        """, bounds)
        top = rows(conn, """
            SELECT l.item_id, i.name, SUM(l.quantity) AS quantity
            FROM menu_orders AS o
            JOIN menu_order_items AS l ON l.order_id = o.id
            JOIN menu_items AS i ON i.id = l.item_id
            WHERE o.store_id = %s AND o.status = 'PAID'
              AND o.paid_at >= %s AND o.paid_at < %s
            GROUP BY l.item_id, i.name
            ORDER BY quantity DESC, name, l.item_id LIMIT 5
        """, bounds)
        by_day = {d["local_day"]: dict(date=d["local_day"], order_count=int(d["order_count"]),
                                     revenue=int(d["revenue"]), refund_count=0) for d in days}
        for refunded in refunds:
            day = by_day.setdefault(refunded["local_day"],
                                    dict(date=refunded["local_day"], order_count=0,
                                         revenue=0, refund_count=0))
            day["revenue"] -= int(refunded["refund_total"])
            day["refund_count"] = int(refunded["refund_count"])
        return dict(days=[by_day[day] for day in sorted(by_day)],
                    top_items=[dict(item_id=int(i["item_id"]), name=i["name"],
                                    quantity=int(i["quantity"])) for i in top])
