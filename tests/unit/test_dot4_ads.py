"""Đợt 4 — Quảng cáo nhận thưởng (AdService trên repository bộ nhớ, đồng hồ giả lập).

Mặc định: quảng cáo nội bộ (HOUSE), thưởng +1 lượt quay, tối đa 3 lần/ngày; nội dung dài 10–15 giây.
"""

from datetime import datetime, timezone

import pytest

from cyberhub_manager.domain.ad import START_FACTOR, AdMode
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.game import LedgerReason
from cyberhub_manager.services.ad_service import (
    ADS_PAUSED,
    ALREADY_HANDLED,
    CAP_REACHED,
    EXPIRED,
    TOO_EARLY,
    TOO_MANY_STARTS,
    WAIT_PROVIDER,
    WALLET_LOCKED,
    sign_callback,
)
from cyberhub_manager.services.game_service import LIMIT_REACHED
from cyberhub_manager.services.mocks.clock import MockClock
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD

NOW = datetime(2026, 10, 18, 9, tzinfo=timezone.utc)
SECRET = "unit-test-ssv-secret"


class FixedRandom:
    def choices(self, population, weights):
        return [population[0]]  # luôn ô 0 = 5 xu


@pytest.fixture
def ctx():
    clock = MockClock(NOW)
    bundle = build_mock_services(p1=True, clock=clock)
    bundle.games._random = FixedRandom()
    bundle.ads._secret = b""  # không phụ thuộc biến môi trường của máy chạy test
    return dict(
        bundle=bundle, ads=bundle.ads, games=bundle.games, clock=clock,
        an=bundle.portal.login("nguyenvanan", DEMO_PASSWORD),
        binh=bundle.portal.login("lethibinh", DEMO_PASSWORD),
        manager=bundle.auth.login("quanly01", DEMO_PASSWORD),
        staff=bundle.auth.login("nhanvien01", DEMO_PASSWORD),
        admin=bundle.auth.login("admin01", DEMO_PASSWORD),
    )


def watch(ctx, principal=None, seconds=61):
    """Bắt đầu xem, chờ đủ thời lượng theo đồng hồ giả lập, rồi nhận thưởng."""
    principal = principal or ctx["an"]
    ad = ctx["ads"].start(principal)
    ctx["clock"].advance(seconds=seconds)
    return ad, ctx["ads"].complete(principal, ad["token"])


def conflict(func, message):
    with pytest.raises(ConflictError) as info:
        func()
    assert info.value.message == message


def set_settings(ctx, **changes):
    s = ctx["ads"].overview(ctx["admin"])["settings"]
    values = dict(enabled=s.enabled, mode=s.mode, daily_cap=s.daily_cap, reward_type=s.reward_type,
                  reward_amount=s.reward_amount)
    values.update(changes)
    return ctx["ads"].save_settings(ctx["admin"], **values)


# ----- Luồng HOUSE ------------------------------------------------------------------
def test_start_issues_one_time_token_and_creative(ctx):
    info = ctx["ads"].portal_ads(ctx["an"])
    ad = ctx["ads"].start(ctx["an"])

    assert info["enabled"] is True and info["remaining"] == 3
    assert len(ad["token"]) == 32 and int(ad["token"], 16) >= 0
    assert ad["provider"] == AdMode.HOUSE and 5 <= ad["duration_seconds"] <= 60
    assert ad["creative"]["title"]


def test_completing_too_early_burns_the_token(ctx):
    ad = ctx["ads"].start(ctx["an"])
    ctx["clock"].advance(seconds=2)

    conflict(lambda: ctx["ads"].complete(ctx["an"], ad["token"]), TOO_EARLY)
    ctx["clock"].advance(seconds=60)
    conflict(lambda: ctx["ads"].complete(ctx["an"], ad["token"]), ALREADY_HANDLED)  # không thử lại được
    assert ctx["ads"].portal_ads(ctx["an"])["remaining"] == 3


def test_valid_view_grants_extra_spin_once(ctx):
    ad, result = watch(ctx)

    assert result["reward_type"] == "EXTRA_SPIN" and result["reward_amount"] == 1
    conflict(lambda: ctx["ads"].complete(ctx["an"], ad["token"]), ALREADY_HANDLED)  # gửi lại cùng sự kiện
    game = ctx["games"].portal_game(ctx["an"])
    assert game["spins_left"] == 4 and game["bonus_spins"] == 1


def test_extra_spin_really_allows_one_more_spin(ctx):
    for _ in range(3):
        ctx["clock"].advance(seconds=5)
        ctx["games"].spin(ctx["an"])
    watch(ctx)

    ctx["clock"].advance(seconds=5)
    assert ctx["games"].spin(ctx["an"])["spins_left"] == 0
    ctx["clock"].advance(seconds=5)
    conflict(lambda: ctx["games"].spin(ctx["an"]), LIMIT_REACHED)


def test_expired_token_is_rejected(ctx):
    ad = ctx["ads"].start(ctx["an"])
    ctx["clock"].advance(hours=2)

    conflict(lambda: ctx["ads"].complete(ctx["an"], ad["token"]), EXPIRED)


def test_daily_cap_then_reset_next_day(ctx):
    for _ in range(3):
        watch(ctx)
    conflict(lambda: ctx["ads"].start(ctx["an"]), CAP_REACHED)
    assert ctx["ads"].portal_ads(ctx["an"])["remaining"] == 0

    ctx["clock"].advance(hours=24)
    assert ctx["ads"].portal_ads(ctx["an"])["remaining"] == 3


def test_new_start_supersedes_unused_token(ctx):
    first = ctx["ads"].start(ctx["an"])
    ctx["ads"].start(ctx["an"])
    ctx["clock"].advance(seconds=61)

    conflict(lambda: ctx["ads"].complete(ctx["an"], first["token"]), ALREADY_HANDLED)


def test_too_many_starts_without_completing_is_blocked(ctx):
    for _ in range(3 * START_FACTOR):
        ctx["ads"].start(ctx["an"])

    conflict(lambda: ctx["ads"].start(ctx["an"]), TOO_MANY_STARTS)


def test_customer_cannot_complete_someone_elses_token(ctx):
    ad = ctx["ads"].start(ctx["an"])
    ctx["clock"].advance(seconds=61)

    with pytest.raises(NotFoundError):
        ctx["ads"].complete(ctx["binh"], ad["token"])


@pytest.mark.parametrize("token", [None, "", "abc", "Z" * 32, "a" * 33, 123])
def test_malformed_token_is_rejected(ctx, token):
    with pytest.raises(ValidationError):
        ctx["ads"].complete(ctx["an"], token)


def test_coin_reward_goes_through_coin_ledger(ctx):
    set_settings(ctx, reward_type="COINS", reward_amount=20)
    ad, result = watch(ctx)

    assert result["coin_balance"] == 20
    game = ctx["games"].portal_game(ctx["an"])
    assert game["wallet"]["balance"] == 20 and game["bonus_spins"] == 0
    [entry] = game["ledger"]
    assert (entry.reason, entry.delta, entry.ref) == (LedgerReason.AD, 20, f"ad:{ad['token']}")


def test_paused_program_and_locked_wallet_block_ads(ctx):
    ctx["games"].set_wallet_lock(ctx["manager"], ctx["an"].account_id, True, "Kiểm tra gian lận")
    conflict(lambda: ctx["ads"].start(ctx["an"]), WALLET_LOCKED)
    assert ctx["ads"].portal_ads(ctx["an"])["enabled"] is False

    set_settings(ctx, enabled=False)
    conflict(lambda: ctx["ads"].start(ctx["binh"]), ADS_PAUSED)


# ----- Luồng NETWORK (xác minh phía máy chủ) ---------------------------------------------
def test_network_mode_requires_configured_secret(ctx):
    with pytest.raises(ValidationError):
        set_settings(ctx, mode="NETWORK")


def test_network_reward_only_via_signed_callback(ctx):
    ctx["ads"]._secret = SECRET.encode()
    set_settings(ctx, mode="NETWORK")
    ad = ctx["ads"].start(ctx["an"])
    ctx["clock"].advance(seconds=61)

    conflict(lambda: ctx["ads"].complete(ctx["an"], ad["token"]), WAIT_PROVIDER)  # client không tự nhận được
    with pytest.raises(PermissionDeniedError):
        ctx["ads"].verify_network_callback(ad["token"], "txn-0001", "0" * 64)  # chữ ký sai

    result = ctx["ads"].verify_network_callback(ad["token"], "txn-0001", sign_callback(SECRET, ad["token"], "txn-0001"))
    assert result["reward_type"] == "EXTRA_SPIN"
    conflict(lambda: ctx["ads"].verify_network_callback(
        ad["token"], "txn-0001", sign_callback(SECRET, ad["token"], "txn-0001")), ALREADY_HANDLED)

    other = ctx["ads"].start(ctx["an"])  # dùng lại mã giao dịch cũ cho token khác
    conflict(lambda: ctx["ads"].verify_network_callback(
        other["token"], "txn-0001", sign_callback(SECRET, other["token"], "txn-0001")), ALREADY_HANDLED)


def test_callback_rejected_when_secret_missing(ctx):
    with pytest.raises(PermissionDeniedError):
        ctx["ads"].verify_network_callback("a" * 32, "txn-1", "0" * 64)


# ----- Quản trị ----------------------------------------------------------------------
def test_overview_counts_valid_and_rejected_without_exposing_tokens(ctx):
    watch(ctx)
    ad = ctx["ads"].start(ctx["binh"])
    ctx["clock"].advance(seconds=1)
    with pytest.raises(ConflictError):
        ctx["ads"].complete(ctx["binh"], ad["token"])

    data = ctx["ads"].overview(ctx["staff"])

    [today] = data["stats"]
    assert (today["issued"], today["completed"], today["rejected"], today["spins"]) == (2, 1, 1, 1)
    assert all("token" not in e for e in data["recent"])
    assert data["can_configure"] is False


def test_only_admin_changes_settings_and_creatives(ctx):
    with pytest.raises(PermissionDeniedError):
        ctx["ads"].save_settings(ctx["manager"], enabled=True, mode="HOUSE", daily_cap=5,
                                 reward_type="EXTRA_SPIN", reward_amount=1)
    with pytest.raises(PermissionDeniedError):
        ctx["ads"].save_creative(ctx["manager"], None, code="NEW1", title="T", body="B", cta="",
                                 duration_seconds=10, is_active=True)
    creative = ctx["ads"].save_creative(ctx["admin"], None, code="NEW1", title="Giờ vàng", body="Giảm giờ chơi",
                                        cta="", duration_seconds=10, is_active=True)
    assert creative.code == "NEW1"


@pytest.mark.parametrize(
    "changes",
    [dict(daily_cap=0), dict(daily_cap=11), dict(reward_type="EXTRA_SPIN", reward_amount=4),
     dict(reward_type="COINS", reward_amount=101), dict(mode="POPUP"), dict(enabled="yes")],
)
def test_invalid_settings_are_rejected(ctx, changes):
    with pytest.raises(ValidationError):
        set_settings(ctx, **changes)
