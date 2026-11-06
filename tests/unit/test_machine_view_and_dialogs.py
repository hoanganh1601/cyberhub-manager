"""Unit tests for Phase 5 Machine Management & Open Session:
- MachineManagementView
- MachineDialog (Create & Edit modes)
- OpenSessionDialog (Eligible, Insufficient balance, Locked account)
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
    CustomerSummary,
    EmployeeSession,
    MachineSummary,
    SessionSummary,
)
from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    MachineStatus,
    Role,
    SessionStatus,
)
from cyberhub_manager.domain.exceptions import ConflictError, ValidationError
from cyberhub_manager.ui.app_shell import ViewContext
from cyberhub_manager.ui.dialogs.machine_dialog import MachineDialog
from cyberhub_manager.ui.dialogs.open_session_dialog import OpenSessionDialog
from cyberhub_manager.ui.machine_management_view import MachineManagementView
from cyberhub_manager.ui.theme import setup_theme


def _make_actor() -> EmployeeSession:
    return EmployeeSession(
        employee_id=1,
        employee_code="NV001",
        full_name="Quản Lý 01",
        username="quanly01",
        store_id=1,
        store_code="ST01",
        store_name="CyberHub Hà Nội",
        role=Role.MANAGER,
    )


def _make_machine(
    mid: int = 1,
    code: str = "PC-01",
    name: str = "Máy VIP 01",
    status: MachineStatus = MachineStatus.AVAILABLE,
    rate: int = 12_000,
    is_active: bool = True,
) -> MachineSummary:
    return MachineSummary(
        machine_id=mid,
        machine_code=code,
        store_id=1,
        name=name,
        status=status,
        hourly_rate=rate,
        is_active=is_active,
        updated_at=datetime.now(timezone.utc),
        active_session=None,
    )


def _make_customer(
    cid: int = 1,
    code: str = "CUS-0001",
    name: str = "Nguyễn Văn An",
    phone: str = "0912345678",
    balance: int = 50_000,
    c_status: CustomerStatus = CustomerStatus.ACTIVE,
    a_status: AccountStatus = AccountStatus.ACTIVE,
) -> CustomerSummary:
    return CustomerSummary(
        customer_id=cid,
        customer_code=code,
        full_name=name,
        phone=phone,
        account_id=cid,
        username="an.nv",
        balance=balance,
        customer_status=c_status,
        account_status=a_status,
    )


_SHARED_ROOT: ctk.CTk | None = None


def setUpModule():
    global _SHARED_ROOT
    setup_theme()
    _SHARED_ROOT = getattr(ctk, "_SHARED_TEST_ROOT", None)
    if _SHARED_ROOT is None:
        _SHARED_ROOT = ctk.CTk()
        _SHARED_ROOT.withdraw()
        ctk._SHARED_TEST_ROOT = _SHARED_ROOT


def tearDownModule():
    global _SHARED_ROOT
    if _SHARED_ROOT is not None:
        for child in list(_SHARED_ROOT.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass


class TestMachineDialog(unittest.TestCase):
    def setUp(self):
        self.root = _SHARED_ROOT
        self.services = MagicMock()
        self.actor = _make_actor()
        self.on_success = MagicMock()

    def test_create_mode_validation_errors(self):
        dlg = MachineDialog(
            self.root,
            self.services,
            actor=self.actor,
            on_success=self.on_success,
        )
        self.addCleanup(dlg.destroy)

        # Trống mã máy
        dlg._code_entry.delete(0, "end")
        dlg._name_entry.delete(0, "end")
        dlg._handle_save()
        self.assertIn("không được để trống", dlg._code_hint.cget("text"))
        self.services.machines.create_machine.assert_not_called()

        # Mã máy hợp lệ, nhưng trống tên máy
        dlg._code_entry.insert(0, "PC-99")
        dlg._handle_save()
        self.assertIn("không được để trống", dlg._name_hint.cget("text"))
        self.services.machines.create_machine.assert_not_called()

        # Giá theo giờ không hợp lệ
        dlg._name_entry.insert(0, "Máy VIP 99")
        dlg._rate_entry.delete(0, "end")
        dlg._rate_entry.insert(0, "-500")
        dlg._handle_save()
        self.assertIn("số nguyên dương", dlg._rate_hint.cget("text"))
        self.services.machines.create_machine.assert_not_called()

    def test_create_mode_success(self):
        dlg = MachineDialog(
            self.root,
            self.services,
            actor=self.actor,
            on_success=self.on_success,
        )
        self.addCleanup(dlg.destroy)

        dlg._code_entry.delete(0, "end")
        dlg._code_entry.insert(0, "PC-21")
        dlg._name_entry.delete(0, "end")
        dlg._name_entry.insert(0, "Máy Standard 21")
        dlg._rate_entry.delete(0, "end")
        dlg._rate_entry.insert(0, "15000")

        dlg._handle_save()
        self.services.machines.create_machine.assert_called_once_with(
            code="PC-21",
            store_id=self.actor.store_id,
            name="Máy Standard 21",
            hourly_rate=15000,
            actor=self.actor,
        )
        self.on_success.assert_called_once()

    def test_edit_mode_success(self):
        mach = _make_machine(mid=2, code="PC-02", name="Máy VIP 02", rate=12000)
        dlg = MachineDialog(
            self.root,
            self.services,
            actor=self.actor,
            machine=mach,
            on_success=self.on_success,
        )
        self.addCleanup(dlg.destroy)

        self.assertEqual(dlg._code_entry.cget("state"), "disabled")
        dlg._name_entry.delete(0, "end")
        dlg._name_entry.insert(0, "Máy VIP 02 Pro")
        dlg._rate_entry.delete(0, "end")
        dlg._rate_entry.insert(0, "18000")

        dlg._handle_save()
        self.services.machines.update_machine.assert_called_once_with(
            machine_id=2,
            name="Máy VIP 02 Pro",
            hourly_rate=18000,
            actor=self.actor,
        )
        self.on_success.assert_called_once()


class TestOpenSessionDialog(unittest.TestCase):
    def setUp(self):
        self.root = _SHARED_ROOT
        self.services = MagicMock()
        self.actor = _make_actor()
        self.machine = _make_machine(mid=1, code="PC-01", rate=12000)
        self.on_success = MagicMock()

    def test_init_without_customer(self):
        dlg = OpenSessionDialog(
            self.root,
            self.services,
            self.machine,
            actor=self.actor,
            on_success=self.on_success,
        )
        self.addCleanup(dlg.destroy)

        self.assertFalse(dlg._can_open_session())
        self.assertFalse(dlg._btn_confirm._is_enabled)
        self.assertIn("tìm và chọn khách hàng", dlg._banner_label.cget("text"))

    def test_customer_eligible(self):
        cus = _make_customer(balance=50_000)
        dlg = OpenSessionDialog(
            self.root,
            self.services,
            self.machine,
            actor=self.actor,
            initial_customer=cus,
            on_success=self.on_success,
        )
        self.addCleanup(dlg.destroy)

        self.assertTrue(dlg._can_open_session())
        self.assertTrue(dlg._btn_confirm._is_enabled)
        self.assertIn("đủ điều kiện", dlg._banner_label.cget("text"))
        self.assertIn("giờ", dlg._metric_est_time.cget("text"))

        # Xác nhận mở phiên
        expected_session = SessionSummary(
            session_id=10,
            session_code="SES-0010",
            customer_id=cus.customer_id,
            customer_code=cus.customer_code,
            customer_name=cus.full_name,
            machine_id=self.machine.machine_id,
            machine_code=self.machine.machine_code,
            machine_name=self.machine.name,
            started_at=datetime.now(timezone.utc),
            hourly_rate=self.machine.hourly_rate,
            status=SessionStatus.ACTIVE,
        )
        self.services.sessions.open_session.return_value = expected_session

        dlg._handle_confirm()
        self.services.sessions.open_session.assert_called_once_with(
            customer_id=cus.customer_id,
            machine_id=self.machine.machine_id,
            actor=self.actor,
        )
        self.on_success.assert_called_once()

    def test_customer_insufficient_balance(self):
        # Đơn giá 12.000đ/h -> số dư tối thiểu là 6.000đ. Khách chỉ có 4.000đ
        cus = _make_customer(balance=4_000)
        dlg = OpenSessionDialog(
            self.root,
            self.services,
            self.machine,
            actor=self.actor,
            initial_customer=cus,
            on_success=self.on_success,
        )
        self.addCleanup(dlg.destroy)

        self.assertFalse(dlg._can_open_session())
        self.assertFalse(dlg._btn_confirm._is_enabled)
        self.assertIn("chưa đạt mức tối thiểu", dlg._banner_label.cget("text"))
        # Nút topup phải được quản lý đóng gói bằng pack
        self.assertEqual(dlg._btn_topup.winfo_manager(), "pack")

    def test_customer_locked(self):
        cus = _make_customer(balance=100_000, a_status=AccountStatus.LOCKED)
        dlg = OpenSessionDialog(
            self.root,
            self.services,
            self.machine,
            actor=self.actor,
            initial_customer=cus,
            on_success=self.on_success,
        )
        self.addCleanup(dlg.destroy)

        self.assertFalse(dlg._can_open_session())
        self.assertFalse(dlg._btn_confirm._is_enabled)
        self.assertIn("bị khóa", dlg._banner_label.cget("text"))


class TestMachineManagementView(unittest.TestCase):
    def setUp(self):
        self.root = _SHARED_ROOT
        self.services = MagicMock()
        self.actor = _make_actor()

        self.machines = [
            _make_machine(mid=1, code="PC-01", name="Máy 01", status=MachineStatus.AVAILABLE),
            _make_machine(mid=2, code="PC-02", name="Máy 02", status=MachineStatus.IN_USE),
            _make_machine(mid=3, code="PC-03", name="Máy 03", status=MachineStatus.MAINTENANCE),
            _make_machine(mid=4, code="PC-04", name="Máy 04", status=MachineStatus.AVAILABLE),
            _make_machine(mid=20, code="PC-20", name="Máy Cũ 20", status=MachineStatus.AVAILABLE, is_active=False),
        ]
        self.services.machines.list_machines.return_value = self.machines

        context = ViewContext(
            services=self.services,
            session=self.actor,
            language="vi",
            navigate=MagicMock(),
        )
        self.view = MachineManagementView(self.root, context)
        self.addCleanup(self.view.destroy)

    def test_kpi_counts(self):
        self.assertEqual(self.view._kpi_total._value_label.cget("text"), "5")
        self.assertEqual(self.view._kpi_available._value_label.cget("text"), "2")
        self.assertEqual(self.view._kpi_in_use._value_label.cget("text"), "1")
        self.assertEqual(self.view._kpi_maintenance._value_label.cget("text"), "1")
        self.assertEqual(self.view._kpi_archived._value_label.cget("text"), "1")

    def test_filter_tabs(self):
        self.view._set_filter("available")
        self.assertEqual(len(self.view._filtered_machines), 2)
        for m in self.view._filtered_machines:
            self.assertEqual(m.status, MachineStatus.AVAILABLE)

        self.view._set_filter("in_use")
        self.assertEqual(len(self.view._filtered_machines), 1)
        self.assertEqual(self.view._filtered_machines[0].machine_code, "PC-02")

        self.view._set_filter("archived")
        self.assertEqual(len(self.view._filtered_machines), 1)
        self.assertFalse(self.view._filtered_machines[0].is_active)

    def test_search_filter(self):
        self.view.handle_search("PC-03")
        self.assertEqual(len(self.view._filtered_machines), 1)
        self.assertEqual(self.view._filtered_machines[0].machine_code, "PC-03")

    def test_actions_enablement_by_status(self):
        # PC-01: Available -> Có thể mở phiên, sửa, bảo trì, lưu trữ
        self.view._select_machine(self.machines[0])
        self.assertTrue(self.view._btn_open_session._is_enabled)
        self.assertTrue(self.view._btn_edit._is_enabled)
        self.assertTrue(self.view._btn_maint._is_enabled)
        self.assertTrue(self.view._btn_archive._is_enabled)

        # PC-02: In Use -> Không thể mở phiên, không thể bảo trì, không thể lưu trữ
        self.view._select_machine(self.machines[1])
        self.assertFalse(self.view._btn_open_session._is_enabled)
        self.assertTrue(self.view._btn_edit._is_enabled)
        self.assertFalse(self.view._btn_maint._is_enabled)
        self.assertFalse(self.view._btn_archive._is_enabled)

        # PC-03: Maintenance -> Không thể mở phiên, có thể bật lại máy, không thể lưu trữ
        self.view._select_machine(self.machines[2])
        self.assertFalse(self.view._btn_open_session._is_enabled)
        self.assertTrue(self.view._btn_edit._is_enabled)
        self.assertTrue(self.view._btn_maint._is_enabled)
        self.assertFalse(self.view._btn_archive._is_enabled)

        # PC-20: Archived -> Vô hiệu hóa tất cả
        self.view._select_machine(self.machines[4])
        self.assertFalse(self.view._btn_open_session._is_enabled)
        self.assertFalse(self.view._btn_edit._is_enabled)
        self.assertFalse(self.view._btn_maint._is_enabled)
        self.assertFalse(self.view._btn_archive._is_enabled)
