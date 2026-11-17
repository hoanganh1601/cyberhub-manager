"""NG-02 — Danh mục menu và quy tắc phân quyền điều hướng.

Module này là logic thuần: không import Tk/CustomTkinter, không import service hay SQL,
nên có thể test bằng pytest mà không cần cửa sổ.
Thứ tự menu theo Stitch export (code.html); phân quyền theo docs/diagrams/ui_wireflow.md mục 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..domain.enums import Role
from ..domain.p1 import Permission, can


class NavKey(StrEnum):
    """Khóa định danh ổn định của từng màn hình trong App Shell."""

    DASHBOARD = "dashboard"
    CUSTOMERS = "customers"
    INVOICES = "invoices"
    REPORTS = "reports"
    MACHINES = "machines"
    EMPLOYEES = "employees"
    PROMOTIONS = "promotions"
    STORES = "stores"


ALL_ROLES: frozenset[Role] = frozenset(Role)
MANAGEMENT_ROLES: frozenset[Role] = frozenset({Role.MANAGER, Role.ADMIN})
BUSINESS_LEADERS: frozenset[Role] = MANAGEMENT_ROLES | {Role.DIRECTOR}


@dataclass(frozen=True)
class NavItem:
    """Một mục menu; allowed_roles là metadata lịch sử, dùng can_access để kiểm quyền."""

    key: NavKey
    i18n_key: str
    icon: str
    allowed_roles: frozenset[Role]


# Thứ tự cố định từ trên xuống theo Stitch export; không đổi vị trí giữa các màn.
NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem(NavKey.DASHBOARD, "nav.dashboard", "▦", ALL_ROLES),
    NavItem(NavKey.CUSTOMERS, "nav.customers", "☻", ALL_ROLES),
    NavItem(NavKey.MACHINES, "nav.machines", "▭", MANAGEMENT_ROLES),
    NavItem(NavKey.INVOICES, "nav.invoices", "▤", ALL_ROLES),
    NavItem(NavKey.REPORTS, "nav.reports", "₫", BUSINESS_LEADERS),
    NavItem(NavKey.EMPLOYEES, "nav.employees", "", BUSINESS_LEADERS),
    NavItem(NavKey.PROMOTIONS, "nav.promotions", "", BUSINESS_LEADERS),
    NavItem(NavKey.STORES, "nav.stores", "", frozenset({Role.ADMIN, Role.DIRECTOR})),
)

DEFAULT_NAV_KEY = NavKey.DASHBOARD


def get_nav_item(key: NavKey | str) -> NavItem:
    """Trả NavItem theo key; raise ValueError nếu key không tồn tại."""
    nav_key = NavKey(key)
    for item in NAV_ITEMS:
        if item.key == nav_key:
            return item
    raise ValueError(f"Unknown navigation key: {key!r}")


def can_access(role: Role, key: NavKey | str) -> bool:
    """Role có được mở màn hình `key` hay không. Key lạ luôn trả False."""
    try:
        item = get_nav_item(key)
    except ValueError:
        return False
    required = {
        NavKey.DASHBOARD: Permission.OPERATE,
        NavKey.CUSTOMERS: Permission.VIEW_CUSTOMERS,
        NavKey.INVOICES: Permission.EXPORT_INVOICE,
        NavKey.REPORTS: Permission.VIEW_REVENUE,
        NavKey.MACHINES: Permission.MANAGE_MACHINES,
        NavKey.EMPLOYEES: Permission.MANAGE_EMPLOYEES,
        NavKey.PROMOTIONS: Permission.MANAGE_PROMOTIONS,
        NavKey.STORES: Permission.MANAGE_STORES,
    }
    if item.key == NavKey.EMPLOYEES:
        return can(role, Permission.MANAGE_EMPLOYEE_CREDENTIALS) or can(role, Permission.MANAGE_EMPLOYEES)
    return can(role, required[item.key])


def visible_nav_items(role: Role) -> tuple[NavItem, ...]:
    """Các mục menu hiển thị cho role, giữ nguyên thứ tự gốc."""
    return tuple(item for item in NAV_ITEMS if can_access(role, item.key))
