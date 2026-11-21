"""Shared validation and identifiers for menu/POS application services."""

from uuid import UUID, uuid4

from cyberhub_manager.domain.exceptions import ValidationError
from cyberhub_manager.domain.menu import (
    MAX_OPEN_ORDERS,
    MAX_PRICE,
    MAX_SORT_ORDER,
    MIN_PRICE,
)

ITEM_NOT_FOUND = "Không tìm thấy món"
CATEGORY_NOT_FOUND = "Không tìm thấy nhóm món"
ORDER_NOT_FOUND = "Không tìm thấy yêu cầu gọi món"
STORE_INVALID = "Cơ sở không khả dụng"
NEED_ACTIVE_SESSION = "Bạn cần đang sử dụng máy tại CyberHub để gọi món"
ITEM_UNAVAILABLE = "Món này hiện không phục vụ"
TOO_MANY_OPEN = (
    f"Bạn đang có {MAX_OPEN_ORDERS} yêu cầu chưa được phục vụ. "
    "Vui lòng chờ nhân viên."
)
ORDER_ALREADY_HANDLED = "Yêu cầu này đã được xử lý"
DUPLICATE_NAME = "Tên đã tồn tại trong cơ sở này"


def positive_id(value: object) -> bool:
    return type(value) is int and value > 0


def text(value: object, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValidationError(
            field_errors={field: f"Nhập từ {minimum} đến {maximum} ký tự"}
        )
    return value.strip()


def flag(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise ValidationError(field_errors={field: "Giá trị không hợp lệ"})
    return value


def sort_order(value: object) -> int:
    if type(value) is not int or not 0 <= value <= MAX_SORT_ORDER:
        raise ValidationError(
            field_errors={"sort_order": f"Thứ tự từ 0 đến {MAX_SORT_ORDER}"}
        )
    return value


def price(value: object) -> int:
    if type(value) is not int or not MIN_PRICE <= value <= MAX_PRICE:
        message = f"Giá từ {MIN_PRICE:,} đến {MAX_PRICE:,} VND".replace(",", ".")
        raise ValidationError(field_errors={"price": message})
    return value


def stock_quantity(value: object, *, allow_zero=False, field="quantity") -> int:
    minimum = 0 if allow_zero else 1
    if type(value) is not int or not minimum <= value <= 1_000_000_000:
        raise ValidationError(field_errors={field: "Số lượng không hợp lệ"})
    return value


def request_uuid(value: object) -> str:
    try:
        parsed = UUID(value)
        if parsed.version != 4:
            raise ValueError
    except (TypeError, ValueError, AttributeError):
        raise ValidationError(
            field_errors={"request_id": "Cần mã yêu cầu UUID v4"}
        ) from None
    return parsed.hex


def new_order_code() -> str:
    return "ORD-" + uuid4().hex[:16].upper()
