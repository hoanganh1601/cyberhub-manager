"""In-memory inventory ledger used by the browser demo.

It mirrors the stock rules that matter to the UI: receipts, manual issues/returns,
reservations, consumption, counts and immutable movement history. MySQL remains the
acceptance environment for persistence and concurrency.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy

from cyberhub_manager.domain.exceptions import ConflictError


class MemoryInventoryRepository:
    def __init__(self, menu_repo, clock):
        self.menu = menu_repo
        self.clock = clock
        self.ingredients = {}
        self.recipes = {}
        self.tracking = {}
        self.counts = {}
        self.movements = []
        self.order_snapshots = {}
        self.used_keys = {}
        self._ids = {"ingredient": 0, "count": 0, "movement": 0}

    def snapshot_state(self):
        return deepcopy((self.ingredients, self.recipes, self.tracking, self.counts,
                         self.movements, self.order_snapshots, self.used_keys, self._ids))

    def restore_state(self, state):
        (self.ingredients, self.recipes, self.tracking, self.counts,
         self.movements, self.order_snapshots, self.used_keys, self._ids) = state

    def _next(self, kind):
        self._ids[kind] += 1
        return self._ids[kind]

    def seed_demo(self):
        samples = (
            ("Coca lon", "each", 48, 6, 12),
            ("Nước suối chai", "each", 9, 2, 12),
            ("Mì gói", "each", 24, 3, 8),
            ("Trứng gà", "each", 18, 2, 10),
            ("Gạo", "g", 18_000, 1_000, 5_000),
            ("Thịt bò", "g", 2_400, 400, 1_000),
            ("Khoai tây", "g", 3_500, 0, 1_500),
            ("Đường", "g", 4_000, 0, 1_000),
        )
        store_id = next(iter(self.menu.data.stores))
        for name, unit, on_hand, reserved, reorder in samples:
            ingredient_id = self.create_ingredient(
                None, store_id=store_id, code=f"DEMO-ING-{self._ids['ingredient'] + 1:02d}",
                name=name, unit=unit, reorder_point=reorder,
            )
            row = self.ingredients[ingredient_id]
            row["on_hand"], row["reserved"] = on_hand, reserved
        by_name = {row["name"]: row["id"] for row in self.ingredients.values()}
        menu_items = {item.name: item.id for item in self.menu.items.values()}
        recipes = {
            "Coca": (("Coca lon", 1),),
            "Nước suối": (("Nước suối chai", 1),),
            "Mì xào trứng": (("Mì gói", 1), ("Trứng gà", 1)),
            "Cơm chiên trứng": (("Gạo", 180), ("Trứng gà", 1)),
            "Cơm chiên bò": (("Gạo", 180), ("Thịt bò", 100)),
            "Khoai tây chiên": (("Khoai tây", 250),),
        }
        for item_name, parts in recipes.items():
            if item_name in menu_items:
                item_id = menu_items[item_name]
                self.replace_recipe(
                    None, item_id,
                    [(by_name[name], quantity) for name, quantity in parts], True,
                )
        self._record(store_id, by_name["Coca lon"], "RECEIVE", 48, 48, 0,
                     employee_id=None, reference_code="PN-DEMO-001", note="Tồn đầu kỳ")
        self._record(store_id, by_name["Nước suối chai"], "RESERVE", 2, 0, 2,
                     employee_id=None, note="Đơn demo đang chờ")

    def _row(self, ingredient):
        row = dict(ingredient)
        row["available"] = row["on_hand"] - row["reserved"]
        return row

    def list_ingredients(self, conn, store_id):
        return [self._row(row) for row in sorted(self.ingredients.values(),
                key=lambda item: (item["name"], item["id"])) if row["store_id"] == store_id]

    def get_ingredient(self, conn, ingredient_id, *, lock=False):
        row = self.ingredients.get(ingredient_id)
        return self._row(row) if row else None

    def create_ingredient(self, conn, *, store_id, code, name, unit, reorder_point):
        ingredient_id = self._next("ingredient")
        self.ingredients[ingredient_id] = dict(
            id=ingredient_id, store_id=store_id, code=code, name=name, unit=unit,
            on_hand=0, reserved=0, reorder_point=reorder_point, is_active=True,
        )
        return ingredient_id

    def list_movements(self, conn, store_id, limit=50):
        names = {row["id"]: row for row in self.ingredients.values()}
        result = []
        for movement in reversed(self.movements):
            if movement["store_id"] != store_id:
                continue
            ingredient = names[movement["ingredient_id"]]
            result.append({**movement, "ingredient_name": ingredient["name"],
                           "unit": ingredient["unit"], "employee_name": None})
            if len(result) == limit:
                break
        return result

    def _record(self, store_id, ingredient_id, kind, quantity, on_hand_delta,
                reserved_delta, *, employee_id, reference_code=None, note=None):
        movement_id = self._next("movement")
        self.movements.append(dict(
            id=movement_id, store_id=store_id, ingredient_id=ingredient_id,
            kind=kind, quantity=quantity, on_hand_delta=on_hand_delta,
            reserved_delta=reserved_delta, reference_code=reference_code,
            note=note, created_at=self.clock(), employee_id=employee_id,
        ))
        return movement_id

    def _last_movement_id(self, ingredient_id):
        return max(
            (movement["id"] for movement in self.movements
             if movement["ingredient_id"] == ingredient_id),
            default=0,
        )

    def _once(self, key, signature):
        existing = self.used_keys.get(key)
        if existing is not None and existing != signature:
            raise ConflictError("Mã yêu cầu kho đã dùng cho giao dịch khác")
        if existing is not None:
            return False
        self.used_keys[key] = signature
        return True

    def receive(self, conn, *, ingredient, quantity, reference_code, note, employee_id,
                idempotency_key):
        signature = (ingredient["id"], quantity, reference_code, note, employee_id)
        if not self._once(idempotency_key, signature):
            return False
        row = self.ingredients[ingredient["id"]]
        row["on_hand"] += quantity
        self._record(row["store_id"], row["id"], "RECEIVE", quantity, quantity, 0,
                     employee_id=employee_id, reference_code=reference_code, note=note)
        return True

    def manual_movement(self, conn, *, ingredient, quantity, reference_code, note,
                        employee_id, idempotency_key, kind):
        signature = (ingredient["id"], kind, quantity, reference_code, note, employee_id)
        if not self._once(idempotency_key, signature):
            return False
        row = self.ingredients[ingredient["id"]]
        delta = -quantity if kind == "ISSUE" else quantity
        if kind == "ISSUE" and row["on_hand"] - row["reserved"] < quantity:
            raise ConflictError("Tồn khả dụng không đủ để xuất kho")
        row["on_hand"] += delta
        self._record(row["store_id"], row["id"], kind, quantity, delta, 0,
                     employee_id=employee_id, reference_code=reference_code, note=note)
        return True

    def item_tracking(self, conn, store_id):
        return [dict(item_id=item.id, is_stock_tracked=self.tracking.get(item.id, False))
                for item in self.menu.items.values() if item.store_id == store_id]

    def get_recipe(self, conn, item_id):
        result = []
        for ingredient_id, quantity in self.recipes.get(item_id, ()):
            ingredient = self.ingredients[ingredient_id]
            result.append(dict(ingredient_id=ingredient_id,
                               ingredient_name=ingredient["name"], unit=ingredient["unit"],
                               quantity_per_unit=quantity))
        return result

    def replace_recipe(self, conn, item_id, parts, track_stock):
        self.recipes[item_id] = list(parts)
        self.tracking[item_id] = track_stock

    def _lock_ingredients(self, conn, ingredient_ids):
        result = {}
        for ingredient_id in sorted(ingredient_ids):
            if ingredient_id not in self.ingredients:
                raise ConflictError("Nguyên liệu của món không còn khả dụng")
            result[ingredient_id] = self._row(self.ingredients[ingredient_id])
        return result

    def list_counts(self, conn, store_id):
        return [dict(row) for row in sorted(self.counts.values(),
                key=lambda item: item["id"], reverse=True)
                if row["store_id"] == store_id and row["status"] == "PENDING"]

    def get_count(self, conn, count_id, *, lock=False):
        row = self.counts.get(count_id)
        return dict(row) if row else None

    def propose_count(self, conn, *, ingredient, counted_on_hand, reason, employee_id,
                      request_id):
        key = "count:" + request_id
        signature = (ingredient["id"], counted_on_hand, reason, employee_id)
        if key in self.used_keys:
            if self.used_keys[key] != signature:
                raise ConflictError("Mã yêu cầu kiểm kê đã dùng cho phiếu khác")
            count_id = next(row["id"] for row in self.counts.values()
                            if row["request_id"] == request_id)
            return dict(self.counts[count_id]), False
        if counted_on_hand < ingredient["reserved"]:
            raise ConflictError("Số đếm thấp hơn lượng đã giữ cho đơn")
        self.used_keys[key] = signature
        count_id = self._next("count")
        self.counts[count_id] = dict(
            id=count_id, store_id=ingredient["store_id"], ingredient_id=ingredient["id"],
            request_id=request_id, expected_on_hand=ingredient["on_hand"],
            expected_reserved=ingredient["reserved"],
            expected_movement_id=self._last_movement_id(ingredient["id"]),
            counted_on_hand=counted_on_hand, proposed_by=employee_id, decided_by=None,
            status="PENDING", reason=reason, created_at=self.clock(), decided_at=None,
        )
        return dict(self.counts[count_id]), True

    def decide_count(self, conn, *, count, ingredient, employee_id, approve):
        row = self.counts[count["id"]]
        if row["status"] != "PENDING":
            raise ConflictError("Phiếu kiểm kê đã được xử lý")
        current = self.ingredients[ingredient["id"]]
        if approve:
            if (current["on_hand"], current["reserved"],
                    self._last_movement_id(current["id"])) != (
                    count["expected_on_hand"], count["expected_reserved"],
                    count["expected_movement_id"]):
                raise ConflictError("Tồn kho đã thay đổi; cần kiểm kê lại")
            delta = count["counted_on_hand"] - current["on_hand"]
            current["on_hand"] += delta
            if delta:
                self._record(current["store_id"], current["id"], "ADJUST", abs(delta),
                             delta, 0, employee_id=employee_id, note=count["reason"])
        row.update(status="APPROVED" if approve else "REJECTED", decided_by=employee_id,
                   decided_at=self.clock())
        return dict(row)

    def reserve_order(self, conn, order_id, store_id, account_id, lines):
        snapshots, needed = [], defaultdict(int)
        for line in lines:
            if not self.tracking.get(line.item_id, False):
                continue
            recipe = self.recipes.get(line.item_id, ())
            if not recipe:
                raise ConflictError("Công thức món chưa hợp lệ", field_errors={"lines": line.item_name})
            for ingredient_id, per_unit in recipe:
                quantity = per_unit * line.quantity
                snapshots.append((line.item_id, ingredient_id, quantity))
                needed[ingredient_id] += quantity
        for ingredient_id, quantity in needed.items():
            row = self.ingredients[ingredient_id]
            if row["store_id"] != store_id or not row["is_active"] or row["on_hand"] - row["reserved"] < quantity:
                raise ConflictError(f"Không đủ nguyên liệu: {row['name']}",
                                    field_errors={"lines": row["name"]})
        self.order_snapshots[order_id] = snapshots
        for ingredient_id, quantity in needed.items():
            row = self.ingredients[ingredient_id]
            row["reserved"] += quantity
            self._record(store_id, ingredient_id, "RESERVE", quantity, 0, quantity,
                         employee_id=None, note=f"Đơn {order_id}")

    def _order_totals(self, order_id):
        totals = defaultdict(int)
        for _, ingredient_id, quantity in self.order_snapshots.get(order_id, ()):
            totals[ingredient_id] += quantity
        return totals

    def transition_order(self, conn, order, target, employee_id, *, reason=None):
        from cyberhub_manager.domain.menu import MenuOrderStatus
        if order.status is MenuOrderStatus.NEW and target in (MenuOrderStatus.PREPARING, MenuOrderStatus.SERVED):
            kind, on_hand_delta, reserved_delta = "CONSUME", -1, -1
        elif order.status is MenuOrderStatus.NEW and target is MenuOrderStatus.CANCELLED:
            kind, on_hand_delta, reserved_delta = "RELEASE", 0, -1
        elif order.status is MenuOrderStatus.PREPARING and target is MenuOrderStatus.CANCELLED:
            kind, on_hand_delta, reserved_delta = "WASTE", 0, 0
        else:
            return
        for ingredient_id, quantity in self._order_totals(order.id).items():
            row = self.ingredients[ingredient_id]
            row["on_hand"] += on_hand_delta * quantity
            row["reserved"] += reserved_delta * quantity
            self._record(order.store_id, ingredient_id, kind, quantity,
                         on_hand_delta * quantity, reserved_delta * quantity,
                         employee_id=employee_id, note=reason)

    def reverse_served_order(self, conn, order, employee_id, *, restock, reason):
        for ingredient_id, quantity in self._order_totals(order.id).items():
            row = self.ingredients[ingredient_id]
            if restock:
                row["on_hand"] += quantity
            self._record(order.store_id, ingredient_id, "RETURN" if restock else "WASTE",
                         quantity, quantity if restock else 0, 0,
                         employee_id=employee_id, note=reason)
