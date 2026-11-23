"""End-to-end unit tests for counter customer creation in separated RBAC,
cancelling active usage sessions (CANCELLED), and voiding paid invoices (VOID)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from cyberhub_manager.domain.dtos import EmployeeSession, InvoiceSummary
from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    InvoiceStatus,
    MachineStatus,
    Role,
    SessionStatus,
)
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from cyberhub_manager.domain.models import Account, Customer, Invoice, Machine, UsageSession
from cyberhub_manager.services.customer_service import CustomerService
from cyberhub_manager.services.report_service import ReportService
from cyberhub_manager.services.session_service import SessionService
from cyberhub_manager.web import create_app

NOW = datetime(2026, 11, 23, 2, 0, tzinfo=timezone.utc)


def _actor(role: Role = Role.STAFF, *, employee_id: int = 1, store_id: int = 1) -> EmployeeSession:
    return EmployeeSession(
        employee_id=employee_id,
        employee_code=f"NV{employee_id:02d}",
        full_name="Test Employee",
        username=f"user{employee_id}",
        role=role,
        store_id=store_id,
        store_code=f"CH{store_id:02d}",
        store_name=f"Store {store_id}",
    )


def _login(client, username: str, password: str = "demo123") -> dict[str, str]:
    csrf = client.get("/api/session").json["csrf_token"]
    res = client.post(
        "/api/login",
        json={"username": username, "password": password, "kind": "employee"},
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200, res.json
    return {"X-CSRF-Token": res.json["csrf_token"]}


# ---------------------------------------------------------------------------
# 1. Counter customer creation allowed in BOTH legacy & separated RBAC
# ---------------------------------------------------------------------------
def test_counter_customer_creation_works_in_separated_rbac_service(monkeypatch):
    monkeypatch.setenv("CYBERHUB_RBAC_POLICY", "separated")
    staff = _actor(Role.STAFF)
    created: dict[str, object] = {}

    class FakeCustomers:
        def create(self, conn, *, code, full_name, phone):
            created["customer"] = (code, full_name, phone)
            return 10

        def get_by_id(self, conn, customer_id):
            code, full_name, phone = created["customer"]
            return Customer(
                id=customer_id,
                code=code,
                full_name=full_name,
                phone=phone,
                status=CustomerStatus.ACTIVE,
                account=Account(
                    id=20,
                    code=created["account"][0],
                    customer_id=customer_id,
                    username=created["account"][1],
                    balance=0,
                    status=AccountStatus.ACTIVE,
                ),
            )

    class FakeAccounts:
        def create(self, conn, *, code, customer_id, username, password_hash):
            created["account"] = (code, username, password_hash)
            return 20

    class FakeAuth:
        def get_active_session_by_id(self, conn, employee_id):
            return staff if employee_id == staff.employee_id else None

    @contextmanager
    def fake_tx():
        yield object()

    svc = CustomerService(
        customer_repo=FakeCustomers(),
        account_repo=FakeAccounts(),
        auth_repo=FakeAuth(),
        actor_provider=lambda: staff,
        transaction_factory=fake_tx,
    )
    result = svc.create_customer("Trần Văn Minh", "0912345678", "tranvanminh", "secret123")
    assert result.full_name == "Trần Văn Minh"
    assert result.account.username == "tranvanminh"
    assert result.account.balance == 0


def test_counter_customer_creation_works_via_web_in_separated_rbac(monkeypatch):
    monkeypatch.setenv("CYBERHUB_RBAC_POLICY", "separated")
    app = create_app({"TESTING": True, "WEB_MODE": "demo", "ASSISTANT_ENABLED": False, "SECRET_KEY": "test-separated-cust"})
    client = app.test_client()
    headers = _login(client, "nhanvien01")
    res = client.post(
        "/api/customers",
        json={
            "full_name": "Khách Tại Quầy",
            "phone": "0987654321",
            "username": "khachquay01",
            "password": "password123",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.json
    assert res.json["username"] == "khachquay01"


# ---------------------------------------------------------------------------
# 2. Cancel active session (CANCELLED) — service & web API
# ---------------------------------------------------------------------------
def test_session_service_cancel_session_frees_machine_and_audits():
    staff = _actor(Role.STAFF)
    machine = Machine(
        id=1, code="PC01", store_id=1, name="Máy 01",
        status=MachineStatus.IN_USE, hourly_rate=10_000, is_active=True, updated_at=NOW,
    )
    session = UsageSession(
        id=100, code="SS-100", customer_id=5, machine_id=1,
        opened_by=1, closed_by=None, started_at=NOW - timedelta(minutes=2),
        ended_at=None, hourly_rate=10_000, cost=None, status=SessionStatus.ACTIVE,
    )
    customer = Customer(
        id=5, code="KH005", full_name="Khách 5", phone="0900000005",
        status=CustomerStatus.ACTIVE,
        account=Account(id=50, code="TK050", customer_id=5, username="khach5", balance=50_000, status=AccountStatus.ACTIVE),
    )
    audit_log: list[tuple] = []
    state = {"open_pos": False}

    class FakeMachines:
        def get_by_id(self, conn, machine_id, *, for_update=False):
            return machine if machine_id == 1 else None

        def mark_available(self, conn, machine_id):
            machine.finish_session()
            return True

    class FakeSessions:
        def get_active_by_machine(self, conn, machine_id, *, for_update=False):
            return session if session.is_active() and machine_id == 1 else None

        def has_open_pos_orders(self, conn, session_id):
            return state["open_pos"]

        def cancel(self, conn, target):
            assert target.status == SessionStatus.CANCELLED
            assert target.closed_by == staff.employee_id
            assert target.ended_at is not None
            return True

    class FakeCustomers:
        def get_by_id(self, conn, customer_id):
            return customer if customer_id == 5 else None

    class FakeAccounts:
        def get_by_id(self, conn, account_id, *, for_update=False):
            return customer.account if account_id == 50 else None

    class FakeAuth:
        def get_active_session_by_id(self, conn, employee_id):
            return staff if employee_id == 1 else None

    class FakeAudit:
        def audit(self, conn, actor, action, entity_id):
            audit_log.append((actor.employee_id, actor.store_id, action, entity_id))

    @contextmanager
    def fake_tx():
        yield object()

    svc = SessionService(
        machine_repo=FakeMachines(),
        session_repo=FakeSessions(),
        customer_repo=FakeCustomers(),
        account_repo=FakeAccounts(),
        auth_repo=FakeAuth(),
        actor_provider=lambda: staff,
        transaction_factory=fake_tx,
        clock=lambda: NOW,
        audit_repo=FakeAudit(),
    )

    # Blocked while open POS orders exist on the session
    state["open_pos"] = True
    with pytest.raises(ConflictError):
        svc.cancel_session(1, staff)
    assert session.is_active()
    assert machine.status == MachineStatus.IN_USE

    # Succeeds once no open POS orders exist
    state["open_pos"] = False
    summary = svc.cancel_session(1, staff)
    assert summary.status == SessionStatus.CANCELLED
    assert machine.status == MachineStatus.AVAILABLE
    assert customer.account.balance == 50_000
    assert audit_log == [(1, 1, "SESSION_CANCEL", 100)]


def test_web_cancel_session_frees_machine_without_charging_or_invoicing():
    app = create_app({"TESTING": True, "WEB_MODE": "demo", "ASSISTANT_ENABLED": False, "SECRET_KEY": "test-cancel-web"})
    client = app.test_client()
    headers = _login(client, "nhanvien01")

    machines_before = client.get("/api/machines").json
    in_use = next(m for m in machines_before if m["status"] == "IN_USE")
    customer_id = in_use["active_session"]["session"]["customer_id"]
    balance_before = client.get(f"/api/customers/{customer_id}").json["customer"]["balance"]
    invoices_before = len(client.get("/api/invoices").json)

    # Missing CSRF -> 403
    assert client.post(f"/api/machines/{in_use['machine_id']}/cancel", json={}).status_code == 403

    # Cancel active session -> 200
    res = client.post(f"/api/machines/{in_use['machine_id']}/cancel", json={}, headers=headers)
    assert res.status_code == 200, res.json
    assert res.json["status"] == "CANCELLED"

    # Machine is now AVAILABLE, balance unchanged, no new invoice created
    refreshed = next(m for m in client.get("/api/machines").json if m["machine_id"] == in_use["machine_id"])
    assert refreshed["status"] == "AVAILABLE"
    assert refreshed["active_session"] is None
    assert client.get(f"/api/customers/{customer_id}").json["customer"]["balance"] == balance_before
    assert len(client.get("/api/invoices").json) == invoices_before

    # Second cancel on already-available machine -> 409 Conflict
    assert client.post(f"/api/machines/{in_use['machine_id']}/cancel", json={}, headers=headers).status_code == 409


# ---------------------------------------------------------------------------
# 3. Void paid invoice (VOID) — service & web API
# ---------------------------------------------------------------------------
def test_report_service_void_invoice_enforces_rbac_and_audits():
    manager = _actor(Role.MANAGER, employee_id=2)
    staff = _actor(Role.STAFF, employee_id=1)
    director = _actor(Role.DIRECTOR, employee_id=3)
    current_holder = {"actor": staff}

    invoice = Invoice(
        id=77, code="INV-77", session_id=100, customer_id=5, employee_id=1,
        store_id=1, usage_cost=20_000, settlement_amount=0, total_amount=20_000,
        status=InvoiceStatus.PAID, created_at=NOW,
    )
    session = UsageSession(
        id=100, code="SS-100", customer_id=5, machine_id=1,
        opened_by=1, closed_by=1, started_at=NOW - timedelta(hours=2),
        ended_at=NOW, hourly_rate=10_000, cost=20_000, status=SessionStatus.COMPLETED,
    )
    machine = Machine(
        id=1, code="PC01", store_id=1, name="Máy 01",
        status=MachineStatus.AVAILABLE, hourly_rate=10_000, is_active=True, updated_at=NOW,
    )
    customer = Customer(
        id=5, code="KH005", full_name="Khách 5", phone="0900000005",
        status=CustomerStatus.ACTIVE,
        account=Account(id=50, code="TK050", customer_id=5, username="khach5", balance=30_000, status=AccountStatus.ACTIVE),
    )
    audits: list[tuple] = []

    class FakeInvoices:
        def get_by_id(self, conn, invoice_id, *, for_update=False):
            return invoice if invoice_id == 77 else None

        def void(self, conn, invoice_id):
            return invoice_id == 77

        def get_summary_by_id(self, conn, invoice_id):
            if invoice_id != 77:
                return None
            return InvoiceSummary(
                invoice_id=invoice.id, invoice_code=invoice.code, session_id=invoice.session_id,
                customer_id=invoice.customer_id, customer_name=customer.full_name,
                employee_id=invoice.employee_id, employee_name="Staff",
                store_id=invoice.store_id, store_name="Store 1",
                usage_cost=invoice.usage_cost, settlement_amount=invoice.settlement_amount,
                total_amount=invoice.total_amount, status=invoice.status, created_at=invoice.created_at,
            )

    class FakeSessions:
        def get_by_id(self, conn, session_id):
            return session if session_id == 100 else None

    class FakeMachines:
        def get_by_id(self, conn, machine_id):
            return machine if machine_id == 1 else None

    class FakeCustomers:
        def get_by_id(self, conn, customer_id):
            return customer if customer_id == 5 else None

    class FakeAuth:
        def get_active_session_by_id(self, conn, employee_id):
            return {1: staff, 2: manager, 3: director}.get(employee_id)

    class FakeAudit:
        def audit(self, conn, actor, action, entity_id):
            audits.append((actor.employee_id, actor.store_id, action, entity_id))

    @contextmanager
    def fake_tx():
        yield object()

    svc = ReportService(
        invoice_repo=FakeInvoices(),
        auth_repo=FakeAuth(),
        session_repo=FakeSessions(),
        machine_repo=FakeMachines(),
        customer_repo=FakeCustomers(),
        audit_repo=FakeAudit(),
        actor_provider=lambda: current_holder["actor"],
        transaction_factory=fake_tx,
    )

    # STAFF and DIRECTOR cannot void invoices
    with pytest.raises(PermissionDeniedError):
        svc.void_invoice(77, staff)
    current_holder["actor"] = director
    with pytest.raises(PermissionDeniedError):
        svc.void_invoice(77, director)

    # Non-existent invoice -> NotFoundError
    current_holder["actor"] = manager
    with pytest.raises(NotFoundError):
        svc.void_invoice(999, manager)

    # MANAGER voids successfully and writes audit
    detail = svc.void_invoice(77, manager)
    assert detail.invoice.status == InvoiceStatus.VOID
    assert audits == [(2, 1, "INVOICE_VOID", 77)]

    # Second void -> ConflictError
    with pytest.raises(ConflictError):
        svc.void_invoice(77, manager)


def test_web_void_invoice_excludes_from_revenue_and_blocks_staff():
    app = create_app({"TESTING": True, "WEB_MODE": "demo", "ASSISTANT_ENABLED": False, "SECRET_KEY": "test-void-web"})

    # STAFF is rejected (403)
    staff_client = app.test_client()
    staff_headers = _login(staff_client, "nhanvien01")
    paid_invoices = [i for i in staff_client.get("/api/invoices?date_from=2026-01-01&date_to=2026-12-31").json if i["status"] == "PAID"]
    assert paid_invoices
    target_id = paid_invoices[0]["invoice_id"]
    assert staff_client.post(f"/api/invoices/{target_id}/void", json={}, headers=staff_headers).status_code == 403

    # MANAGER voids invoice and sees machine revenue decrease accordingly
    mgr_client = app.test_client()
    mgr_headers = _login(mgr_client, "quanly01")
    inv_list = [i for i in mgr_client.get("/api/invoices?date_from=2026-01-01&date_to=2026-12-31").json if i["status"] == "PAID"]
    target = inv_list[0]
    rev_before = mgr_client.get("/api/revenue?date_from=2026-01-01&date_to=2026-12-31").json["machine_revenue"]

    # Missing CSRF -> 403
    assert mgr_client.post(f"/api/invoices/{target['invoice_id']}/void", json={}).status_code == 403

    res = mgr_client.post(f"/api/invoices/{target['invoice_id']}/void", json={}, headers=mgr_headers)
    assert res.status_code == 200, res.json
    assert res.json["invoice"]["status"] == "VOID"

    rev_after = mgr_client.get("/api/revenue?date_from=2026-01-01&date_to=2026-12-31").json["machine_revenue"]
    assert rev_after == rev_before - target["usage_cost"]

    # Second void -> 409 Conflict
    assert mgr_client.post(f"/api/invoices/{target['invoice_id']}/void", json={}, headers=mgr_headers).status_code == 409
