"""Đợt 3 — Vòng quay và xu game (GameService trên repository bộ nhớ, không cần MySQL).

Vòng quay mặc định: 3 lượt/ngày, cách nhau ≥ 3 giây; ô 0 "5 xu", 1 "Chúc may mắn", 2 "10 xu",
3 "20 xu", 4 "50 xu", 5 "100 xu". Phần thưởng đổi xu (Đợt 2): GIAM20K=1 (200 xu), NUOCFREE=2 (150),
GIO10K=3 (120), DIEM50=4 (80).
"""

from datetime import datetime, timezone

import pytest

from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.game import SUSPICIOUS_LIMIT, LedgerReason
from cyberhub_manager.domain.voucher import VoucherSource
from cyberhub_manager.services.game_service import (
    AUTO_LOCKED,
    GAME_PAUSED,
    LIMIT_REACHED,
    TOO_FAST,
    WALLET_LOCKED,
)
from cyberhub_manager.services.mocks.clock import MockClock
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD

NOW = datetime(2026, 10, 18, 9, tzinfo=timezone.utc)


class FixedRandom:
    """Thay bốc thăm ngẫu nhiên: luôn trúng ô `index` (kiểm chứng kết quả do máy chủ quyết định)."""

    def __init__(self, index):
        self.index = index
        self.calls = []

    def choices(self, population, weights):
        self.calls.append(list(weights))
        return [population[self.index]]


@pytest.fixture
def ctx():
    clock = MockClock(NOW)
    bundle = build_mock_services(p1=True, clock=clock)
    games = bundle.games
    games._random = FixedRandom(5)  # 100 xu
    return dict(
        bundle=bundle, games=games, clock=clock,
        an=bundle.portal.login("nguyenvanan", DEMO_PASSWORD),
        manager=bundle.auth.login("quanly01", DEMO_PASSWORD),
        staff=bundle.auth.login("nhanvien01", DEMO_PASSWORD),
        admin=bundle.auth.login("admin01", DEMO_PASSWORD),
    )


def spin(ctx, seconds=5):
    ctx["clock"].advance(seconds=seconds)
    return ctx["games"].spin(ctx["an"])


def rejected(ctx, message, seconds=5):
    ctx["clock"].advance(seconds=seconds)
    with pytest.raises(ConflictError) as info:
        ctx["games"].spin(ctx["an"])
    assert info.value.message == message


# ----- Xem trò chơi --------------------------------------------------------------
def test_new_player_has_full_spins_and_coin_shop(ctx):
    data = ctx["games"].portal_game(ctx["an"])

    assert data["wallet"]["balance"] == 0 and data["spins_left"] == 3
    assert [s["coin_cost"] for s in data["shop"]] == [80, 120, 150, 200]
    assert len(data["game"]["prizes"]) == 6
    assert "weight" not in data["game"]["prizes"][0]  # khách không cần thấy trọng số nội bộ


# ----- Quay ------------------------------------------------------------------------
def test_server_decides_prize_and_credits_coins_once(ctx):
    result = spin(ctx)

    assert (result["prize_index"], result["coins"], result["balance"]) == (5, 100, 100)
    assert ctx["games"]._random.calls[0] == [30, 25, 25, 15, 5, 2]  # bốc theo trọng số cấu hình
    data = ctx["games"].portal_game(ctx["an"])
    assert data["wallet"]["balance"] == 100 and data["spins_left"] == 2
    [entry] = data["ledger"]
    assert (entry.reason, entry.delta, entry.balance_after) == (LedgerReason.PLAY, 100, 100)
    assert data["history"][0].prize_label == "100 xu"


def test_no_luck_prize_records_session_without_ledger(ctx):
    ctx["games"]._random = FixedRandom(1)

    assert spin(ctx)["coins"] == 0
    data = ctx["games"].portal_game(ctx["an"])
    assert len(data["history"]) == 1 and data["ledger"] == []


def test_daily_limit_then_reset_next_day(ctx):
    for _ in range(3):
        spin(ctx)
    rejected(ctx, LIMIT_REACHED)
    assert ctx["games"].portal_game(ctx["an"])["spins_left"] == 0

    ctx["clock"].advance(hours=24)
    assert spin(ctx)["spins_left"] == 2


def test_spinning_too_fast_is_rejected(ctx):
    spin(ctx)
    rejected(ctx, TOO_FAST, seconds=1)


def test_repeated_blocked_attempts_lock_the_game_wallet(ctx):
    for _ in range(3):
        spin(ctx)
    for _ in range(SUSPICIOUS_LIMIT - 1):
        rejected(ctx, LIMIT_REACHED)
    rejected(ctx, AUTO_LOCKED)  # lần thứ SUSPICIOUS_LIMIT

    rejected(ctx, WALLET_LOCKED)
    with pytest.raises(ConflictError):
        ctx["games"].redeem(ctx["an"], 4, "key-locked-0001")
    locked = ctx["games"].manage(ctx["manager"])["locked"]
    assert [w["account_id"] for w in locked] == [ctx["an"].account_id]


def test_manager_unlocks_wallet_and_counter_resets(ctx):
    games = ctx["games"]
    games.set_wallet_lock(ctx["manager"], ctx["an"].account_id, True, "Kiểm tra thủ công")
    rejected(ctx, WALLET_LOCKED)
    with pytest.raises(PermissionDeniedError):
        games.set_wallet_lock(ctx["staff"], ctx["an"].account_id, False)

    wallet = games.set_wallet_lock(ctx["manager"], ctx["an"].account_id, False)

    assert wallet.is_locked is False and wallet.suspicious_count == 0
    assert spin(ctx)["coins"] == 100
    audit = ctx["bundle"].games._p1.data.management_audit
    assert [a[2] for a in audit[-2:]] == ["GAME_WALLET_LOCK", "GAME_WALLET_UNLOCK"]


def test_paused_game_cannot_be_played(ctx):
    game = ctx["games"].manage(ctx["admin"])["game"]
    prizes = [dict(label=p.label, coins=p.coins, weight=p.weight) for p in game["prizes"]]
    ctx["games"].save_game(ctx["admin"], is_active=False, daily_limit=3, min_interval_seconds=3, prizes=prizes)

    rejected(ctx, GAME_PAUSED)
    assert ctx["games"].portal_game(ctx["an"])["spins_left"] == 0


# ----- Đổi xu lấy voucher ------------------------------------------------------------
def test_redeem_coins_for_voucher_and_replay_is_idempotent(ctx):
    games = ctx["games"]
    spin(ctx)  # 100 xu

    first = games.redeem(ctx["an"], 4, "key-redeem-0001")  # DIEM50 = 80 xu
    again = games.redeem(ctx["an"], 4, "key-redeem-0001")  # gửi lại cùng khóa

    assert first["balance"] == 20 and first["replayed"] is False
    assert again["replayed"] is True and again["voucher"]["id"] == first["voucher"]["id"]
    assert games.portal_game(ctx["an"])["wallet"]["balance"] == 20
    vouchers = ctx["bundle"].vouchers.portal_vouchers(ctx["an"])["items"]
    assert [v["source"] for v in vouchers].count(VoucherSource.GAME) == 1
    redeem_rows = [e for e in games.portal_game(ctx["an"])["ledger"] if e.reason == LedgerReason.REDEEM]
    assert [(e.delta, e.balance_after) for e in redeem_rows] == [(-80, 20)]


def test_cannot_redeem_more_than_balance(ctx):
    spin(ctx)  # 100 xu

    with pytest.raises(ConflictError):
        ctx["games"].redeem(ctx["an"], 1, "key-too-much-01")  # GIAM20K = 200 xu
    assert ctx["games"].portal_game(ctx["an"])["wallet"]["balance"] == 100


def test_reward_without_coin_price_cannot_be_bought(ctx):
    reward = ctx["bundle"].vouchers.save_reward(
        ctx["manager"], None, code="NOCOIN", name="Không bán bằng xu", reward_type="MEMBER_POINTS", value=5,
        min_order_amount=0, valid_days=5, coin_cost=None, is_active=True, all_stores=False)
    spin(ctx)

    with pytest.raises(NotFoundError):
        ctx["games"].redeem(ctx["an"], reward.id, "key-no-coin-001")


@pytest.mark.parametrize("key", [None, "", "short", "has space key", "x" * 65, 12345678])
def test_invalid_request_key_is_rejected(ctx, key):
    with pytest.raises(ValidationError):
        ctx["games"].redeem(ctx["an"], 4, key)


# ----- Quản lý ----------------------------------------------------------------------
def test_staff_sees_stats_but_only_admin_configures(ctx):
    spin(ctx)
    data = ctx["games"].manage(ctx["staff"])

    assert data["stats"]["sessions"] == 1 and data["stats"]["coins_awarded"] == 100
    assert data["can_manage"] is False and data["can_configure"] is False
    prizes = [dict(label="A", coins=1, weight=1), dict(label="B", coins=2, weight=1)]
    with pytest.raises(PermissionDeniedError):
        ctx["games"].save_game(ctx["manager"], is_active=True, daily_limit=5, min_interval_seconds=2, prizes=prizes)
    saved = ctx["games"].save_game(ctx["admin"], is_active=True, daily_limit=5, min_interval_seconds=2, prizes=prizes)
    assert saved.daily_limit == 5 and [p.label for p in saved.prizes] == ["A", "B"]


@pytest.mark.parametrize(
    "prizes",
    [
        [dict(label="Chỉ một ô", coins=1, weight=1)],
        [dict(label="A", coins=-1, weight=1), dict(label="B", coins=1, weight=1)],
        [dict(label="A", coins=1, weight=0), dict(label="B", coins=1, weight=1)],
        [dict(label="", coins=1, weight=1), dict(label="B", coins=1, weight=1)],
        [dict(label="A", coins=1001, weight=1), dict(label="B", coins=1, weight=1)],
    ],
)
def test_invalid_wheel_configuration_is_rejected(ctx, prizes):
    with pytest.raises(ValidationError):
        ctx["games"].save_game(ctx["admin"], is_active=True, daily_limit=3, min_interval_seconds=3, prizes=prizes)
