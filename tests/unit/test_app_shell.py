"""Unit tests cho NG-02 — App Shell và navigation."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import customtkinter as ctk
import pytest

from cyberhub_manager.domain.enums import Role
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.ui import app_shell as app_shell_module
from cyberhub_manager.ui.app_shell import AppShell, PlaceholderView, initials
from cyberhub_manager.ui.navigation import (
    NAV_ITEMS,
    NavKey,
    can_access,
    visible_nav_items,
)

# ----------------------------------------------------------------------
# 1. Logic thuần — không cần cửa sổ
# ----------------------------------------------------------------------
def test_menu_order_is_fixed() -> None:
    assert [item.key for item in NAV_ITEMS] == [
        NavKey.DASHBOARD,
        NavKey.CUSTOMERS,
        NavKey.MACHINES,
        NavKey.INVOICES,
        NavKey.REPORTS,
    ]


def test_staff_does_not_see_machine_management() -> None:
    keys = [item.key for item in visible_nav_items(Role.STAFF)]
    assert NavKey.MACHINES not in keys
    assert keys == [NavKey.DASHBOARD, NavKey.CUSTOMERS, NavKey.INVOICES, NavKey.REPORTS]


@pytest.mark.parametrize("role", [Role.MANAGER, Role.ADMIN])
def test_manager_and_admin_see_machine_management(role: Role) -> None:
    assert NavKey.MACHINES in [item.key for item in visible_nav_items(role)]


def test_can_access_rejects_unknown_key() -> None:
    assert can_access(Role.ADMIN, "not-a-screen") is False
    assert can_access(Role.STAFF, NavKey.MACHINES) is False
    assert can_access(Role.STAFF, "dashboard") is True


@pytest.mark.parametrize(
    ("full_name", "expected"),
    [("Nguyễn Tuấn Kiệt", "TK"), ("Trần Minh Quân", "MQ"), ("An", "AN"), ("  ", "?")],
)
def test_initials(full_name: str, expected: str) -> None:
    assert initials(full_name) == expected


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_shell_does_not_depend_on_sql_layers() -> None:
    ui_dir = Path(app_shell_module.__file__).parent
    for name in ("app_shell.py", "navigation.py"):
        for module in _imported_modules(ui_dir / name):
            for forbidden in ("repositories", "database", "mysql"):
                assert forbidden not in module, f"{name} import {module}"


# ----------------------------------------------------------------------
# 2. Widget — cần Tk
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def tk_root():
    root = ctk.CTk()
    root.geometry("1280x720")
    yield root
    root.destroy()


def _make_shell(tk_root, username: str, **kwargs):
    services = build_mock_services()
    session = services.auth.login(username, DEMO_PASSWORD)
    logout_calls: list[bool] = []
    shell = AppShell(
        tk_root,
        services,
        session,
        on_logout=lambda: logout_calls.append(True),
        **kwargs,
    )
    return shell, session, logout_calls


def test_shell_opens_dashboard_and_shows_role_menu(tk_root) -> None:
    shell, session, _ = _make_shell(tk_root, "quanly01")
    assert session.role == Role.MANAGER
    assert shell.current_key == NavKey.DASHBOARD
    assert isinstance(shell.current_view, PlaceholderView)
    assert NavKey.MACHINES in shell.nav_keys
    shell.destroy()


def test_staff_cannot_navigate_to_machines_directly(tk_root) -> None:
    shell, session, _ = _make_shell(tk_root, "nhanvien01")
    assert session.role == Role.STAFF
    assert NavKey.MACHINES not in shell.nav_keys
    with patch.object(app_shell_module.ToastManager, "show") as toast:
        assert shell.navigate(NavKey.MACHINES) is False
        toast.assert_called_once()
    assert shell.current_key == NavKey.DASHBOARD
    shell.destroy()


def test_navigate_replaces_view_and_calls_shutdown(tk_root) -> None:
    shutdown_calls: list[str] = []

    class FakeDashboard(ctk.CTkFrame):
        def __init__(self, master, context) -> None:
            super().__init__(master)
            self.context = context

        def shutdown(self) -> None:
            shutdown_calls.append("dashboard")

    shell, session, _ = _make_shell(
        tk_root,
        "quanly01",
        view_factories={NavKey.DASHBOARD: FakeDashboard},
    )
    dashboard = shell.current_view
    assert isinstance(dashboard, FakeDashboard)
    assert dashboard.context.session == session

    assert shell.navigate(NavKey.CUSTOMERS) is True
    assert shutdown_calls == ["dashboard"]
    assert not dashboard.winfo_exists()
    assert shell.current_key == NavKey.CUSTOMERS
    shell.destroy()


def test_broken_view_factory_keeps_current_view(tk_root) -> None:
    def broken(master, context):
        raise RuntimeError("boom")

    shell, _, _ = _make_shell(tk_root, "quanly01", view_factories={NavKey.INVOICES: broken})
    with patch.object(app_shell_module.ToastManager, "show") as toast:
        assert shell.navigate(NavKey.INVOICES) is False
        toast.assert_called_once()
    assert shell.current_key == NavKey.DASHBOARD
    assert shell.current_view is not None
    shell.destroy()


def test_logout_clears_session_and_calls_callback(tk_root) -> None:
    shell, _, logout_calls = _make_shell(tk_root, "quanly01")
    view = shell.current_view
    with patch.object(app_shell_module.ConfirmDialog, "ask", return_value=True):
        shell._on_logout_clicked()
    assert logout_calls == [True]
    assert shell.session is None
    assert shell.current_view is None
    assert not view.winfo_exists()
    assert shell.navigate(NavKey.DASHBOARD) is False


def test_cancel_logout_keeps_shell(tk_root) -> None:
    shell, session, logout_calls = _make_shell(tk_root, "quanly01")
    with patch.object(app_shell_module.ConfirmDialog, "ask", return_value=False):
        shell._on_logout_clicked()
    assert logout_calls == []
    assert shell.session == session
    shell.destroy()


def test_language_switch_rebuilds_current_view(tk_root) -> None:
    shell, _, _ = _make_shell(tk_root, "quanly01")
    old_view = shell.current_view
    shell.set_language("en")
    assert shell.language == "en"
    assert shell.current_key == NavKey.DASHBOARD
    assert shell.current_view is not old_view
    shell.destroy()


def test_search_enabled_only_for_views_with_handle_search(tk_root) -> None:
    received: list[str] = []

    class SearchableView(ctk.CTkFrame):
        def __init__(self, master, context) -> None:
            super().__init__(master)

        def handle_search(self, text: str) -> None:
            received.append(text)

    shell, _, _ = _make_shell(
        tk_root, "quanly01", view_factories={NavKey.CUSTOMERS: SearchableView}
    )
    assert shell.search_enabled is False  # Dashboard placeholder không hỗ trợ tìm kiếm

    shell.navigate(NavKey.CUSTOMERS)
    assert shell.search_enabled is True
    shell._search_entry.insert(0, "  KH001 ")
    shell._on_search_submitted()
    assert received == ["KH001"]

    shell.navigate(NavKey.DASHBOARD)
    assert shell.search_enabled is False
    shell.destroy()
