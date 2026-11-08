"""Membership money boundaries, policy snapshots and audience authorization."""

from dataclasses import replace
from datetime import timedelta
from io import BytesIO
import pytest
from PIL import Image

from cyberhub_manager.domain.loyalty import LoyaltySettings, membership
from cyberhub_manager.domain.p1 import Promotion
from cyberhub_manager.domain.enums import PaymentMethod
from cyberhub_manager.domain.exceptions import (
    PermissionDeniedError,
    ValidationError,
    ConflictError,
    NotFoundError,
)
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.clock import MockClock
from cyberhub_manager.services.avatar import normalize_avatar


@pytest.fixture
def scenario():
    clock = MockClock()
    bundle = build_mock_services(p1=True, customer_offers=True, clock=clock)
    return (
        bundle,
        bundle.portal.login("nguyenvanan", "demo123"),
        bundle.auth.login("admin01", "demo123"),
        clock,
    )


def test_opening_points_and_void_reversal_are_invoice_based(scenario):
    b, c, _, _ = scenario
    m = b.portal.member(c)
    assert m["points"] == 5 and m["eligible_spend"] == 50000 and m["tier"] == "BRONZE"
    b.portal._repo.data.invoices[1].void()
    m = b.portal.member(c)
    assert m["points"] == 2 and m["eligible_spend"] == 20000
    void = next(i for i in m["history"]["items"] if i["status"] == "VOID")
    assert void["points"] == 3 and void["effective_points"] == 0
    assert all(
        p.target_customer_id is None for p in b.portal.dashboard(c)["promotions"]
    )


@pytest.mark.parametrize(
    "spent,tier",
    [
        (0, "BRONZE"),
        (999999, "BRONZE"),
        (1000000, "SILVER"),
        (3000000, "GOLD"),
        (5000000, "PLATINUM"),
    ],
)
def test_exact_tier_boundaries(spent, tier):
    assert membership(0, spent, LoyaltySettings())["tier"] == tier


def test_bonus_does_not_earn_points_and_snapshot_keeps_old_rule(scenario):
    b, c, a, clock = scenario
    b.wallet.top_up(1, 100000, PaymentMethod.CASH, a.employee_id)
    b.sessions.open_session(1, 1, a)
    clock.advance(hours=1)
    b.sessions.complete_checkout(1, a, 0, None)  # 10,000 paid entirely from bonus
    assert b.portal.member(c)["points"] == 5
    config = b.management.loyalty_settings(a)
    b.management.update_loyalty_settings(a, replace(config, unit_amount=5000))
    b.sessions.open_session(1, 1, a)
    clock.advance(hours=1)
    b.sessions.complete_checkout(1, a, 0, None)
    m = b.portal.member(c)
    assert m["points"] == 7 and m["eligible_spend"] == 60000
    assert (
        m["history"]["items"][0]["unit_amount"] == 5000
        and m["history"]["items"][0]["rule_version"] == 2
    )
    assert (
        next(i for i in m["history"]["items"] if i["code"] == "HD0001")["unit_amount"]
        == 10000
    )


def test_personalized_quotes_match_staff_and_never_leak_to_other_customer(scenario):
    b, c, a, _ = scenario
    q = b.portal.promotion_quote(c, 1, 300000)
    assert q["bonus_amount"] == 75000 and q["promotion"].target_customer_id == 1
    assert b.wallet.preview_top_up(1, 300000, a.employee_id).bonus_amount == 75000
    other = b.portal.login("lethibinh", "demo123")
    assert b.portal.promotion_quote(other, 1, 300000)["bonus_amount"] == 60000
    assert all(
        p.target_customer_id is None for p in b.portal.dashboard(other)["promotions"]
    )
    assert all(
        n.get("code") != "DEMO-PERSONAL" for n in b.portal.notifications(other)["items"]
    )


def test_public_and_personal_same_threshold_do_not_stack(scenario):
    b, c, a, clock = scenario
    now = clock.now()
    b.management.save_promotion(
        a,
        Promotion(
            0,
            "FOR-AN",
            "For An",
            None,
            100000,
            15,
            now - timedelta(days=1),
            now + timedelta(days=1),
            True,
            "BRONZE",
            5,
            1,
        ),
    )
    assert b.portal.promotion_quote(c, 1, 100000)["bonus_amount"] == 15000
    assert (
        b.wallet.top_up(1, 100000, PaymentMethod.CASH, a.employee_id).bonus_amount
        == 15000
    )


def test_settings_admin_only_optimistic_and_no_retroactive_point_changes(scenario):
    b, c, a, _ = scenario
    config = b.management.loyalty_settings(a)
    manager = b.auth.login("quanly01", "demo123")
    with pytest.raises(PermissionDeniedError):
        b.management.update_loyalty_settings(manager, config)
    updated = b.management.update_loyalty_settings(
        a, replace(config, silver_spend=40000)
    )
    assert b.portal.member(c)["tier"] == "SILVER" and b.portal.member(c)["points"] == 5
    with pytest.raises(ConflictError):
        b.management.update_loyalty_settings(a, config)
    assert b.management.loyalty_settings(a) == updated
    with pytest.raises(ValidationError):
        b.management.update_loyalty_settings(a, replace(updated, unit_amount=True))


def test_pausing_new_points_preserves_past_points_and_tier_spend(scenario):
    b, c, a, clock = scenario
    config = b.management.loyalty_settings(a)
    b.management.update_loyalty_settings(a, replace(config, enabled=False))
    b.sessions.open_session(1, 1, a)
    clock.advance(hours=1)
    b.sessions.complete_checkout(1, a, 0, None)
    member = b.portal.member(c)
    assert (
        member["points"] == 5
        and member["eligible_spend"] == 60000
        and not member["enabled"]
    )


def test_avatar_normalized_owned_and_failed_upload_preserves_old_image(scenario):
    b, c, _, _ = scenario
    source = BytesIO()
    Image.new("RGB", (900, 400), "cyan").save(source, format="PNG")
    result = b.portal.update_avatar(c, source.getvalue())
    photo = b.portal.avatar(c)
    assert result["avatar_version"] == photo["digest"]
    with Image.open(BytesIO(photo["image_data"])) as image:
        assert image.format == "WEBP" and image.size == (512, 512)
    with pytest.raises(ValidationError):
        b.portal.update_avatar(c, b"<svg></svg>")
    assert b.portal.avatar(c) == photo
    other = b.portal.login("hoangvanem", "demo123")
    with pytest.raises(NotFoundError):
        b.portal.avatar(other)
    b.portal.remove_avatar(c)
    b.portal.remove_avatar(c)
    assert b.portal.dashboard(c)["avatar_version"] is None


@pytest.mark.parametrize(
    "content",
    [b"", b"not-an-image", b"x" * (2 * 1024 * 1024 + 1)],
    ids=["empty", "invalid", "oversize"],
)
def test_invalid_avatar_data_rejected(content):
    with pytest.raises(ValidationError):
        normalize_avatar(content)


def test_image_dimension_and_animation_limits():
    source = BytesIO()
    Image.new("RGB", (8193, 1)).save(source, format="PNG")
    with pytest.raises(ValidationError):
        normalize_avatar(source.getvalue())
    source = BytesIO()
    Image.new("RGB", (10, 10), "red").save(source, format="GIF")
    with pytest.raises(ValidationError):
        normalize_avatar(source.getvalue())


def test_locked_account_cannot_access_membership_or_avatar(scenario):
    b, c, _, _ = scenario
    b.portal._repo.data.customers[1].account.lock()
    for call in (
        lambda: b.portal.member(c),
        lambda: b.portal.avatar(c),
        lambda: b.portal.remove_avatar(c),
        lambda: b.portal.update_avatar(c, b"anything"),
    ):
        with pytest.raises(PermissionDeniedError):
            call()
