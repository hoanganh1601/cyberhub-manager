"""Đợt 2 — Nghiệp vụ voucher (VoucherService trên repository bộ nhớ, không cần MySQL).

Voucher demo (theo thứ tự phát):
  CHDEMO0001 nguyenvanan  GIO10K   (cộng 10.000đ giờ chơi)   còn hạn
  CHDEMO0002 nguyenvanan  DIEM50   (50 điểm)                  còn hạn
  CHDEMO0003 nguyenvanan  GIAM20K  (giảm 20.000đ, đơn ≥ 50k)  hết hạn
  CHDEMO0004 lethibinh    GIAM20K                              còn hạn
  CHDEMO0005 lethibinh    NUOCFREE (tặng nước ≤ 20.000đ)       còn hạn
  CHDEMO0006 lethibinh    DIEM50                               đã dùng
"""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from cyberhub_manager.domain.exceptions import (
    ConflictError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.voucher import RewardType, VoucherAction, VoucherSource, VoucherState
from cyberhub_manager.services.mocks.clock import MockClock
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.services.voucher_service import REJECT_MESSAGES

NOW = datetime(2026, 10, 18, 9, tzinfo=timezone.utc)


@pytest.fixture
def ctx():
    bundle = build_mock_services(p1=True, clock=MockClock(NOW))
    return dict(
        bundle=bundle,
        svc=bundle.vouchers,
        an=bundle.portal.login("nguyenvanan", DEMO_PASSWORD),
        binh=bundle.portal.login("lethibinh", DEMO_PASSWORD),
        manager=bundle.auth.login("quanly01", DEMO_PASSWORD),
        staff=bundle.auth.login("nhanvien01", DEMO_PASSWORD),
        admin=bundle.auth.login("admin01", DEMO_PASSWORD),
    )


def account(ctx, principal):
    return ctx["svc"]._repo.data.customers[principal.customer_id].account


def rejects(ctx, code, customer, reason, order_id=None):
    with pytest.raises(ConflictError) as info:
        ctx["svc"].redeem(ctx["staff"], code, customer.customer_id, order_id)
    assert info.value.message.startswith(REJECT_MESSAGES[reason])


# ----- Khách xem voucher -----------------------------------------------------------
def test_customer_sees_own_vouchers_with_derived_state(ctx):
    data = ctx["svc"].portal_vouchers(ctx["an"])

    states = sorted(v["state"].value for v in data["items"])
    assert states == ["ACTIVE", "ACTIVE", "EXPIRED"]
    assert data["active"] == 2
    assert {v["customer_id"] for v in data["items"]} == {ctx["an"].customer_id}


# ----- Xác nhận sử dụng -------------------------------------------------------------
def test_playtime_voucher_credits_promotional_balance_once(ctx):
    before = account(ctx, ctx["an"]).bonus_balance

    result = ctx["svc"].redeem(ctx["staff"], "chdemo-0001", ctx["an"].customer_id)

    assert result.reward_type == RewardType.PLAYTIME_CREDIT and result.bonus_credited == 10_000
    assert account(ctx, ctx["an"]).bonus_balance == before + 10_000
    assert result.voucher.state(NOW) == VoucherState.USED
    rejects(ctx, "CHDEMO0001", ctx["an"], "USED")  # dùng lại bị từ chối
    assert account(ctx, ctx["an"]).bonus_balance == before + 10_000


def test_member_points_voucher_adds_points_but_not_spend(ctx):
    loyalty = ctx["bundle"].portal._repo
    before = loyalty.loyalty_summary(None, ctx["an"].customer_id)

    result = ctx["svc"].redeem(ctx["staff"], "CHDEMO0002", ctx["an"].customer_id)

    after = loyalty.loyalty_summary(None, ctx["an"].customer_id)
    assert result.points_granted == 50
    assert after["points"] == before["points"] + 50
    assert after["tier"] == before["tier"]  # tặng điểm không đổi hạng


def test_wrong_owner_expired_and_used_are_rejected(ctx):
    rejects(ctx, "CHDEMO0001", ctx["binh"], "WRONG_OWNER")
    rejects(ctx, "CHDEMO0003", ctx["an"], "EXPIRED")
    rejects(ctx, "CHDEMO0006", ctx["binh"], "USED")
    rejects(ctx, "CHKHONGCO1", ctx["an"], "UNKNOWN")


def test_revoked_voucher_is_rejected(ctx):
    svc = ctx["svc"]
    voucher = svc.lookup(ctx["manager"], "CHDEMO0002")["voucher"]

    svc.revoke(ctx["manager"], voucher["id"], "Phát nhầm khách")

    rejects(ctx, "CHDEMO0002", ctx["an"], "REVOKED")
    with pytest.raises(ConflictError):
        svc.revoke(ctx["manager"], voucher["id"], "Khóa lần hai")


def test_rejections_are_logged_and_kept(ctx):
    rejects(ctx, "CHDEMO0003", ctx["an"], "EXPIRED")
    rejects(ctx, "CHKHONGCO1", ctx["an"], "UNKNOWN")

    events = ctx["svc"].overview(ctx["staff"])["events"]

    assert [e.action for e in events[:2]] == [VoucherAction.REJECT, VoucherAction.REJECT]
    assert events[0].voucher_id is None and "UNKNOWN" in events[0].reason
    assert events[1].reason == "EXPIRED"


@pytest.mark.parametrize("code", ["", "AB", "CH-!!!", None, 123, "X" * 21])
def test_malformed_code_is_rejected_before_database(ctx, code):
    with pytest.raises(ValidationError):
        ctx["svc"].redeem(ctx["staff"], code, ctx["an"].customer_id)


def test_food_voucher_needs_eligible_order_and_applies_once(ctx):
    bundle, binh = ctx["bundle"], ctx["binh"]
    menu = bundle.menu.portal_menu(binh)
    items = {i.name: i for p in menu["pages"] for g in p["categories"] for i in g["items"]}

    rejects(ctx, "CHDEMO0004", binh, "ORDER_REQUIRED")
    small = bundle.menu.place_order(binh, [{"item_id": items["Coca"].id, "quantity": 1}])
    rejects(ctx, "CHDEMO0004", binh, "MIN_ORDER", small.id)  # 10.000đ < 50.000đ

    big = bundle.menu.place_order(binh, [{"item_id": items["Cơm chiên bò"].id, "quantity": 2}])
    result = ctx["svc"].redeem(ctx["staff"], "CHDEMO0004", binh.customer_id, big.id)
    assert result.discount == 20_000

    rejects(ctx, "CHDEMO0005", binh, "ORDER_HAS_VOUCHER", big.id)  # một đơn chỉ một voucher
    assert ctx["svc"].redeem(ctx["staff"], "CHDEMO0005", binh.customer_id, small.id).discount == 10_000


def test_food_voucher_does_not_stack_with_better_pos_promotion(ctx):
    binh = ctx["binh"]
    menu = ctx["bundle"].menu.portal_menu(binh)
    coca = next(i for page in menu["pages"] for group in page["categories"]
                for i in group["items"] if i.name == "Coca")
    order = ctx["bundle"].menu.place_order(binh, [{"item_id": coca.id, "quantity": 6}])
    assert order.discount_amount == 30_000
    rejects(ctx, "CHDEMO0005", binh, "PROMOTION_BETTER", order.id)
    assert ctx["bundle"].menu._repo.get_order(None, order.id).discount_amount == 30_000


def test_food_voucher_cannot_use_another_customers_order(ctx):
    bundle = ctx["bundle"]
    menu = bundle.menu.portal_menu(ctx["binh"])
    item = next(i for p in menu["pages"] for g in p["categories"] for i in g["items"] if i.is_available)
    order = bundle.menu.place_order(ctx["binh"], [{"item_id": item.id, "quantity": 1}])
    voucher = ctx["svc"].issue_voucher(ctx["manager"], 2, ctx["an"].customer_id)  # NUOCFREE cho An

    rejects(ctx, voucher.code, ctx["an"], "ORDER_INVALID", order.id)


def test_voucher_scoped_to_other_store_is_rejected(ctx):
    svc, manager = ctx["svc"], ctx["manager"]
    reward = svc.save_reward(manager, None, code="CH1ONLY", name="Chỉ cơ sở 1", reward_type="PLAYTIME_CREDIT",
                             value=5_000, min_order_amount=0, valid_days=7, coin_cost=None, is_active=True,
                             all_stores=False)
    voucher = svc.issue_voucher(manager, reward.id, ctx["an"].customer_id)
    other_store = next(s for s in ctx["bundle"].vouchers._p1.list_stores(None) if s.id != manager.store_id)
    admin_elsewhere = replace(ctx["admin"], store_id=other_store.id)

    with pytest.raises(ConflictError) as info:
        svc.redeem(admin_elsewhere, voucher.code, ctx["an"].customer_id)
    assert info.value.message == REJECT_MESSAGES["WRONG_STORE"]


# ----- Quản trị ----------------------------------------------------------------------
def test_staff_cannot_manage_rewards_or_issue(ctx):
    svc, staff = ctx["svc"], ctx["staff"]

    assert svc.overview(staff)["can_manage"] is False
    with pytest.raises(PermissionDeniedError):
        svc.issue_voucher(staff, 1, ctx["an"].customer_id)
    with pytest.raises(PermissionDeniedError):
        svc.save_reward(staff, None, code="X1", name="x", reward_type="MEMBER_POINTS", value=1,
                        min_order_amount=0, valid_days=1, coin_cost=None, is_active=True, all_stores=False)
    with pytest.raises(PermissionDeniedError):
        svc.revoke(staff, 1, "không có quyền")


def test_manager_issues_voucher_with_random_code_and_snapshot(ctx):
    svc = ctx["svc"]
    voucher = svc.issue_voucher(ctx["manager"], 1, ctx["an"].customer_id)  # GIAM20K

    assert voucher.code.startswith("CH") and len(voucher.code) == 10
    assert voucher.source == VoucherSource.MANUAL
    assert (voucher.expires_at - voucher.issued_at).days == 30
    # Sửa danh mục sau khi phát không đổi điều kiện voucher đã phát.
    reward = svc._repo.get_catalog(None, 1)
    svc.save_reward(ctx["manager"] if reward.store_id else ctx["admin"], 1, code=reward.code, name=reward.name,
                    reward_type=reward.reward_type, value=5_000, min_order_amount=0, valid_days=reward.valid_days,
                    coin_cost=reward.coin_cost, is_active=True, all_stores=reward.store_id is None)
    assert svc.lookup(ctx["staff"], voucher.code)["voucher"]["value"] == 20_000


def test_only_admin_creates_rewards_for_all_stores(ctx):
    svc = ctx["svc"]
    fields = dict(code="ALL1", name="Mọi cơ sở", reward_type="MEMBER_POINTS", value=10, min_order_amount=0,
                  valid_days=10, coin_cost=None, is_active=True, all_stores=True)

    with pytest.raises(PermissionDeniedError):
        svc.save_reward(ctx["manager"], None, **fields)
    assert svc.save_reward(ctx["admin"], None, **fields).store_id is None


@pytest.mark.parametrize(
    "changes",
    [
        dict(value=0), dict(value=1_000_001), dict(reward_type="CASH"), dict(valid_days=0),
        dict(valid_days=366), dict(code="có dấu"), dict(min_order_amount=10_000),  # đơn tối thiểu cho loại điểm
        dict(coin_cost=0),
    ],
)
def test_invalid_reward_definitions_are_rejected(ctx, changes):
    fields = dict(code="BAD1", name="Sai", reward_type="MEMBER_POINTS", value=10, min_order_amount=0,
                  valid_days=10, coin_cost=None, is_active=True, all_stores=False)
    fields.update(changes)
    with pytest.raises(ValidationError):
        ctx["svc"].save_reward(ctx["manager"], None, **fields)


def test_issue_from_same_source_is_idempotent(ctx):
    svc = ctx["svc"]
    catalog = svc._repo.get_catalog(None, 4)
    with svc._transaction() as conn:
        first = svc.issue_in_transaction(conn, catalog=catalog, account_id=ctx["an"].account_id,
                                         source=VoucherSource.GAME, source_ref="spin-42", employee_id=None,
                                         store_id=None)
        second = svc.issue_in_transaction(conn, catalog=catalog, account_id=ctx["an"].account_id,
                                          source=VoucherSource.GAME, source_ref="spin-42", employee_id=None,
                                          store_id=None)
    assert first.id == second.id


def test_customer_cannot_read_others_vouchers_with_forged_principal(ctx):
    forged = replace(ctx["an"], customer_id=ctx["binh"].customer_id)
    with pytest.raises(PermissionDeniedError):
        ctx["svc"].portal_vouchers(forged)
