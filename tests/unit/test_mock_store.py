"""Unit test cho kho dữ liệu dùng chung của mock services."""

from datetime import date, timedelta

import pytest

from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    EmployeeStatus,
    MachineStatus,
    Role,
    SessionStatus,
    StoreStatus,
)
from cyberhub_manager.domain.exceptions import NotFoundError
from cyberhub_manager.domain.models import (
    Account,
    Customer,
    Employee,
    Machine,
    Store,
    UsageSession,
)
from cyberhub_manager.services.mocks.clock import DEFAULT_NOW
from cyberhub_manager.services.mocks.store import (
    MockDataStore,
    copy_customer,
    local_date,
)

NOW = DEFAULT_NOW


def make_data_with_active_session() -> MockDataStore:
    data = MockDataStore()
    data.stores[1] = Store(
        id=1,
        code="CH01",
        name="CyberHub Demo",
        address="Hà Nội",
        status=StoreStatus.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
    )
    data.employees[1] = Employee(
        id=1,
        code="NV001",
        full_name="Trần Quản Lý",
        store_id=1,
        username="quanly01",
        role=Role.MANAGER,
        status=EmployeeStatus.ACTIVE,
    )
    account = Account(
        id=2,
        code="TK002",
        customer_id=2,
        username="khach02",
        balance=5_000,
        status=AccountStatus.ACTIVE,
    )
    data.customers[2] = Customer(
        id=2,
        code="KH002",
        full_name="Lê Văn Bình",
        phone="0900000002",
        status=CustomerStatus.ACTIVE,
        account=account,
    )
    data.machines[2] = Machine(
        id=2,
        code="PC02",
        store_id=1,
        name="Máy 02",
        status=MachineStatus.IN_USE,
        hourly_rate=10_000,
        is_active=True,
        updated_at=NOW,
    )
    data.sessions[1] = UsageSession(
        id=1,
        code="PH0001",
        customer_id=2,
        machine_id=2,
        opened_by=1,
        closed_by=None,
        started_at=NOW - timedelta(minutes=90),
        ended_at=None,
        hourly_rate=10_000,
        cost=None,
        status=SessionStatus.ACTIVE,
    )
    return data


def test_next_id_is_per_kind_and_code_is_padded() -> None:
    data = MockDataStore()

    assert data.next_id("customer") == 1
    assert data.next_id("customer") == 2
    assert data.next_id("invoice") == 1
    assert MockDataStore.make_code("customer", 6) == "KH006"
    assert MockDataStore.make_code("invoice", 12) == "HD0012"


def test_missing_object_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        MockDataStore().get_customer(999)


def test_copy_customer_does_not_leak_internal_state() -> None:
    data = make_data_with_active_session()

    copied = copy_customer(data.get_customer(2))
    copied.deactivate()
    copied.account.credit(1_000)

    original = data.get_customer(2)
    assert original.status == CustomerStatus.ACTIVE
    assert original.account.status == AccountStatus.ACTIVE
    assert original.account.balance == 5_000


def test_machine_summary_projects_negative_balance() -> None:
    data = make_data_with_active_session()

    summary = data.to_machine_summary(data.get_machine(2), NOW)

    assert summary.active_session is not None
    assert summary.active_session.elapsed_seconds == 90 * 60
    assert summary.active_session.estimated_cost == 15_000
    assert summary.active_session.projected_balance == -10_000


def test_touch_machine_only_changes_updated_at() -> None:
    data = make_data_with_active_session()
    later = NOW + timedelta(minutes=5)

    data.touch_machine(2, later)

    machine = data.get_machine(2)
    assert machine.updated_at == later
    assert machine.status == MachineStatus.IN_USE


def test_local_date_uses_vietnam_time() -> None:
    assert local_date(NOW.replace(hour=16, minute=59)) == date(2026, 10, 18)
    assert local_date(NOW.replace(hour=17)) == date(2026, 10, 19)
