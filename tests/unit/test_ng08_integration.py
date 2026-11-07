"""Unit tests cho NG-08 — error states, phím tắt và integration sweep của toàn bộ UI trên mock.

- Mọi màn có trạng thái lỗi + Thử lại, không lộ traceback hay câu lỗi nội bộ (tiếng Việt) của service.
- Mỗi loại exception đi đúng kênh: field / alert / toast (feedback.notify_error).
- Code UI chạy thật không import mock (chỉ demo `_run_demo` và component_gallery được phép).
- Phím tắt của App Shell: Ctrl+F, Esc, F5, Ctrl+1..5.
- Luồng nghiệm thu chính chạy hết qua UI: tạo khách -> nạp tiền -> mở phiên -> thanh toán -> hóa đơn -> doanh thu.
"""

from __future__ import annotations

import ast
from contextlib import ExitStack, contextmanager
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import patch

import customtkinter as ctk
import pytest

from cyberhub_manager.domain.enums import InvoiceStatus, MachineStatus, PaymentMethod
from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationError,
)
from cyberhub_manager.services.mocks.clock import MockClock
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.services.mocks.scenarios import MockScenario
from cyberhub_manager.ui import feedback as feedback_module
from cyberhub_manager.ui.app_shell import AppShell, PlaceholderView, ViewContext
from cyberhub_manager.ui.background import ImmediateTaskRunner
from cyberhub_manager.ui.customers_view import CustomersView
from cyberhub_manager.ui.dashboard_view import DashboardView
from cyberhub_manager.ui.dialogs import checkout_dialog as checkout_module
from cyberhub_manager.ui.dialogs.checkout_dialog import CheckoutDialog
from cyberhub_manager.ui.dialogs.customer_dialog import CustomerDialog
from cyberhub_manager.ui.dialogs.open_session_dialog import ELIGIBLE, OpenSessionDialog
from cyberhub_manager.ui.dialogs.topup_dialog import TopUpDialog
from cyberhub_manager.ui.invoices_view import InvoicesView
from cyberhub_manager.ui.machine_management_view import MachineManagementView
from cyberhub_manager.ui.messages import MSG_OPERATION_FAILED
from cyberhub_manager.ui.navigation import NAV_ITEMS, NavKey
from cyberhub_manager.ui.reports_view import ReportsView
from cyberhub_manager.ui.state import ViewState
from cyberhub_manager.ui.views import default_view_factories

RUNNER = ImmediateTaskRunner()
UI_DIR = Path(__file__).resolve().parents[2] / "src" / "cyberhub_manager" / "ui"
# Câu lỗi nội bộ (tiếng Việt) của mock service — không bao giờ được hiện ra giao diện.
INTERNAL_MESSAGES = ("Không tải được dữ liệu", "Dịch vụ hiện không khả dụng", "Traceback", "SELECT ", "mysql")
VIEWS = {
    NavKey.DASHBOARD: DashboardView,
    NavKey.CUSTOMERS: CustomersView,
    NavKey.MACHINES: MachineManagementView,
    NavKey.INVOICES: InvoicesView,
    NavKey.REPORTS: ReportsView,
}


def _login(username: str = "quanly01", scenario: MockScenario = MockScenario.SUCCESS, clock: MockClock | None = None):
    services = build_mock_services(scenario, clock=clock)
    session = build_mock_services().auth.login(username, DEMO_PASSWORD)  # đăng nhập không phụ thuộc scenario
    context = ViewContext(services=services, session=session, language="vi", navigate=lambda _k: True)
    return services, session, context


def _texts(widget: Any) -> list[str]:
    """Mọi chữ đang hiển thị trong cây widget."""
    found: list[str] = []
    for child in widget.winfo_children():
        if isinstance(child, (ctk.CTkLabel, ctk.CTkButton)):
            found.append(str(child.cget("text")))
        found.extend(_texts(child))
    return found


@pytest.fixture(autouse=True)
def _silence_feedback():
    with patch.object(feedback_module.ToastManager, "show") as toast, patch.object(
        feedback_module.ConfirmDialog, "alert"
    ) as alert:
        toast.alert = alert
        yield toast


# ----------------------------------------------------------------------
# 1. Đăng ký màn + không còn mock trong code chạy thật
# ----------------------------------------------------------------------
def test_every_menu_item_has_a_real_view() -> None:
    factories = default_view_factories()
    assert {item.key for item in NAV_ITEMS} == set(factories)
    assert all(factory is not PlaceholderView for factory in factories.values())


def test_production_ui_modules_do_not_import_mocks() -> None:
    allowed = {"component_gallery.py"}  # bộ sưu tập component NG-01 (công cụ dev)
    offenders = []
    for path in UI_DIR.rglob("*.py"):
        if path.name in allowed:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_run_demo":
                continue  # demo chạy không cần MySQL: import mock bên trong hàm, không ở module
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node.col_offset == 0:
                names = [node.module or ""] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names]
                if any("mocks" in name for name in names):
                    offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []


# ----------------------------------------------------------------------
# 2. Error state của từng màn
# ----------------------------------------------------------------------
@pytest.mark.parametrize("key", list(VIEWS))
def test_every_view_shows_safe_error_state_with_retry(tk_root, key: NavKey) -> None:
    _, _, context = _login(scenario=MockScenario.UNAVAILABLE)
    view = VIEWS[key](tk_root, context, runner=RUNNER)
    assert view.state == ViewState.ERROR
    assert view._retry_button.winfo_manager() == "pack"
    texts = _texts(view)
    assert any("temporarily unavailable" in text for text in texts)
    for text in texts:
        assert not any(bad in text for bad in INTERNAL_MESSAGES), text
    view.destroy()


LOADERS = {
    NavKey.DASHBOARD: ("machines", "list_machines"),
    NavKey.CUSTOMERS: ("customers", "search_customers"),
    NavKey.MACHINES: ("machines", "list_machines"),
    NavKey.INVOICES: ("reports", "list_invoices"),
    NavKey.REPORTS: ("reports", "daily_revenue"),
}


@pytest.mark.parametrize("key", list(VIEWS))
def test_every_view_recovers_after_retry(tk_root, key: NavKey) -> None:
    services, _, context = _login()
    service_name, method = LOADERS[key]
    service = getattr(services, service_name)
    with patch.object(service, method, side_effect=ServiceUnavailableError()):
        view = VIEWS[key](tk_root, context, runner=RUNNER)
    assert view.state == ViewState.ERROR
    view._retry_button.invoke()  # dịch vụ đã trở lại
    assert view.state in (ViewState.READY, ViewState.EMPTY)
    assert view._retry_button.winfo_manager() == ""
    view.destroy()


@pytest.mark.parametrize(
    ("error", "channel"),
    [
        (ValidationError(field_errors={"phone": "x"}), "toast"),
        (ConflictError("x"), "alert"),
        (PermissionDeniedError(), "toast"),
        (NotFoundError(), "toast"),
        (ServiceUnavailableError(), "toast"),
        (RuntimeError("SELECT * FROM secret"), "toast"),
    ],
)
def test_notify_error_routes_each_exception(tk_root, _silence_feedback, error: Exception, channel: str) -> None:
    feedback_module.notify_error(tk_root, error, conflict_as_alert=True)
    if channel == "alert":
        _silence_feedback.alert.assert_called_once()
        _silence_feedback.assert_not_called()
        message = _silence_feedback.alert.call_args.args[2]
    else:
        _silence_feedback.alert.assert_not_called()
        message = _silence_feedback.call_args.args[1]
    assert "SELECT" not in message and "x" != message
    if isinstance(error, RuntimeError):
        assert message == MSG_OPERATION_FAILED  # lỗi hệ thống: câu chung, chi tiết chỉ ghi log


# ----------------------------------------------------------------------
# 3. Phím tắt App Shell
# ----------------------------------------------------------------------
@contextmanager
def _shell(tk_root, username: str = "quanly01"):
    """App Shell thật với các màn chạy runner đồng bộ."""
    services, session, _ = _login(username)
    modules = ("dashboard_view", "customers_view", "invoices_view", "reports_view", "machine_management_view")
    with ExitStack() as stack:
        for module in modules:
            stack.enter_context(patch(f"cyberhub_manager.ui.{module}.default_runner", return_value=RUNNER))
        shell = AppShell(tk_root, services, session, on_logout=lambda: None, view_factories=default_view_factories())
        try:
            yield shell, services
        finally:
            if shell.winfo_exists():
                shell.destroy()


def test_ctrl_number_navigates_visible_menu(tk_root) -> None:
    with _shell(tk_root) as (shell, _):
        shell._navigate_by_index(4)  # quản lý: Tổng quan, Khách hàng, Quản lý máy, Hóa đơn, Doanh thu
        assert shell.current_key == NavKey.INVOICES
        shell._navigate_by_index(9)  # ngoài phạm vi: bỏ qua
        assert shell.current_key == NavKey.INVOICES


def test_staff_shortcuts_skip_hidden_menu(tk_root) -> None:
    with _shell(tk_root, "nhanvien01") as (shell, _):
        assert NavKey.MACHINES not in shell.nav_keys
        shell._navigate_by_index(3)  # nhân viên: menu thứ 3 là Hóa đơn
        assert shell.current_key == NavKey.INVOICES


def test_search_shortcuts(tk_root) -> None:
    with _shell(tk_root) as (shell, _):
        shell.navigate(NavKey.CUSTOMERS)
        view = shell.current_view
        assert shell.focus_search() == "break"
        shell._search_entry.insert(0, "0901000004")
        shell._on_search_submitted()
        assert view.visible_customer_ids == [4]
        shell.clear_search()  # Esc
        assert shell._search_entry.get() == ""
        assert len(view.visible_customer_ids) == 5


def test_f5_refreshes_current_view(tk_root) -> None:
    with _shell(tk_root) as (shell, services):
        with patch.object(services.machines, "list_machines", wraps=services.machines.list_machines) as listing:
            shell.refresh_current_view()  # dashboard: refresh(manual=True)
        listing.assert_called_once()
        shell.navigate(NavKey.REPORTS)
        with patch.object(services.reports, "daily_revenue", wraps=services.reports.daily_revenue) as daily:
            shell.refresh_current_view()
        daily.assert_called_once()


def test_shortcuts_unbound_after_logout(tk_root) -> None:
    with _shell(tk_root) as (shell, _):
        assert shell._shortcut_ids
        shell.destroy()
        assert shell._shortcut_ids == []
        assert tk_root.bind("<F5>") == ""


# ----------------------------------------------------------------------
# 4. Luồng nghiệm thu chính qua UI
# ----------------------------------------------------------------------
def test_full_demo_flow_through_ui(tk_root) -> None:
    clock = MockClock()
    services, session, context = _login(clock=clock)
    created = []
    dialog = CustomerDialog(tk_root, context, runner=RUNNER, on_saved=created.append)
    for key, value in {
        "full_name": "Khách Demo",
        "phone": "0909888777",
        "username": "khachdemo",
        "password": "secret1",
        "confirm_password": "secret1",
    }.items():
        dialog.fields[key].set_value(value)
    dialog.submit()
    customer = next(c for c in services.customers.search_customers("0909888777"))
    assert created[0].id == customer.customer_id and customer.balance == 0

    # Chưa nạp tiền -> không mở được phiên
    pc01 = next(m for m in services.machines.list_machines(session.store_id) if m.machine_code == "PC01")
    opener = OpenSessionDialog(tk_root, context, pc01, runner=RUNNER)
    opener.select_customer(customer)
    assert not opener.can_confirm and opener.top_up_visible
    opener.close()

    topups = []
    top_up = TopUpDialog(tk_root, context, customer, runner=RUNNER, on_success=topups.append)
    top_up.set_amount(50_000)
    top_up.set_method(PaymentMethod.CASH)
    top_up.submit()
    assert topups[0].balance_after == 50_000

    opened = []
    customer = next(c for c in services.customers.search_customers("0909888777"))
    opener = OpenSessionDialog(tk_root, context, pc01, runner=RUNNER, on_opened=opened.append)
    opener.select_customer(customer)
    assert opener.phase == ELIGIBLE
    opener.submit()
    assert opened and opened[0].machine_code == "PC01"

    clock.advance(minutes=60)
    pc01 = next(m for m in services.machines.list_machines(session.store_id) if m.machine_code == "PC01")
    assert pc01.status == MachineStatus.IN_USE
    results = []
    with patch.object(checkout_module, "PaymentSuccessDialog"):
        checkout = CheckoutDialog(tk_root, context, pc01, runner=RUNNER, on_completed=results.append)
        assert checkout.preview.usage_cost == 10_000 and not checkout.needs_settlement
        checkout.submit()
    invoice = results[0].invoice.invoice
    assert results[0].balance_after == 40_000

    invoices = InvoicesView(tk_root, context, runner=RUNNER)
    assert invoices.invoices[0].invoice_code == invoice.invoice_code
    assert invoices.invoices[0].status == InvoiceStatus.PAID
    reports = ReportsView(tk_root, context, runner=RUNNER)
    today = next(d for d in reports.days if d.date == date(2026, 10, 18))
    assert (today.invoice_count, today.revenue) == (2, 20_000)  # 10.000 có sẵn + 10.000 vừa thanh toán
    invoices.destroy()
    reports.destroy()
