"""Phase 2 invariants: aggregate availability, actual usage and owned profile edits."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from cyberhub_manager.domain.exceptions import (
    PermissionDeniedError,
    ValidationError,
    ConflictError,
    AuthenticationError,
)
from cyberhub_manager.domain.usage_analysis import analyze_usage
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.clock import MockClock

NOW = datetime(2026, 11, 8, 9, tzinfo=timezone.utc)


@pytest.fixture
def scenario():
    clock = MockClock(NOW)
    bundle = build_mock_services(p1=True, customer_offers=True, clock=clock)
    customer = bundle.portal.login("nguyenvanan", "demo123")
    admin = bundle.auth.login("admin01", "demo123")
    return bundle, customer, admin, clock


def test_availability_is_aggregate_scoped_and_has_five_minute_contract(scenario):
    bundle, customer, _, _ = scenario
    result = bundle.portal.availability(customer, 1)
    assert result["rooms"] == [
        dict(room_type="STANDARD", available=5, total=8, min_hourly_rate=10000, max_hourly_rate=10000),
        dict(room_type="VIP", available=8, total=8, min_hourly_rate=20000, max_hourly_rate=20000),
        dict(room_type="COUPLE", available=2, total=2, min_hourly_rate=25000, max_hourly_rate=25000),
        dict(room_type="SUPER_VIP", available=2, total=2, min_hourly_rate=35000, max_hourly_rate=35000),
    ]
    assert result["refresh_seconds"] == 300
    assert result["next_update_at"] - result["as_of"] == timedelta(minutes=5)
    assert all(
        set(row) == {"room_type", "available", "total", "min_hourly_rate", "max_hourly_rate"} for row in result["rooms"]
    )
    assert bundle.portal.availability(customer, 2)["rooms"] == [
        dict(room_type="STANDARD", available=0, total=0, min_hourly_rate=None, max_hourly_rate=None),
        dict(room_type="VIP", available=0, total=0, min_hourly_rate=None, max_hourly_rate=None),
        dict(room_type="COUPLE", available=0, total=0, min_hourly_rate=None, max_hourly_rate=None),
        dict(room_type="SUPER_VIP", available=0, total=0, min_hourly_rate=None, max_hourly_rate=None),
    ]
    for store in (None, True, -1, 999):
        with pytest.raises(ValidationError):
            bundle.portal.availability(customer, store)


def test_manager_classification_affects_counts_without_changing_machine_or_wallet(
    scenario,
):
    bundle, customer, admin, _ = scenario
    before = bundle.portal.snapshot(customer)
    bundle.management.set_machine_room(admin, 1, "VIP")
    result = bundle.portal.availability(customer, 1)
    assert (
        result["rooms"][0]["available"] == 4 and result["rooms"][1]["available"] == 9
    )
    assert (result["rooms"][1]["min_hourly_rate"], result["rooms"][1]["max_hourly_rate"]) == (10000, 20000)
    assert bundle.portal.snapshot(customer) == before
    staff = bundle.auth.login("nhanvien01", "demo123")
    with pytest.raises(PermissionDeniedError):
        bundle.management.set_machine_room(staff, 1, "STANDARD")
    with pytest.raises(ConflictError):
        bundle.management.set_machine_room(admin, 2, "VIP")
    with pytest.raises(PermissionDeniedError):
        bundle.management.set_machine_room(
            bundle.management.switch_store(admin, 2), 1, "STANDARD"
        )


def test_demo_room_prices_drive_open_preview_and_leave_running_session_rate(scenario):
    bundle, _, admin, _ = scenario
    rates = {machine.machine_id: machine.hourly_rate for machine in bundle.machines.list_machines(1)}
    assert [rates[machine_id] for machine_id in (1, 9, 17, 19)] == [10000, 20000, 25000, 35000]
    for machine_id, rate in ((1, 10000), (9, 20000), (17, 25000), (19, 35000)):
        preview = bundle.sessions.preview_open(1, machine_id, admin)
        assert preview.hourly_rate == rate
        assert preview.minimum_balance == rate // 2
    assert bundle.machines.list_machines(1)[1].active_session.session.hourly_rate == 10000


def test_usage_matches_dashboard_and_has_no_other_customer_rows(scenario):
    bundle, customer, _, _ = scenario
    result = bundle.portal.usage_analysis(customer)
    assert (
        result["usage_seconds"]
        == bundle.portal.dashboard(customer)["totals"]["usage_seconds"]
        == 18000
    )
    assert sum(x["usage_seconds"] for x in result["daily"]) == 18000
    assert sum(x["usage_seconds"] for x in result["hours"]) == 18000
    assert sum(x["usage_seconds"] for x in result["weekdays"]) == 18000
    assert result["sessions"] == 2 and result["machines"] == 2
    assert len(result["daily"]) == 30 and len(result["hours"]) == 24


def test_usage_splits_midnight_hours_and_clips_window():
    start = datetime(2026, 11, 7, 16, 30, tzinfo=timezone.utc)  # 23:30 in Vietnam
    end = start + timedelta(minutes=105)
    row = dict(
        started_at=start,
        ended_at=end,
        machine_id=1,
        store_id=1,
        store_name="CyberHub",
        status="COMPLETED",
    )
    result = analyze_usage(
        [row, {**row, "status": "CANCELLED"}], start - timedelta(hours=2), end, end
    )
    assert [r["usage_seconds"] for r in result["daily"]] == [1800, 4500]
    assert result["hours"][23]["usage_seconds"] == 1800
    assert result["hours"][0]["usage_seconds"] == 3600
    assert result["hours"][1]["usage_seconds"] == 900
    assert (
        result["weekdays"][5]["usage_seconds"] == 1800
        and result["weekdays"][6]["usage_seconds"] == 4500
    )
    midnight = datetime(2026, 11, 7, 17, tzinfo=timezone.utc)
    clipped = analyze_usage([row], midnight, end, end)
    assert clipped["usage_seconds"] == 4500 and clipped["sessions"] == 1


def test_profile_update_only_changes_owned_contact_fields(scenario):
    bundle, customer, _, _ = scenario
    before = bundle.portal.snapshot(customer)
    changed = bundle.portal.update_profile(
        customer, "  Nguyễn Văn An mới  ", "0912345678", "demo123"
    )
    assert (
        changed["full_name"] == "Nguyễn Văn An mới" and changed["phone"] == "0912345678"
    )
    after = bundle.portal.snapshot(customer)
    assert after["wallet"]["balance"] == before["wallet"]["balance"]
    assert (
        after["transactions"] == before["transactions"]
        and changed["username"] == "nguyenvanan"
    )
    assert "password" not in str(changed) and "auth_version" not in changed
    assert (
        bundle.portal.profile(bundle.portal.login("hoangvanem", "demo123"))["phone"]
        == "0901000005"
    )


@pytest.mark.parametrize(
    "name,phone,password,field",
    [
        ("A", "0912345678", "demo123", "full_name"),
        ("Valid Name", "abc", "demo123", "phone"),
        ("Valid Name", "0901000002", "demo123", "phone"),
        ("Valid Name", "0912345678", "wrong", "current_password"),
    ],
)
def test_profile_validation_and_failed_edits_are_atomic(
    scenario, name, phone, password, field
):
    bundle, customer, _, _ = scenario
    before = bundle.portal.profile(customer)
    with pytest.raises(ValidationError) as error:
        bundle.portal.update_profile(customer, name, phone, password)
    assert field in error.value.field_errors
    assert bundle.portal.profile(customer) == before


def test_password_change_revokes_old_principal_and_keeps_new_one(scenario):
    bundle, customer, _, _ = scenario
    fresh = bundle.portal.change_password(
        customer, "demo123", "new-password123", "new-password123"
    )
    assert fresh.auth_version == customer.auth_version + 1
    assert bundle.portal.validate(fresh) == fresh
    assert bundle.portal.login("nguyenvanan", "new-password123") == fresh
    with pytest.raises(AuthenticationError):
        bundle.portal.login("nguyenvanan", "demo123")
    for call in (
        lambda: bundle.portal.validate(customer),
        lambda: bundle.portal.snapshot(customer),
        lambda: bundle.portal.availability(customer, 1),
        lambda: bundle.portal.history(customer),
        lambda: bundle.portal.usage_analysis(customer),
        lambda: bundle.portal.invoice(customer, 1),
    ):
        with pytest.raises(PermissionDeniedError):
            call()


@pytest.mark.parametrize(
    "current,new,confirm",
    [
        ("wrong", "new-password123", "new-password123"),
        ("demo123", "new-password123", "different"),
        ("demo123", "short", "short"),
        ("demo123", "demo123", "demo123"),
        ("demo123", "á" * 37, "á" * 37),
    ],
)
def test_password_failure_leaves_credentials_and_sessions_unchanged(
    scenario, current, new, confirm
):
    bundle, customer, _, _ = scenario
    with pytest.raises(ValidationError):
        bundle.portal.change_password(customer, current, new, confirm)
    assert bundle.portal.login("nguyenvanan", "demo123") == customer


def test_locked_and_forged_profiles_cannot_read_or_change_data(scenario):
    bundle, customer, _, _ = scenario
    with pytest.raises(PermissionDeniedError):
        bundle.portal.profile(replace(customer, customer_id=2))
    bundle.portal._repo.data.customers[1].account.lock()
    for operation in (
        lambda: bundle.portal.profile(customer),
        lambda: bundle.portal.availability(customer, 1),
        lambda: bundle.portal.usage_analysis(customer),
        lambda: bundle.portal.update_profile(
            customer, "Valid Name", "0912345678", "demo123"
        ),
        lambda: bundle.portal.change_password(
            customer, "demo123", "new12345", "new12345"
        ),
    ):
        with pytest.raises(PermissionDeniedError):
            operation()
