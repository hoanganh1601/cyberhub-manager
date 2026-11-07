"""Unit tests cho NG-05 — dialog Mở phiên sử dụng (tìm khách, kiểm tra điều kiện, nạp tiền, mở phiên)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from cyberhub_manager.domain.dtos import OpenSessionPreview
from cyberhub_manager.domain.enums import MachineStatus, PaymentMethod
from cyberhub_manager.domain.exceptions import ConflictError, ServiceUnavailableError
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.ui import dashboard_view as dashboard_module
from cyberhub_manager.ui import feedback as feedback_module
from cyberhub_manager.ui.app_shell import ViewContext
from cyberhub_manager.ui.background import ImmediateTaskRunner
from cyberhub_manager.ui.dashboard_view import DashboardView
from cyberhub_manager.ui.dialogs import open_session_dialog as open_module
from cyberhub_manager.ui.dialogs.open_session_dialog import (
    BLOCKED,
    CHECKING,
    ELIGIBLE,
    HINT_CANCEL_ONLY,
    HINT_READY,
    IDLE,
    INSUFFICIENT,
    NOT_AVAILABLE,
    OpenSessionDialog,
    conflict_reason,
    customer_block_reason,
    customer_option_text,
    estimate_text,
    required_top_up,
    status_text,
)

RUNNER = ImmediateTaskRunner()


def _login(username: str = "quanly01"):
    services = build_mock_services()
    session = services.auth.login(username, DEMO_PASSWORD)
    context = ViewContext(services=services, session=session, language="vi", navigate=lambda _k: True)
    return services, session, context


def _machine(services, session, code: str = "PC01"):
    return next(m for m in services.machines.list_machines(session.store_id) if m.machine_code == code)


def _customer(services, code: str):
    return next(c for c in services.customers.search_customers("") if c.customer_code == code)


def _preview(balance: int, *, minimum: int = 5_000, minutes: int = 250, can_open: bool = True) -> OpenSessionPreview:
    return OpenSessionPreview(
        customer_id=1,
        machine_id=1,
        balance=balance,
        hourly_rate=10_000,
        minimum_balance=minimum,
        estimated_minutes=minutes,
        can_open=can_open,
        blocked_reason=None if can_open else "Số dư chưa đủ",
        as_of=datetime(2026, 11, 7, tzinfo=timezone.utc),
    )


def _dialog(tk_root, username: str = "quanly01", machine_code: str = "PC01", **kwargs):
    services, session, context = _login(username)
    dialog = OpenSessionDialog(tk_root, context, _machine(services, session, machine_code), runner=RUNNER, **kwargs)
    return dialog, services, session


def _new_customer(services, phone: str = "0909111222"):
    created = services.customers.create_customer("Khách Mới", phone, "khachmoi", "secret1")
    return next(c for c in services.customers.search_customers(phone) if c.customer_id == created.id)


@pytest.fixture(autouse=True)
def _silence_feedback():
    """Toast/alert thật cần cửa sổ hiển thị; trong test chỉ ghi lại lời gọi."""
    with patch.object(feedback_module.ToastManager, "show") as toast, patch.object(
        dashboard_module.ToastManager, "show", toast
    ), patch.object(feedback_module.ConfirmDialog, "alert") as alert:
        toast.alert = alert
        yield toast


# ----------------------------------------------------------------------
# 1. Hàm thuần
# ----------------------------------------------------------------------
def test_customer_option_text_matches_stitch() -> None:
    services, _, _ = _login()
    assert customer_option_text(_customer(services, "KH001")) == "0901000001 - Nguyễn Văn An"


def test_estimate_text_and_required_top_up() -> None:
    assert estimate_text(_preview(50_000, minutes=250)) == "4 giờ 10 phút"
    assert estimate_text(_preview(2_000, can_open=False)) == NOT_AVAILABLE
    assert estimate_text(None) == NOT_AVAILABLE
    assert required_top_up(_preview(2_000, minimum=5_000, can_open=False)) == 3_000
    assert required_top_up(_preview(9_000, minimum=5_000)) == 0


def test_customer_block_reason_and_status_chips() -> None:
    services, _, _ = _login()
    assert customer_block_reason(_customer(services, "KH001")) is None
    assert customer_block_reason(_customer(services, "KH003")) == "Tài khoản khách hàng đã bị khóa"
    assert customer_block_reason(_customer(services, "KH004")) == "Khách hàng đã ngừng hoạt động"
    assert status_text(_customer(services, "KH003")) == (("Trạng thái KH: Hoạt động", True), ("Trạng thái TK: Đã khóa", False))


def test_conflict_reason_uses_field_not_internal_message() -> None:
    assert conflict_reason(ConflictError("x", field_errors={"machine_id": "Máy đang bảo trì"})).startswith("Máy không còn trống")
    assert conflict_reason(ConflictError("x", field_errors={"customer_id": "Khách hàng đang có phiên khác"})).startswith(
        "Khách hàng đang có phiên khác"
    )
    assert "Operation conflict" in conflict_reason(ConflictError("x"))


# ----------------------------------------------------------------------
# 2. Dialog
# ----------------------------------------------------------------------
def test_dialog_starts_idle_with_machine_info(tk_root) -> None:
    dialog, _, _ = _dialog(tk_root)
    assert dialog.phase == IDLE
    assert dialog.machine.machine_code == "PC01"
    assert not dialog.can_confirm and not dialog.confirm_button.is_enabled
    assert dialog.hint == HINT_CANCEL_ONLY
    assert not dialog.top_up_visible
    assert dialog._rate_label.cget("text") == "10.000 VND/giờ"
    dialog.submit()  # chưa chọn khách -> không làm gì
    assert dialog.phase == IDLE
    dialog.close()


def test_search_and_enter_selects_first_result(tk_root) -> None:
    dialog, _, _ = _dialog(tk_root)
    dialog._search_entry.insert(0, "nguyenvanan")
    dialog.search("nguyenvanan")
    assert [c.customer_code for c in dialog.results] == ["KH001"]
    assert dialog._results_box.winfo_manager() == "pack"
    dialog._on_search_return(SimpleNamespace(keysym="Return"))
    assert dialog.customer.customer_code == "KH001"
    assert dialog._search_entry.get() == "0901000001 - Nguyễn Văn An"
    assert not dialog._results_box.winfo_manager()  # danh sách gợi ý ẩn sau khi chọn
    assert dialog.phase == ELIGIBLE
    assert dialog.can_confirm
    assert dialog.hint == HINT_READY
    assert dialog.banner_text == "Khách hàng đủ điều kiện mở phiên"
    assert dialog._estimate_label.cget("text") == estimate_text(dialog.preview)
    dialog.close()


def test_search_without_match_shows_empty_message(tk_root) -> None:
    dialog, _, _ = _dialog(tk_root)
    dialog.search("không-có-ai")
    assert dialog.results == []
    assert dialog._results_box.winfo_manager() == "pack"
    dialog.search("   ")
    assert not dialog._results_box.winfo_manager()
    dialog.close()


def test_editing_search_clears_selected_customer(tk_root) -> None:
    dialog, services, _ = _dialog(tk_root)
    dialog.select_customer(_customer(services, "KH001"))
    assert dialog.phase == ELIGIBLE
    dialog._search_entry.insert("end", "x")
    dialog._on_key_release(SimpleNamespace(keysym="x"))
    assert dialog.customer is None
    assert dialog.phase == IDLE
    assert not dialog.confirm_button.is_enabled
    dialog.close()


def test_confirm_opens_session_and_calls_back(tk_root) -> None:
    opened = []
    dialog, services, session = _dialog(tk_root, on_opened=opened.append)
    dialog.select_customer(_customer(services, "KH001"))
    dialog.submit()
    assert [s.customer_code for s in opened] == ["KH001"]
    assert opened[0].machine_code == "PC01"
    assert _machine(services, session).status == MachineStatus.IN_USE


def test_staff_can_open_session(tk_root) -> None:
    opened = []
    dialog, services, _ = _dialog(tk_root, "nhanvien01", on_opened=opened.append)
    dialog.select_customer(_customer(services, "KH001"))
    dialog.submit()
    assert len(opened) == 1


def test_insufficient_balance_disables_confirm_and_offers_top_up(tk_root) -> None:
    dialog, services, session = _dialog(tk_root)
    customer = _new_customer(services)
    dialog.select_customer(customer)
    assert dialog.phase == INSUFFICIENT
    assert not dialog.can_confirm and not dialog.confirm_button.is_enabled
    assert dialog.top_up_visible
    assert dialog.hint == HINT_CANCEL_ONLY
    assert dialog._estimate_label.cget("text") == NOT_AVAILABLE
    assert dialog.banner_text == "Số dư chưa đạt mức tối thiểu để mở phiên"
    dialog.submit()  # nút bị khóa: Enter cũng không mở phiên
    assert _machine(services, session).status == MachineStatus.AVAILABLE
    dialog.close()


def test_top_up_cta_then_recheck_allows_opening(tk_root) -> None:
    opened = []
    dialog, services, session = _dialog(tk_root, on_opened=opened.append)
    customer = _new_customer(services)
    dialog.select_customer(customer)
    with patch.object(open_module, "TopUpDialog") as top_up_cls:
        dialog._top_up_button.invoke()
    args, kwargs = top_up_cls.call_args
    assert args[2].customer_id == customer.customer_id
    assert kwargs["account_code"]  # mã tài khoản lấy từ get_customer
    result = services.wallet.top_up(customer.customer_id, 50_000, PaymentMethod.CASH, session.employee_id)
    kwargs["on_success"](result)
    assert dialog.phase == ELIGIBLE
    assert dialog.preview.balance == 50_000
    assert not dialog.top_up_visible
    dialog.submit()
    assert len(opened) == 1


def test_locked_customer_is_blocked_without_calling_service(tk_root) -> None:
    dialog, services, _ = _dialog(tk_root)
    with patch.object(services.sessions, "preview_open") as preview:
        dialog.select_customer(_customer(services, "KH003"))
    preview.assert_not_called()
    assert dialog.phase == BLOCKED
    assert dialog.block_reason == "Tài khoản khách hàng đã bị khóa"
    assert dialog.banner_text == "Tài khoản khách hàng đã bị khóa"
    assert not dialog.top_up_visible and not dialog.can_confirm
    dialog.close()


def test_customer_with_active_session_is_blocked(tk_root) -> None:
    dialog, services, _ = _dialog(tk_root)
    dialog.select_customer(_customer(services, "KH002"))  # Bình đang chơi máy khác
    assert dialog.phase == BLOCKED
    assert dialog.block_reason.startswith("Khách hàng đang có phiên khác")
    dialog.close()


def test_conflict_on_confirm_shows_alert_and_blocks(tk_root, _silence_feedback) -> None:
    dialog, services, session = _dialog(tk_root)
    an = _customer(services, "KH001")
    dialog.select_customer(an)
    services.sessions.open_session(an.customer_id, _machine(services, session, "PC04").machine_id, session)  # quầy khác mở trước
    dialog.submit()
    _silence_feedback.alert.assert_called_once()
    assert dialog.phase == BLOCKED
    assert not dialog.is_submitting
    dialog.close()


def test_preview_service_error_returns_to_idle(tk_root, _silence_feedback) -> None:
    dialog, services, _ = _dialog(tk_root)
    with patch.object(services.sessions, "preview_open", side_effect=ServiceUnavailableError()):
        dialog.select_customer(_customer(services, "KH001"))
    assert dialog.phase == IDLE
    assert _silence_feedback.called
    dialog.close()


def test_stale_preview_result_is_ignored(tk_root) -> None:
    dialog, services, _ = _dialog(tk_root)
    dialog._customer = _customer(services, "KH001")
    dialog._phase = CHECKING
    dialog._preview_request = 5
    dialog._on_preview(4, _preview(1_000, can_open=False))  # kết quả cũ về muộn
    assert dialog.phase == CHECKING
    dialog.close()


# ----------------------------------------------------------------------
# 3. Dashboard
# ----------------------------------------------------------------------
def test_dashboard_open_button_opens_dialog(tk_root) -> None:
    services, session, context = _login()
    view = DashboardView(tk_root, context, runner=RUNNER)
    pc01 = _machine(services, session, "PC01")
    with patch.object(dashboard_module, "OpenSessionDialog") as dialog_cls:
        view.card_for(pc01.machine_id)._on_click()
    args, kwargs = dialog_cls.call_args
    assert args[2].machine_id == pc01.machine_id
    assert kwargs["on_opened"] == view._session_opened
    view.destroy()


def test_dashboard_refreshes_after_session_opened(tk_root, _silence_feedback) -> None:
    services, session, context = _login()
    view = DashboardView(tk_root, context, runner=RUNNER)
    pc01 = _machine(services, session, "PC01")
    view.card_for(pc01.machine_id)._on_click()  # mở dialog thật
    opened_dialog = next(w for w in tk_root.winfo_children() if isinstance(w, OpenSessionDialog))
    opened_dialog.select_customer(_customer(services, "KH001"))
    opened_dialog.submit()
    assert _silence_feedback.call_args.args[1] == "Session started on PC01."
    assert next(m for m in view.machines if m.machine_id == pc01.machine_id).status == MachineStatus.IN_USE
    view.destroy()
