"""Unit test cho hành vi và invariant của domain model."""

from datetime import datetime, timedelta

import pytest

from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    InvoiceStatus,
    MachineStatus,
    SessionStatus,
)
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    ValidationError,
)
from cyberhub_manager.domain.models import (
    Account,
    Customer,
    Invoice,
    Machine,
    UsageSession,
)


NOW = datetime(2026, 10, 19, 10, 0, 0)


def make_account(balance: int = 100_000) -> Account:
    return Account(
        id=1,
        code="ACC001",
        customer_id=1,
        username="customer01",
        balance=balance,
        status=AccountStatus.ACTIVE,
    )


def make_customer(account: Account | None = None) -> Customer:
    return Customer(
        id=1,
        code="CUS001",
        full_name="Nguyễn Văn An",
        phone="0912345678",
        status=CustomerStatus.ACTIVE,
        account=account or make_account(),
    )


def make_machine() -> Machine:
    return Machine(
        id=1,
        code="PC001",
        store_id=1,
        name="Máy 01",
        status=MachineStatus.AVAILABLE,
        hourly_rate=30_000,
        is_active=True,
        updated_at=NOW,
    )


def make_session() -> UsageSession:
    return UsageSession(
        id=1,
        code="SES001",
        customer_id=1,
        machine_id=1,
        opened_by=1,
        closed_by=None,
        started_at=NOW,
        ended_at=None,
        hourly_rate=30_000,
        cost=None,
        status=SessionStatus.ACTIVE,
    )


def test_account_balance_is_read_only() -> None:
    account = make_account()

    with pytest.raises(AttributeError):
        account.balance = 500_000


def test_account_credit_and_debit() -> None:
    account = make_account(balance=100_000)

    assert account.credit(20_000) == 120_000
    assert account.debit(50_000) == 70_000
    assert account.balance == 70_000


def test_account_rejects_invalid_amount() -> None:
    account = make_account()

    with pytest.raises(ValidationError):
        account.credit(0)

    with pytest.raises(ValidationError):
        account.debit(-10_000)


def test_customer_status_updates_account_status() -> None:
    account = make_account()
    customer = make_customer(account)

    customer.deactivate()

    assert customer.status == CustomerStatus.INACTIVE
    assert account.status == AccountStatus.LOCKED
    assert not customer.can_open_session()

    customer.activate()

    assert customer.status == CustomerStatus.ACTIVE
    assert account.status == AccountStatus.ACTIVE
    assert customer.can_open_session()


def test_machine_session_state_transitions() -> None:
    machine = make_machine()

    assert machine.is_available()

    machine.start_session()

    assert machine.status == MachineStatus.IN_USE
    assert not machine.is_available()

    machine.finish_session()

    assert machine.status == MachineStatus.AVAILABLE
    assert machine.is_available()


def test_machine_rejects_maintenance_while_in_use() -> None:
    machine = make_machine()
    machine.start_session()

    with pytest.raises(ConflictError):
        machine.set_maintenance(True)

    assert machine.status == MachineStatus.IN_USE


def test_session_rounds_time_and_calculates_cost() -> None:
    session = make_session()
    calculated_at = NOW + timedelta(seconds=61)

    assert session.elapsed_seconds(calculated_at) == 61
    assert session.calculate_billed_minutes(calculated_at) == 2
    assert session.calculate_cost(calculated_at) == 1_000


def test_session_completion_records_result() -> None:
    session = make_session()
    ended_at = NOW + timedelta(seconds=61)

    cost = session.complete(
        employee_id=2,
        ended_at=ended_at,
    )

    assert cost == 1_000
    assert session.status == SessionStatus.COMPLETED
    assert session.closed_by == 2
    assert session.ended_at == ended_at
    assert session.cost == 1_000


def test_invoice_can_be_voided_only_once() -> None:
    invoice = Invoice(
        id=1,
        code="INV001",
        session_id=1,
        customer_id=1,
        employee_id=2,
        store_id=1,
        usage_cost=1_000,
        settlement_amount=0,
        total_amount=1_000,
        status=InvoiceStatus.PAID,
        created_at=NOW,
    )

    assert invoice.is_paid()

    invoice.void()

    assert invoice.status == InvoiceStatus.VOID
    assert not invoice.is_paid()

    with pytest.raises(ConflictError):
        invoice.void()