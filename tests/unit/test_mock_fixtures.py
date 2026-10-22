"""Unit test cho dữ liệu demo của mock services (mục 9)."""

from collections import Counter
from datetime import date

from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    InvoiceStatus,
    MachineStatus,
    SessionStatus,
)
from cyberhub_manager.services.mocks.clock import DEFAULT_NOW
from cyberhub_manager.services.mocks.fixtures import seed_empty, seed_success
from cyberhub_manager.services.mocks.store import MockDataStore, local_date


def make_success_data() -> MockDataStore:
    data = MockDataStore()
    seed_success(data, DEFAULT_NOW)
    return data


def machine_by_code(data: MockDataStore, code: str):
    return next(m for m in data.machines.values() if m.code == code)


def test_success_has_expected_store_staff_and_machine_counts() -> None:
    data = make_success_data()

    statuses = Counter(machine.status for machine in data.machines.values())
    roles = Counter(employee.role for employee in data.employees.values())

    assert len(data.stores) == 1
    assert roles == {"MANAGER": 1, "STAFF": 2}
    assert len(data.machines) == 20
    assert statuses == {
        MachineStatus.AVAILABLE: 17,
        MachineStatus.IN_USE: 2,
        MachineStatus.MAINTENANCE: 1,
    }
    assert machine_by_code(data, "PC03").status == MachineStatus.MAINTENANCE


def test_active_sessions_match_reference_snapshot() -> None:
    data = make_success_data()

    pc02 = data.to_machine_summary(machine_by_code(data, "PC02"), DEFAULT_NOW)
    pc05 = data.to_machine_summary(machine_by_code(data, "PC05"), DEFAULT_NOW)

    assert pc02.active_session.session.customer_code == "KH002"
    assert pc02.active_session.account_balance == 5_000
    assert pc02.active_session.estimated_cost == 15_000
    assert pc02.active_session.projected_balance == -10_000
    assert pc05.active_session.session.customer_code == "KH005"
    assert pc05.active_session.estimated_cost == 5_000
    assert pc05.active_session.projected_balance == 95_000


def test_customers_match_reference_table() -> None:
    data = make_success_data()

    rows = {
        c.code: (c.status, c.account.status, c.account.balance)
        for c in data.customers.values()
    }

    assert rows == {
        "KH001": (CustomerStatus.ACTIVE, AccountStatus.ACTIVE, 50_000),
        "KH002": (CustomerStatus.ACTIVE, AccountStatus.ACTIVE, 5_000),
        "KH003": (CustomerStatus.ACTIVE, AccountStatus.LOCKED, 20_000),
        "KH004": (CustomerStatus.INACTIVE, AccountStatus.LOCKED, -5_000),
        "KH005": (CustomerStatus.ACTIVE, AccountStatus.ACTIVE, 100_000),
    }


def test_balances_equal_sum_of_transaction_history() -> None:
    data = make_success_data()

    for customer in data.customers.values():
        history = data.transactions_for_account(customer.account.id)
        assert history
        assert sum(t.amount for t in history) == customer.account.balance


def test_invoices_reference_completed_sessions_only() -> None:
    data = make_success_data()

    for invoice in data.invoices.values():
        assert data.get_session(invoice.session_id).status == SessionStatus.COMPLETED
    assert {i.status for i in data.invoices.values()} == {
        InvoiceStatus.PAID,
        InvoiceStatus.VOID,
    }


def test_paid_invoices_spread_over_vietnam_days() -> None:
    data = make_success_data()

    paid_days = sorted(
        local_date(i.created_at)
        for i in data.invoices.values()
        if i.status == InvoiceStatus.PAID
    )

    assert paid_days == [date(2026, 10, 16), date(2026, 10, 17), date(2026, 10, 18)]


def test_ids_continue_after_fixture() -> None:
    data = make_success_data()

    assert data.next_id("customer") == 6
    assert data.next_id("machine") == 21


def test_empty_keeps_only_store_and_employees() -> None:
    data = MockDataStore()

    seed_empty(data, DEFAULT_NOW)

    assert len(data.stores) == 1
    assert len(data.employees) == 3
    assert not data.customers
    assert not data.machines
    assert not data.sessions
    assert not data.transactions
    assert not data.invoices
