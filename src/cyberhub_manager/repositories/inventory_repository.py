"""Transactional POS stock reservations and immutable inventory movements."""

from collections import defaultdict

from cyberhub_manager.domain.exceptions import ConflictError
from cyberhub_manager.repositories.p1_repository import execute, rows


class InventoryRepository:
    def list_counts(self, conn, store_id):
        return rows(
            conn,
            "SELECT id, store_id, ingredient_id, expected_on_hand, expected_reserved,"
            " expected_movement_id,"
            " counted_on_hand, proposed_by, decided_by, status, reason, created_at,"
            " decided_at FROM inventory_counts WHERE store_id = %s AND status = 'PENDING'"
            " ORDER BY created_at DESC, id DESC LIMIT 100",
            (store_id,),
        )

    def get_count(self, conn, count_id, *, lock=False):
        result = rows(
            conn,
            "SELECT id, store_id, ingredient_id, request_id, expected_on_hand,"
            " expected_reserved, expected_movement_id, counted_on_hand,"
            " proposed_by, decided_by, status, reason"
            " FROM inventory_counts WHERE id = %s" + (" FOR UPDATE" if lock else ""),
            (count_id,),
        )
        return result[0] if result else None

    def propose_count(self, conn, *, ingredient, counted_on_hand, reason, employee_id,
                      request_id):
        existing = rows(
            conn,
            "SELECT id FROM inventory_counts WHERE request_id = %s FOR UPDATE",
            (request_id,),
        )
        if existing:
            # The employee lookup may already have opened a REPEATABLE READ
            # snapshot. Read the existing proposal from the current version.
            proposal = self.get_count(conn, existing[0]["id"], lock=True)
            if (proposal["ingredient_id"], proposal["store_id"],
                    proposal["counted_on_hand"], proposal["reason"],
                    proposal["proposed_by"]) != (
                    ingredient["id"], ingredient["store_id"], counted_on_hand,
                    reason, employee_id):
                raise ConflictError("Mã yêu cầu kiểm kê đã dùng cho phiếu khác")
            return proposal, False
        if counted_on_hand < ingredient["reserved"]:
            raise ConflictError("Số đếm thấp hơn lượng đã giữ cho đơn")
        count_id = execute(
            conn,
            "INSERT INTO inventory_counts (store_id, ingredient_id, request_id,"
            " expected_on_hand, expected_reserved, expected_movement_id,"
            " counted_on_hand, proposed_by, reason)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (ingredient["store_id"], ingredient["id"], request_id,
             ingredient["on_hand"], ingredient["reserved"],
             self._last_movement_id(conn, ingredient["id"]), counted_on_hand,
             employee_id, reason),
        )
        return self.get_count(conn, count_id), True

    def decide_count(self, conn, *, count, ingredient, employee_id, approve):
        if count["status"] != "PENDING":
            raise ConflictError("Phiếu kiểm kê đã được xử lý")
        if approve:
            if (ingredient["on_hand"], ingredient["reserved"]) != (
                    count["expected_on_hand"], count["expected_reserved"]):
                raise ConflictError("Tồn kho đã thay đổi; cần kiểm kê lại")
            if self._last_movement_id(conn, ingredient["id"]) != count["expected_movement_id"]:
                raise ConflictError("Tồn kho đã phát sinh giao dịch; cần kiểm kê lại")
            target = count["counted_on_hand"]
            if target < ingredient["reserved"]:
                raise ConflictError("Số đếm thấp hơn lượng đã giữ cho đơn")
            delta = target - ingredient["on_hand"]
            if delta:
                if execute(
                    conn,
                    "UPDATE inventory_ingredients SET on_hand = on_hand + %s"
                    " WHERE id = %s AND store_id = %s AND on_hand = %s"
                    " AND reserved = %s AND on_hand + %s >= reserved",
                    (delta, ingredient["id"], ingredient["store_id"],
                     ingredient["on_hand"], ingredient["reserved"], delta),
                ) != 1:
                    raise ConflictError("Tồn kho vừa thay đổi")
                execute(
                    conn,
                    "INSERT INTO inventory_movements (store_id, ingredient_id, employee_id,"
                    " kind, quantity, on_hand_delta, reserved_delta, idempotency_key, note)"
                    " VALUES (%s, %s, %s, 'ADJUST', %s, %s, 0, %s, %s)",
                    (ingredient["store_id"], ingredient["id"], employee_id,
                     abs(delta), delta, f"count:{count['id']}", count["reason"]),
                )
        if execute(
            conn,
            "UPDATE inventory_counts SET status = %s, decided_by = %s,"
            " decided_at = UTC_TIMESTAMP() WHERE id = %s AND status = 'PENDING'",
            ("APPROVED" if approve else "REJECTED", employee_id, count["id"]),
        ) != 1:
            raise ConflictError("Phiếu kiểm kê vừa được xử lý")
        return self.get_count(conn, count["id"])

    def _last_movement_id(self, conn, ingredient_id):
        # A locking read sees the latest committed movement under MySQL's
        # default REPEATABLE READ isolation, even after an earlier plain SELECT.
        result = rows(
            conn,
            "SELECT id AS last_id FROM inventory_movements"
            " WHERE ingredient_id = %s ORDER BY id DESC LIMIT 1 FOR UPDATE",
            (ingredient_id,),
        )
        return int(result[0]["last_id"]) if result else 0

    def manual_movement(self, conn, *, ingredient, quantity, reference_code, note,
                        employee_id, idempotency_key, kind):
        existing = rows(
            conn,
            "SELECT store_id, ingredient_id, kind, quantity, reference_code, note, employee_id"
            " FROM inventory_movements WHERE idempotency_key = %s FOR UPDATE",
            (idempotency_key,),
        )
        if existing:
            row = existing[0]
            if (row["store_id"], row["ingredient_id"], row["kind"], row["quantity"],
                    row["reference_code"], row["note"], row["employee_id"]) != (
                    ingredient["store_id"], ingredient["id"], kind, quantity,
                    reference_code, note, employee_id):
                raise ConflictError("Mã yêu cầu kho đã dùng cho giao dịch khác")
            return False
        delta = -quantity if kind == "ISSUE" else quantity
        if kind == "ISSUE" and ingredient["available"] < quantity:
            raise ConflictError("Tồn khả dụng không đủ để xuất kho")
        if execute(
            conn,
            "UPDATE inventory_ingredients SET on_hand = on_hand + %s"
            " WHERE id = %s AND store_id = %s AND on_hand + %s >= reserved",
            (delta, ingredient["id"], ingredient["store_id"], delta),
        ) != 1:
            raise ConflictError("Tồn kho vừa thay đổi")
        execute(
            conn,
            "INSERT INTO inventory_movements (store_id, ingredient_id, employee_id,"
            " kind, quantity, on_hand_delta, reserved_delta, idempotency_key,"
            " reference_code, note) VALUES (%s, %s, %s, %s, %s, %s, 0, %s, %s, %s)",
            (ingredient["store_id"], ingredient["id"], employee_id, kind,
             quantity, delta, idempotency_key, reference_code, note),
        )
        return True

    def item_tracking(self, conn, store_id):
        return rows(
            conn,
            "SELECT id AS item_id, is_stock_tracked FROM menu_items WHERE store_id = %s",
            (store_id,),
        )

    def list_ingredients(self, conn, store_id):
        return rows(
            conn,
            "SELECT id, store_id, code, name, unit, on_hand, reserved,"
            " on_hand - reserved AS available, reorder_point, is_active"
            " FROM inventory_ingredients WHERE store_id = %s ORDER BY name, id",
            (store_id,),
        )

    def get_ingredient(self, conn, ingredient_id, *, lock=False):
        result = rows(
            conn,
            "SELECT id, store_id, code, name, unit, on_hand, reserved,"
            " on_hand - reserved AS available, reorder_point, is_active"
            " FROM inventory_ingredients WHERE id = %s"
            + (" FOR UPDATE" if lock else ""),
            (ingredient_id,),
        )
        return result[0] if result else None

    def create_ingredient(self, conn, *, store_id, code, name, unit, reorder_point):
        return execute(
            conn,
            "INSERT INTO inventory_ingredients"
            " (store_id, code, name, unit, reorder_point) VALUES (%s, %s, %s, %s, %s)",
            (store_id, code, name, unit, reorder_point),
        )

    def receive(self, conn, *, ingredient, quantity, reference_code, note, employee_id,
                idempotency_key):
        """Receive stock once; caller locks the ingredient before checking the key."""
        existing = rows(
            conn,
            "SELECT store_id, ingredient_id, quantity, reference_code, note, employee_id"
            " FROM inventory_movements WHERE idempotency_key = %s FOR UPDATE",
            (idempotency_key,),
        )
        if existing:
            row = existing[0]
            if (row["store_id"], row["ingredient_id"], row["quantity"],
                    row["reference_code"], row["note"], row["employee_id"]) != (
                    ingredient["store_id"], ingredient["id"], quantity,
                    reference_code, note, employee_id):
                raise ConflictError("Khóa yêu cầu nhập kho đã dùng cho giao dịch khác")
            return False
        execute(
            conn,
            "UPDATE inventory_ingredients SET on_hand = on_hand + %s WHERE id = %s",
            (quantity, ingredient["id"]),
        )
        execute(
            conn,
            "INSERT INTO inventory_movements"
            " (store_id, ingredient_id, employee_id, kind, quantity, on_hand_delta,"
            " reserved_delta, idempotency_key, reference_code, note)"
            " VALUES (%s, %s, %s, 'RECEIVE', %s, %s, 0, %s, %s, %s)",
            (ingredient["store_id"], ingredient["id"], employee_id, quantity,
             quantity, idempotency_key, reference_code, note),
        )
        return True

    def get_recipe(self, conn, item_id):
        return rows(
            conn,
            "SELECT r.ingredient_id, i.name AS ingredient_name, i.unit,"
            " r.quantity_per_unit FROM menu_item_recipes AS r"
            " JOIN inventory_ingredients AS i ON i.id = r.ingredient_id"
            " WHERE r.item_id = %s ORDER BY r.ingredient_id",
            (item_id,),
        )

    def replace_recipe(self, conn, item_id, parts, track_stock):
        """Caller holds the menu item row lock while replacing the recipe."""
        execute(conn, "DELETE FROM menu_item_recipes WHERE item_id = %s", (item_id,))
        for ingredient_id, quantity in parts:
            execute(
                conn,
                "INSERT INTO menu_item_recipes (item_id, ingredient_id, quantity_per_unit)"
                " VALUES (%s, %s, %s)",
                (item_id, ingredient_id, quantity),
            )
        execute(
            conn, "UPDATE menu_items SET is_stock_tracked = %s WHERE id = %s",
            (track_stock, item_id),
        )

    def _lock_ingredients(self, conn, ingredient_ids):
        # A single global lock order avoids two concurrent orders locking recipes backwards.
        locked = {}
        for ingredient_id in sorted(ingredient_ids):
            result = rows(
                conn,
                "SELECT id, store_id, name, on_hand, reserved, is_active FROM inventory_ingredients"
                " WHERE id = %s FOR UPDATE",
                (ingredient_id,),
            )
            if not result:
                raise ConflictError("Nguyên liệu của món không còn khả dụng")
            locked[ingredient_id] = result[0]
        return locked

    def _record(self, conn, *, store_id, ingredient_id, order_id, employee_id,
                account_id, kind, quantity, on_hand_delta, reserved_delta, note=None):
        execute(
            conn,
            "INSERT INTO inventory_movements"
            " (store_id, ingredient_id, order_id, employee_id, account_id, kind,"
            " quantity, on_hand_delta, reserved_delta, idempotency_key, note)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (store_id, ingredient_id, order_id, employee_id, account_id, kind,
             quantity, on_hand_delta, reserved_delta,
             f"order:{order_id}:{kind}:{ingredient_id}", note),
        )

    def reserve_order(self, conn, order_id, store_id, account_id, lines):
        """Snapshot recipes and reserve stock in the caller's order transaction."""
        snapshots = []
        needed = defaultdict(int)
        for line in sorted(lines, key=lambda entry: entry.item_id):
            item = rows(
                conn,
                "SELECT is_stock_tracked FROM menu_items WHERE id = %s AND store_id = %s FOR SHARE",
                (line.item_id, store_id),
            )
            if not item:
                raise ConflictError("Món không thuộc cửa hàng này")
            if not item[0]["is_stock_tracked"]:
                continue  # Existing untracked menu items keep their manual availability flag.
            recipe = rows(
                conn,
                "SELECT ingredient_id, quantity_per_unit FROM menu_item_recipes"
                " WHERE item_id = %s ORDER BY ingredient_id FOR SHARE",
                (line.item_id,),
            )
            if not recipe:
                raise ConflictError("Công thức món chưa hợp lệ", field_errors={"lines": line.item_name})
            for part in recipe:
                quantity = int(part["quantity_per_unit"]) * line.quantity
                snapshots.append((order_id, line.item_id, part["ingredient_id"], quantity))
                needed[part["ingredient_id"]] += quantity

        if not needed:
            return
        locked = self._lock_ingredients(conn, needed)
        for ingredient_id, quantity in sorted(needed.items()):
            ingredient = locked[ingredient_id]
            if (ingredient["store_id"] != store_id or not ingredient["is_active"] or
                    ingredient["on_hand"] - ingredient["reserved"] < quantity):
                name = ingredient["name"]
                raise ConflictError(f"Không đủ nguyên liệu: {name}", field_errors={"lines": name})
        for snapshot in snapshots:
            execute(
                conn,
                "INSERT INTO menu_order_recipe_snapshots"
                " (order_id, item_id, ingredient_id, quantity) VALUES (%s, %s, %s, %s)",
                snapshot,
            )
        for ingredient_id, quantity in sorted(needed.items()):
            if execute(
                conn,
                "UPDATE inventory_ingredients SET reserved = reserved + %s"
                " WHERE id = %s AND store_id = %s AND on_hand - reserved >= %s",
                (quantity, ingredient_id, store_id, quantity),
            ) != 1:
                raise ConflictError("Tồn khả dụng vừa thay đổi")
            self._record(conn, store_id=store_id, ingredient_id=ingredient_id,
                         order_id=order_id, employee_id=None, account_id=account_id,
                         kind="RESERVE", quantity=quantity, on_hand_delta=0,
                         reserved_delta=quantity)

    def transition_order(self, conn, order, target, employee_id, *, reason=None):
        """Apply stock effect of a successfully changed order status once."""
        from cyberhub_manager.domain.menu import MenuOrderStatus

        previous = order.status
        if previous is MenuOrderStatus.NEW and target in (MenuOrderStatus.PREPARING, MenuOrderStatus.SERVED):
            kind, on_hand_sign, reserved_sign = "CONSUME", -1, -1
        elif previous is MenuOrderStatus.NEW and target is MenuOrderStatus.CANCELLED:
            kind, on_hand_sign, reserved_sign = "RELEASE", 0, -1
        elif previous is MenuOrderStatus.PREPARING and target is MenuOrderStatus.CANCELLED:
            kind, on_hand_sign, reserved_sign = "WASTE", 0, 0
        else:
            return  # PREPARING -> SERVED and SERVED -> PAID do not move stock.

        snapshots = rows(
            conn,
            "SELECT ingredient_id, SUM(quantity) AS quantity"
            " FROM menu_order_recipe_snapshots WHERE order_id = %s"
            " GROUP BY ingredient_id ORDER BY ingredient_id",
            (order.id,),
        )
        locked = self._lock_ingredients(conn, [r["ingredient_id"] for r in snapshots])
        for part in snapshots:
            ingredient_id, quantity = int(part["ingredient_id"]), int(part["quantity"])
            if locked[ingredient_id]["store_id"] != order.store_id:
                raise ConflictError("Nguyên liệu không thuộc cửa hàng của đơn")
            if reserved_sign and locked[ingredient_id]["reserved"] < quantity:
                raise ConflictError("Lượng giữ chỗ không khớp đơn")
            if on_hand_sign and locked[ingredient_id]["on_hand"] < quantity:
                raise ConflictError("Tồn kho không đủ để xuất dùng")
            if on_hand_sign or reserved_sign:
                if execute(
                    conn,
                    "UPDATE inventory_ingredients SET on_hand = on_hand + %s,"
                    " reserved = reserved + %s WHERE id = %s AND store_id = %s",
                    (on_hand_sign * quantity, reserved_sign * quantity, ingredient_id, order.store_id),
                ) != 1:
                    raise ConflictError("Không thể cập nhật tồn kho")
            self._record(conn, store_id=order.store_id, ingredient_id=ingredient_id,
                         order_id=order.id, employee_id=employee_id, account_id=None,
                         kind=kind, quantity=quantity, on_hand_delta=on_hand_sign * quantity,
                         reserved_delta=reserved_sign * quantity,
                         note=reason if kind == "WASTE" else None)
