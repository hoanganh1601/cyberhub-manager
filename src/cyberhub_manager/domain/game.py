"""Đợt 3 — Game (vòng quay may mắn) và xu game.

Xu game là đơn vị riêng: không phải tiền, không phải điểm thành viên. Kết quả mỗi lượt do
máy chủ bốc thăm; trình duyệt chỉ nhận kết quả để chạy hiệu ứng.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from enum import StrEnum

DEFAULT_GAME = "LUCKY_WHEEL"
SUSPICIOUS_LIMIT = 10  # số lần bị chặn trong ngày trước khi tự khóa ví game
MAX_PRIZES = 12
MIN_PRIZES = 2

# Danh mục Game Center do backend công bố. Engine của game nội bộ chạy trên trình duyệt,
# nhưng quyền hoạt động/tài trợ và phần thưởng luôn do backend kiểm soát.
GAME_CENTER_CATALOG = (
    dict(code="wheel", name="Vòng quay may mắn", active=True, featured=True,
         sponsored=False, reward_mode="SERVER_DRAW"),
    dict(code="2048", name="Cyber 2048", active=True, featured=True,
         sponsored=False, reward_mode="SERVER_DRAW"),
    dict(code="snake", name="Snake Arena", active=True, featured=False,
         sponsored=False, reward_mode="SERVER_DRAW"),
    dict(code="memory", name="Puzzle ký ức", active=True, featured=False,
         sponsored=False, reward_mode="SERVER_DRAW"),
    dict(code="bubble", name="Bubble Blast", active=False, featured=False,
         sponsored=True, reward_mode="SERVER_DRAW"),
    dict(code="candy", name="Candy Match", active=False, featured=False,
         sponsored=True, reward_mode="SERVER_DRAW"),
)


class LedgerReason(StrEnum):
    PLAY = "PLAY"
    REDEEM = "REDEEM"
    AD = "AD"  # Đợt 4
    ADJUST = "ADJUST"


@dataclass(frozen=True)
class GamePrize:
    sort_order: int
    label: str
    coins: int
    weight: int


@dataclass(frozen=True)
class Game:
    id: int
    code: str
    name: str
    is_active: bool
    daily_limit: int
    min_interval_seconds: int
    prizes: tuple[GamePrize, ...]


@dataclass(frozen=True)
class GameWallet:
    account_id: int
    balance: int
    is_locked: bool
    locked_reason: str | None
    locked_at: datetime | None
    suspicious_count: int
    suspicious_on: date | None


@dataclass(frozen=True)
class GameSession:
    """Read model; ``played_on`` is derived from ``created_at`` in UTC+7."""

    id: int
    account_id: int
    customer_name: str
    prize_index: int
    prize_label: str
    coins: int
    played_on: date
    created_at: datetime


@dataclass(frozen=True)
class CoinLedgerEntry:
    id: int
    account_id: int
    delta: int
    reason: LedgerReason
    ref: str
    balance_after: int
    voucher_id: int | None
    created_at: datetime


def expected_coins(prizes) -> float:
    """Số xu kỳ vọng mỗi lượt — để quản lý cân chỉnh vòng quay."""
    total = sum(p.weight for p in prizes)
    return sum(p.coins * p.weight for p in prizes) / total if total else 0.0
