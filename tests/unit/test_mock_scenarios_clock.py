"""Unit test cho MockClock và bảng kịch bản mock."""

import inspect
from datetime import datetime, timedelta, timezone

import pytest

from cyberhub_manager.services import contracts
from cyberhub_manager.services.mocks import DEFAULT_NOW, MockClock, MockScenario
from cyberhub_manager.services.mocks.scenarios import (
    AFFECTED_OPERATIONS,
    scenario_error,
)

PROTOCOLS = (
    contracts.AuthServiceProtocol,
    contracts.CustomerServiceProtocol,
    contracts.WalletServiceProtocol,
    contracts.MachineServiceProtocol,
    contracts.SessionServiceProtocol,
    contracts.ReportServiceProtocol,
)
PROTOCOL_OPERATIONS = {
    name
    for protocol in PROTOCOLS
    for name, _ in inspect.getmembers(protocol, inspect.isfunction)
    if not name.startswith("_")
}


def test_clock_starts_at_reference_time_and_advances() -> None:
    clock = MockClock()

    assert clock.now() == DEFAULT_NOW
    assert clock.advance(minutes=90) == DEFAULT_NOW + timedelta(minutes=90)

    clock.reset()

    assert clock.now() == DEFAULT_NOW


def test_clock_rejects_naive_datetime_and_going_backwards() -> None:
    clock = MockClock()

    with pytest.raises(ValueError):
        clock.set(datetime(2026, 10, 18, 9, 0))

    with pytest.raises(ValueError):
        clock.advance(minutes=-1)


def test_clock_normalizes_to_utc() -> None:
    vietnam = timezone(timedelta(hours=7))
    clock = MockClock(datetime(2026, 10, 18, 16, 0, tzinfo=vietnam))

    assert clock.now() == DEFAULT_NOW
    assert clock.now().tzinfo == timezone.utc


def test_every_scenario_is_declared() -> None:
    assert set(AFFECTED_OPERATIONS) == set(MockScenario)
    assert AFFECTED_OPERATIONS[MockScenario.SUCCESS] == frozenset()
    assert AFFECTED_OPERATIONS[MockScenario.EMPTY] == frozenset()


def test_affected_operations_exist_in_contracts() -> None:
    for operations in AFFECTED_OPERATIONS.values():
        assert operations <= PROTOCOL_OPERATIONS


def test_scenario_error_only_for_declared_operations() -> None:
    assert scenario_error(MockScenario.CONFLICT, "open_session").code == "CONFLICT"
    assert scenario_error(MockScenario.CONFLICT, "top_up") is None
    assert scenario_error(MockScenario.UNAVAILABLE, "login") is None

    error = scenario_error(MockScenario.VALIDATION_ERROR, "top_up")
    assert error.field_errors == {"amount": "Số tiền nạp phải là số nguyên lớn hơn 0"}
