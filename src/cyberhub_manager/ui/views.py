"""Đăng ký view thật cho App Shell. Màn nào chưa có ở đây sẽ hiện PlaceholderView.

Composition root (app.py — HA-11) gọi:
    AppShell(root, services, session, on_logout=..., view_factories=default_view_factories())
"""

from __future__ import annotations

from .app_shell import ViewFactory
from .customers_view import CustomersView
from .dashboard_view import DashboardView
from .machine_management_view import MachineManagementView
from .navigation import NavKey


def default_view_factories() -> dict[NavKey, ViewFactory]:
    return {
        NavKey.DASHBOARD: DashboardView,
        NavKey.CUSTOMERS: CustomersView,
        NavKey.MACHINES: MachineManagementView,
    }
