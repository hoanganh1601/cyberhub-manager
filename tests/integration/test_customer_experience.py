"""Real-MySQL parity for full-history analytics and durable customer read receipts."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from cyberhub_manager.domain.enums import PaymentMethod
from cyberhub_manager.domain.exceptions import ValidationError, PermissionDeniedError
from cyberhub_manager.domain.p1 import CustomerSession, Promotion
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.repositories.p1_repository import P1Repository, execute, rows
from cyberhub_manager.services.portal_service import PortalService
from cyberhub_manager.services.session_service import SessionService
from cyberhub_manager.services.wallet_service import WalletService


def services(conn, scenario, now):
    @contextmanager
    def boundary():
        yield conn

    actor = AuthRepository().get_active_session_by_id(conn, scenario.employee_id)
    return (
        WalletService(
            transaction_factory=boundary,
            actor_provider=lambda: actor,
            clock=lambda: now[0],
        ),
        SessionService(
            transaction_factory=boundary,
            actor_provider=lambda: actor,
            clock=lambda: now[0],
        ),
        PortalService(transaction_factory=boundary, clock=lambda: now[0]),
        actor,
    )


def test_full_analytics_bonus_split_and_vietnam_midnight(db_conn, test_scenario):
    scenario = test_scenario(db_conn, hourly_rate=10000)
    now = [datetime(2026, 11, 7, 15, 30, tzinfo=timezone.utc)]
    wallet, sessions, portal, actor = services(db_conn, scenario, now)
    P1Repository().save_promotion(
        db_conn,
        Promotion(
            0,
            "P" + scenario.token,
            "Reward",
            scenario.store_id,
            100000,
            10,
            now[0] - timedelta(days=1),
            now[0] + timedelta(days=2),
        ),
    )
    wallet.top_up(scenario.customer_id, 100000, PaymentMethod.CASH, actor.employee_id)
    sessions.open_session(scenario.customer_id, scenario.machine_id, actor)
    now[0] += timedelta(minutes=90)  # exactly 00:00 on November 8 in Vietnam
    sessions.complete_checkout(scenario.machine_id, actor, 0, None)
    # Ledger creation uses the database clock; pin these isolated fixtures to the
    # simulated checkout clock so the test actually crosses Vietnam midnight.
    execute(
        db_conn,
        "UPDATE invoices SET created_at=%s WHERE customer_id=%s",
        (now[0].replace(tzinfo=None), scenario.customer_id),
    )
    execute(
        db_conn,
        "UPDATE account_transactions SET created_at=%s WHERE account_id=%s AND type='USAGE_PAYMENT'",
        (now[0].replace(tzinfo=None), scenario.account_id),
    )
    execute(
        db_conn,
        "UPDATE account_transactions SET created_at=%s WHERE account_id=%s AND type IN ('TOP_UP','PROMOTION')",
        ((now[0] - timedelta(minutes=90)).replace(tzinfo=None), scenario.account_id),
    )
    principal = CustomerSession(scenario.customer_id, scenario.account_id, "", "")
    result = portal.dashboard(principal, days=7, store_id=scenario.store_id)
    assert result["totals"]["spent"] == 15000
    assert result["totals"]["bonus_spent"] == 10000
    assert result["totals"]["principal_spent"] == 5000
    assert result["totals"]["topped_up"] == 100000
    assert result["totals"]["usage_seconds"] == 5400
    assert result["chart"][-1]["spent"] == 15000
    assert result["chart"][-2]["topped_up"] == 100000
    assert (
        portal.history(
            principal, "invoices", date_from="2026-11-08", date_to="2026-11-08"
        )["total"]
        == 1
    )
    assert (
        portal.history(
            principal, "invoices", date_from="2026-11-07", date_to="2026-11-07"
        )["total"]
        == 0
    )
    # Query beyond the old 100-item snapshot cap, using deterministic same-time ordering.
    for _ in range(105):
        wallet.top_up(scenario.customer_id, 1000, PaymentMethod.CASH, actor.employee_id)
    execute(
        db_conn,
        "UPDATE account_transactions SET created_at=%s WHERE account_id=%s AND type='TOP_UP' AND amount=1000",
        (now[0].replace(tzinfo=None), scenario.account_id),
    )
    assert (
        portal.history(principal, status="TOP_UP", page=3, page_size=50)["total"] == 106
    )
    assert (
        len(portal.history(principal, status="TOP_UP", page=3, page_size=50)["items"])
        == 6
    )
    assert portal.dashboard(principal)["totals"]["topped_up"] == 205000


def test_reads_survive_service_reload_and_cannot_ack_another_customer(
    db_conn, test_scenario
):
    first = test_scenario(db_conn)
    other = test_scenario(db_conn)
    now = [datetime.now(timezone.utc)]
    wallet, _, portal, actor = services(db_conn, first, now)
    principal = CustomerSession(first.customer_id, first.account_id, "", "")
    wallet.top_up(first.customer_id, 50000, PaymentMethod.CASH, actor.employee_id)
    notices = portal.notifications(principal)
    assert notices["unread"] == 1
    keys = [n["key"] for n in notices["items"]]
    portal.mark_notifications_read(principal, keys)
    portal.mark_notifications_read(principal, keys)
    assert (
        len(
            rows(
                db_conn,
                "SELECT * FROM customer_notification_reads WHERE account_id=%s",
                (first.account_id,),
            )
        )
        == 1
    )
    reloaded = services(db_conn, first, now)[2]
    assert reloaded.notifications(principal)["unread"] == 0
    other_customer = CustomerSession(other.customer_id, other.account_id, "", "")
    with pytest.raises(ValidationError):
        portal.mark_notifications_read(other_customer, keys)
    assert portal.history(other_customer)["total"] == 0
    now[0] += timedelta(seconds=1)
    wallet.top_up(first.customer_id, 1000, PaymentMethod.CASH, actor.employee_id)
    assert reloaded.notifications(principal)["unread"] == 1
    execute(
        db_conn, "UPDATE accounts SET status='LOCKED' WHERE id=%s", (first.account_id,)
    )
    with pytest.raises(PermissionDeniedError):
        portal.mark_notifications_read(principal, [])
