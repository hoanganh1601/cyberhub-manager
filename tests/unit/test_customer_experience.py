"""Business regressions for the customer portal, independent of presentation."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from cyberhub_manager.domain.enums import PaymentMethod
from cyberhub_manager.domain.exceptions import PermissionDeniedError, ValidationError
from cyberhub_manager.domain.p1 import Promotion
from cyberhub_manager.services.mocks.clock import MockClock
from cyberhub_manager.services.mocks.factory import build_mock_services

NOW = datetime(2026, 10, 18, 9, tzinfo=timezone.utc)


@pytest.fixture
def scenario():
    clock = MockClock(NOW)
    bundle = build_mock_services(p1=True, clock=clock)
    customer = bundle.portal.login("nguyenvanan", "demo123")
    admin = bundle.auth.login("admin01", "demo123")
    return bundle, customer, admin, clock


def test_dashboard_counts_paid_cost_once_not_wallet_credits(scenario):
    bundle, customer, _, _ = scenario
    result = bundle.portal.dashboard(customer)
    assert result["totals"]["spent"] == 50000
    assert result["totals"]["topped_up"] == 100000
    assert result["totals"]["paid_invoices"] == 2
    assert result["totals"]["usage_seconds"] == 5 * 3600
    assert result["totals"]["average_invoice"] == 25000
    assert sum(r["spent"] for r in result["chart"]) == 50000
    assert len(result["chart"]) == 30
    assert result["wallet"]["balance"] == 50000


def test_checkout_settlement_not_counted_twice(scenario):
    bundle, _, _, _ = scenario
    em = bundle.portal.login("hoangvanem", "demo123")
    result = bundle.portal.dashboard(em)
    assert result["totals"]["spent"] == 10000
    assert result["totals"]["topped_up"] == 105000  # excludes the 5,000 settlement
    assert result["totals"]["usage_seconds"] == 90 * 60
    assert result["active_sessions"][0]["estimated_cost"] == 5000


def test_full_history_paginates_beyond_100_and_aggregates_all(scenario):
    bundle, customer, admin, _ = scenario
    for _ in range(110):
        bundle.wallet.top_up(1, 1000, PaymentMethod.CASH, admin.employee_id)
    history = bundle.portal.history(customer, status="TOP_UP", page=3, page_size=50)
    assert history["total"] == 111 and len(history["items"]) == 11
    assert bundle.portal.dashboard(customer)["totals"]["topped_up"] == 210000
    assert len(bundle.portal.snapshot(customer)["transactions"]) == 100


def test_vietnam_midnight_endpoints_and_zero_days(scenario):
    bundle, _, _, _ = scenario
    em = bundle.portal.login("hoangvanem", "demo123")
    today = bundle.portal.history(
        em, "invoices", date_from="2026-10-18", date_to="2026-10-18"
    )
    yesterday = bundle.portal.history(
        em, "invoices", date_from="2026-10-17", date_to="2026-10-17"
    )
    assert today["total"] == 1 and yesterday["total"] == 0
    chart = bundle.portal.dashboard(em, days=7)["chart"]
    assert chart[-1]["spent"] == 10000 and chart[0]["spent"] == 0


def test_live_warning_and_exact_domain_rounding(scenario):
    bundle, _, _, clock = scenario
    binh = bundle.portal.login("lethibinh", "demo123")
    clock.advance(seconds=1)
    live = bundle.portal.dashboard(binh)["active_sessions"][0]
    # A 90m1s session bills 91 minutes, with integer VND rounding.
    assert live["estimated_cost"] == 15167
    assert live["projected_balance"] == -10167
    assert live["remaining_minutes"] == 0
    warnings = bundle.portal.notifications(binh)["items"]
    assert any(n["kind"] == "SESSION_DEPLETED" for n in warnings)


def test_usage_is_window_overlap_not_entire_cross_boundary_session(scenario):
    bundle, _, _, clock = scenario
    em = bundle.portal.login("hoangvanem", "demo123")
    clock.advance(hours=24 * 7)
    result = bundle.portal.dashboard(em, days=7)
    # The old live session spans the whole window; completed sessions predate it.
    assert result["totals"]["spent"] == 0
    assert result["totals"]["usage_seconds"] == 6 * 86400 + 16 * 3600


def test_effective_offers_use_same_rule_as_staff_and_preview_never_credits(scenario):
    bundle, customer, admin, clock = scenario
    for p in [
        Promotion(
            0,
            "GLOBAL",
            "Global",
            None,
            100000,
            30,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
        ),
        Promotion(
            0,
            "LOCAL",
            "Local",
            1,
            100000,
            10,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
        ),
        Promotion(
            0,
            "HIGH",
            "High tier",
            1,
            200000,
            20,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
        ),
    ]:
        bundle.management.save_promotion(admin, p)
    before = bundle.portal.snapshot(customer)
    result = bundle.portal.promotion_quote(customer, 1, 150000)
    assert result["bonus_amount"] == 15000 and result["amount_to_next"] == 50000
    assert result["promotion"].code == "LOCAL"
    assert bundle.portal.promotion_quote(customer, 2, 150000)["bonus_amount"] == 45000
    assert [p.code for p in bundle.portal.dashboard(customer)["promotions"]] == [
        "LOCAL",
        "HIGH",
    ]
    assert bundle.portal.snapshot(customer) == before
    staff_quote = bundle.wallet.preview_top_up(1, 150000, admin.employee_id)
    assert staff_quote.bonus_amount == result["bonus_amount"]
    clock.advance(hours=24)
    assert not bundle.portal.dashboard(customer)["promotions"]  # exclusive end


def test_bonus_spend_and_void_invoice_are_distinct(scenario):
    bundle, customer, admin, clock = scenario
    bundle.management.save_promotion(
        admin,
        Promotion(
            0,
            "BONUS",
            "Bonus",
            1,
            100000,
            10,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
        ),
    )
    bundle.wallet.top_up(1, 100000, PaymentMethod.CASH, admin.employee_id)
    bundle.sessions.open_session(1, 1, admin)
    clock.advance(hours=1)
    bundle.sessions.complete_checkout(1, admin, 0, None)
    totals = bundle.portal.dashboard(customer)["totals"]
    assert totals["spent"] == 60000 and totals["bonus_spent"] == 10000
    assert totals["principal_spent"] == 50000 and totals["bonus_received"] == 10000
    # VOID is excluded even though its legacy usage ledger still exists.
    data = bundle.portal._repo.data
    dung = data.customers[4]
    dung.activate()
    dung.account.unlock()
    customer = bundle.portal.login("phamthidung", "demo123")
    assert bundle.portal.dashboard(customer)["totals"]["spent"] == 0


def test_read_receipts_are_idempotent_owned_and_new_events_stay_unread(scenario):
    bundle, customer, admin, clock = scenario
    notices = bundle.portal.notifications(customer)
    keys = [n["key"] for n in notices["items"]]
    assert notices["unread"] == len(keys) > 0
    bundle.portal.mark_notifications_read(customer, keys)
    bundle.portal.mark_notifications_read(customer, keys)
    assert bundle.portal.notifications(customer)["unread"] == 0
    clock.advance(seconds=1)
    bundle.wallet.top_up(1, 5000, PaymentMethod.CASH, admin.employee_id)
    assert bundle.portal.notifications(customer)["unread"] == 1
    other = bundle.portal.login("hoangvanem", "demo123")
    with pytest.raises(ValidationError):
        bundle.portal.mark_notifications_read(other, keys)
    assert bundle.portal.notifications(other)["unread"] > 0


def test_every_new_feature_revalidates_locked_owner(scenario):
    bundle, customer, _, _ = scenario
    bundle.portal._repo.data.customers[1].account.lock()
    for operation in (
        lambda: bundle.portal.dashboard(customer),
        lambda: bundle.portal.history(customer),
        lambda: bundle.portal.notifications(customer),
        lambda: bundle.portal.mark_notifications_read(customer, []),
        lambda: bundle.portal.promotion_quote(customer, 1, 100000),
    ):
        with pytest.raises(PermissionDeniedError):
            operation()


def test_low_warning_escalates_and_new_wallet_events_reopen_alert(scenario):
    bundle, _, admin, clock = scenario
    customer = bundle.portal.login("hoangvanem", "demo123")
    # 100,000 balance, 10,000/hour, initially 30 minutes elapsed.
    clock.advance(hours=9, minutes=15)
    notices = bundle.portal.notifications(customer)
    low = next(n for n in notices["items"] if n["kind"] == "SESSION_LOW")
    bundle.portal.mark_notifications_read(customer, [low["key"]])
    clock.advance(minutes=15)
    depleted = next(
        n
        for n in bundle.portal.notifications(customer)["items"]
        if n["kind"] == "SESSION_DEPLETED"
    )
    assert not depleted["read"] and depleted["key"] != low["key"]
    bundle.portal.mark_notifications_read(customer, [depleted["key"]])
    bundle.wallet.top_up(
        customer.customer_id, 1000, PaymentMethod.CASH, admin.employee_id
    )
    current = next(
        n
        for n in bundle.portal.notifications(customer)["items"]
        if n["kind"] in ("SESSION_LOW", "SESSION_DEPLETED")
    )
    assert not current["read"]


@pytest.mark.parametrize(
    "options",
    [
        dict(kind="employees"),
        dict(status="DROP TABLE"),
        dict(page=True),
        dict(page_size=1000000),
        dict(date_from="2026-99-20"),
        dict(date_from="2026-11-08", date_to="2026-11-01"),
    ],
)
def test_history_rejects_invalid_queries(scenario, options):
    bundle, customer, _, _ = scenario
    with pytest.raises(ValidationError):
        bundle.portal.history(customer, **options)


def test_forged_owner_and_invalid_offer_requests(scenario):
    bundle, customer, _, _ = scenario
    with pytest.raises(PermissionDeniedError):
        bundle.portal.dashboard(replace(customer, customer_id=2))
    for store, amount in [
        (9999, 100000),
        (True, 100000),
        (1, True),
        (1, 0),
        (1, 100000001),
    ]:
        with pytest.raises(ValidationError):
            bundle.portal.promotion_quote(customer, store, amount)
    with pytest.raises(ValidationError):
        bundle.portal.dashboard(customer, days=365)
