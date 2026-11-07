"""Unit tests for Phase 4 Customer Dialogs: CustomerDialog, TopUpDialog, CustomerLockDialog."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import customtkinter as ctk

from cyberhub_manager.domain.dtos import CustomerSummary, EmployeeSession
from cyberhub_manager.domain.enums import AccountStatus, CustomerStatus, PaymentMethod, Role
from cyberhub_manager.ui.dialogs.customer_dialog import CustomerDialog
from cyberhub_manager.ui.dialogs.customer_lock_dialog import CustomerLockDialog, LockAccountDialog
from cyberhub_manager.ui.dialogs.topup_dialog import PRESET_AMOUNTS, TopUpDialog
from cyberhub_manager.ui.theme import setup_theme


def _make_dummy_customer(
    cid: int = 143,
    status: CustomerStatus = CustomerStatus.ACTIVE,
    acc_status: AccountStatus = AccountStatus.ACTIVE,
    balance: int = 50_000,
) -> CustomerSummary:
    return CustomerSummary(
        customer_id=cid,
        customer_code=f"CUS-{cid:04d}",
        full_name="Nguyễn Thị Lan Anh",
        phone="0934567890",
        account_id=cid,
        username="lan.nt",
        balance=balance,
        customer_status=status,
        account_status=acc_status,
    )


def _make_dummy_actor() -> EmployeeSession:
    return EmployeeSession(
        employee_id=1,
        employee_code="NV001",
        full_name="Quản Lý 01",
        username="quanly01",
        store_id=1,
        store_code="ST01",
        store_name="CyberHub Center",
        role=Role.MANAGER,
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


class TestCustomerDialog(unittest.TestCase):
    def setUp(self):
        self.root = _SHARED_ROOT
        self.mock_services = MagicMock()
        self.on_success = MagicMock()

    def test_create_mode_validation_errors(self):
        """Kiểm tra validation client-side khi tạo mới khách hàng với dữ liệu thiếu."""
        dlg = CustomerDialog(self.root, self.mock_services, on_success=self.on_success, language="vi")
        self.addCleanup(dlg.destroy)

        # 1. Để trống toàn bộ và nhấn Lưu
        dlg._handle_save()
        self.assertEqual(self.mock_services.customers.create_customer.call_count, 0)
        self.assertIn("⚠", dlg._name_err.cget("text"))
        self.assertIn("⚠", dlg._phone_err.cget("text"))
        self.assertIn("⚠", dlg._user_err.cget("text"))
        self.assertIn("⚠", dlg._pass_err.cget("text"))

        # 2. Nhập họ tên nhưng SĐT không hợp lệ
        dlg._name_entry.insert(0, "Nguyễn Văn Test")
        dlg._phone_entry.insert(0, "123")  # Quá ngắn
        dlg._user_entry.insert(0, "test.nv")
        dlg._pass_entry.insert(0, "123456")
        dlg._confirm_entry.insert(0, "123456")
        dlg._handle_save()

        self.assertEqual(self.mock_services.customers.create_customer.call_count, 0)
        self.assertIn("Số điện thoại", dlg._phone_err.cget("text"))

        # 3. Mật khẩu xác nhận không khớp
        dlg._phone_entry.delete(0, "end")
        dlg._phone_entry.insert(0, "0912345678")
        dlg._confirm_entry.delete(0, "end")
        dlg._confirm_entry.insert(0, "654321")
        dlg._handle_save()

        self.assertEqual(self.mock_services.customers.create_customer.call_count, 0)
        self.assertIn("không khớp", dlg._confirm_err.cget("text"))

    def test_create_mode_success(self):
        """Tạo khách hàng mới thành công gọi service và trigger on_success."""
        dlg = CustomerDialog(self.root, self.mock_services, on_success=self.on_success, language="vi")
        self.addCleanup(dlg.destroy)

        dlg._name_entry.insert(0, "Nguyễn Văn Test")
        dlg._phone_entry.insert(0, "0912345678")
        dlg._user_entry.insert(0, "test.nv")
        dlg._pass_entry.insert(0, "123456")
        dlg._confirm_entry.insert(0, "123456")

        with patch("cyberhub_manager.ui.dialogs.customer_dialog.ToastManager.show"):
            dlg._handle_save()

        self.mock_services.customers.create_customer.assert_called_once_with(
            full_name="Nguyễn Văn Test",
            phone="0912345678",
            username="test.nv",
            password="123456",
        )
        self.on_success.assert_called_once()

    def test_edit_mode_prefill_and_update(self):
        """Chế độ sửa khách hàng điền sẵn dữ liệu và cập nhật thành công."""
        cust = _make_dummy_customer()
        dlg = CustomerDialog(self.root, self.mock_services, customer=cust, on_success=self.on_success, language="vi")
        self.addCleanup(dlg.destroy)

        # Kiểm tra dữ liệu điền sẵn
        self.assertEqual(dlg._name_entry.get(), "Nguyễn Thị Lan Anh")
        self.assertEqual(dlg._phone_entry.get(), "0934567890")

        # Thay đổi họ tên và SĐT
        dlg._name_entry.delete(0, "end")
        dlg._name_entry.insert(0, "Nguyễn Thị Lan Anh Cập Nhật")
        dlg._phone_entry.delete(0, "end")
        dlg._phone_entry.insert(0, "0987654321")

        with patch("cyberhub_manager.ui.dialogs.customer_dialog.ToastManager.show"):
            dlg._handle_save()

        self.mock_services.customers.update_customer.assert_called_once_with(
            customer_id=143,
            full_name="Nguyễn Thị Lan Anh Cập Nhật",
            phone="0987654321",
        )
        self.on_success.assert_called_once()


class TestTopUpDialog(unittest.TestCase):
    def setUp(self):
        self.root = _SHARED_ROOT
        self.mock_services = MagicMock()
        self.on_success = MagicMock()
        self.cust = _make_dummy_customer(balance=100_000)

    def test_initial_state_empty(self):
        """TopUpDialog khởi tạo rỗng đúng thiết kế n_p_ti_n_default."""
        dlg = TopUpDialog(self.root, self.mock_services, self.cust, employee_id=1, on_success=self.on_success, language="vi")
        self.addCleanup(dlg.destroy)

        self.assertEqual(dlg._amount_entry.get(), "")
        self.assertEqual(dlg._preview_amount_lbl.cget("text"), "—")
        self.assertEqual(dlg._preview_new_bal_lbl.cget("text"), "—")
        self.assertFalse(dlg._submit_btn.cget("state") == "normal")

    def test_preset_clicks(self):
        """Click các nút preset cập nhật giá trị ô nhập và xem trước số dư."""
        dlg = TopUpDialog(self.root, self.mock_services, self.cust, employee_id=1, on_success=self.on_success, language="vi")
        self.addCleanup(dlg.destroy)

        self.assertEqual(PRESET_AMOUNTS, [10_000, 20_000, 50_000, 100_000])

        dlg._on_preset_click(50_000)
        self.assertEqual(dlg._amount_entry.get(), "50.000")
        self.assertIn("50.000", dlg._preview_amount_lbl.cget("text"))
        self.assertIn("150.000", dlg._preview_new_bal_lbl.cget("text"))
        self.assertEqual(dlg._submit_btn.cget("state"), "normal")

    def test_amount_validation_error(self):
        """Nhập số tiền vượt hạn mức hoặc ký tự lạ hiển thị thông báo lỗi đúng Stitch."""
        dlg = TopUpDialog(self.root, self.mock_services, self.cust, employee_id=1, on_success=self.on_success, language="vi")
        self.addCleanup(dlg.destroy)

        # 1. Quá 100.000.000
        dlg._amount_entry.insert(0, "100.000.001")
        dlg._on_entry_changed()
        self.assertIn("100.000.000", dlg._err_label.cget("text"))
        self.assertEqual(dlg._preview_amount_lbl.cget("text"), "—")
        self.assertFalse(dlg._submit_btn.cget("state") == "normal")

        # 2. Ký tự không phải số
        dlg._amount_entry.delete(0, "end")
        dlg._amount_entry.insert(0, "abc")
        dlg._on_entry_changed()
        self.assertIn("⚠", dlg._err_label.cget("text"))
        self.assertFalse(dlg._submit_btn.cget("state") == "normal")

    def test_payment_method_and_top_up_success(self):
        """Đổi phương thức thanh toán và hoàn tất nạp tiền gọi service thành công."""
        dlg = TopUpDialog(self.root, self.mock_services, self.cust, employee_id=1, on_success=self.on_success, language="vi")
        self.addCleanup(dlg.destroy)

        dlg._set_method(PaymentMethod.TRANSFER)
        self.assertEqual(dlg._selected_method, PaymentMethod.TRANSFER)

        dlg._on_preset_click(20_000)
        with patch("cyberhub_manager.ui.dialogs.topup_dialog.ToastManager.show"):
            dlg._handle_top_up()

        self.mock_services.wallet.top_up.assert_called_once_with(
            customer_id=143,
            amount=20_000,
            method=PaymentMethod.TRANSFER,
            employee_id=1,
        )
        self.on_success.assert_called_once()


class TestCustomerLockDialog(unittest.TestCase):
    def setUp(self):
        self.root = _SHARED_ROOT
        self.mock_services = MagicMock()
        self.on_success = MagicMock()
        self.actor = _make_dummy_actor()

    def test_lock_account_confirm(self):
        """Khóa tài khoản khách hàng gọi set_customer_status với INACTIVE."""
        cust = _make_dummy_customer(status=CustomerStatus.ACTIVE)
        dlg = LockAccountDialog(self.root, self.mock_services, cust, self.actor, on_success=self.on_success, language="vi")
        self.addCleanup(dlg.destroy)

        self.assertEqual(dlg._target_status, CustomerStatus.INACTIVE)

        with patch("cyberhub_manager.ui.dialogs.customer_lock_dialog.ToastManager.show"):
            dlg._handle_confirm()

        self.mock_services.customers.set_customer_status.assert_called_once_with(
            customer_id=143,
            status=CustomerStatus.INACTIVE,
            actor=self.actor,
        )
        self.on_success.assert_called_once()

    def test_unlock_account_confirm(self):
        """Mở khóa tài khoản khách hàng gọi set_customer_status với ACTIVE."""
        cust = _make_dummy_customer(status=CustomerStatus.INACTIVE)
        dlg = CustomerLockDialog(self.root, self.mock_services, cust, self.actor, on_success=self.on_success, language="vi")
        self.addCleanup(dlg.destroy)

        self.assertEqual(dlg._target_status, CustomerStatus.ACTIVE)

        with patch("cyberhub_manager.ui.dialogs.customer_lock_dialog.ToastManager.show"):
            dlg._handle_confirm()

        self.mock_services.customers.set_customer_status.assert_called_once_with(
            customer_id=143,
            status=CustomerStatus.ACTIVE,
            actor=self.actor,
        )
        self.on_success.assert_called_once()
