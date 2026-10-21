"""Unit test cho mock machine, session và report service."""

from dataclasses import dataclass
from datetime import date

import pytest

from cyberhub_manager.domain.dtos import EmployeeSession, InvoiceFilters
from cyberhub_manager.domain.enums import (
    InvoiceStatus,
    MachineArchiveAction,
    MachineStatus,
    PaymentMethod,
    TransactionType,
)
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    InsufficientBalanceError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    SettlementRequiredError,
    ValidationError,
)
from cyberhub_manager.services.mocks.auth import MockAuthService
from cyberhub_manager.services.mocks.clock import MockClock
from cyberhub_manager.services.mocks.customers import MockCustomerService
from cyberhub_manager.services.mocks.fixtures import (
    DEMO_PASSWORD,
    seed_empty,
    seed_success,
)
from cyberhub_manager.services.mocks.machines import MockMachineService
from cyberhub_manager.services.mocks.reports import MockReportService
from cyberhub_manager.services.mocks.scenarios import MockScenario
from cyberhub_manager.services.mocks.sessions import MockSessionService
from cyberhub_manager.services.mocks.store import MockDataStore
from cyberhub_manager.services.mocks.wallet import MockWalletService


@dataclass
class Services:
    data: MockDataStore
    clock: MockClock
    customers: MockCustomerService
    wallet: MockWalletService
    machines: MockMachineService
    sessions: MockSessionService
    reports: MockReportService
    manager: EmployeeSession
    staff: EmployeeSession


def make_services(scenario: MockScenario = MockScenario.SUCCESS) -> Services:
    data = MockDataStore()
    clock = MockClock()
    seed = seed_empty if scenario == MockScenario.EMPTY else seed_success
    seed(data, clock.now())
    auth = MockAuthService(data, clock, scenario)
    return Services(
        data=data,
        clock=clock,
        customers=MockCustomerService(data, clock, scenario),
        wallet=MockWalletService(data, clock, scenario),
        machines=MockMachineService(data, clock, scenario),
        sessions=MockSessionService(data, clock, scenario),
        reports=MockReportService(data, clock, scenario),
        manager=auth.login("quanly01", DEMO_PASSWORD),
        staff=auth.login("nhanvien01", DEMO_PASSWORD),
    )


def machine_id(services: Services, code: str) -> int:
    return next(m.id for m in services.data.machines.values() if m.code == code)


def machine_summary(services: Services, code: str):
    machines = services.machines.list_machines(services.manager.store_id)
    return next(m for m in machines if m.machine_code == code)


# ----- Machine ---------------------------------------------------------------


def test_list_machines_is_sorted_and_only_in_use_has_active_session() -> None:
    services = make_services()

    machines = services.machines.list_machines(services.staff.store_id)

    assert [m.machine_code for m in machines] == [f"PC{n:02d}" for n in range(1, 21)]
    for machine in machines:
        assert (machine.active_session is not None) == (
            machine.status == MachineStatus.IN_USE
        )
    assert services.machines.list_machines(999) == []


def test_staff_is_denied_every_machine_admin_operation() -> None:
    services = make_services()
    staff = services.staff
    pc01 = machine_id(services, "PC01")

    with pytest.raises(PermissionDeniedError):
        services.machines.create_machine("PC21", staff.store_id, "Máy 21", 10_000, staff)
    with pytest.raises(PermissionDeniedError):
        services.machines.update_machine(pc01, "Máy VIP", 20_000, staff)
    with pytest.raises(PermissionDeniedError):
        services.machines.set_maintenance(pc01, True, staff)
    with pytest.raises(PermissionDeniedError):
        services.machines.archive_machine(pc01, staff)

    pc01_summary = machine_summary(services, "PC01")
    assert pc01_summary.status == MachineStatus.AVAILABLE
    assert pc01_summary.hourly_rate == 10_000
    assert len(services.machines.list_machines(staff.store_id)) == 20


def test_create_machine_validates_and_rejects_duplicate_code() -> None:
    services = make_services()
    manager = services.manager

    with pytest.raises(ValidationError) as error:
        services.machines.create_machine(" ", manager.store_id, "", 0, manager)
    assert set(error.value.field_errors) == {"code", "name", "hourly_rate"}

    with pytest.raises(ConflictError) as error:
        services.machines.create_machine("pc01", manager.store_id, "Máy 1", 10_000, manager)
    assert error.value.field_errors == {"code": "Mã máy đã tồn tại"}

    with pytest.raises(PermissionDeniedError):
        services.machines.create_machine("PC21", 999, "Máy 21", 10_000, manager)

    created = services.machines.create_machine(
        "PC21", manager.store_id, "Máy 21", 12_000, manager
    )
    assert created.updated_at == services.clock.now()
    assert machine_summary(services, "PC21").hourly_rate == 12_000


def test_update_rate_keeps_active_session_snapshot() -> None:
    services = make_services()

    services.machines.update_machine(
        machine_id(services, "PC02"), "Máy 02", 20_000, services.manager
    )

    pc02 = machine_summary(services, "PC02")
    assert pc02.hourly_rate == 20_000
    assert pc02.active_session.session.hourly_rate == 10_000
    assert pc02.active_session.estimated_cost == 15_000


def test_maintenance_toggle_and_in_use_conflict() -> None:
    services = make_services()
    services.clock.advance(minutes=5)

    machine = services.machines.set_maintenance(
        machine_id(services, "PC03"), False, services.manager
    )
    assert machine.status == MachineStatus.AVAILABLE
    assert machine.updated_at == services.clock.now()

    with pytest.raises(ConflictError):
        services.machines.set_maintenance(
            machine_id(services, "PC02"), True, services.manager
        )
    assert machine_summary(services, "PC02").status == MachineStatus.IN_USE


def test_archive_deletes_new_machine_and_archives_machine_with_history() -> None:
    services = make_services()
    manager = services.manager
    pc09, pc04, pc02 = (machine_id(services, c) for c in ("PC09", "PC04", "PC02"))

    assert services.machines.archive_machine(pc09, manager).action == (
        MachineArchiveAction.DELETED
    )
    assert services.machines.archive_machine(pc04, manager).action == (
        MachineArchiveAction.ARCHIVED
    )
    with pytest.raises(ConflictError):
        services.machines.archive_machine(pc02, manager)
    with pytest.raises(NotFoundError):
        services.machines.archive_machine(pc09, manager)

    codes = [m.machine_code for m in services.machines.list_machines(manager.store_id)]
    assert "PC09" not in codes and "PC04" not in codes
    assert len(codes) == 18
    assert services.reports.get_invoice(1).session.machine_code == "PC04"


# ----- Session ---------------------------------------------------------------


def test_preview_open_reports_minimum_balance_and_estimate() -> None:
    services = make_services()

    preview = services.sessions.preview_open(
        1, machine_id(services, "PC01"), services.staff
    )

    assert preview.can_open is True
    assert preview.blocked_reason is None
    assert preview.minimum_balance == 5_000
    assert preview.estimated_minutes == 300
    assert preview.as_of == services.clock.now()


def test_low_balance_preview_blocks_and_open_raises_without_changes() -> None:
    services = make_services()
    customer = services.customers.create_customer(
        "Đỗ Thị Hoa", "0987654321", "dothihoa", "matkhau1"
    )
    pc01 = machine_id(services, "PC01")

    preview = services.sessions.preview_open(customer.id, pc01, services.staff)
    assert preview.can_open is False
    assert preview.blocked_reason

    with pytest.raises(InsufficientBalanceError) as error:
        services.sessions.open_session(customer.id, pc01, services.staff)
    assert error.value.details["required_top_up"] == 5_000
    assert machine_summary(services, "PC01").status == MachineStatus.AVAILABLE


@pytest.mark.parametrize(
    ("customer_id", "machine_code", "field"),
    [
        (3, "PC01", "customer_id"),
        (4, "PC01", "customer_id"),
        (5, "PC01", "customer_id"),
        (1, "PC02", "machine_id"),
        (1, "PC03", "machine_id"),
    ],
)
def test_open_conflicts_raise_with_field(customer_id, machine_code, field) -> None:
    services = make_services()
    target = machine_id(services, machine_code)

    with pytest.raises(ConflictError) as error:
        services.sessions.preview_open(customer_id, target, services.staff)
    assert field in error.value.field_errors

    with pytest.raises(ConflictError):
        services.sessions.open_session(customer_id, target, services.staff)


def test_open_unknown_objects_raise_not_found() -> None:
    services = make_services()

    with pytest.raises(NotFoundError):
        services.sessions.preview_open(999, machine_id(services, "PC01"), services.staff)
    with pytest.raises(NotFoundError):
        services.sessions.preview_open(1, 999, services.staff)


def test_open_then_checkout_updates_machine_balance_history_and_invoices() -> None:
    services = make_services()
    staff = services.staff
    pc01 = machine_id(services, "PC01")

    session = services.sessions.open_session(1, pc01, staff)
    assert session.customer_code == "KH001"
    assert machine_summary(services, "PC01").active_session.session == session

    services.clock.advance(minutes=60)
    preview = services.sessions.preview_checkout(pc01, services.clock.now())
    assert (preview.billed_minutes, preview.usage_cost) == (60, 10_000)
    assert preview.settlement_required == 0

    result = services.sessions.complete_checkout(pc01, staff, 0, None)

    assert result.balance_after == 40_000
    assert result.invoice.billed_minutes == 60
    assert result.invoice.invoice.invoice_code == "HD0005"
    assert result.invoice.invoice.usage_cost == 10_000
    assert machine_summary(services, "PC01").status == MachineStatus.AVAILABLE
    assert machine_summary(services, "PC01").active_session is None
    assert services.customers.search_customers("KH001")[0].balance == 40_000
    assert services.wallet.get_history(1)[0].type == TransactionType.USAGE_PAYMENT
    invoices = services.reports.list_invoices(staff.store_id, InvoiceFilters())
    assert invoices[0] == result.invoice.invoice
    assert services.reports.get_invoice(invoices[0].invoice_id) == result.invoice


def test_checkout_requires_settlement_and_changes_nothing_until_paid() -> None:
    services = make_services()
    pc02 = machine_id(services, "PC02")
    transactions_before = len(services.data.transactions)
    invoices_before = len(services.data.invoices)

    with pytest.raises(SettlementRequiredError) as error:
        services.sessions.complete_checkout(pc02, services.staff, 0, None)

    assert error.value.details["settlement_required"] == 10_000
    assert "settlement_amount" in error.value.field_errors
    assert machine_summary(services, "PC02").status == MachineStatus.IN_USE
    assert services.customers.get_customer(2).account.balance == 5_000
    assert len(services.data.transactions) == transactions_before
    assert len(services.data.invoices) == invoices_before

    result = services.sessions.complete_checkout(
        pc02, services.staff, 10_000, PaymentMethod.CASH
    )

    assert result.balance_after == 0
    assert result.invoice.invoice.settlement_amount == 10_000
    assert result.invoice.invoice.total_amount == 15_000
    types = [t.type for t in services.wallet.get_history(2)[:2]]
    assert set(types) == {TransactionType.USAGE_PAYMENT, TransactionType.DEBT_SETTLEMENT}


@pytest.mark.parametrize(
    ("settlement", "method", "field"),
    [
        (0, PaymentMethod.CASH, "method"),
        (1_000, None, "method"),
        (-1, None, "settlement_amount"),
        (6_000, PaymentMethod.CASH, "settlement_amount"),
    ],
)
def test_invalid_checkout_input_changes_nothing(settlement, method, field) -> None:
    services = make_services()
    pc05 = machine_id(services, "PC05")

    with pytest.raises(ValidationError) as error:
        services.sessions.complete_checkout(pc05, services.staff, settlement, method)

    assert field in error.value.field_errors
    assert machine_summary(services, "PC05").status == MachineStatus.IN_USE
    assert services.customers.get_customer(5).account.balance == 100_000


def test_checkout_machine_without_session_conflicts() -> None:
    services = make_services()
    pc01 = machine_id(services, "PC01")

    with pytest.raises(ConflictError):
        services.sessions.preview_checkout(pc01, services.clock.now())
    with pytest.raises(ConflictError):
        services.sessions.complete_checkout(pc01, services.staff, 0, None)


def test_conflict_scenario_only_breaks_open_session() -> None:
    services = make_services(MockScenario.CONFLICT)
    pc01 = machine_id(services, "PC01")

    assert services.sessions.preview_open(1, pc01, services.staff).can_open
    with pytest.raises(ConflictError) as error:
        services.sessions.open_session(1, pc01, services.staff)

    assert "machine_id" in error.value.field_errors
    assert machine_summary(services, "PC01").status == MachineStatus.AVAILABLE


# ----- Report ----------------------------------------------------------------


def test_list_invoices_filters() -> None:
    services = make_services()
    store_id = services.staff.store_id

    def codes(**kwargs) -> list[str]:
        filters = InvoiceFilters(**kwargs)
        return [i.invoice_code for i in services.reports.list_invoices(store_id, filters)]

    assert codes() == ["HD0004", "HD0003", "HD0002", "HD0001"]
    assert codes(date_from=date(2026, 10, 18), date_to=date(2026, 10, 18)) == ["HD0004"]
    assert codes(date_to=date(2026, 10, 16)) == ["HD0001"]
    assert codes(status=InvoiceStatus.VOID) == ["HD0003"]
    assert codes(keyword="hoàng") == ["HD0004"]
    assert codes(customer_id=1) == ["HD0002", "HD0001"]
    assert services.reports.list_invoices(999, InvoiceFilters()) == []

    with pytest.raises(ValidationError) as error:
        codes(date_from=date(2026, 10, 18), date_to=date(2026, 10, 16))
    assert "date_to" in error.value.field_errors


def test_daily_revenue_uses_vietnam_days_and_paid_invoices_only() -> None:
    services = make_services()
    store_id = services.staff.store_id

    rows = services.reports.daily_revenue(store_id, date(2026, 10, 16), date(2026, 10, 18))

    assert [(r.date.day, r.invoice_count, r.revenue) for r in rows] == [
        (16, 1, 30_000),
        (17, 1, 20_000),
        (18, 1, 10_000),
    ]
    assert services.reports.daily_revenue(store_id, date(2026, 1, 1), date(2026, 1, 2)) == []
    with pytest.raises(ValidationError):
        services.reports.daily_revenue(store_id, date(2026, 10, 18), date(2026, 10, 16))


def test_get_invoice_detail_and_not_found() -> None:
    services = make_services()

    detail = services.reports.get_invoice(4)

    assert detail.invoice.customer_name == "Hoàng Văn Em"
    assert detail.billed_minutes == 60
    assert detail.ended_at == detail.invoice.created_at
    with pytest.raises(NotFoundError):
        services.reports.get_invoice(999)


# ----- Kịch bản EMPTY / UNAVAILABLE -------------------------------------------


def test_empty_scenario_returns_empty_lists() -> None:
    services = make_services(MockScenario.EMPTY)
    store_id = services.staff.store_id

    assert services.machines.list_machines(store_id) == []
    assert services.reports.list_invoices(store_id, InvoiceFilters()) == []
    assert services.reports.daily_revenue(store_id, date(2026, 10, 1), date(2026, 10, 31)) == []
    with pytest.raises(NotFoundError):
        services.reports.get_invoice(1)


def test_unavailable_scenario_breaks_only_list_operations() -> None:
    services = make_services(MockScenario.UNAVAILABLE)
    store_id = services.staff.store_id

    with pytest.raises(ServiceUnavailableError):
        services.machines.list_machines(store_id)
    with pytest.raises(ServiceUnavailableError):
        services.reports.list_invoices(store_id, InvoiceFilters())
    with pytest.raises(ServiceUnavailableError):
        services.reports.daily_revenue(store_id, date(2026, 10, 16), date(2026, 10, 18))

    assert services.reports.get_invoice(1).invoice.invoice_code == "HD0001"
    assert services.sessions.preview_open(
        1, machine_id(services, "PC01"), services.staff
    ).can_open
