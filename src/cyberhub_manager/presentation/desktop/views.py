"""Đăng ký view thật cho App Shell. Màn nào chưa có ở đây sẽ hiện PlaceholderView.

Composition root (app.py — HA-11) gọi:
    AppShell(root, services, session, on_logout=..., view_factories=default_view_factories())
"""

from __future__ import annotations

from cyberhub_manager.presentation.desktop.app_shell import ViewFactory
from cyberhub_manager.presentation.desktop.customers_view import CustomersView
from cyberhub_manager.presentation.desktop.dashboard_view import DashboardView
from cyberhub_manager.presentation.desktop.invoices_view import InvoicesView
from cyberhub_manager.presentation.desktop.machine_management_view import MachineManagementView
from cyberhub_manager.presentation.desktop.navigation import NavKey
from cyberhub_manager.presentation.desktop.reports_view import ReportsView
from functools import partial
from cyberhub_manager.presentation.desktop.p1_views import ManagementView


def default_view_factories() -> dict[NavKey, ViewFactory]:
    return {
        NavKey.DASHBOARD: DashboardView,
        NavKey.CUSTOMERS: CustomersView,
        NavKey.MACHINES: MachineManagementView,
        NavKey.INVOICES: InvoicesView,
        NavKey.REPORTS: ReportsView,
        NavKey.EMPLOYEES: partial(ManagementView, kind="employees"),
        NavKey.PROMOTIONS: partial(ManagementView, kind="promotions"),
        NavKey.STORES: partial(ManagementView, kind="stores"),
    }
