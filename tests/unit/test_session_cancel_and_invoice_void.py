"""Unit tests for cancel_session and void_invoice flows (service, mock, and web API)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from cyberhub_manager.application.services.mocks import (
    DEFAULT_NOW,
    DEMO_PASSWORD,
    build_mock_services,
)
from cyberhub_manager.application.services.mocks.store import local_date
from cyberhub_manager.application.services.report_service import (
    INVOICE_VOID_AUDIT,
    ReportService,
)
from cyberhub_manager.application.services.session_service import (
    SESSION_CANCEL_AUDIT,
    SessionService,
)
from cyberhub_manager.domain.dtos import EmployeeSession, InvoiceSummary
from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    InvoiceStatus,
    MachineStatus,
    PaymentMethod,
    Role,
    SessionStatus,
)
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from cyberhub_manager.domain.models import Account, Customer, Invoice, Machine, UsageSession
from cyberhub_manager.presentation.web import create_app


UTC = timezone.utc


def _actor(
    employee_id: int = 1,
    role: Role = Role.MANAGER,
    store_id: int = 1,
) -> EmployeeSession:
    return EmployeeSession(
        employee_id=employee_id,
        employee_code=f"NV{employee_id:03d}",
        full_name="Test Employee",
        username=f"emp{employee_id}",
        role=role,
        store_id=store_id,
        store_code="CH01",
        store_name="CyberHub Cầu Giấy",
    )


def _dummy_tx():
    @contextmanager
    def _tx():
        yield object()

    return _tx


class _StubAudit:
    def __init__(self) -> None:
        self.events: list[tuple[int, str, int]] = []

    def audit(self, conn, actor, action, target_id):
        self.events.append((actor.employee_id, action, target_id))


class _StubAuth:
    def __init__(self, actor: EmployeeSession) -> None:
        self.actor = actor

    def get_active_session_by_id(self, conn, employee_id: int):
        if employee_id == self.actor.employee_id:
            return self.actor
        return None


def _demo_login(client, username: str, password: str = DEMO_PASSWORD) -> dict[str, str]:
    token = client.get("/api/session").json["csrf_token"]
    res = client.post(
        "/api/login",
        json={"username": username, "password": password, "kind": "employee"},
        headers={"X-CSRF-Token": token},
    )
    assert res.status_code == 200, res.json
    return {"X-CSRF-Token": res.json["csrf_token"]}


# ----- MockService tests ------------------------------------------------------


def test_mock_cancel_session_frees_machine_and_preserves_balance():
    services = build_mock_services(p1=True)
    staff = services.auth.login("nhanvien01", DEMO_PASSWORD)

    in_use = next(
        m for m in services.machines.list_machines(staff.store_id)
        if m.status == MachineStatus.IN_USE
    )
    customer_id = services.sessions.preview_checkout(
        in_use.machine_id, DEFAULT_NOW
    ).session.customer_id
    balance_before = services.customers.get_customer(customer_id).account.balance

    summary = services.sessions.cancel_session(in_use.machine_id, staff)
    assert summary.status == SessionStatus.CANCELLED
    assert summary.machine_id == in_use.machine_id

    refreshed = next(
        m for m in services.machines.list_machines(staff.store_id)
        if m.machine_id == in_use.machine_id
    )
    assert refreshed.status == MachineStatus.AVAILABLE
    assert refreshed.active_session is None
    assert services.customers.get_customer(customer_id).account.balance == balance_before


def test_mock_cancel_session_blocks_when_open_pos_order_exists():
    services = build_mock_services(p1=True)
    staff = services.auth.login("nhanvien01", DEMO_PASSWORD)
    player = services.portal.login("lethibinh", DEMO_PASSWORD)
    in_use = next(
        m for m in services.machines.list_machines(staff.store_id)
        if m.status == MachineStatus.IN_USE
        and services.sessions.preview_checkout(
            m.machine_id, DEFAULT_NOW
        ).session.customer_id == player.customer_id
    )
    menu = services.menu.portal_menu(player)
    available = next(
        item
        for page in menu["pages"]
        for group in page["categories"]
        for item in group["items"]
        if item.is_available
    )
    services.menu.place_order(player, [{"item_id": available.id, "quantity": 1}])

    with pytest.raises(ConflictError) as exc:
        services.sessions.cancel_session(in_use.machine_id, staff)
    assert "đơn gọi món" in str(exc.value)


def test_mock_void_invoice_excludes_from_revenue_and_rejects_second_void():
    services = build_mock_services(p1=True)
    manager = services.auth.login("quanly01", DEMO_PASSWORD)
    staff = services.auth.login("nhanvien01", DEMO_PASSWORD)

    in_use = next(
        m for m in services.machines.list_machines(manager.store_id)
        if m.status == MachineStatus.IN_USE
    )
    preview = services.sessions.preview_checkout(in_use.machine_id, DEFAULT_NOW)
    result = services.sessions.complete_checkout(
        in_use.machine_id,
        manager,
        preview.settlement_required,
        PaymentMethod.CASH if preview.settlement_required else None,
    )
    invoice_id = result.invoice.invoice.invoice_id
    inv_day = local_date(result.invoice.invoice.created_at)

    # STAFF cannot void
    with pytest.raises(PermissionDeniedError):
        services.reports.void_invoice(invoice_id, staff)

    rev_before = sum(
        d.revenue for d in services.reports.daily_revenue(manager.store_id, inv_day, inv_day)
    )

    voided = services.reports.void_invoice(invoice_id, manager)
    assert voided.invoice.status == InvoiceStatus.VOID

    rev_after = sum(
        d.revenue for d in services.reports.daily_revenue(manager.store_id, inv_day, inv_day)
    )
    assert rev_after == rev_before - result.invoice.invoice.usage_cost

    # Voiding twice raises ConflictError
    with pytest.raises(ConflictError):
        services.reports.void_invoice(invoice_id, manager)


def test_mock_void_invoice_blocks_separated_admin(monkeypatch):
    monkeypatch.setenv("CYBERHUB_RBAC_POLICY", "separated")
    services = build_mock_services(p1=True)
    admin = services.auth.login("admin01", DEMO_PASSWORD)
    paid_invoices = services.reports.list_invoices(admin.store_id, None)
    paid = next(i for i in paid_invoices if i.status == InvoiceStatus.PAID)

    with pytest.raises(PermissionDeniedError):
        services.reports.void_invoice(paid.invoice_id, admin)


# ----- Real service unit tests (with fake repositories) -----------------------


def test_session_service_cancel_writes_audit_and_blocks_open_pos():
    actor = _actor(employee_id=2, role=Role.STAFF, store_id=1)
    started = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    now = datetime(2026, 6, 1, 10, 5, tzinfo=UTC)
    machine = Machine(
        id=10,
        code="M01",
        store_id=1,
        name="PC-01",
        status=MachineStatus.IN_USE,
        hourly_rate=15000,
        is_active=True,
        updated_at=started,
    )
    account = Account(
        id=20,
        code="ACC01",
        customer_id=30,
        username="kh01",
        balance=50000,
        status=AccountStatus.ACTIVE,
    )
    customer = Customer(30, "KH01", "Nguyen Van A", "0901234567", CustomerStatus.ACTIVE, account)
    session = UsageSession(
        40, "SS-1", 30, 10, 2, None, started, None, 15000, None, SessionStatus.ACTIVE
    )

    class _Machines:
        def __init__(self):
            self.freed = False

        def get_by_id(self, conn, mid, for_update=False):
            return machine if mid == 10 else None

        def mark_available(self, conn, mid):
            self.freed = True
            return True

    class _Sessions:
        def __init__(self, has_orders: bool):
            self.has_orders = has_orders
            self.cancelled = False

        def get_active_by_machine(self, conn, mid, for_update=False):
            return session if mid == 10 and session.is_active() else None

        def has_open_pos_orders(self, conn, sid):
            return self.has_orders

        def cancel(self, conn, s):
            self.cancelled = True
            return True

    class _Customers:
        def get_by_id(self, conn, cid):
            return customer if cid == 30 else None

    class _Accounts:
        def get_by_id(self, conn, aid, for_update=False):
            return account if aid == 20 else None

    audit = _StubAudit()

    # Blocked when open POS order exists
    svc_blocked = SessionService(
        machine_repo=_Machines(),
        session_repo=_Sessions(has_orders=True),
        customer_repo=_Customers(),
        account_repo=_Accounts(),
        auth_repo=_StubAuth(actor),
        audit_repo=audit,
        actor_provider=lambda: actor,
        transaction_factory=_dummy_tx(),
        clock=lambda: now,
    )
    with pytest.raises(ConflictError):
        svc_blocked.cancel_session(10, actor)
    assert audit.events == []

    # Succeeds when no open POS order
    machines = _Machines()
    sessions = _Sessions(has_orders=False)
    svc_ok = SessionService(
        machine_repo=machines,
        session_repo=sessions,
        customer_repo=_Customers(),
        account_repo=_Accounts(),
        auth_repo=_StubAuth(actor),
        audit_repo=audit,
        actor_provider=lambda: actor,
        transaction_factory=_dummy_tx(),
        clock=lambda: now,
    )
    summary = svc_ok.cancel_session(10, actor)
    assert summary.status == SessionStatus.CANCELLED
    assert sessions.cancelled is True
    assert machines.freed is True
    assert audit.events == [(2, SESSION_CANCEL_AUDIT, 40)]


def test_report_service_void_invoice_checks_rbac_store_and_writes_audit():
    manager = _actor(employee_id=5, role=Role.MANAGER, store_id=1)
    started = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
    ended = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    machine = Machine(
        id=10,
        code="M01",
        store_id=1,
        name="PC-01",
        status=MachineStatus.AVAILABLE,
        hourly_rate=15000,
        is_active=True,
        updated_at=ended,
    )
    account = Account(
        id=20,
        code="ACC01",
        customer_id=30,
        username="kh01",
        balance=50000,
        status=AccountStatus.ACTIVE,
    )
    customer = Customer(30, "KH01", "Nguyen Van A", "0901234567", CustomerStatus.ACTIVE, account)
    session = UsageSession(
        40, "SS-1", 30, 10, 5, 5, started, ended, 15000, 15000, SessionStatus.COMPLETED
    )

    class _Invoices:
        def __init__(self):
            self.status = InvoiceStatus.PAID

        def get_by_id(self, conn, iid, for_update=False):
            if iid != 50:
                return None
            return Invoice(
                50, "INV-1", 40, 30, 5, 1, 15000, 0, 15000, self.status, ended
            )

        def void(self, conn, iid):
            if self.status != InvoiceStatus.PAID:
                return False
            self.status = InvoiceStatus.VOID
            return True

        def get_summary_by_id(self, conn, iid):
            if iid != 50:
                return None
            return InvoiceSummary(
                invoice_id=50,
                invoice_code="INV-1",
                session_id=40,
                customer_id=30,
                customer_name="Nguyen Van A",
                employee_id=5,
                employee_name="Test Employee",
                store_id=1,
                store_name="CyberHub Cầu Giấy",
                usage_cost=15000,
                settlement_amount=0,
                total_amount=15000,
                status=self.status,
                created_at=ended,
            )

    class _Sessions:
        def get_by_id(self, conn, sid):
            return session if sid == 40 else None

    class _Machines:
        def get_by_id(self, conn, mid):
            return machine if mid == 10 else None

    class _Customers:
        def get_by_id(self, conn, cid):
            return customer if cid == 30 else None

    audit = _StubAudit()
    svc = ReportService(
        invoice_repo=_Invoices(),
        auth_repo=_StubAuth(manager),
        session_repo=_Sessions(),
        machine_repo=_Machines(),
        customer_repo=_Customers(),
        audit_repo=audit,
        actor_provider=lambda: manager,
        transaction_factory=_dummy_tx(),
    )

    detail = svc.void_invoice(50, manager)
    assert detail.invoice.status == InvoiceStatus.VOID
    assert audit.events == [(5, INVOICE_VOID_AUDIT, 50)]

    with pytest.raises(ConflictError):
        svc.void_invoice(50, manager)

    with pytest.raises(NotFoundError):
        svc.void_invoice(999, manager)


# ----- Web API tests ----------------------------------------------------------


def test_web_api_cancel_session_and_void_invoice():
    app = create_app(
        {"TESTING": True, "WEB_MODE": "demo", "SECRET_KEY": "cancel-void-web-tests"}
    )
    client = app.test_client()
    headers = _demo_login(client, "quanly01")

    # Pre-seeded IN_USE machine with open POS orders returns 409 Conflict
    machines = client.get("/api/machines").json
    busy_with_pos = next(m for m in machines if m["status"] == "IN_USE")
    blocked_res = client.post(
        f"/api/machines/{busy_with_pos['machine_id']}/cancel", headers=headers
    )
    assert blocked_res.status_code == 409

    # Open a fresh session on an AVAILABLE machine and cancel it cleanly
    available = next(m for m in machines if m["status"] == "AVAILABLE")
    customers = client.get("/api/customers?keyword=An").json
    customer_id = customers[0]["customer_id"]
    open_res = client.post(
        f"/api/machines/{available['machine_id']}/open",
        json={"customer_id": customer_id},
        headers=headers,
    )
    assert open_res.status_code == 201, open_res.json
    cancel_res = client.post(
        f"/api/machines/{available['machine_id']}/cancel", headers=headers
    )
    assert cancel_res.status_code == 200, cancel_res.json
    assert cancel_res.json["status"] == "CANCELLED"

    # Void a PAID invoice
    invoices = client.get("/api/invoices?status=PAID").json
    assert invoices
    target_id = invoices[0]["invoice_id"]
    void_res = client.post(f"/api/invoices/{target_id}/void", headers=headers)
    assert void_res.status_code == 200, void_res.json
    assert void_res.json["invoice"]["status"] == "VOID"

    # Second void returns 409
    again_res = client.post(f"/api/invoices/{target_id}/void", headers=headers)
    assert again_res.status_code == 409
