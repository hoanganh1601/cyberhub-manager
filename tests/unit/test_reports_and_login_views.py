"""Unit tests for Phase 7:
- ReportsView (5 Financial cards, Table with ratio bar and inline tags, 4-box Summary panel, Date filters & presets, Empty state)
- LoginView (2-column layout, Canvas circuits, Username/Password icon inputs, Eye toggle, Auth failure banner, Submit flow)
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

_SRC = str(Path(__file__).resolve().parent.parent.parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import customtkinter as ctk

from cyberhub_manager.domain.dtos import DailyRevenue, EmployeeSession
from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.exceptions import AuthenticationError
from cyberhub_manager.ui.app_shell import ViewContext
from cyberhub_manager.ui.login_view import LoginView
from cyberhub_manager.ui.reports_view import ReportsView
from cyberhub_manager.ui.state import ViewState
from cyberhub_manager.ui.theme import setup_theme


def _make_actor() -> EmployeeSession:
    return EmployeeSession(
        employee_id=1,
        employee_code="NV001",
        full_name="Nguyễn Tuấn Kiệt",
        username="quanly01",
        store_id=1,
        store_code="ST01",
        store_name="CyberHub Hà Nội",
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


class TestReportsView(unittest.TestCase):
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

    def test_reports_view_render_and_5_cards(self):
        # Given: daily data for 2 days
        d1 = DailyRevenue(date=date(2026, 2, 24), invoice_count=42, revenue=1_250_000)
        d2 = DailyRevenue(date=date(2026, 2, 23), invoice_count=38, revenue=1_080_000)
        self.services.reports.daily_revenue.return_value = [d1, d2]

        view = ReportsView(self.root, self.context)
        view.update_idletasks()

        # 5 Financial Cards check
        # Card 1: Total Revenue = 2,330,000 VND
        self.assertEqual(view._card1_val.cget("text"), "2.330.000 VND")
        self.assertIn("80 HĐ", view._card1_sub.cget("text"))

        # Card 2: Count = 80 đơn
        self.assertEqual(view._card2_val.cget("text"), "80 đơn")

        # Card 3: Avg per invoice = 2,330,000 / 80 = 29,125 VND
        self.assertEqual(view._card3_val.cget("text"), "29.125 VND")

        # Card 4: Peak Date = 24/02/2026
        self.assertEqual(view._card4_val.cget("text"), "24/02/2026")

        # Card 5: Max Revenue = 1,250,000 VND
        self.assertEqual(view._card5_val.cget("text"), "1.250.000 VND")
        self.assertIn("53.6%", view._card5_sub.cget("text"))

        # Table rows check
        self.assertEqual(len(view._table._rows), 2)
        row1 = view._table._rows[0]
        self.assertIn("ratio", row1.ratio_bars)
        pct, label = row1.ratio_bars["ratio"]
        self.assertAlmostEqual(pct, 53.6, delta=0.5)

        # 4-box Summary Panel
        self.assertEqual(view._lbl_days.cget("text"), "2 ngày")
        self.assertEqual(view._lbl_tot_invoices.cget("text"), "80 hóa đơn")
        self.assertEqual(view._lbl_tot_revenue.cget("text"), "2.330.000 VND")
        self.assertEqual(view._lbl_avg_day.cget("text"), "1.165.000 VND")
        self.assertEqual(view._lbl_avg_inv.cget("text"), "29.125 VND")

    def test_reports_view_empty_state(self):
        self.services.reports.daily_revenue.return_value = []
        view = ReportsView(self.root, self.context)
        view.update_idletasks()

        self.assertEqual(view._card1_val.cget("text"), "0 VND")
        self.assertEqual(len(view._table._rows), 0)
        self.assertEqual(view._table._state, ViewState.EMPTY)

    def test_date_filters_and_presets(self):
        self.services.reports.daily_revenue.return_value = []
        view = ReportsView(self.root, self.context)
        view.update_idletasks()

        # Change entries and apply
        view._entry_from.delete(0, "end")
        view._entry_from.insert(0, "2026-02-01")
        view._entry_to.delete(0, "end")
        view._entry_to.insert(0, "2026-02-15")
        view._apply_date_filter()

        self.assertEqual(view._date_from, date(2026, 2, 1))
        self.assertEqual(view._date_to, date(2026, 2, 15))


class TestLoginView(unittest.TestCase):
    def setUp(self):
        self.root = _SHARED_ROOT
        self.auth_service = MagicMock()
        self.on_success = MagicMock()

    def test_login_view_render_and_components(self):
        view = LoginView(
            self.root,
            self.auth_service,
            on_login_success=self.on_success,
            language="vi",
        )
        view.update_idletasks()

        # Check circuit canvas exists
        self.assertTrue(view._circuit_canvas.winfo_exists())

        # Check fields exist and have initial values
        self.assertEqual(view._username_entry.get(), "quanly01")
        self.assertEqual(view._password_entry.get(), "demo123")
        self.assertEqual(view._password_entry.cget("show"), "*")

    def test_password_toggle_visibility(self):
        view = LoginView(
            self.root,
            self.auth_service,
            on_login_success=self.on_success,
            language="vi",
        )
        view.update_idletasks()

        # Initially hidden
        self.assertFalse(view._password_visible)
        self.assertEqual(view._password_entry.cget("show"), "*")

        # Toggle to show
        view._toggle_password_visibility()
        self.assertTrue(view._password_visible)
        self.assertEqual(view._password_entry.cget("show"), "")

        # Toggle back to hide
        view._toggle_password_visibility()
        self.assertFalse(view._password_visible)
        self.assertEqual(view._password_entry.cget("show"), "*")

    def test_validation_empty_fields(self):
        view = LoginView(
            self.root,
            self.auth_service,
            on_login_success=self.on_success,
            language="vi",
        )
        view.update_idletasks()

        # Empty username
        view._username_entry.delete(0, "end")
        view._handle_submit()
        self.assertIn("Vui lòng nhập tên đăng nhập", view._err_username.cget("text"))
        self.auth_service.login.assert_not_called()

        # Fill username, empty password
        view._username_entry.insert(0, "quanly01")
        view._password_entry.delete(0, "end")
        view._handle_submit()
        self.assertIn("Vui lòng nhập mật khẩu", view._err_password.cget("text"))
        self.auth_service.login.assert_not_called()

    def test_successful_login(self):
        session = _make_actor()
        self.auth_service.login.return_value = session

        view = LoginView(
            self.root,
            self.auth_service,
            on_login_success=self.on_success,
            language="vi",
        )
        view.update_idletasks()

        view._handle_submit()
        self.auth_service.login.assert_called_once_with("quanly01", "demo123")
        self.on_success.assert_called_once_with(session)

    def test_failed_login_shows_alert(self):
        self.auth_service.login.side_effect = AuthenticationError("Sai mật khẩu")

        view = LoginView(
            self.root,
            self.auth_service,
            on_login_success=self.on_success,
            language="vi",
        )
        view.update_idletasks()

        view._handle_submit()
        self.auth_service.login.assert_called_once_with("quanly01", "demo123")
        self.on_success.assert_not_called()

        # Auth alert banner should be packed
        self.assertEqual(view._auth_alert.winfo_manager(), "pack")
        self.assertIn("Tên đăng nhập hoặc mật khẩu không đúng", view._lbl_auth_alert.cget("text"))


if __name__ == "__main__":
    unittest.main()
