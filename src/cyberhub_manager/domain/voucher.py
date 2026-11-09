"""Đợt 2 — Voucher và phần thưởng.

Nguyên tắc: voucher KHÔNG có giá trị tiền mặt. Mỗi loại chỉ có một cách dùng:
- FOOD_DISCOUNT: giảm tiền một yêu cầu gọi món (nhân viên trừ khi thu tại quầy).
- FREE_DRINK: tặng đồ uống trong một yêu cầu gọi món, tối đa `value` VND.
- PLAYTIME_CREDIT: cộng `value` VND vào số dư khuyến mãi (chỉ dùng trả giờ chơi, không rút được).
- MEMBER_POINTS: cộng `value` điểm thành viên (không đổi hạng; hạng tính theo chi tiêu).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class RewardType(StrEnum):
    FOOD_DISCOUNT = "FOOD_DISCOUNT"
    FREE_DRINK = "FREE_DRINK"
    PLAYTIME_CREDIT = "PLAYTIME_CREDIT"
    MEMBER_POINTS = "MEMBER_POINTS"


class VoucherStatus(StrEnum):
    ISSUED = "ISSUED"
    USED = "USED"
    REVOKED = "REVOKED"


class VoucherState(StrEnum):
    """Trạng thái hiển thị: EXPIRED suy ra từ expires_at, không lưu trong DB."""

    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    USED = "USED"
    REVOKED = "REVOKED"


class VoucherSource(StrEnum):
    MANUAL = "MANUAL"
    GAME = "GAME"  # Đợt 3
    AD = "AD"  # Đợt 4


class VoucherAction(StrEnum):
    ISSUE = "ISSUE"
    REDEEM = "REDEEM"
    REVOKE = "REVOKE"
    REJECT = "REJECT"


# Trần giá trị theo loại để một voucher không thể "đáng giá" quá mức.
VALUE_LIMITS = {
    RewardType.FOOD_DISCOUNT: 200_000,
    RewardType.FREE_DRINK: 100_000,
    RewardType.PLAYTIME_CREDIT: 200_000,
    RewardType.MEMBER_POINTS: 10_000,
}
FOOD_TYPES = frozenset({RewardType.FOOD_DISCOUNT, RewardType.FREE_DRINK})
MAX_VALID_DAYS = 365


@dataclass(frozen=True)
class RewardCatalogItem:
    id: int
    code: str
    name: str
    store_id: int | None
    reward_type: RewardType
    value: int
    min_order_amount: int
    valid_days: int
    coin_cost: int | None
    is_active: bool


@dataclass(frozen=True)
class Voucher:
    id: int
    code: str
    catalog_id: int
    catalog_name: str
    account_id: int
    customer_id: int
    customer_name: str
    store_id: int | None
    reward_type: RewardType
    value: int
    min_order_amount: int
    status: VoucherStatus
    source: VoucherSource
    issued_at: datetime
    expires_at: datetime
    used_at: datetime | None = None
    used_store_id: int | None = None
    used_order_id: int | None = None
    revoked_reason: str | None = None

    def state(self, now: datetime) -> VoucherState:
        if self.status == VoucherStatus.USED:
            return VoucherState.USED
        if self.status == VoucherStatus.REVOKED:
            return VoucherState.REVOKED
        return VoucherState.EXPIRED if now >= self.expires_at else VoucherState.ACTIVE


@dataclass(frozen=True)
class VoucherEvent:
    id: int
    voucher_id: int | None
    voucher_code: str | None
    action: VoucherAction
    employee_name: str | None
    reason: str
    created_at: datetime


@dataclass(frozen=True)
class RedeemResult:
    voucher: Voucher
    reward_type: RewardType
    discount: int  # VND nhân viên trừ khi thu tiền đồ ăn; 0 với loại khác
    bonus_credited: int  # VND cộng vào số dư khuyến mãi
    points_granted: int
