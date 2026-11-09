"""Đợt 4 — Quảng cáo nhận thưởng.

Nguyên tắc: xem quảng cáo luôn tự nguyện; không cộng thưởng chỉ dựa vào tín hiệu từ trình duyệt.
- HOUSE: máy chủ cấp token dùng một lần lúc bắt đầu và chỉ chấp nhận hoàn thành khi đã đủ
  thời lượng theo đồng hồ máy chủ, trước khi token hết hạn.
- NETWORK: chỉ callback có chữ ký HMAC của nhà cung cấp mới hoàn thành được sự kiện.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

TOKEN_HOURS = 1  # token hết hạn sau 1 giờ kể từ khi bắt đầu xem
START_FACTOR = 3  # mỗi ngày bắt đầu tối đa daily_cap × 3 lần (chống spam token)


class AdMode(StrEnum):
    HOUSE = "HOUSE"
    NETWORK = "NETWORK"


class AdRewardType(StrEnum):
    EXTRA_SPIN = "EXTRA_SPIN"
    COINS = "COINS"


class AdStatus(StrEnum):
    ISSUED = "ISSUED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


REWARD_LIMITS = {AdRewardType.EXTRA_SPIN: 3, AdRewardType.COINS: 100}


@dataclass(frozen=True)
class AdSettings:
    enabled: bool
    mode: AdMode
    daily_cap: int
    reward_type: AdRewardType
    reward_amount: int


@dataclass(frozen=True)
class AdCreative:
    id: int
    code: str
    title: str
    body: str
    cta: str
    duration_seconds: int
    is_active: bool


@dataclass(frozen=True)
class AdEvent:
    id: int
    token: str
    account_id: int
    customer_name: str
    creative_id: int | None
    provider: AdMode
    reward_type: AdRewardType
    reward_amount: int
    status: AdStatus
    played_on: date
    issued_at: datetime
    min_complete_at: datetime
    expires_at: datetime
    completed_at: datetime | None = None
    provider_txn_id: str | None = None
    reject_reason: str | None = None
