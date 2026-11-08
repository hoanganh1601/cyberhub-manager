"""Real MySQL: checkout point snapshots, VOID reversal, audience and avatar storage."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from io import BytesIO
import pytest
from PIL import Image

from cyberhub_manager.repositories.p1_repository import P1Repository, execute, rows
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.domain.p1 import Promotion, CustomerSession
from cyberhub_manager.domain.enums import PaymentMethod
from cyberhub_manager.services.portal_service import PortalService
from cyberhub_manager.services.management_service import ManagementService
from cyberhub_manager.services.wallet_service import WalletService
from cyberhub_manager.services.session_service import SessionService
from cyberhub_manager.domain.exceptions import PermissionDeniedError


def test_paid_checkout_freezes_points_and_void_reverses_qualification(
    db_conn, test_scenario
):
    s = test_scenario(db_conn, hourly_rate=10000)
    execute(db_conn, "UPDATE employees SET role='ADMIN' WHERE id=%s", (s.employee_id,))
    actor = AuthRepository().get_active_session_by_id(db_conn, s.employee_id)

    @contextmanager
    def boundary():
        yield db_conn

    now = [datetime.now(timezone.utc).replace(microsecond=0)]
    wallet = WalletService(
        transaction_factory=boundary, actor_provider=lambda: actor, clock=lambda: now[0]
    )
    sessions = SessionService(
        transaction_factory=boundary, actor_provider=lambda: actor, clock=lambda: now[0]
    )
    portal = PortalService(transaction_factory=boundary, clock=lambda: now[0])
    manager = ManagementService(
        transaction_factory=boundary, actor_provider=lambda: actor
    )
    customer = CustomerSession(s.customer_id, s.account_id, "", "")
    wallet.top_up(s.customer_id, 100000, PaymentMethod.CASH, actor.employee_id)
    sessions.open_session(s.customer_id, s.machine_id, actor)
    now[0] += timedelta(minutes=90)
    checkout = sessions.complete_checkout(s.machine_id, actor, 0, None)
    assert portal.member(customer)["points"] == 1
    config = manager.loyalty_settings(actor)
    manager.update_loyalty_settings(actor, replace(config, unit_amount=5000))
    assert portal.member(customer)["points"] == 1
    sessions.open_session(s.customer_id, s.machine_id, actor)
    now[0] += timedelta(minutes=30)
    sessions.complete_checkout(s.machine_id, actor, 0, None)
    assert portal.member(customer)["points"] == 2
    execute(
        db_conn,
        "UPDATE invoices SET status='VOID' WHERE id=%s",
        (checkout.invoice.invoice.invoice_id,),
    )
    assert (
        portal.member(customer)["points"] == 1
        and portal.member(customer)["eligible_spend"] == 5000
    )


def test_real_targeted_topup_uses_server_membership_and_excludes_other_customer(
    db_conn, test_scenario
):
    s = test_scenario(db_conn)
    other = test_scenario(db_conn)
    actor = AuthRepository().get_active_session_by_id(db_conn, s.employee_id)

    @contextmanager
    def boundary():
        yield db_conn

    now = datetime.now(timezone.utc)
    P1Repository().save_promotion(
        db_conn,
        Promotion(
            0,
            "P" + s.token,
            "Private offer",
            s.store_id,
            100000,
            12,
            now - timedelta(days=1),
            now + timedelta(days=1),
            True,
            "BRONZE",
            0,
            s.customer_id,
        ),
    )
    portal = PortalService(transaction_factory=boundary)
    customer = CustomerSession(s.customer_id, s.account_id, "", "")
    outsider = CustomerSession(other.customer_id, other.account_id, "", "")
    assert portal.promotion_quote(customer, s.store_id, 100000)["bonus_amount"] == 12000
    assert portal.promotion_quote(outsider, s.store_id, 100000)["bonus_amount"] == 0
    wallet = WalletService(transaction_factory=boundary, actor_provider=lambda: actor)
    assert (
        wallet.top_up(
            s.customer_id, 100000, PaymentMethod.CASH, actor.employee_id
        ).bonus_amount
        == 12000
    )


def test_real_avatar_survives_service_reload_and_lock_revokes_read(
    db_conn, test_scenario
):
    s = test_scenario(db_conn)

    @contextmanager
    def boundary():
        yield db_conn

    customer = CustomerSession(s.customer_id, s.account_id, "", "")
    portal = PortalService(transaction_factory=boundary)
    image = BytesIO()
    Image.new("RGB", (40, 30), "cyan").save(image, format="PNG")
    result = portal.update_avatar(customer, image.getvalue())
    reloaded = PortalService(transaction_factory=boundary)
    stored = reloaded.avatar(customer)
    assert stored["digest"] == result["avatar_version"]
    assert (
        len(
            rows(
                db_conn,
                "SELECT account_id FROM customer_avatars WHERE account_id=%s",
                (s.account_id,),
            )
        )
        == 1
    )
    execute(db_conn, "UPDATE accounts SET status='LOCKED' WHERE id=%s", (s.account_id,))
    with pytest.raises(PermissionDeniedError):
        reloaded.avatar(customer)
