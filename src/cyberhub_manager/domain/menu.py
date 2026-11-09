"""Đợt 1 — Menu đồ ăn/đồ uống theo cửa hàng và yêu cầu gọi món.

Giá luôn là số nguyên VND và được backend đọc lại từ database khi khách đặt món;
trình duyệt chỉ gửi mã món và số lượng.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class MenuPage(StrEnum):
    FOOD = "FOOD"  # trang 1: món chính, ăn nhanh, ăn vặt, combo
    DRINK = "DRINK"  # trang 2: nước ngọt, trà, cà phê, tăng lực


class MenuOrderStatus(StrEnum):
    NEW = "NEW"
    SERVED = "SERVED"
    CANCELLED = "CANCELLED"


class MenuChangeField(StrEnum):
    CREATE = "CREATE"
    NAME = "NAME"
    CATEGORY = "CATEGORY"
    PRICE = "PRICE"
    AVAILABLE = "AVAILABLE"
    VISIBLE = "VISIBLE"
    IMAGE = "IMAGE"


MIN_PRICE = 1_000
MAX_PRICE = 10_000_000
MAX_QUANTITY = 20
MAX_ORDER_LINES = 20
MAX_OPEN_ORDERS = 3  # chống spam: tối đa 3 yêu cầu chưa phục vụ mỗi tài khoản
MAX_SORT_ORDER = 9_999


@dataclass(frozen=True)
class MenuCategory:
    id: int
    store_id: int
    page: MenuPage
    name: str
    sort_order: int
    is_active: bool


@dataclass(frozen=True)
class MenuItem:
    id: int
    store_id: int
    category_id: int
    name: str
    description: str
    price: int
    sort_order: int
    is_visible: bool
    is_available: bool
    image_version: str | None  # 12 ký tự đầu digest ảnh, None khi chưa có ảnh
    updated_at: datetime | None = None


@dataclass(frozen=True)
class MenuItemChange:
    item_id: int
    employee_id: int
    employee_name: str
    field: MenuChangeField
    old_value: str | None
    new_value: str | None
    created_at: datetime


@dataclass(frozen=True)
class MenuOrderLine:
    item_id: int
    item_name: str
    unit_price: int
    quantity: int

    @property
    def amount(self) -> int:
        return self.unit_price * self.quantity


@dataclass(frozen=True)
class MenuOrder:
    id: int
    code: str
    store_id: int
    account_id: int
    customer_name: str
    machine_code: str
    status: MenuOrderStatus
    total_amount: int
    note: str
    lines: tuple[MenuOrderLine, ...]
    created_at: datetime
    handled_by: int | None = None


def order_total(lines: tuple[MenuOrderLine, ...] | list[MenuOrderLine]) -> int:
    return sum(line.amount for line in lines)
