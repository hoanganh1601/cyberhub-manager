"""Unit tests cho NG-06 — dialog Xác nhận thanh toán và Thanh toán thành công (hóa đơn)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from cyberhub_manager.domain.enums import InvoiceStatus, MachineStatus, PaymentMethod, TransactionType
from cyberhub_manager.services.mocks.clock import MockClock
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.ui import dashboard_view as dashboard_module
from cyberhub_manager.ui import feedback as feedback_module
from cyberhub_manager.ui.app_shell import ViewContext
from cyberhub_manager.ui.background import ImmediateTaskRunner
from cyberhub_manager.ui.dashboard_view import DashboardView
from cyberhub_manager.ui.dialogs import checkout_dialog as checkout_module
from cyberhub_manager.ui.dialogs.checkout_dialog import (
    READY,
    CheckoutDialog,
    change_due,
    cost_breakdown,
    qr_matrix,
    service_now,
    transfer_content,
)
from cyberhub_manager.ui.dialogs.payment_success_dialog import PaymentSuccessDialog, confirmation_lines

RUNNER = ImmediateTaskRunner()


def _login(username: str = "quanly01", clock: MockClock | None = None):
    services = build_mock_services(clock=clock)
    session = services.auth.login(username, DEMO_PASSWORD)
    context = ViewContext(services=services, session=session, language="vi", navigate=lambda _k: True)
    return services, session, context


def _machine(services, session, code: str):
    return next(m for m in services.machines.list_machines(session.store_id) if m.machine_code == code)


def _dialog(tk_root, code: str, username: str = "quanly01", clock: MockClock | None = None, **kwargs):
    services, session, context = _login(username, clock)
    dialog = CheckoutDialog(tk_root, context, _machine(services, session, code), runner=RUNNER, **kwargs)
    return dialog, services, session


@pytest.fixture(autouse=True)
def _silence_feedback():
    """Toast/alert thật cần cửa sổ hiển thị; trong test chỉ ghi lại lời gọi."""
    with patch.object(feedback_module.ToastManager, "show") as toast, patch.object(
        feedback_module.ConfirmDialog, "alert"
    ) as alert:
        toast.alert = alert
        yield toast


@pytest.fixture
def receipts():
    """Không mở dialog hóa đơn thật trong test luồng thanh toán; chỉ ghi lại tham số."""
    with patch.object(checkout_module, "PaymentSuccessDialog") as receipt_cls:
        yield receipt_cls


# ----------------------------------------------------------------------
# 1. Hàm thuần
# ----------------------------------------------------------------------
def test_service_now_uses_mock_clock_and_falls_back_to_utc() -> None:
    services, _, _ = _login()
    assert service_now(services) == services.sessions._clock.now()
    real_like = SimpleNamespace(sessions=SimpleNamespace(_clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)))
    assert service_now(real_like) == datetime(2026, 1, 1, tzinfo=timezone.utc)
    before = datetime.now(timezone.utc)
    assert service_now(SimpleNamespace(sessions=object())) >= before


def test_cost_breakdown_with_and_without_settlement() -> None:
    services, session, _ = _login()
    now = services.sessions._clock.now()
    binh = cost_breakdown(services.sessions.preview_checkout(_machine(services, session, "PC02").machine_id, now))
    assert (binh.usage_cost, binh.balance_before, binh.from_account, binh.settlement, binh.balance_after) == (15_000, 5_000, 5_000, 10_000, 0)
    em = cost_breakdown(services.sessions.preview_checkout(_machine(services, session, "PC05").machine_id, now))
    assert (em.usage_cost, em.from_account, em.settlement, em.balance_after) == (5_000, 5_000, 0, 95_000)


def test_change_due_and_transfer_content() -> None:
    assert change_due(20_000, 10_000) == 10_000
    assert change_due(10_000, 10_000) == 0
    assert change_due(9_000, 10_000) is None
    assert change_due(None, 10_000) is None
    assert transfer_content("PC02", "KH002") == "PC02-KH002"


def test_qr_matrix_is_stable_and_has_finder_patterns() -> None:
    matrix = qr_matrix("PC02-KH002")
    assert matrix == qr_matrix("PC02-KH002")
    assert matrix != qr_matrix("PC03-KH002")
    assert len(matrix) == 21 and all(len(row) == 21 for row in matrix)
    for top, left in ((0, 0), (0, 14), (14, 0)):
        assert all(matrix[top][left + i] for i in range(7))  # cạnh trên ô định vị
        assert matrix[top + 3][left + 3]  # lõi
        assert not matrix[top + 1][left + 1]  # vòng trắng


# ----------------------------------------------------------------------
# 2. Dialog xác nhận
# ----------------------------------------------------------------------
def test_no_settlement_checkout_debits_balance(tk_root, receipts) -> None:
    completed = []
    dialog, services, session = _dialog(tk_root, "PC05", on_completed=completed.append)
    assert dialog.phase == READY
    assert not dialog.needs_settlement
    assert dialog.username == "hoangvanem"
    assert dialog.can_confirm and dialog.confirm_button.is_enabled
    dialog.submit()
    result = completed[0]
    assert result.invoice.invoice.settlement_amount == 0
    assert result.invoice.invoice.status == InvoiceStatus.PAID
    assert result.balance_after == 95_000
    assert _machine(services, session, "PC05").status == MachineStatus.AVAILABLE
    assert receipts.call_args.kwargs == {"username": "hoangvanem", "method": None, "cash_given": None, "language": "vi"}


def test_cash_settlement_requires_enough_cash(tk_root, receipts) -> None:
    completed = []
    dialog, services, session = _dialog(tk_root, "PC02", on_completed=completed.append)
    assert dialog.needs_settlement and dialog.method == PaymentMethod.CASH
    assert not dialog.can_confirm  # chưa nhập tiền khách đưa
    dialog.set_cash_given("9.000")
    assert not dialog.can_confirm
    assert dialog._cash_status.cget("text") == "●  Còn thiếu 1.000 VND"
    dialog.submit()  # bị chặn
    assert completed == []
    dialog.set_cash_given("20.000")
    assert dialog.can_confirm
    assert dialog._change_label.cget("text") == "10.000 VND"
    assert dialog._cash_status.cget("text") == "●  Đã nhận đủ tiền"
    dialog.submit()
    invoice = completed[0].invoice.invoice
    assert invoice.settlement_amount == 10_000  # đúng settlement_required, không phải tiền khách đưa
    assert completed[0].balance_after == 0
    assert receipts.call_args.kwargs == {"username": "lethibinh", "method": PaymentMethod.CASH, "cash_given": 20_000, "language": "vi"}
    settlement = [t for t in services.wallet.get_history(2) if t.type == TransactionType.DEBT_SETTLEMENT][0]
    assert (settlement.amount, settlement.method, settlement.employee_id) == (10_000, PaymentMethod.CASH, session.employee_id)


def test_transfer_settlement_requires_staff_confirmation(tk_root, receipts) -> None:
    completed = []
    dialog, services, _ = _dialog(tk_root, "PC02", "nhanvien01", on_completed=completed.append)
    dialog.set_cash_given("50.000")
    dialog.set_method(PaymentMethod.TRANSFER)
    assert dialog.method == PaymentMethod.TRANSFER
    assert not dialog.can_confirm  # tiền mặt đã nhập không còn tính
    dialog.set_transfer_confirmed(True)
    assert dialog.can_confirm
    dialog.submit()
    assert completed[0].invoice.invoice.settlement_amount == 10_000
    assert receipts.call_args.kwargs["method"] == PaymentMethod.TRANSFER
    assert receipts.call_args.kwargs["cash_given"] is None
    settlement = [t for t in services.wallet.get_history(2) if t.type == TransactionType.DEBT_SETTLEMENT][0]
    assert settlement.method == PaymentMethod.TRANSFER


def test_method_switch_keeps_cash_input(tk_root) -> None:
    dialog, _, _ = _dialog(tk_root, "PC02")
    dialog.set_cash_given("15.000")
    dialog.set_method(PaymentMethod.TRANSFER)
    dialog.set_method(PaymentMethod.CASH)
    assert dialog._cash_entry.get() == "15.000"
    assert dialog.can_confirm
    dialog.close()


def test_fee_increase_before_confirm_reloads_preview(tk_root, receipts, _silence_feedback) -> None:
    clock = MockClock()
    completed = []
    dialog, _, _ = _dialog(tk_root, "PC02", clock=clock, on_completed=completed.append)
    dialog.set_cash_given("10.000")
    clock.advance(minutes=30)  # sang phút mới: phí tăng 5.000 -> tiền bù cũ không đủ
    dialog.submit()
    assert completed == []
    assert _silence_feedback.called  # Toast lỗi
    assert dialog.phase == READY
    assert dialog.preview.settlement_required == 15_000
    assert dialog._cash_entry.get() == "10.000"  # giữ tiền đã nhập
    assert not dialog.can_confirm
    dialog.set_cash_given("15.000")
    dialog.submit()
    assert completed[0].invoice.invoice.settlement_amount == 15_000


def test_already_checked_out_closes_with_alert(tk_root, _silence_feedback) -> None:
    refreshed = []
    dialog, services, session = _dialog(tk_root, "PC05", on_conflict=lambda: refreshed.append(True))
    services.sessions.complete_checkout(_machine(services, session, "PC05").machine_id, session, 0, None)  # quầy khác
    dialog.submit()
    _silence_feedback.alert.assert_called_once()
    assert refreshed == [True]
    assert not dialog.winfo_exists()


def test_preview_conflict_on_open_closes_dialog(tk_root, _silence_feedback) -> None:
    refreshed = []
    services, session, context = _login()
    pc01 = _machine(services, session, "PC01")  # máy trống, không có phiên
    dialog = CheckoutDialog(tk_root, context, pc01, runner=RUNNER, on_conflict=lambda: refreshed.append(True))
    _silence_feedback.alert.assert_called_once()
    assert refreshed == [True]
    assert not dialog.winfo_exists()


# ----------------------------------------------------------------------
# 3. Dialog hóa đơn
# ----------------------------------------------------------------------
def _checkout(services, session, code: str, settlement: int, method):
    return services.sessions.complete_checkout(_machine(services, session, code).machine_id, session, settlement, method)


def test_confirmation_lines_for_cash_and_balance_only() -> None:
    services, session, _ = _login()
    cash = _checkout(services, session, "PC02", 10_000, PaymentMethod.CASH)
    texts = [(line.strong, line.text, line.code) for line in confirmation_lines(cash, PaymentMethod.CASH)]
    assert texts[0] == ("", "Phiên sử dụng đã hoàn thành", "")
    assert texts[1][1] == "Máy PC02 đã chuyển về trạng thái "
    assert ("5.000 VND", " đã được trừ từ tài khoản khách hàng", "") in texts
    assert ("10.000 VND", " tiền mặt đã được ghi nhận", "") in texts
    assert texts[-1] == ("", "Hóa đơn ", cash.invoice.invoice.invoice_code)
    balance_only = _checkout(services, session, "PC05", 0, None)
    assert len(confirmation_lines(balance_only, None)) == 4  # không có dòng tiền mặt/chuyển khoản


def test_transfer_confirmation_line() -> None:
    services, session, _ = _login()
    result = _checkout(services, session, "PC02", 10_000, PaymentMethod.TRANSFER)
    assert any(line.text == " chuyển khoản đã được nhân viên xác nhận" for line in confirmation_lines(result, PaymentMethod.TRANSFER))


def test_success_dialog_shows_invoice_and_copies_code(tk_root, _silence_feedback) -> None:
    services, session, _ = _login()
    result = _checkout(services, session, "PC02", 10_000, PaymentMethod.CASH)
    dialog = PaymentSuccessDialog(tk_root, result, username="lethibinh", method=PaymentMethod.CASH, cash_given=20_000)
    assert dialog.invoice_code == result.invoice.invoice.invoice_code
    assert dialog._change_label.cget("text") == "10.000 VND"
    dialog.cancel_button.invoke()  # "Sao chép mã HĐ" không đóng dialog
    assert dialog.clipboard_get() == dialog.invoice_code
    assert _silence_feedback.call_args.args[1] == "Invoice code copied."
    assert dialog.winfo_exists()
    dialog.confirm_button.invoke()  # "Đóng"
    assert not dialog.winfo_exists()


# ----------------------------------------------------------------------
# 4. Dashboard
# ----------------------------------------------------------------------
def test_dashboard_checkout_button_opens_dialog(tk_root) -> None:
    services, session, context = _login()
    view = DashboardView(tk_root, context, runner=RUNNER)
    pc02 = _machine(services, session, "PC02")
    with patch.object(dashboard_module, "CheckoutDialog") as dialog_cls:
        view.card_for(pc02.machine_id)._on_click()
    args, kwargs = dialog_cls.call_args
    assert args[2].machine_id == pc02.machine_id
    assert kwargs["on_conflict"] == view.refresh
    view.destroy()


def test_dashboard_refreshes_after_checkout(tk_root, receipts) -> None:
    services, session, context = _login()
    view = DashboardView(tk_root, context, runner=RUNNER)
    pc05 = _machine(services, session, "PC05")
    view.card_for(pc05.machine_id)._on_click()  # mở dialog thật
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, CheckoutDialog))
    dialog.submit()
    assert next(m for m in view.machines if m.machine_id == pc05.machine_id).status == MachineStatus.AVAILABLE
    assert receipts.called
    view.destroy()


def test_preview_uses_service_clock_not_wall_clock(tk_root) -> None:
    clock = MockClock(datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc))
    dialog, _, _ = _dialog(tk_root, "PC02", clock=clock)
    assert dialog.preview.calculated_at == clock.now()
    assert dialog.preview.elapsed_seconds == int(timedelta(minutes=90).total_seconds())
    dialog.close()
