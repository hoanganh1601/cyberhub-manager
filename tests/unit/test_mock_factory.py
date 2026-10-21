"""Unit test cho build_mock_services và hợp đồng ServiceBundle."""

import inspect
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import fields
from datetime import date
from pathlib import Path

import pytest

import cyberhub_manager
from cyberhub_manager.domain.dtos import InvoiceFilters
from cyberhub_manager.domain.enums import (
    CustomerStatus,
    MachineStatus,
    PaymentMethod,
)
from cyberhub_manager.domain.exceptions import (
    ApplicationError,
    ConflictError,
    ServiceUnavailableError,
    ValidationError,
)
from cyberhub_manager.services import contracts
from cyberhub_manager.services.contracts import ServiceBundle
from cyberhub_manager.services.mocks import (
    AFFECTED_OPERATIONS,
    DEMO_PASSWORD,
    MockClock,
    MockScenario,
    build_mock_services,
)

BUNDLE_PROTOCOLS = {
    "auth": contracts.AuthServiceProtocol,
    "customers": contracts.CustomerServiceProtocol,
    "wallet": contracts.WalletServiceProtocol,
    "machines": contracts.MachineServiceProtocol,
    "sessions": contracts.SessionServiceProtocol,
    "reports": contracts.ReportServiceProtocol,
}

# Fixture SUCCESS tạo PC01..PC20 với id 1..20 theo thứ tự.
PC01, PC05, PC09 = 1, 5, 9

# Một lời gọi hợp lệ cho mỗi operation trên dữ liệu SUCCESS.
OPERATION_CALLS: dict[str, Callable[[ServiceBundle, MockClock], object]] = {
    "login": lambda b, c: b.auth.login("quanly01", DEMO_PASSWORD),
    "create_customer": lambda b, c: b.customers.create_customer(
        "Đỗ Thị Hoa", "0987654321", "dothihoa", "matkhau1"
    ),
    "get_customer": lambda b, c: b.customers.get_customer(1),
    "search_customers": lambda b, c: b.customers.search_customers(""),
    "update_customer": lambda b, c: b.customers.update_customer(
        1, "Nguyễn Văn An", "0901000001"
    ),
    "set_customer_status": lambda b, c: b.customers.set_customer_status(
        1, CustomerStatus.ACTIVE, manager(b)
    ),
    "top_up": lambda b, c: b.wallet.top_up(
        1, 10_000, PaymentMethod.CASH, manager(b).employee_id
    ),
    "get_history": lambda b, c: b.wallet.get_history(1),
    "list_machines": lambda b, c: b.machines.list_machines(manager(b).store_id),
    "create_machine": lambda b, c: b.machines.create_machine(
        "PC21", manager(b).store_id, "Máy 21", 10_000, manager(b)
    ),
    "update_machine": lambda b, c: b.machines.update_machine(
        PC01, "Máy 01", 12_000, manager(b)
    ),
    "set_maintenance": lambda b, c: b.machines.set_maintenance(
        PC01, True, manager(b)
    ),
    "archive_machine": lambda b, c: b.machines.archive_machine(PC09, manager(b)),
    "preview_open": lambda b, c: b.sessions.preview_open(1, PC01, manager(b)),
    "open_session": lambda b, c: b.sessions.open_session(1, PC01, manager(b)),
    "preview_checkout": lambda b, c: b.sessions.preview_checkout(PC05, c.now()),
    "complete_checkout": lambda b, c: b.sessions.complete_checkout(
        PC05, manager(b), 0, None
    ),
    "list_invoices": lambda b, c: b.reports.list_invoices(
        manager(b).store_id, InvoiceFilters()
    ),
    "get_invoice": lambda b, c: b.reports.get_invoice(1),
    "daily_revenue": lambda b, c: b.reports.daily_revenue(
        manager(b).store_id, date(2026, 10, 16), date(2026, 10, 18)
    ),
}

SCENARIO_ERRORS: dict[MockScenario, type[ApplicationError]] = {
    MockScenario.VALIDATION_ERROR: ValidationError,
    MockScenario.CONFLICT: ConflictError,
    MockScenario.UNAVAILABLE: ServiceUnavailableError,
}


def manager(bundle: ServiceBundle):
    return bundle.auth.login("quanly01", DEMO_PASSWORD)


def protocol_operations(protocol: type) -> list[str]:
    return [
        name
        for name, _ in inspect.getmembers(protocol, inspect.isfunction)
        if not name.startswith("_")
    ]


# ----- Hợp đồng --------------------------------------------------------------


def test_bundle_services_match_protocol_signatures() -> None:
    bundle = build_mock_services()

    for field_name, protocol in BUNDLE_PROTOCOLS.items():
        service = getattr(bundle, field_name)
        assert isinstance(service, protocol)
        for name in protocol_operations(protocol):
            expected = list(inspect.signature(getattr(protocol, name)).parameters)
            actual = list(inspect.signature(getattr(service, name)).parameters)
            assert actual == expected[1:], f"{field_name}.{name}"


def test_operation_table_covers_every_protocol_method() -> None:
    all_operations = {
        name
        for protocol in BUNDLE_PROTOCOLS.values()
        for name in protocol_operations(protocol)
    }

    assert set(OPERATION_CALLS) == all_operations


# ----- Dữ liệu dùng chung và độc lập -----------------------------------------


def test_services_in_one_bundle_share_data() -> None:
    bundle = build_mock_services()
    actor = manager(bundle)

    bundle.wallet.top_up(1, 20_000, PaymentMethod.TRANSFER, actor.employee_id)
    bundle.sessions.open_session(1, PC01, actor)

    assert bundle.customers.get_customer(1).account.balance == 70_000
    machines = bundle.machines.list_machines(actor.store_id)
    assert machines[0].status == MachineStatus.IN_USE
    assert machines[0].active_session.account_balance == 70_000


def test_two_bundles_do_not_share_data() -> None:
    first = build_mock_services()
    second = build_mock_services()

    first.wallet.top_up(1, 20_000, PaymentMethod.CASH, manager(first).employee_id)
    first.customers.create_customer("Đỗ Thị Hoa", "0987654321", "dothihoa", "matkhau1")

    assert second.customers.get_customer(1).account.balance == 50_000
    assert len(second.customers.search_customers("")) == 5
    created = second.customers.create_customer(
        "Đỗ Thị Hoa", "0987654321", "dothihoa", "matkhau1"
    )
    assert created.code == "KH006"


def test_external_clock_controls_session_duration() -> None:
    clock = MockClock()
    bundle = build_mock_services(clock=clock)
    store_id = manager(bundle).store_id

    def pc05_cost() -> int:
        pc05 = bundle.machines.list_machines(store_id)[PC05 - 1]
        return pc05.active_session.estimated_cost

    assert pc05_cost() == 5_000
    clock.advance(minutes=30)
    assert pc05_cost() == 10_000


def test_scenario_accepts_plain_string() -> None:
    bundle = build_mock_services("EMPTY")

    assert bundle.customers.search_customers("") == []


# ----- Kịch bản --------------------------------------------------------------


@pytest.mark.parametrize("operation", sorted(OPERATION_CALLS))
def test_success_scenario_runs_every_operation(operation: str) -> None:
    clock = MockClock()
    bundle = build_mock_services(MockScenario.SUCCESS, clock=clock)

    OPERATION_CALLS[operation](bundle, clock)


@pytest.mark.parametrize(
    ("scenario", "operation"),
    [
        (scenario, operation)
        for scenario in SCENARIO_ERRORS
        for operation in sorted(OPERATION_CALLS)
    ],
)
def test_scenario_errors_only_affect_declared_operations(
    scenario: MockScenario, operation: str
) -> None:
    clock = MockClock()
    bundle = build_mock_services(scenario, clock=clock)
    call = OPERATION_CALLS[operation]

    if operation in AFFECTED_OPERATIONS[scenario]:
        with pytest.raises(SCENARIO_ERRORS[scenario]):
            call(bundle, clock)
    else:
        call(bundle, clock)


def test_empty_scenario_returns_empty_lists_and_login_still_works() -> None:
    bundle = build_mock_services(MockScenario.EMPTY)
    actor = manager(bundle)

    assert bundle.customers.search_customers("") == []
    assert bundle.machines.list_machines(actor.store_id) == []
    assert bundle.reports.list_invoices(actor.store_id, InvoiceFilters()) == []
    assert bundle.reports.daily_revenue(
        actor.store_id, date(2026, 10, 1), date(2026, 10, 31)
    ) == []


# ----- An toàn dữ liệu và phụ thuộc -------------------------------------------


def test_outputs_do_not_expose_password_fields() -> None:
    bundle = build_mock_services()

    outputs = [
        manager(bundle),
        bundle.customers.search_customers("")[0],
        bundle.wallet.get_history(1)[0],
    ]

    for output in outputs:
        assert not any("password" in f.name for f in fields(output))


def test_mock_package_does_not_load_mysql_env_or_ui() -> None:
    script = (
        "import sys\n"
        "from cyberhub_manager.services.mocks import build_mock_services\n"
        "build_mock_services()\n"
        "forbidden = ('mysql', 'dotenv', 'customtkinter', 'tkinter',\n"
        "             'cyberhub_manager.config', 'cyberhub_manager.database',\n"
        "             'cyberhub_manager.ui')\n"
        "loaded = sorted(m for m in sys.modules if m.startswith(forbidden))\n"
        "print(','.join(loaded))\n"
    )

    # Chạy tiến trình riêng để sys.modules không bị test khác làm bẩn.
    src_dir = Path(cyberhub_manager.__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(src_dir)}
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )

    assert result.stdout.strip() == ""
