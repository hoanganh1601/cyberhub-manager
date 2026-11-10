"""Phase 2 runs on the migrated MySQL schema, not just the demo adapter."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from cyberhub_manager.domain.enums import PaymentMethod
from cyberhub_manager.domain.exceptions import PermissionDeniedError, ConflictError
from cyberhub_manager.repositories.p1_repository import execute
from cyberhub_manager.repositories.auth_repository import AuthRepository
from cyberhub_manager.services.management_service import ManagementService
from cyberhub_manager.services.portal_service import PortalService
from cyberhub_manager.services.session_service import SessionService
from cyberhub_manager.services.wallet_service import WalletService
from cyberhub_manager.security import hash_password


def setup_services(conn, scenario):
    @contextmanager
    def boundary():
        yield conn

    execute(
        conn, "UPDATE employees SET role='MANAGER' WHERE id=%s", (scenario.employee_id,)
    )
    execute(
        conn,
        "UPDATE accounts SET password_hash=%s WHERE id=%s",
        (hash_password("customer123"), scenario.account_id),
    )
    actor = AuthRepository().get_active_session_by_id(conn, scenario.employee_id)
    now = [datetime.now(timezone.utc).replace(microsecond=0)]
    portal = PortalService(transaction_factory=boundary, clock=lambda: now[0])
    return (
        portal,
        ManagementService(transaction_factory=boundary, actor_provider=lambda: actor),
        actor,
        boundary,
        now,
    )


def test_mysql_categories_counts_and_usage_with_running_machine(db_conn, test_scenario):
    scenario = test_scenario(db_conn, hourly_rate=10000)
    portal, management, actor, boundary, now = setup_services(db_conn, scenario)
    principal = portal.login("test.c." + scenario.token, "customer123")
    management.set_machine_room(actor, scenario.machine_id, "VIP")
    assert portal.availability(principal, scenario.store_id)["rooms"] == [
        dict(room_type="STANDARD", available=0, total=0, min_hourly_rate=None, max_hourly_rate=None),
        dict(room_type="VIP", available=1, total=1, min_hourly_rate=10000, max_hourly_rate=10000),
        dict(room_type="COUPLE", available=0, total=0, min_hourly_rate=None, max_hourly_rate=None),
        dict(room_type="SUPER_VIP", available=0, total=0, min_hourly_rate=None, max_hourly_rate=None),
    ]
    # Classification leaves existing MySQL tariffs under manager control.
    assert portal.availability(principal, scenario.store_id)["rooms"][1]["min_hourly_rate"] == 10000
    wallet = WalletService(
        transaction_factory=boundary, actor_provider=lambda: actor, clock=lambda: now[0]
    )
    wallet.top_up(scenario.customer_id, 100000, PaymentMethod.CASH, actor.employee_id)
    sessions = SessionService(
        transaction_factory=boundary, actor_provider=lambda: actor, clock=lambda: now[0]
    )
    sessions.open_session(scenario.customer_id, scenario.machine_id, actor)
    assert (
        portal.availability(principal, scenario.store_id)["rooms"][1]["available"] == 0
    )
    with pytest.raises(ConflictError):
        management.set_machine_room(actor, scenario.machine_id, "STANDARD")
    now[0] += timedelta(minutes=90)
    usage = portal.usage_analysis(principal, 7)
    assert usage["usage_seconds"] == 5400 and usage["sessions"] == 1
    assert sum(r["usage_seconds"] for r in usage["hours"]) == 5400
    assert usage["stores"][0]["store_name"] == "Test store"
    assert portal.profile(principal)["phone"].startswith("02")


def test_mysql_profile_password_rotation_and_retained_wallet(db_conn, test_scenario):
    scenario = test_scenario(db_conn)
    portal, _, _, _, _ = setup_services(db_conn, scenario)
    principal = portal.login("test.c." + scenario.token, "customer123")
    # The test scenario phone is already valid and unique in this transaction.
    original = portal.profile(principal)
    changed = portal.update_profile(
        principal, "Updated Customer", original["phone"], "customer123"
    )
    assert changed["full_name"] == "Updated Customer"
    assert changed["member_since"].tzinfo is not None
    fresh = portal.change_password(
        principal, "customer123", "new-customer123", "new-customer123"
    )
    assert fresh.auth_version == 1
    assert portal.login("test.c." + scenario.token, "new-customer123").auth_version == 1
    with pytest.raises(PermissionDeniedError):
        portal.profile(principal)
    with pytest.raises(PermissionDeniedError):
        portal.dashboard(principal)
    assert portal.snapshot(fresh)["wallet"]["balance"] == 0
