"""Đợt 1 — Repository menu trong bộ nhớ cho chế độ demo (web demo, --mock, unit test).

Cùng chữ ký với repositories/menu_repository.py để MenuService chạy y hệt bản MySQL.
Transaction bọc transaction của MemoryP1Repository (audit cùng rollback) và tự chụp
lại trạng thái menu để rollback khi có lỗi.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone

from cyberhub_manager.domain.menu import (
    MenuCategory,
    MenuItem,
    MenuItemChange,
    MenuOrder,
    MenuOrderStatus,
    MenuPage,
)

# Menu dạng bảng: mỗi nhóm là một cột có nhãn tiêu đề; trong nhóm chia "nhóm nhỏ" bằng vạch kẻ.
# Nhóm nhỏ được mã hóa qua sort_order: cùng hàng trăm = cùng nhóm nhỏ (0-99, 100-199, ...).
# (trang, nhóm, ( (nhóm nhỏ: (tên, mô tả, giá, còn món), ...), ... ))
DEMO_MENU = (
    (MenuPage.FOOD, "Cơm", (
        (("Cơm chiên bò", "", 26_000, True), ("Cơm chiên đùi gà", "", 25_000, True),
         ("Cơm chiên trứng", "", 18_000, True)),
        (("Cơm trắng đùi gà sốt", "", 25_000, True), ("Cơm trắng bò xào cải", "", 25_000, True)),
    )),
    (MenuPage.FOOD, "Mì · Nui", (
        (("Nui xào bò", "", 25_000, True), ("Nui xào trứng", "", 20_000, True)),
        (("Mì xào bò", "", 25_000, True), ("Mì xào trứng", "", 18_000, True),
         ("Mì nước bò", "", 25_000, True), ("Mì nước trứng", "", 18_000, True)),
    )),
    (MenuPage.FOOD, "Ăn vặt & gọi thêm", (
        (("Cá viên chiên", "", 15_000, True), ("Khoai tây chiên", "", 25_000, True),
         ("Xúc xích chiên", "", 20_000, False)),
        (("Trứng thêm", "", 6_000, True), ("Mì thêm", "", 6_000, True), ("Cơm thêm", "", 6_000, True)),
    )),
    (MenuPage.DRINK, "Nước ngọt", (
        (("Coca", "", 10_000, True), ("7Up", "", 10_000, True), ("Revive", "", 15_000, True),
         ("Sting", "", 15_000, True), ("Redbull Thái", "", 15_000, True), ("Nước suối", "", 10_000, True),
         ("Mountain Dew", "", 12_000, True)),
    )),
    (MenuPage.DRINK, "Cà phê · Cacao", (
        (("Cà phê đá/nóng", "", 15_000, True), ("Cà phê sữa đá/nóng", "", 18_000, True),
         ("Bạc xỉu", "", 20_000, True), ("Cacao đá/nóng", "", 20_000, True)),
        (("Cà phê đá xay", "", 25_000, True), ("Cacao đá xay", "", 25_000, True),
         ("Matcha đá xay", "", 25_000, True)),
    )),
    (MenuPage.DRINK, "Trà · Soda · Yogurt", (
        (("Trà sả", "", 20_000, True), ("Trà đào", "", 20_000, True), ("Trà chanh", "", 20_000, True)),
        (("Soda đào", "", 20_000, True), ("Soda việt quất", "", 20_000, True)),
        (("Yogurt đá", "", 20_000, True), ("Yogurt đào", "", 20_000, True), ("Yogurt việt quất", "", 20_000, True)),
    )),
)


class MemoryMenuRepository:
    def __init__(self, data, p1_repo, clock=None):
        self.data = data
        self.p1 = p1_repo
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.categories: dict[int, MenuCategory] = {}
        self.items: dict[int, MenuItem] = {}
        self.images: dict[int, bytes] = {}
        self.changes: list[MenuItemChange] = []
        self.orders: dict[int, MenuOrder] = {}
        self._ids = {"category": 0, "item": 0, "order": 0}

    # ----- Transaction ---------------------------------------------------------
    @contextmanager
    def transaction(self):
        with self.p1.transaction() as conn:
            snapshot = deepcopy(
                (self.categories, self.items, self.images, self.changes, self.orders, self._ids)
            )
            try:
                yield conn
            except Exception:
                (self.categories, self.items, self.images, self.changes, self.orders, self._ids) = snapshot
                raise

    def _next(self, kind: str) -> int:
        self._ids[kind] += 1
        return self._ids[kind]

    # ----- Dữ liệu mẫu ----------------------------------------------------------
    def seed_demo(self) -> None:
        for store_id in list(self.data.stores):
            for sort, (page, name, items) in enumerate(DEMO_MENU):
                category_id = self.insert_category(
                    None, store_id=store_id, page=page, name=name, sort_order=sort * 10, is_active=True
                )
                for group, group_items in enumerate(items):
                    for position, (item_name, description, price, available) in enumerate(group_items):
                        self.insert_item(
                            None, store_id=store_id, category_id=category_id, name=item_name,
                            description=description, price=price, sort_order=group * 100 + position * 10,
                            is_visible=True, is_available=available,
                        )

    # ----- Nhóm món --------------------------------------------------------------
    def list_categories(self, conn, store_id):
        return sorted(
            (c for c in self.categories.values() if c.store_id == store_id),
            key=lambda c: (c.page, c.sort_order, c.id),
        )

    def get_category(self, conn, category_id, *, lock=False):
        return self.categories.get(category_id)

    def insert_category(self, conn, *, store_id, page, name, sort_order, is_active):
        category_id = self._next("category")
        self.categories[category_id] = MenuCategory(category_id, store_id, MenuPage(page), name, sort_order, is_active)
        return category_id

    def update_category(self, conn, category_id, *, page, name, sort_order, is_active):
        self.categories[category_id] = replace(
            self.categories[category_id], page=MenuPage(page), name=name, sort_order=sort_order, is_active=is_active
        )

    # ----- Món ---------------------------------------------------------------------
    def list_items(self, conn, store_id):
        return sorted(
            (i for i in self.items.values() if i.store_id == store_id),
            key=lambda i: (i.category_id, i.sort_order, i.id),
        )

    def get_item(self, conn, item_id, *, lock=False):
        return self.items.get(item_id)

    def insert_item(self, conn, *, store_id, category_id, name, description, price, sort_order,
                    is_visible, is_available):
        item_id = self._next("item")
        self.items[item_id] = MenuItem(
            item_id, store_id, category_id, name, description, price, sort_order,
            is_visible, is_available, None, self.clock(),
        )
        return item_id

    def update_item(self, conn, item_id, *, category_id, name, description, price, sort_order,
                    is_visible, is_available):
        self.items[item_id] = replace(
            self.items[item_id], category_id=category_id, name=name, description=description, price=price,
            sort_order=sort_order, is_visible=is_visible, is_available=is_available, updated_at=self.clock(),
        )

    def set_item_available(self, conn, item_id, available):
        self.items[item_id] = replace(self.items[item_id], is_available=available, updated_at=self.clock())

    # ----- Ảnh -----------------------------------------------------------------------
    def save_image(self, conn, item_id, data, digest):
        self.images[item_id] = data
        self.items[item_id] = replace(self.items[item_id], image_version=digest[:12])

    def get_image(self, conn, item_id):
        return self.images.get(item_id)

    # ----- Lịch sử -----------------------------------------------------------------------
    def record_change(self, conn, *, item_id, employee_id, field, old_value, new_value):
        employee = self.data.employees.get(employee_id)
        self.changes.append(
            MenuItemChange(item_id, employee_id, employee.full_name if employee else "", field,
                           old_value, new_value, self.clock())
        )

    def item_changes(self, conn, item_id, limit=50):
        return [c for c in reversed(self.changes) if c.item_id == item_id][:limit]

    # ----- Phiên đang chơi ---------------------------------------------------------------
    def active_session(self, conn, customer_id):
        session = next(
            (s for s in self.data.sessions.values() if s.customer_id == customer_id and s.is_active()),
            None,
        )
        if session is None:
            return None
        machine = self.data.machines[session.machine_id]
        return dict(session_id=session.id, machine_id=machine.id, machine_code=machine.code,
                    store_id=machine.store_id)

    # ----- Yêu cầu gọi món -------------------------------------------------------------
    def count_open_orders(self, conn, account_id):
        return sum(1 for o in self.orders.values() if o.account_id == account_id and o.status == MenuOrderStatus.NEW)

    def insert_order(self, conn, *, code, store_id, account_id, session_id, machine_id, note, lines):
        order_id = self._next("order")
        customer = next(c for c in self.data.customers.values() if c.account.id == account_id)
        self.orders[order_id] = MenuOrder(
            order_id, code, store_id, account_id, customer.full_name, self.data.machines[machine_id].code,
            MenuOrderStatus.NEW, sum(line.amount for line in lines), note, tuple(lines), self.clock(), None,
        )
        return order_id

    def list_orders(self, conn, store_id, status, limit=100):
        found = [o for o in self.orders.values() if o.store_id == store_id and (status is None or o.status == status)]
        if status is None:
            found.sort(key=lambda o: (o.created_at, o.id), reverse=True)
        else:
            found.sort(key=lambda o: (o.created_at, o.id))
        return found[:limit]

    def account_orders(self, conn, account_id, limit=5):
        found = sorted((o for o in self.orders.values() if o.account_id == account_id),
                       key=lambda o: (o.created_at, o.id), reverse=True)
        return found[:limit]

    def get_order(self, conn, order_id, *, lock=False):
        return self.orders.get(order_id)

    def finish_order(self, conn, order_id, status, employee_id):
        order = self.orders.get(order_id)
        if order is None or order.status != MenuOrderStatus.NEW:
            return False
        self.orders[order_id] = replace(order, status=status, handled_by=employee_id)
        return True
