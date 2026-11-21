"""Integration tests for migration 024 and commercial reconciliation.

The tests exercise the real MySQL schema and repository.  All rows live in the
``db_conn`` transaction supplied by the shared test harness and are rolled back
after each test.
"""

from contextlib import contextmanager
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from cyberhub_manager.domain.commercial import partner_event_signature
from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.infrastructure.repositories.sql import execute, rows
from cyberhub_manager.application.services.commercial_service import CommercialService


NOW = datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc)
SECRET_REF = "CYBERHUB_PARTNER_INTEGRATION_SECRET"
SECRET = "integration-secret-not-for-production"


def _actor(conn, scenario, *, role: Role, name: str) -> EmployeeSession:
    token = uuid4().hex[:8]
    profile_id = execute(
        conn,
        "INSERT INTO employee_profiles(code,home_store_id,full_name) VALUES(%s,%s,%s)",
        (f"CM-{token}", scenario.store_id, name),
    )
    employee_id = execute(
        conn,
        "INSERT INTO employees(profile_id,username,password_hash,role) "
        "VALUES(%s,%s,'x',%s)",
        (profile_id, f"cm.{token}", role.value),
    )
    return EmployeeSession(
        employee_id,
        f"CM-{token}",
        name,
        f"cm.{token}",
        scenario.store_id,
        "STORE",
        "Test store",
        role,
        0,
    )


def _boundary(conn):
    @contextmanager
    def boundary():
        yield conn

    return boundary


def _service(conn) -> CommercialService:
    return CommercialService(
        transaction_factory=_boundary(conn),
        clock=lambda: NOW,
        environment={SECRET_REF: SECRET},
    )


def _active_contract(
    service: CommercialService,
    creator: EmployeeSession,
    approver: EmployeeSession,
    token: str,
    *,
    model: str = "CPM",
    rate: int = 10_000,
) -> dict:
    partner = service.save_partner(
        creator,
        code=f"PTN-{token}",
        name="Đối tác tích hợp",
        partner_type="AD_NETWORK",
        status="ACTIVE",
        callback_secret_ref=SECRET_REF,
    )
    contract = service.create_contract(
        creator,
        partner_id=partner["id"],
        code=f"CTR-{token}",
        revenue_model=model,
        rate_amount=rate,
        starts_on=date(2026, 11, 1),
        ends_on=date(2026, 11, 30),
    )
    with pytest.raises(PermissionDeniedError):
        service.activate_contract(creator, contract["id"])
    return service.activate_contract(approver, contract["id"])


def _active_ad_placement(
    service: CommercialService,
    actor: EmployeeSession,
    contract_id: int,
    token: str,
) -> dict:
    campaign = service.create_campaign(
        actor,
        contract_id=contract_id,
        code=f"CMP-{token}",
        name="Chiến dịch tích hợp",
        kind="AD",
        starts_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        ends_at=datetime(2026, 11, 30, 23, 59, tzinfo=timezone.utc),
        reward_type="NONE",
        reward_amount=0,
    )
    campaign = service.set_campaign_status(actor, campaign["id"], "ACTIVE")
    return service.create_placement(
        actor,
        campaign_id=campaign["id"],
        store_id=None,
        code=f"AD-{token}",
        placement_type="AD",
        surface="PORTAL_BANNER",
    )


def test_signed_event_is_idempotent_and_reconciled_once(db_conn, test_scenario):
    scenario = test_scenario(db_conn)
    creator = _actor(db_conn, scenario, role=Role.ADMIN, name="Commercial creator")
    approver = _actor(db_conn, scenario, role=Role.ADMIN, name="Commercial approver")
    service = _service(db_conn)
    token = uuid4().hex[:8].upper()

    contract = _active_contract(service, creator, approver, token)
    placement = _active_ad_placement(service, creator, contract["id"], token)
    provider_event_id = f"provider-event-{token.lower()}"
    signature = partner_event_signature(
        SECRET,
        placement["code"],
        provider_event_id,
        "IMPRESSION",
    )

    accepted = service.verify_partner_event_callback(
        placement["code"], provider_event_id, "IMPRESSION", signature
    )
    replayed = service.verify_partner_event_callback(
        placement["code"], provider_event_id, "IMPRESSION", signature
    )
    assert accepted["accepted"] is True
    assert accepted["idempotent"] is False
    assert replayed == {
        "event_id": accepted["event_id"],
        "accepted": True,
        "idempotent": True,
    }

    settlement = service.generate_settlement(
        creator,
        contract["id"],
        date(2026, 11, 1),
        date(2026, 11, 30),
        adjustment_amount=90,
        adjustment_reason="Điều chỉnh theo biên bản",
    )
    assert settlement["gross_amount"] == 10
    assert settlement["adjustment_amount"] == 90
    assert settlement["net_amount"] == 100
    with pytest.raises(PermissionDeniedError):
        service.approve_settlement(creator, settlement["id"])
    approved = service.approve_settlement(approver, settlement["id"])
    assert approved["status"] == "APPROVED"

    event_rows = rows(
        db_conn,
        "SELECT verification_method,COUNT(*) AS total FROM commercial_events "
        "WHERE provider_event_id=%s GROUP BY verification_method",
        (provider_event_id,),
    )
    assert event_rows == [{"verification_method": "SERVER", "total": 1}]
    assert rows(
        db_conn,
        "SELECT units,unit_rate,amount FROM v_commercial_settlement_lines "
        "WHERE settlement_id=%s",
        (settlement["id"],),
    ) == [{"units": 1, "unit_rate": 10_000, "amount": 10}]


def test_fixed_contract_requires_one_full_period_settlement(db_conn, test_scenario):
    scenario = test_scenario(db_conn)
    creator = _actor(db_conn, scenario, role=Role.ADMIN, name="Fixed creator")
    approver = _actor(db_conn, scenario, role=Role.ADMIN, name="Fixed approver")
    service = _service(db_conn)
    token = uuid4().hex[:8].upper()

    contract = _active_contract(
        service,
        creator,
        approver,
        token,
        model="FIXED",
        rate=500_000,
    )
    _active_ad_placement(service, creator, contract["id"], token)

    with pytest.raises(ValidationError) as exc_info:
        service.generate_settlement(
            creator,
            contract["id"],
            date(2026, 11, 1),
            date(2026, 11, 15),
        )
    assert "period_start" in exc_info.value.field_errors
    assert rows(
        db_conn,
        "SELECT id FROM commercial_settlements WHERE contract_id=%s",
        (contract["id"],),
    ) == []

    settlement = service.generate_settlement(
        creator,
        contract["id"],
        date(2026, 11, 1),
        date(2026, 11, 30),
    )
    assert settlement["gross_amount"] == 500_000
    assert settlement["net_amount"] == 500_000


def test_ended_campaign_is_terminal(db_conn, test_scenario):
    scenario = test_scenario(db_conn)
    creator = _actor(db_conn, scenario, role=Role.ADMIN, name="Campaign creator")
    approver = _actor(db_conn, scenario, role=Role.ADMIN, name="Campaign approver")
    service = _service(db_conn)
    token = uuid4().hex[:8].upper()
    contract = _active_contract(service, creator, approver, token)

    campaign = service.create_campaign(
        creator,
        contract_id=contract["id"],
        code=f"CMP-{token}",
        name="Chiến dịch kết thúc",
        kind="AD",
        starts_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        ends_at=datetime(2026, 11, 30, 23, 59, tzinfo=timezone.utc),
        reward_type="NONE",
        reward_amount=0,
    )
    service.set_campaign_status(creator, campaign["id"], "ACTIVE")
    service.set_campaign_status(creator, campaign["id"], "ENDED")

    with pytest.raises(ConflictError):
        service.set_campaign_status(creator, campaign["id"], "ACTIVE")


def test_fixed_contract_without_placement_cannot_be_reconciled(
    db_conn,
    test_scenario,
):
    scenario = test_scenario(db_conn)
    creator = _actor(db_conn, scenario, role=Role.ADMIN, name="No placement creator")
    approver = _actor(db_conn, scenario, role=Role.ADMIN, name="No placement approver")
    service = _service(db_conn)
    token = uuid4().hex[:8].upper()
    contract = _active_contract(
        service,
        creator,
        approver,
        token,
        model="FIXED",
        rate=500_000,
    )

    with pytest.raises(ConflictError):
        service.generate_settlement(
            creator,
            contract["id"],
            date(2026, 11, 1),
            date(2026, 11, 30),
        )

    assert rows(
        db_conn,
        "SELECT id FROM commercial_settlements WHERE contract_id=%s",
        (contract["id"],),
    ) == []
