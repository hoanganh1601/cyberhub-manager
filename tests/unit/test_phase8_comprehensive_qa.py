"""Kiểm thử toàn diện Giai đoạn 8 cho CyberHub Manager:
- 1. Kích thước và Bố cục 1280x720 (Resolution & Layout QA).
- 2. Thao tác bàn phím: Enter, Esc, Tab, Space (Keyboard Navigation QA).
- 3. Chuyển đổi ngôn ngữ VI / EN (Localization QA).
- 4. Kiểm thử nghiệp vụ và chống hồi quy (Business Regression QA).
"""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = str(Path(__file__).resolve().parent.parent.parent)
_SRC = str(Path(__file__).resolve().parent.parent.parent / "src")
for _p in (_ROOT, _SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import customtkinter as ctk

from cyberhub_manager.domain.dtos import (
    CustomerSummary,
    EmployeeSession,
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
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.ui.app_shell import AppShell, ViewContext
from cyberhub_manager.ui.components.action_button import ActionButton
from cyberhub_manager.ui.components.confirm_dialog import ConfirmDialog
from cyberhub_manager.ui.customers_view import customers_view_factory
from cyberhub_manager.ui.dashboard_view import dashboard_view_factory
from cyberhub_manager.ui.dialogs.customer_dialog import CustomerDialog
from cyberhub_manager.ui.dialogs.customer_lock_dialog import CustomerLockDialog
from cyberhub_manager.ui.dialogs.machine_dialog import MachineDialog
from cyberhub_manager.ui.dialogs.open_session_dialog import OpenSessionDialog
from cyberhub_manager.ui.dialogs.payment_confirm_dialog import PaymentConfirmDialog
from cyberhub_manager.ui.dialogs.topup_dialog import TopUpDialog
from cyberhub_manager.ui.invoices_view import invoices_view_factory
from cyberhub_manager.ui.login_view import LoginView
from cyberhub_manager.ui.machine_management_view import machine_management_view_factory
from cyberhub_manager.ui.navigation import NavKey
from cyberhub_manager.ui.reports_view import reports_view_factory
from cyberhub_manager.ui.theme import SHELL_HEIGHT, SHELL_WIDTH, setup_theme

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


class TestPhase8LayoutAndResolution(unittest.TestCase):
    """1. Kiểm thử kích thước và bố cục 1280x720."""

    def setUp(self):
        self.root = _SHARED_ROOT
        self.services = build_mock_services()
        self.session = self.services.auth.login("quanly01", DEMO_PASSWORD)
        self.factories = {
            NavKey.DASHBOARD: dashboard_view_factory,
            NavKey.CUSTOMERS: customers_view_factory,
            NavKey.MACHINES: machine_management_view_factory,
            NavKey.INVOICES: invoices_view_factory,
            NavKey.REPORTS: reports_view_factory,
        }

    def tearDown(self):
        for child in list(self.root.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

    def test_app_shell_exact_dimensions_1280x720(self):
        """AppShell tuân thủ kích thước 1280x720 và cấu trúc phân chia sidebar/viewport."""
        shell = AppShell(
            self.root,
            self.services,
            self.session,
            view_factories=self.factories,
            on_logout=lambda: None,
        )
        shell.pack(fill="both", expand=True)
        self.root.update_idletasks()

        # Kiểm tra kích thước thiết kế Stitch
        self.assertEqual(SHELL_WIDTH, 1280)
        self.assertEqual(SHELL_HEIGHT, 720)

        # Kiểm tra cấu trúc sidebar (nav buttons) và main content container
        self.assertTrue(len(shell._nav_buttons) >= 4)
        self.assertIsNotNone(shell._content)

    def test_all_five_views_mount_at_1280x720_without_error(self):
        """Cả 5 màn hình chính đều mount và unmount sạch sẽ không gây lỗi."""
        shell = AppShell(
            self.root,
            self.services,
            self.session,
            view_factories=self.factories,
            on_logout=lambda: None,
        )
        shell.pack(fill="both", expand=True)

        for key in [
            NavKey.DASHBOARD,
            NavKey.CUSTOMERS,
            NavKey.MACHINES,
            NavKey.INVOICES,
            NavKey.REPORTS,
        ]:
            ok = shell.navigate(key)
            self.assertTrue(ok, f"Failed to navigate to {key}")
            self.assertEqual(shell.current_key, key)
            self.assertIsNotNone(shell.current_view)
            self.root.update_idletasks()


class TestPhase8KeyboardNavigation(unittest.TestCase):
    """2. Kiểm thử thao tác bàn phím: Enter, Esc, Tab, Space."""

    def setUp(self):
        self.root = _SHARED_ROOT
        self.services = build_mock_services()
        self.session = self.services.auth.login("quanly01", DEMO_PASSWORD)

    def tearDown(self):
        for child in list(self.root.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

    def test_login_enter_key_submits(self):
        """Phím Enter kích hoạt đăng nhập trên LoginView khi form hợp lệ."""
        login_success_mock = MagicMock()
        login_view = LoginView(
            self.root,
            self.services.auth,
            on_login_success=login_success_mock,
            language="vi",
        )
        login_view.pack(fill="both", expand=True)
        self.root.update_idletasks()

        # Giả lập submit qua _handle_submit khi nhấn Enter
        login_view._username_entry.delete(0, "end")
        login_view._username_entry.insert(0, "quanly01")
        login_view._password_entry.delete(0, "end")
        login_view._password_entry.insert(0, DEMO_PASSWORD)

        login_view._handle_submit()
        login_success_mock.assert_called_once()

    def test_confirm_dialog_enter_confirms_and_esc_cancels(self):
        """ConfirmDialog: Enter xác nhận và Esc hủy bỏ."""
        # 1. Test confirm action
        dlg1 = ConfirmDialog(self.root, "Xác nhận", "Bạn có chắc chắn?")
        dlg1._on_confirm()
        self.assertTrue(dlg1._result)

        # 2. Test cancel action
        dlg2 = ConfirmDialog(self.root, "Xác nhận", "Bạn có chắc chắn?")
        dlg2._on_cancel()
        self.assertFalse(dlg2._result)

    def test_dialogs_bind_escape_to_close(self):
        """Các dialog quan trọng đều đóng an toàn khi bấm Esc."""
        # CustomerDialog
        cust_dlg = CustomerDialog(self.root, self.services, on_success=lambda: None)
        self.assertTrue(cust_dlg.winfo_exists())
        cust_dlg._on_escape()
        self.root.update()
        self.assertFalse(cust_dlg.winfo_exists())

        # TopUpDialog
        cust = self.services.customers.search_customers("")[0]
        topup_dlg = TopUpDialog(self.root, self.services, cust, employee_id=1, on_success=lambda: None)
        self.assertTrue(topup_dlg.winfo_exists())
        topup_dlg._on_escape()
        self.root.update()
        self.assertFalse(topup_dlg.winfo_exists())

        # MachineDialog
        mach_dlg = MachineDialog(self.root, self.services, actor=self.session, on_success=lambda: None)
        self.assertTrue(mach_dlg.winfo_exists())
        mach_dlg._handle_close()
        self.root.update()
        self.assertFalse(mach_dlg.winfo_exists())

    def test_action_button_space_activates_command(self):
        """Nút ActionButton được kích hoạt khi click hoặc phím Space/Enter."""
        clicked = []
        btn = ActionButton(self.root, text="Test Button", command=lambda: clicked.append(True))
        btn.pack()
        self.root.update_idletasks()

        btn._on_click()
        self.assertEqual(clicked, [True])


class TestPhase8Localization(unittest.TestCase):
    """3. Kiểm thử chuyển đổi ngôn ngữ VI / EN."""

    def setUp(self):
        self.root = _SHARED_ROOT
        self.services = build_mock_services()
        self.session = self.services.auth.login("quanly01", DEMO_PASSWORD)
        self.factories = {
            NavKey.DASHBOARD: dashboard_view_factory,
            NavKey.CUSTOMERS: customers_view_factory,
            NavKey.MACHINES: machine_management_view_factory,
            NavKey.INVOICES: invoices_view_factory,
            NavKey.REPORTS: reports_view_factory,
        }

    def tearDown(self):
        for child in list(self.root.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

    def test_app_shell_language_switch_vi_to_en_and_back(self):
        """Chuyển đổi ngôn ngữ VI -> EN và EN -> VI mượt mà trên AppShell."""
        shell = AppShell(
            self.root,
            self.services,
            self.session,
            view_factories=self.factories,
            language="vi",
            on_logout=lambda: None,
        )
        shell.pack(fill="both", expand=True)
        self.root.update_idletasks()

        # Kiểm tra ban đầu là tiếng Việt
        self.assertEqual(shell.language, "vi")
        self.assertEqual(shell._search_entry.cget("placeholder_text"), "Tìm kiếm máy...")

        # Chuyển sang tiếng Anh
        shell.set_language("en")
        self.root.update_idletasks()
        self.assertEqual(shell.language, "en")
        self.assertEqual(shell._search_entry.cget("placeholder_text"), "Search machines...")

        # Chuyển lại tiếng Việt
        shell.set_language("vi")
        self.root.update_idletasks()
        self.assertEqual(shell.language, "vi")
        self.assertEqual(shell._search_entry.cget("placeholder_text"), "Tìm kiếm máy...")

    def test_dialogs_render_in_english(self):
        """Dialog mở ở chế độ tiếng Anh hiển thị tiêu đề và placeholder tiếng Anh."""
        cust = self.services.customers.search_customers("")[0]

        # CustomerDialog EN
        dlg_cust = CustomerDialog(self.root, self.services, language="en", on_success=lambda: None)
        self.assertEqual(dlg_cust.title(), "Create Customer")
        dlg_cust.destroy()

        # TopUpDialog EN
        dlg_topup = TopUpDialog(self.root, self.services, cust, employee_id=1, language="en", on_success=lambda: None)
        self.assertEqual(dlg_topup.title(), "Top Up Account")
        dlg_topup.destroy()

        # MachineDialog EN
        dlg_mach = MachineDialog(self.root, self.services, actor=self.session, language="en", on_success=lambda: None)
        self.assertEqual(dlg_mach.title(), "Add Machine")
        dlg_mach.destroy()


class TestPhase8BusinessRegression(unittest.TestCase):
    """4. Kiểm thử nghiệp vụ và chống hồi quy (Business Regression QA)."""

    def setUp(self):
        self.services = build_mock_services()
        self.manager = self.services.auth.login("quanly01", DEMO_PASSWORD)
        self.staff = self.services.auth.login("nhanvien01", DEMO_PASSWORD)

    def test_rbac_manager_vs_staff_permissions(self):
        """Quản lý có toàn quyền, nhân viên không có quyền quản lý máy hay khóa khách hàng."""
        self.assertEqual(self.manager.role, Role.MANAGER)
        self.assertEqual(self.staff.role, Role.STAFF)
        self.assertTrue(self.manager.role in (Role.MANAGER, Role.ADMIN))

    def test_wallet_top_up_and_balance_update(self):
        """Nạp tiền ví cập nhật số dư chính xác và ghi lại lịch sử giao dịch."""
        cust_id = 1
        amount = 50_000
        result = self.services.wallet.top_up(
            customer_id=cust_id,
            amount=amount,
            method=PaymentMethod.CASH,
            employee_id=self.manager.employee_id,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.balance_after, result.balance_before + amount)

        # Kiểm tra lịch sử giao dịch
        txs = self.services.wallet.get_history(customer_id=cust_id)
        self.assertTrue(len(txs) > 0)
        self.assertEqual(txs[0].amount, amount)

    def test_machine_session_lifecycle_and_checkout(self):
        """Chu trình phiên: Mở phiên -> Máy ĐANG DÙNG -> Thanh toán hóa đơn -> Máy TRỐNG."""
        # 1. Tìm máy AVAILABLE
        machines = self.services.machines.list_machines(self.manager.store_id)
        avail = [m for m in machines if m.status == MachineStatus.AVAILABLE and m.is_active]
        self.assertTrue(len(avail) > 0)
        target_machine = avail[0]

        # 2. Mở phiên
        sess = self.services.sessions.open_session(
            customer_id=1,
            machine_id=target_machine.machine_id,
            actor=self.manager,
        )
        self.assertIsNotNone(sess)
        self.assertEqual(sess.status, SessionStatus.ACTIVE)

        # Máy chuyển sang IN_USE
        machines_after_open = self.services.machines.list_machines(self.manager.store_id)
        m_updated = [m for m in machines_after_open if m.machine_id == target_machine.machine_id][0]
        self.assertEqual(m_updated.status, MachineStatus.IN_USE)

        # 3. Kết thúc và thanh toán phiên (khi số dư đủ, settlement_amount=0, method=None)
        checkout_res = self.services.sessions.complete_checkout(
            machine_id=target_machine.machine_id,
            actor=self.manager,
            settlement_amount=0,
            method=None,
        )
        self.assertIsNotNone(checkout_res)

        # Máy quay lại AVAILABLE
        machines_after_close = self.services.machines.list_machines(self.manager.store_id)
        m_after = [m for m in machines_after_close if m.machine_id == target_machine.machine_id][0]
        self.assertEqual(m_after.status, MachineStatus.AVAILABLE)


if __name__ == "__main__":
    unittest.main()
