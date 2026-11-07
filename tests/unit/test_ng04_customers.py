"""Unit tests cho NG-04 — màn Khách hàng (bảng, lọc, chi tiết, giao dịch gần đây)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from cyberhub_manager.domain.dtos import TransactionSummary
from cyberhub_manager.domain.enums import CustomerStatus, PaymentMethod, Role, TransactionType
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.services.mocks.scenarios import MockScenario
from cyberhub_manager.ui import customers_view as customers_module
from cyberhub_manager.ui.app_shell import AppShell, ViewContext
from cyberhub_manager.ui.background import ImmediateTaskRunner
from cyberhub_manager.ui.customers_view import (
    CustomersView,
    balance_color,
    count_by_status,
    filter_customers,
    page_caption,
    row_badge,
    transaction_line,
)
from cyberhub_manager.ui.navigation import NavKey
from cyberhub_manager.ui.state import ViewState
from cyberhub_manager.ui.table_kit import paginate
from cyberhub_manager.ui.theme import STITCH_DANGER, STITCH_SUCCESS, STITCH_TEXT_MUTED, STITCH_WARNING
from cyberhub_manager.ui.views import default_view_factories

RUNNER = ImmediateTaskRunner()


def _login(username: str = "quanly01", scenario: MockScenario = MockScenario.SUCCESS):
    services = build_mock_services(scenario)
    session = services.auth.login(username, DEMO_PASSWORD)
    return services, session


def _customers():
    services, _ = _login()
    return {c.customer_code: c for c in services.customers.search_customers("")}


def _transaction(amount: int, kind: TransactionType, method: PaymentMethod) -> TransactionSummary:
    return TransactionSummary(
        transaction_id=1,
        transaction_code="GD001",
        account_id=1,
        session_id=None,
        type=kind,
        amount=amount,
        method=method,
        employee_id=1,
        employee_name="NV",
        created_at=datetime(2026, 2, 24, 7, 30, tzinfo=timezone.utc),  # 14:30 giờ Việt Nam
    )


# ----------------------------------------------------------------------
# 1. Hàm thuần
# ----------------------------------------------------------------------
def test_filter_by_status_and_keyword() -> None:
    customers = list(_customers().values())
    assert len(filter_customers(customers)) == 5
    assert [c.customer_code for c in filter_customers(customers, CustomerStatus.INACTIVE)] == ["KH004"]
    # CUS-02: tìm theo mã, họ tên, SĐT, tên đăng nhập (không phân biệt hoa thường)
    assert [c.customer_code for c in filter_customers(customers, keyword=" kh002 ")] == ["KH002"]
    assert [c.customer_code for c in filter_customers(customers, keyword="0901000005")] == ["KH005"]
    assert [c.customer_code for c in filter_customers(customers, keyword="TRANQUOC")] == ["KH003"]
    assert [c.customer_code for c in filter_customers(customers, keyword="bình")] == ["KH002"]
    assert filter_customers(customers, CustomerStatus.INACTIVE, "KH001") == []


def test_count_by_status() -> None:
    counts = count_by_status(_customers().values())
    assert counts == {None: 5, CustomerStatus.ACTIVE: 4, CustomerStatus.INACTIVE: 1}


def test_balance_color_negative_is_red() -> None:
    assert balance_color(-1) == STITCH_DANGER
    assert balance_color(0) == STITCH_TEXT_MUTED
    assert balance_color(50_000) == STITCH_SUCCESS


def test_row_badge_warns_when_account_locked() -> None:
    customers = _customers()
    assert row_badge(customers["KH001"]).label == "Hoạt động"
    locked_account = row_badge(customers["KH003"])  # khách ACTIVE nhưng tài khoản LOCKED
    assert (locked_account.label, locked_account.text_color) == ("TK đã khóa", STITCH_WARNING)
    assert row_badge(customers["KH004"]).label == "Ngừng hoạt động"


def test_transaction_line() -> None:
    top_up = transaction_line(_transaction(50_000, TransactionType.TOP_UP, PaymentMethod.CASH))
    assert top_up == customers_module.TransactionLine("+50.000 VND", STITCH_SUCCESS, "Nạp tiền • Tiền mặt", "14:30 24/02")
    usage = transaction_line(_transaction(-25_000, TransactionType.USAGE_PAYMENT, PaymentMethod.ACCOUNT_BALANCE))
    assert (usage.amount, usage.color) == ("-25.000 VND", STITCH_DANGER)
    assert usage.description == "Thanh toán phiên • Số dư tài khoản"


def test_page_caption() -> None:
    assert page_caption(paginate(range(23), 3, 10)) == "Hiển thị 21 - 23 trên 23 khách hàng"


# ----------------------------------------------------------------------
# 2. View
# ----------------------------------------------------------------------
def _view(tk_root, username: str = "quanly01", scenario: MockScenario = MockScenario.SUCCESS):
    services, session = _login(username, scenario)
    context = ViewContext(services=services, session=session, language="vi", navigate=lambda _k: True)
    return CustomersView(tk_root, context, runner=RUNNER), services, session


def test_view_loads_customers_and_selects_first(tk_root) -> None:
    view, _, _ = _view(tk_root)
    assert view.state == ViewState.READY
    assert len(view.customers) == 5
    assert view.selected_customer.customer_code == "KH001"
    assert len(view.history) == 3  # lịch sử của KH001 trong mock
    assert view._tab_buttons[CustomerStatus.ACTIVE].cget("text") == "Hoạt động (4)"
    assert view._caption_label.cget("text") == "Hiển thị 1 - 5 trên 5 khách hàng"
    view.destroy()


def test_view_search_filter_and_select(tk_root) -> None:
    view, _, _ = _view(tk_root)
    view.handle_search("0901000004")  # từ ô tìm kiếm trên topbar
    assert view._search_entry.get() == "0901000004"
    assert view.visible_customer_ids == [4]
    view.handle_search("")
    view.set_status_filter(CustomerStatus.INACTIVE)
    assert view.visible_customer_ids == [4]
    view.select(4)
    assert view.selected_customer.customer_code == "KH004"
    assert len(view.history) == 2
    assert view._balance_label.cget("text") == "-5.000 VND"
    assert view._balance_label.cget("text_color") == STITCH_DANGER
    view.handle_search("không-có-khách-này")
    assert view.state == ViewState.EMPTY
    view.destroy()


def test_lock_button_only_for_manager(tk_root) -> None:
    view, _, session = _view(tk_root, "nhanvien01")
    assert session.role == Role.STAFF
    assert set(view.action_buttons) == {"top_up", "edit"}  # NG-04: STAFF không có action khóa
    view.destroy()

    view, _, _ = _view(tk_root, "quanly01")
    assert view.action_buttons["lock"].cget("text") == "Khóa"
    view.select(4)  # khách INACTIVE
    assert view.action_buttons["lock"].cget("text") == "Mở khóa"
    view.destroy()


def test_unavailable_service_shows_retry(tk_root) -> None:
    view, _, _ = _view(tk_root, scenario=MockScenario.UNAVAILABLE)
    assert view.state == ViewState.ERROR
    assert view._retry_button.winfo_manager() == "pack"
    assert view.selected_customer is None
    view.destroy()


def test_action_buttons_open_dialogs(tk_root) -> None:
    view, _, _ = _view(tk_root)
    view._account_code = "TK001"
    with patch.object(customers_module, "TopUpDialog") as top_up, patch.object(
        customers_module, "CustomerDialog"
    ) as customer_dialog, patch.object(customers_module, "CustomerLockDialog") as lock:
        view.action_buttons["top_up"].invoke()
        view.action_buttons["edit"].invoke()
        view.action_buttons["lock"].invoke()
        view._create_button.invoke()
    assert top_up.call_args.args[2].customer_code == "KH001"
    assert top_up.call_args.kwargs["account_code"] == "TK001"
    edit_call, create_call = customer_dialog.call_args_list
    assert edit_call.kwargs["customer"].customer_code == "KH001"
    assert "customer" not in create_call.kwargs
    assert lock.call_args.args[2].customer_code == "KH001"
    view.destroy()


def test_shell_registers_customers_view(tk_root) -> None:
    services, session = _login()
    with patch.object(customers_module, "default_runner", return_value=RUNNER), patch(
        "cyberhub_manager.ui.dashboard_view.default_runner", return_value=RUNNER
    ):
        shell = AppShell(tk_root, services, session, on_logout=lambda: None, view_factories=default_view_factories())
        assert shell.navigate(NavKey.CUSTOMERS)
        assert isinstance(shell.current_view, CustomersView)
        shell.destroy()


@pytest.mark.parametrize("username", ["quanly01", "nhanvien01"])
def test_create_button_visible_for_all_roles(tk_root, username: str) -> None:
    view, _, _ = _view(tk_root, username)
    assert view._create_button.winfo_manager() == "pack"
    view.destroy()
