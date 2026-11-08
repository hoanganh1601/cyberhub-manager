"""LI-10 — mọi service dùng chung db_errors: thao tác ghi chạy lại khi deadlock, thao tác đọc thì không."""

from __future__ import annotations

import inspect

import pytest

from cyberhub_manager.services import (
    auth_service,
    customer_service,
    machine_service,
    report_service,
    session_service,
    wallet_service,
)
from cyberhub_manager.services.auth_service import AuthService
from cyberhub_manager.services.customer_service import CustomerService
from cyberhub_manager.services.machine_service import MachineService
from cyberhub_manager.services.report_service import ReportService
from cyberhub_manager.services.session_service import SessionService
from cyberhub_manager.services.wallet_service import WalletService

# Mỗi thao tác ghi nằm trọn trong một transaction nên chạy lại an toàn sau deadlock.
WRITES = {
    CustomerService: ("create_customer", "update_customer", "set_customer_status"),
    WalletService: ("top_up",),
    MachineService: ("create_machine", "update_machine", "set_maintenance", "archive_machine"),
    SessionService: ("open_session", "complete_checkout"),
}
READS = {
    AuthService: ("login",),
    CustomerService: ("get_customer", "search_customers"),
    WalletService: ("get_history",),
    MachineService: ("list_machines",),
    SessionService: ("preview_open", "preview_checkout"),
    ReportService: ("list_invoices", "get_invoice", "daily_revenue"),
}


def _cases(table: dict[type, tuple[str, ...]]) -> list[tuple[type, str]]:
    return [(cls, name) for cls, names in table.items() for name in names]


@pytest.mark.parametrize(("cls", "name"), _cases(WRITES))
def test_write_operations_retry_on_deadlock(cls: type, name: str) -> None:
    assert hasattr(getattr(cls, name), "__wrapped__"), f"{cls.__name__}.{name} thiếu @retry_on_transient"


@pytest.mark.parametrize(("cls", "name"), _cases(READS))
def test_read_operations_are_not_retried(cls: type, name: str) -> None:
    assert not hasattr(getattr(cls, name), "__wrapped__")


@pytest.mark.parametrize(
    "module",
    [auth_service, customer_service, wallet_service, machine_service, session_service, report_service],
)
def test_services_no_longer_catch_mysql_errors_themselves(module) -> None:
    source = inspect.getsource(module)
    assert "translate_db_errors" in source
    for leftover in ("except MySQLError", "except IntegrityError", "errorcode."):
        assert leftover not in source, f"{module.__name__} còn tự bắt lỗi MySQL: {leftover}"
