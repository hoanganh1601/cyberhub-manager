"""P1 regression: tier boundaries, bonus spending, scopes, revocation and receipt safety."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from cyberhub_manager.domain.enums import Role, PaymentMethod
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    PermissionDeniedError,
    NotFoundError,
)
from cyberhub_manager.domain.p1 import Promotion, quote_top_up, Permission, ROLE_PERMISSIONS, can
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.invoice_export import invoice_html, invoice_csv

NOW = datetime(2026, 10, 18, 9, tzinfo=timezone.utc)


def policy(id=0, minimum=100000, percent=10, store=1, **kw):
    return Promotion(
        id,
        kw.get("code", f"P{id}"),
        f"Promotion {id}",
        store,
        minimum,
        percent,
        kw.get("start", NOW - timedelta(days=1)),
        kw.get("end", NOW + timedelta(days=1)),
        kw.get("active", True),
    )


@pytest.mark.parametrize(
    "amount,expected", [(99999, 0), (100000, 10000), (199999, 19999), (200000, 40000)]
)
def test_highest_tier_no_stacking(amount, expected):
    q = quote_top_up(amount, [policy(1), policy(2, 200000, 20)], 1, NOW)
    assert q.bonus_amount == expected


def test_policy_scope_period_and_local_precedence():
    candidates = [
        policy(1, store=None, percent=30),
        policy(2, percent=10),
        policy(3, store=2, percent=99),
        policy(4, start=NOW + timedelta(seconds=1)),
        policy(5, end=NOW),
        policy(6, active=False),
    ]
    assert quote_top_up(100000, candidates, 1, NOW).promotion.id == 2
    assert quote_top_up(100000, [policy(1, start=NOW)], 1, NOW).bonus_amount == 10000


@pytest.fixture
def bundle():
    return build_mock_services(p1=True)


def test_topup_then_checkout_spends_bonus_first_and_snapshots_receipt(bundle):
    manager = bundle.auth.login("quanly01", "demo123")
    bundle.management.save_promotion(manager, policy(code="TIER10"))
    result = bundle.wallet.top_up(1, 100000, PaymentMethod.CASH, manager.employee_id)
    assert result.bonus_amount == 10000
    assert result.balance_after - result.balance_before == 110000
    c = bundle.customers.get_customer(1)
    assert c.account.cash_balance == 150000 and c.account.bonus_balance == 10000
    bundle.sessions.open_session(1, 1, manager)
    bundle.sessions._clock.advance(minutes=90)
    preview = bundle.sessions.preview_checkout(1, bundle.sessions._clock.now())
    assert preview.bonus_used == 10000
    paid = bundle.sessions.complete_checkout(1, manager, 0, None)
    assert paid.bonus_used == 10000 and paid.bonus_balance_after == 0
    assert paid.balance_after == 145000
    detail = bundle.reports.get_invoice(paid.invoice.invoice.invoice_id)
    assert detail.invoice.bonus_used == 10000
    assert "10.000 VND" in invoice_html(detail)
    assert "bonus_used_vnd" in invoice_csv(detail)


def test_manager_cannot_escalate_or_cross_store(bundle):
    manager = bundle.auth.login("quanly01", "demo123")
    with pytest.raises(PermissionDeniedError):
        bundle.management.switch_store(manager, 2)
    with pytest.raises(PermissionDeniedError):
        bundle.management.save_store(manager, None, "CH03", "Store", "Address")
    with pytest.raises(PermissionDeniedError):
        bundle.management.save_employee(
            manager, None, 1, "New Admin", "newadmin", "ADMIN", password="strong123"
        )
    with pytest.raises(PermissionDeniedError):
        bundle.management.save_employee(
            manager, None, 2, "New Staff", "newstaff", password="strong123"
        )
    with pytest.raises(PermissionDeniedError):
        bundle.management.save_promotion(manager, policy(store=None))


def test_employee_password_role_and_revocation(bundle):
    manager = bundle.auth.login("quanly01", "demo123")
    new = bundle.management.save_employee(
        manager, None, 1, "New Staff", "newstaff", password="secret123"
    )
    actor = bundle.auth.login("newstaff", "secret123")
    assert actor.employee_id == new.id and actor.role == Role.STAFF
    with pytest.raises(PermissionDeniedError):
        bundle.management.list_employees(actor)
    bundle.management.save_employee(
        manager, new.id, 1, new.full_name, new.username, "STAFF", "LOCKED"
    )
    with pytest.raises(PermissionDeniedError):
        bundle.management.validate_actor(actor)
    assert bundle.management._repo.data.employee_password_hashes[new.id].startswith(
        "$2"
    )


def test_admin_switch_and_store_session_guard(bundle):
    admin = bundle.auth.login("admin01", "demo123")
    other = bundle.management.switch_store(admin, 2)
    machine = bundle.machines.create_machine("H01", 2, "Ha Dong PC", 10000, other)
    assert bundle.machines.list_machines(2)[0].machine_id == machine.id
    with pytest.raises(ConflictError):
        bundle.management.save_store(admin, 1, "CH01", "Main", "Address", "INACTIVE")
    with pytest.raises(ConflictError):
        bundle.management.save_employee(
            admin,
            admin.employee_id,
            1,
            admin.full_name,
            admin.username,
            "ADMIN",
            "LOCKED",
        )


def test_overlap_rejected_but_adjacent_policy_allowed(bundle):
    manager = bundle.auth.login("quanly01", "demo123")
    bundle.management.save_promotion(manager, policy(code="FIRST"))
    with pytest.raises(ConflictError):
        bundle.management.save_promotion(manager, policy(code="OVERLAP"))
    bundle.management.save_promotion(
        manager,
        policy(code="NEXT", start=NOW + timedelta(days=1), end=NOW + timedelta(days=2)),
    )
    assert len(bundle.management.list_promotions(manager)) == 2


def test_management_audit_failure_rolls_back_password_and_employee(bundle, monkeypatch):
    manager = bundle.auth.login("admin01", "demo123")

    def fail(*args):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(bundle.management._repo, "audit", fail)
    with pytest.raises(RuntimeError):
        bundle.management.save_employee(
            manager,
            manager.employee_id,
            1,
            manager.full_name,
            "renamed",
            "ADMIN",
            password="updated123",
        )
    assert bundle.auth.login("admin01", "demo123").employee_id == manager.employee_id


def test_portal_only_own_data_and_revokes_on_lock(bundle):
    customer = bundle.portal.login("nguyenvanan", "demo123")
    snapshot = bundle.portal.snapshot(customer)
    assert snapshot["wallet"]["cash_balance"] == 50000
    assert all(i["code"] in ("HD0001", "HD0002") for i in snapshot["invoices"])
    with pytest.raises(PermissionDeniedError):
        bundle.portal.snapshot(replace(customer, customer_id=2))
    with pytest.raises(NotFoundError):
        bundle.portal.invoice(customer, 4)
    manager = bundle.auth.login("quanly01", "demo123")
    from cyberhub_manager.domain.enums import CustomerStatus

    bundle.customers.set_customer_status(1, CustomerStatus.INACTIVE, manager)
    with pytest.raises(PermissionDeniedError):
        bundle.portal.validate(customer)


def test_receipt_escapes_data_and_csv_formulas(bundle):
    detail = bundle.reports.get_invoice(1)
    detail = replace(
        detail,
        invoice=replace(detail.invoice, customer_name='=HYPERLINK("bad")'),
        session=replace(detail.session, customer_name="<script>alert(1)</script>"),
    )
    assert "<script>" not in invoice_html(detail)
    assert "&lt;script&gt;" in invoice_html(detail)
    assert "'=HYPERLINK" in invoice_csv(detail)


@pytest.mark.parametrize(
    "role,cap,expected",
    [
        (Role.STAFF, Permission.EXPORT_INVOICE, True),
        (Role.STAFF, Permission.MANAGE_PROMOTIONS, False),
        (Role.MANAGER, Permission.MANAGE_STORES, False),
        (Role.ADMIN, Permission.SWITCH_STORE, True),
    ],
)
def test_permission_matrix(role, cap, expected):
    assert can(role, cap) == expected


def test_pos_capabilities_are_explicitly_granted_without_cross_store_access():
    pos = {
        Permission.POS_VIEW_ORDERS,
        Permission.POS_PREPARE_ORDERS,
        Permission.POS_SERVE_ORDERS,
        Permission.POS_CANCEL_ORDERS,
        Permission.POS_COLLECT_PAYMENT,
    }
    assert ROLE_PERMISSIONS[Role.STAFF] == pos | {
        Permission.OPERATE, Permission.EXPORT_INVOICE, Permission.INVENTORY_VIEW,
        Permission.INVENTORY_COUNT,
    }
    assert ROLE_PERMISSIONS[Role.MANAGER] == ROLE_PERMISSIONS[Role.STAFF] | {
        Permission.MANAGE_MACHINES,
        Permission.LOCK_CUSTOMERS,
        Permission.MANAGE_EMPLOYEES,
        Permission.MANAGE_PROMOTIONS,
        Permission.MANAGE_MENU,
        Permission.MANAGE_REWARDS,
        Permission.INVENTORY_CONFIGURE,
        Permission.INVENTORY_RECEIVE,
        Permission.INVENTORY_ISSUE,
        Permission.INVENTORY_APPROVE,
    }
    assert ROLE_PERMISSIONS[Role.ADMIN] == ROLE_PERMISSIONS[Role.MANAGER] | {
        Permission.MANAGE_STORES, Permission.SWITCH_STORE,
    }
    assert can(Role.STAFF, Permission.INVENTORY_COUNT)
    assert not can(Role.STAFF, Permission.INVENTORY_ISSUE)
    assert not can(Role.STAFF, Permission.INVENTORY_APPROVE)
