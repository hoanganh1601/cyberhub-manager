"""NG-02 — Danh mục menu và quy tắc phân quyền điều hướng.

Module này là logic thuần: không import Tk/CustomTkinter, không import service hay SQL,
nên có thể test bằng pytest mà không cần cửa sổ.
Thứ tự menu theo Stitch export (code.html); phân quyền theo docs/diagrams/ui_wireflow.md mục 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..domain.enums import Role


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


@dataclass(frozen=True)
class NavItem:
    """Một mục menu trên sidebar."""

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
    NavItem(NavKey.REPORTS, "nav.reports", "₫", ALL_ROLES),
    NavItem(NavKey.EMPLOYEES, "nav.employees", "", MANAGEMENT_ROLES),
    NavItem(NavKey.PROMOTIONS, "nav.promotions", "", MANAGEMENT_ROLES),
    NavItem(NavKey.STORES, "nav.stores", "", frozenset({Role.ADMIN})),
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
        return role in get_nav_item(key).allowed_roles
    except ValueError:
        return False


def visible_nav_items(role: Role) -> tuple[NavItem, ...]:
    """Các mục menu hiển thị cho role, giữ nguyên thứ tự gốc."""
    return tuple(item for item in NAV_ITEMS if role in item.allowed_roles)
