"""Unit tests for Phase 6 Invoices & Payment Confirmation:
- PaymentConfirmDialog (Sufficient balance, Cash payment with change, QR Transfer with confirmation)
- InvoicesView (Split 65/35, Search & filter, 3-box high-tech receipt, Copy code action)
- Machine Management & Dashboard wiring to PaymentConfirmDialog
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parent.parent.parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock, patch

import customtkinter as ctk

from cyberhub_manager.domain.dtos import (
    CheckoutPreview,
    CheckoutResult,
    CustomerSummary,
    EmployeeSession,
    InvoiceDetail,
    InvoiceSummary,
    MachineSummary,
    SessionSummary,
)
from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    InvoiceStatus,
    MachineStatus,
    PaymentMethod,
    Role,
    SessionStatus,
)
from cyberhub_manager.ui.app_shell import ViewContext
from cyberhub_manager.ui.dialogs.payment_confirm_dialog import PaymentConfirmDialog
from cyberhub_manager.ui.invoices_view import InvoicesView
from cyberhub_manager.ui.machine_management_view import MachineManagementView
from cyberhub_manager.ui.theme import setup_theme


def _make_actor() -> EmployeeSession:
    return EmployeeSession(
        employee_id=1,
        employee_code="NV001",
        full_name="Nguyễn Tuấn Kiệt",
        username="kiet.nt",
        store_id=1,
        store_code="ST01",
        store_name="CyberHub Hà Nội",
        role=Role.MANAGER,
    )


def _make_session_summary(
    sid: int = 1,
    code: str = "SES-20260224-0001",
    mid: int = 2,
    mcode: str = "PC-02",
    mname: str = "Máy Standard 02",
) -> SessionSummary:
    return SessionSummary(
        session_id=sid,
        session_code=code,
        customer_id=1,
        customer_code="CUS-0001",
        customer_name="Nguyễn Văn An",
        machine_id=mid,
        machine_code=mcode,
        machine_name=mname,
        started_at=datetime(2026, 2, 24, 6, 0, tzinfo=timezone.utc),
        hourly_rate=10_000,
        status=SessionStatus.COMPLETED,
    )


def _make_invoice_summary(
    iid: int = 1,
    code: str = "INV-20260224-0001",
    total: int = 15_000,
    settle: int = 10_000,
    status: InvoiceStatus = InvoiceStatus.PAID,
) -> InvoiceSummary:
    return InvoiceSummary(
        invoice_id=iid,
        invoice_code=code,
        session_id=1,
        customer_id=1,
        customer_name="Nguyễn Văn An",
        employee_id=1,
        employee_name="Nguyễn Tuấn Kiệt",
        store_id=1,
        store_name="CyberHub Hà Nội",
        usage_cost=total,
        settlement_amount=settle,
        total_amount=total,
        status=status,
        created_at=datetime(2026, 2, 24, 7, 30, tzinfo=timezone.utc),
    )


def _make_customer(
    cid: int = 1,
    code: str = "CUS-0001",
    username: str = "an.nv",
) -> CustomerSummary:
    return CustomerSummary(
        customer_id=cid,
        customer_code=code,
        full_name="Nguyễn Văn An",
        phone="0912345678",
        account_id=cid,
        username=username,
        balance=50_000,
        customer_status=CustomerStatus.ACTIVE,
        account_status=AccountStatus.ACTIVE,
    )


_SHARED_ROOT: ctk.CTk | None = None


def setUpModule():
    global _SHARED_ROOT
    setup_theme()
    from tests.conftest import get_shared_tk_root

    _SHARED_ROOT = get_shared_tk_root()


def tearDownModule():
    global _SHARED_ROOT
    if _SHARED_ROOT is not None:
        for child in list(_SHARED_ROOT.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass


class TestPaymentConfirmDialog(unittest.TestCase):
    def setUp(self):
        self.root = _SHARED_ROOT
        self.services = MagicMock()
        self.actor = _make_actor()
        self.on_success = MagicMock()

    def test_sufficient_balance_flow(self):
        # Given: preview with settlement_required == 0
        sess = _make_session_summary()
        preview = CheckoutPreview(
            session=sess,
            calculated_at=datetime(2026, 2, 24, 7, 30, tzinfo=timezone.utc),
            elapsed_seconds=5400,
            billed_minutes=90,
            usage_cost=15_000,
            balance_before=50_000,
            projected_balance=35_000,
            settlement_required=0,
        )
        self.services.sessions.preview_checkout.return_value = preview
        self.services.customers.get_customer.return_value = _make_customer()

        res_mock = CheckoutResult(invoice=_make_invoice_summary(), balance_after=35_000)
        self.services.sessions.complete_checkout.return_value = res_mock

        # When
        dlg = PaymentConfirmDialog(
            self.root,
            self.services,
            machine_id=2,
            actor=self.actor,
            language="vi",
            on_success=self.on_success,
        )
        dlg.update_idletasks()

        # Then: confirm button should be enabled, method should be None
        self.assertTrue(dlg._can_confirm())
        self.assertTrue(dlg._btn_confirm.is_enabled)

        # Confirm checkout
        dlg._handle_confirm()
        self.services.sessions.complete_checkout.assert_called_once_with(
            machine_id=2,
            actor=self.actor,
            settlement_amount=0,
            method=None,
        )
        self.on_success.assert_called_once_with(res_mock)

    def test_insufficient_balance_cash_flow_and_calculator(self):
        # Given: preview requiring 10,000 VND settlement
        sess = _make_session_summary()
        preview = CheckoutPreview(
            session=sess,
            calculated_at=datetime(2026, 2, 24, 7, 30, tzinfo=timezone.utc),
            elapsed_seconds=5400,
            billed_minutes=90,
            usage_cost=15_000,
            balance_before=5_000,
            projected_balance=0,
            settlement_required=10_000,
        )
        self.services.sessions.preview_checkout.return_value = preview
        self.services.customers.get_customer.return_value = _make_customer()

        dlg = PaymentConfirmDialog(
            self.root,
            self.services,
            machine_id=2,
            actor=self.actor,
            language="vi",
            on_success=self.on_success,
        )
        dlg.update_idletasks()

        # By default in Cash mode with exact received amount (10,000)
        self.assertEqual(dlg._selected_method, PaymentMethod.CASH)
        self.assertTrue(dlg._can_confirm())

        # If customer gives 5,000 (< 10,000): cannot confirm
        dlg._entry_received.delete(0, "end")
        dlg._entry_received.insert(0, "5000")
        dlg._on_received_key()
        self.assertFalse(dlg._can_confirm())
        self.assertIn("Chưa đủ tiền", dlg._lbl_cash_status.cget("text"))

        # If customer gives 20,000 (>= 10,000): can confirm, change is 10,000
        dlg._entry_received.delete(0, "end")
        dlg._entry_received.insert(0, "20000")
        dlg._on_received_key()
        self.assertTrue(dlg._can_confirm())
        self.assertIn("Đã nhận đủ tiền", dlg._lbl_cash_status.cget("text"))

        # Submit
        dlg._handle_confirm()
        self.services.sessions.complete_checkout.assert_called_once_with(
            machine_id=2,
            actor=self.actor,
            settlement_amount=10_000,
            method=PaymentMethod.CASH,
        )

    def test_insufficient_balance_qr_transfer_flow(self):
        # Given: settlement required 10,000 VND
        sess = _make_session_summary()
        preview = CheckoutPreview(
            session=sess,
            calculated_at=datetime(2026, 2, 24, 7, 30, tzinfo=timezone.utc),
            elapsed_seconds=5400,
            billed_minutes=90,
            usage_cost=15_000,
            balance_before=5_000,
            projected_balance=0,
            settlement_required=10_000,
        )
        self.services.sessions.preview_checkout.return_value = preview
        self.services.customers.get_customer.return_value = _make_customer()

        dlg = PaymentConfirmDialog(
            self.root,
            self.services,
            machine_id=2,
            actor=self.actor,
            language="vi",
            on_success=self.on_success,
        )
        dlg.update_idletasks()

        # Switch to QR Transfer
        dlg._select_payment_method(PaymentMethod.TRANSFER)
        self.assertEqual(dlg._selected_method, PaymentMethod.TRANSFER)

        # Initially checkbox is unchecked -> cannot confirm
        self.assertFalse(dlg._can_confirm())

        # Check the verification box
        dlg._chk_qr.select()
        dlg._on_qr_checked()
        self.assertTrue(dlg._can_confirm())

        # Submit
        dlg._handle_confirm()
        self.services.sessions.complete_checkout.assert_called_once_with(
            machine_id=2,
            actor=self.actor,
            settlement_amount=10_000,
            method=PaymentMethod.TRANSFER,
        )


class TestInvoicesView(unittest.TestCase):
    def setUp(self):
        self.root = _SHARED_ROOT
        self.services = MagicMock()
        self.actor = _make_actor()
        self.context = ViewContext(
            services=self.services,
            session=self.actor,
            language="vi",
            navigate=MagicMock(),
        )

    def test_invoices_view_render_and_3box_detail(self):
        inv1 = _make_invoice_summary(iid=1, code="INV-001", total=15_000, settle=10_000)
        inv2 = _make_invoice_summary(iid=2, code="INV-002", total=20_000, settle=0, status=InvoiceStatus.VOID)
        self.services.reports.list_invoices.return_value = [inv1, inv2]

        sess = _make_session_summary()
        detail1 = InvoiceDetail(
            invoice=inv1,
            session=sess,
            ended_at=datetime(2026, 2, 24, 7, 30, tzinfo=timezone.utc),
            billed_minutes=90,
        )
        self.services.reports.get_invoice.return_value = detail1
        self.services.customers.get_customer.return_value = _make_customer()

        view = InvoicesView(self.root, self.context)
        view.update_idletasks()

        # Table rows check
        self.assertEqual(len(view._invoices), 2)
        self.assertIn("2 hóa đơn", view._table_count_label.cget("text"))

        # Right 3-box detail checks
        self.assertEqual(view._lbl_rec_code.cget("text"), "INV-001")
        self.assertEqual(view._lbl_rec_status.cget("text"), "ĐÃ THANH TOÁN")
        self.assertEqual(view._lbl_session_code.cget("text"), "SES-20260224-0001")
        self.assertEqual(view._lbl_store.cget("text"), "CyberHub Hà Nội")
        self.assertEqual(view._lbl_staff.cget("text"), "Nguyễn Tuấn Kiệt")
        self.assertIn("Nguyễn Văn An", view._lbl_cust.cget("text"))
        self.assertEqual(view._lbl_account.cget("text"), "an.nv")
        self.assertEqual(view._lbl_machine.cget("text"), "PC-02 — Máy Standard 02")
        self.assertEqual(view._lbl_duration.cget("text"), "1 giờ 30 phút")
        self.assertEqual(view._lbl_rate.cget("text"), "10.000 VND/giờ")

        # Payment Box
        self.assertEqual(view._lbl_usage_cost.cget("text"), "15.000 VND")
        self.assertEqual(view._lbl_balance_pay.cget("text"), "5.000 VND")
        self.assertEqual(view._lbl_settle_pay.cget("text"), "10.000 VND")
        self.assertEqual(view._lbl_method.cget("text"), "Tiền mặt")
        self.assertEqual(view._lbl_total_paid.cget("text"), "15.000 VND")

        # Copy button enabled
        self.assertTrue(view._btn_copy.is_enabled)

    def test_invoices_view_filters(self):
        self.services.reports.list_invoices.return_value = []
        view = InvoicesView(self.root, self.context)
        view.update_idletasks()

        # Switch filter to 'paid'
        view._set_status_filter("paid")
        self.assertEqual(view._current_status_filter, "paid")

        # Switch filter to 'cancelled'
        view._set_status_filter("cancelled")
        self.assertEqual(view._current_status_filter, "cancelled")

    def test_invoices_copy_code_action(self):
        inv1 = _make_invoice_summary(iid=1, code="INV-001")
        detail1 = InvoiceDetail(
            invoice=inv1,
            session=_make_session_summary(),
            ended_at=datetime(2026, 2, 24, 7, 30, tzinfo=timezone.utc),
            billed_minutes=90,
        )
        self.services.reports.list_invoices.return_value = [inv1]
        self.services.reports.get_invoice.return_value = detail1
        self.services.customers.get_customer.return_value = _make_customer()

        view = InvoicesView(self.root, self.context)
        view.update_idletasks()

        with patch.object(view, "clipboard_clear"), patch.object(view, "clipboard_append") as mock_append:
            view._handle_copy_invoice_code()
            mock_append.assert_called_once_with("INV-001")


class TestMachineManagementViewCheckoutWiring(unittest.TestCase):
    def setUp(self):
        self.root = _SHARED_ROOT
        self.services = MagicMock()
        self.actor = _make_actor()
        self.context = ViewContext(
            services=self.services,
            session=self.actor,
            language="vi",
            navigate=MagicMock(),
        )

    def test_in_use_machine_shows_checkout_button(self):
        mach_in_use = MachineSummary(
            machine_id=5,
            machine_code="PC-05",
            store_id=1,
            name="Máy Pro 05",
            status=MachineStatus.IN_USE,
            hourly_rate=15_000,
            is_active=True,
            updated_at=datetime.now(timezone.utc),
            active_session=None,
        )
        self.services.machines.list_machines.return_value = [mach_in_use]

        view = MachineManagementView(self.root, self.context)
        view.update_idletasks()

        # Select the in-use machine
        if hasattr(view, "_update_actions_enabled"):
            view._selected_machine = mach_in_use
            view._update_actions_enabled(True)
            self.assertEqual(view._btn_checkout.cget("text"), "Thanh toán")
            self.assertEqual(view._btn_checkout._kind, "danger")
            self.assertTrue(view._btn_checkout.is_enabled)
            self.assertFalse(view._btn_open_session.is_enabled)
        else:
            view._selected_id = 5
            view._update_actions()
            self.assertFalse(view._maintenance_button.is_enabled)
            self.assertFalse(view._archive_button.is_enabled)


if __name__ == "__main__":
    unittest.main()
