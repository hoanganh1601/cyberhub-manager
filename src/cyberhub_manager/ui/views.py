"""Đăng ký view thật cho App Shell. Màn nào chưa có ở đây sẽ hiện PlaceholderView.

Composition root (app.py — HA-11) gọi:
    AppShell(root, services, session, on_logout=..., view_factories=default_view_factories())
"""

from __future__ import annotations

from .app_shell import ViewFactory
from .customers_view import customers_view_factory
from .dashboard_view import dashboard_view_factory
from .invoices_view import invoices_view_factory
from .machine_management_view import machine_management_view_factory
from .navigation import NavKey
from .reports_view import reports_view_factory


def default_view_factories() -> dict[NavKey, ViewFactory]:
    return {
        NavKey.DASHBOARD: dashboard_view_factory,
        NavKey.CUSTOMERS: customers_view_factory,
        NavKey.MACHINES: machine_management_view_factory,
        NavKey.INVOICES: invoices_view_factory,
        NavKey.REPORTS: reports_view_factory,
    }


DEFAULT_VIEW_FACTORIES = default_view_factories()

