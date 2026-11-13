"""Khuyến mãi POS: bật/tắt, kiểm tra ngày, số tiền giảm hiển thị rõ, lịch sử thay đổi (bộ nhớ, không cần MySQL).

Dữ liệu demo mỗi cơ sở có 3 ưu đãi đang chạy: DEMO_NUOC_5000 (giảm nước), DEMO_MUA3_TRA2 (mua 3 trả 2)
và DEMO_VIP_10 (hạng GOLD giảm 10%). Khách `lethibinh` đang chơi; `nguyenvanan` thì không.
"""

from datetime import datetime, timedelta, timezone

import pytest

from cyberhub_manager.domain.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from cyberhub_manager.services.menu_service import MAX_PROMOTION_DAYS, PROMOTION_EXPIRED
from cyberhub_manager.services.mocks.clock import MockClock
from cyberhub_manager.services.mocks.factory import build_mock_services

NOW = datetime(2026, 11, 13, 8, tzinfo=timezone.utc)


@pytest.fixture
def ctx():
    clock = MockClock(NOW)
    bundle = build_mock_services(p1=True, clock=clock)
    return dict(
        bundle=bundle, menu=bundle.menu, clock=clock,
        player=bundle.portal.login("lethibinh", "demo123"),
        visitor=bundle.portal.login("nguyenvanan", "demo123"),
        manager=bundle.auth.login("quanly01", "demo123"),
        staff=bundle.auth.login("nhanvien01", "demo123"),
    )


def promo(ctx, code):
    return next(p for p in ctx["menu"].list_promotions(ctx["manager"]) if p["code"] == code)


def coca(ctx):
    menu = ctx["menu"].portal_menu(ctx["player"])
    return next(i for page in menu["pages"] for group in page["categories"] for i in group["items"]
                if i.name == "Coca")


def save(ctx, existing, **changes):
    values = dict(promotion_id=existing["id"], code=existing["code"], kind=existing["kind"],
                  item_id=existing["item_id"], value=existing["value"], minimum_tier=existing["minimum_tier"],
                  starts_at=existing["starts_at"], ends_at=existing["ends_at"], is_active=existing["is_active"])
    values.update(changes)
    return ctx["menu"].save_promotion(ctx["manager"], **values)


def new_promo(ctx, **changes):
    values = dict(code="HAPPY_HOUR", kind="TIER_PERCENT", value=5, minimum_tier="BRONZE",
                  starts_at=NOW, ends_at=NOW + timedelta(days=7), is_active=True)
    values.update(changes)
    return ctx["menu"].save_promotion(ctx["manager"], **values)


# ----- Trạng thái và số tiền đã giảm ---------------------------------------------------
def test_list_shows_state_and_zero_usage_at_first(ctx):
    promotions = ctx["menu"].list_promotions(ctx["manager"])

    assert {p["state"] for p in promotions} == {"ACTIVE"}
    assert all(p["orders_count"] == 0 and p["discount_total"] == 0 for p in promotions)
    assert all(p["starts_at"].tzinfo is not None for p in promotions)


def test_state_follows_switch_and_dates(ctx):
    scheduled = new_promo(ctx, code="LATER", starts_at=NOW + timedelta(days=1), ends_at=NOW + timedelta(days=3))
    assert scheduled["state"] == "SCHEDULED"
    ctx["clock"].advance(hours=24 * 4)

    assert promo(ctx, "LATER")["state"] == "EXPIRED"
    off = ctx["menu"].set_promotion_active(ctx["manager"], promo(ctx, "DEMO_VIP_10")["id"], False)
    assert off["state"] == "OFF" and off["is_active"] is False


def test_usage_counts_discount_given_in_orders(ctx):
    order = ctx["menu"].place_order(ctx["player"], [{"item_id": coca(ctx).id, "quantity": 3}])

    used = promo(ctx, "DEMO_NUOC_5000")
    assert order.discount_amount == 15_000
    assert (used["orders_count"], used["discount_total"]) == (1, 15_000)
    ctx["menu"].finish_order(ctx["staff"], order.id, "CANCELLED")
    assert promo(ctx, "DEMO_NUOC_5000")["orders_count"] == 0  # đơn đã hủy không tính vào số tiền giảm


# ----- Bật/tắt ------------------------------------------------------------------------
def test_switching_off_stops_discount_for_new_orders(ctx):
    item = {"item_id": coca(ctx).id, "quantity": 3}
    ctx["menu"].set_promotion_active(ctx["manager"], promo(ctx, "DEMO_NUOC_5000")["id"], False)
    second_best = ctx["menu"].place_order(ctx["player"], [item])
    assert (second_best.promotion_code, second_best.discount_amount) == ("DEMO_MUA3_TRA2", 10_000)

    for code in ("DEMO_MUA3_TRA2", "DEMO_VIP_10"):
        ctx["menu"].set_promotion_active(ctx["manager"], promo(ctx, code)["id"], False)
    ctx["menu"].finish_order(ctx["staff"], second_best.id, "CANCELLED")
    plain = ctx["menu"].place_order(ctx["player"], [item])
    assert (plain.promotion_code, plain.discount_amount) == (None, 0)


def test_switching_is_idempotent_and_writes_one_history_row(ctx):
    target = promo(ctx, "DEMO_VIP_10")["id"]
    ctx["menu"].set_promotion_active(ctx["manager"], target, False)
    ctx["menu"].set_promotion_active(ctx["manager"], target, False)  # bấm lần hai: không đổi gì

    history = ctx["menu"].promotion_history(ctx["manager"], target)
    assert [h["action"] for h in history] == ["DISABLE"]
    assert history[0]["changes"] == {"is_active": [True, False]}


def test_cannot_switch_on_an_expired_promotion(ctx):
    expired = new_promo(ctx, code="SHORT", ends_at=NOW + timedelta(days=1))
    ctx["menu"].set_promotion_active(ctx["manager"], expired["id"], False)
    ctx["clock"].advance(hours=48)

    with pytest.raises(ValidationError) as info:
        ctx["menu"].set_promotion_active(ctx["manager"], expired["id"], True)
    assert info.value.field_errors == {"ends_at": PROMOTION_EXPIRED}
    assert promo(ctx, "SHORT")["is_active"] is False


# ----- Kiểm tra ngày ---------------------------------------------------------------------
@pytest.mark.parametrize(
    ("starts", "ends", "active", "field"),
    [
        (NOW, NOW, True, "starts_at"),  # kết thúc phải sau bắt đầu
        (NOW + timedelta(days=2), NOW + timedelta(days=1), True, "starts_at"),
        (NOW, NOW + timedelta(days=MAX_PROMOTION_DAYS + 1), True, "ends_at"),  # dài quá một năm
        (NOW - timedelta(days=5), NOW - timedelta(days=1), True, "ends_at"),  # đang bật mà đã quá hạn
    ],
)
def test_invalid_dates_are_rejected(ctx, starts, ends, active, field):
    with pytest.raises(ValidationError) as info:
        new_promo(ctx, starts_at=starts, ends_at=ends, is_active=active)
    assert field in info.value.field_errors


def test_past_promotion_can_be_saved_while_switched_off(ctx):
    archived = new_promo(ctx, code="OLD_ONE", starts_at=NOW - timedelta(days=9), ends_at=NOW - timedelta(days=2),
                         is_active=False)
    assert archived["state"] == "OFF"


def test_naive_datetime_is_rejected(ctx):
    with pytest.raises(ValidationError):
        new_promo(ctx, starts_at=datetime(2026, 11, 13, 8), ends_at=datetime(2026, 11, 14, 8))


# ----- Lịch sử thay đổi ----------------------------------------------------------------------
def test_history_records_create_update_and_switch(ctx):
    created = new_promo(ctx)
    save(ctx, created, value=8)
    save(ctx, promo(ctx, "HAPPY_HOUR"), value=8)  # lưu y nguyên: không thêm dòng lịch sử
    ctx["menu"].set_promotion_active(ctx["manager"], created["id"], False)

    history = ctx["menu"].promotion_history(ctx["manager"], created["id"])

    assert [h["action"] for h in history] == ["DISABLE", "UPDATE", "CREATE"]
    assert history[1]["changes"] == {"value": [5, 8]}
    assert history[2]["changes"]["code"] == [None, "HAPPY_HOUR"]
    assert {h["employee_name"] for h in history} == {ctx["manager"].full_name}


def test_failed_save_leaves_no_history(ctx):
    target = promo(ctx, "DEMO_VIP_10")
    with pytest.raises(ValidationError):
        save(ctx, target, value=0)
    assert ctx["menu"].promotion_history(ctx["manager"], target["id"]) == []


# ----- Quyền và phạm vi cơ sở ----------------------------------------------------------------------
def test_staff_cannot_manage_or_view_promotions(ctx):
    target = promo(ctx, "DEMO_VIP_10")["id"]
    for call in (
        lambda: ctx["menu"].set_promotion_active(ctx["staff"], target, False),
        lambda: ctx["menu"].promotion_history(ctx["staff"], target),
        lambda: ctx["menu"].list_promotions(ctx["staff"]),
    ):
        with pytest.raises(PermissionDeniedError):
            call()


def test_promotion_of_another_store_is_not_found(ctx):
    other = next(p for p in ctx["menu"]._repo.promotions.values() if p["store_id"] != ctx["manager"].store_id)

    with pytest.raises(NotFoundError):
        ctx["menu"].set_promotion_active(ctx["manager"], other["id"], False)
    with pytest.raises(NotFoundError):
        ctx["menu"].promotion_history(ctx["manager"], other["id"])
    assert ctx["menu"]._repo.promotions[other["id"]]["is_active"] is True


@pytest.mark.parametrize("promotion_id", [0, -1, True, "1", None, 9999])
def test_invalid_promotion_id_is_not_found(ctx, promotion_id):
    with pytest.raises(NotFoundError):
        ctx["menu"].promotion_history(ctx["manager"], promotion_id)


# ----- Báo giá cho khách ----------------------------------------------------------------------------
def test_quote_matches_the_order_that_follows_and_writes_nothing(ctx):
    lines = [{"item_id": coca(ctx).id, "quantity": 3}]

    quote = ctx["menu"].quote_order(ctx["player"], lines)

    assert (quote["gross_amount"], quote["discount_amount"], quote["final_amount"]) == (30_000, 15_000, 15_000)
    assert (quote["promotion_code"], quote["promotion_kind"]) == ("DEMO_NUOC_5000", "PLAY_DRINK")
    assert ctx["menu"].portal_menu(ctx["player"])["orders"] == []
    order = ctx["menu"].place_order(ctx["player"], lines)
    assert (order.total_amount, order.discount_amount, order.promotion_code) == (30_000, 15_000, "DEMO_NUOC_5000")


def test_quote_follows_the_switch(ctx):
    lines = [{"item_id": coca(ctx).id, "quantity": 3}]
    for code in ("DEMO_NUOC_5000", "DEMO_MUA3_TRA2", "DEMO_VIP_10"):
        ctx["menu"].set_promotion_active(ctx["manager"], promo(ctx, code)["id"], False)

    quote = ctx["menu"].quote_order(ctx["player"], lines)

    assert (quote["discount_amount"], quote["final_amount"], quote["promotion_code"]) == (0, 30_000, None)


def test_quote_skips_unavailable_items_and_requires_a_session(ctx):
    menu = ctx["menu"].portal_menu(ctx["player"])
    sold_out = next(i for page in menu["pages"] for group in page["categories"] for i in group["items"]
                    if not i.is_available)

    quote = ctx["menu"].quote_order(ctx["player"], [{"item_id": sold_out.id, "quantity": 1}])
    assert quote["gross_amount"] == 0 and quote["unavailable"] == [sold_out.name]
    with pytest.raises(ValidationError):
        ctx["menu"].quote_order(ctx["visitor"], [{"item_id": coca(ctx).id, "quantity": 1}])


@pytest.mark.parametrize(
    "lines",
    [[], "x", [{"item_id": 1, "quantity": 0}], [{"item_id": 1, "quantity": 99}], [{"item_id": True, "quantity": 1}],
     [{"item_id": 1, "quantity": 1}, {"item_id": 1, "quantity": 2}]],
)
def test_malformed_quote_lines_are_rejected(ctx, lines):
    with pytest.raises(ValidationError):
        ctx["menu"].quote_order(ctx["player"], lines)
