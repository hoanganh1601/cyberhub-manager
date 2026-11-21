"""Procurement states and line validation."""

from enum import StrEnum

from cyberhub_manager.domain.exceptions import ValidationError


class PurchaseRequestStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ORDERED = "ORDERED"


class PurchaseOrderStatus(StrEnum):
    OPEN = "OPEN"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


def parse_quantity_lines(lines, *, with_cost=False) -> list[dict]:
    if not isinstance(lines, list) or not 1 <= len(lines) <= 100:
        raise ValidationError(field_errors={"lines": "Cần từ 1 đến 100 dòng hàng"})
    parsed, seen = [], set()
    for line in lines:
        ingredient_id = line.get("ingredient_id") if isinstance(line, dict) else None
        quantity = line.get("quantity") if isinstance(line, dict) else None
        unit_cost = line.get("unit_cost") if isinstance(line, dict) else None
        if type(ingredient_id) is not int or ingredient_id <= 0 or ingredient_id in seen:
            raise ValidationError(field_errors={"lines": "Nguyên liệu bị trùng hoặc không hợp lệ"})
        if type(quantity) is not int or not 1 <= quantity <= 1_000_000_000:
            raise ValidationError(field_errors={"lines": "Số lượng nhập không hợp lệ"})
        item = {"ingredient_id": ingredient_id, "quantity": quantity}
        if with_cost:
            if type(unit_cost) is not int or not 1 <= unit_cost <= 1_000_000_000:
                raise ValidationError(field_errors={"lines": "Giá nhập không hợp lệ"})
            item["unit_cost"] = unit_cost
        parsed.append(item)
        seen.add(ingredient_id)
    return parsed
