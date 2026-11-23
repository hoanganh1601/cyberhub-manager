"""P1 public contracts and deterministic money rules shared by desktop/web/DB/demo."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import os

from .enums import Role
from .exceptions import ValidationError


class Permission(StrEnum):
    OPERATE = "operate"
    MANAGE_MACHINES = "manage_machines"
    LOCK_CUSTOMERS = "lock_customers"
    VIEW_CUSTOMERS = "view_customers"
    CREATE_CUSTOMERS = "create_customers"
    EDIT_CUSTOMERS = "edit_customers"
    OPERATE_WALLET = "operate_wallet"
    MANAGE_EMPLOYEES = "manage_employees"
    MANAGE_EMPLOYEE_CREDENTIALS = "manage_employee_credentials"
    MANAGE_PROMOTIONS = "manage_promotions"
    MANAGE_STORES = "manage_stores"
    SWITCH_STORE = "switch_store"
    EXPORT_INVOICE = "export_invoice"
    VIEW_REVENUE = "view_revenue"
    MANAGE_MENU = "manage_menu"  # Đợt 1: thêm/sửa/ẩn món, nhóm món, giá (MANAGER/ADMIN)
    POS_VIEW_ORDERS = "pos_view_orders"
    POS_PREPARE_ORDERS = "pos_prepare_orders"
    POS_SERVE_ORDERS = "pos_serve_orders"
    POS_CANCEL_ORDERS = "pos_cancel_orders"
    POS_COLLECT_PAYMENT = "pos_collect_payment"
    POS_REQUEST_REVERSAL = "pos_request_reversal"
    POS_APPROVE_REVERSAL = "pos_approve_reversal"


# Grant every capability deliberately. A new Permission must not silently become
# available to MANAGER or ADMIN merely because it was added to the enum.
_STAFF_PERMISSIONS = frozenset({
    Permission.OPERATE,
    Permission.VIEW_CUSTOMERS,
    Permission.CREATE_CUSTOMERS,
    Permission.EDIT_CUSTOMERS,
    Permission.OPERATE_WALLET,
    Permission.EXPORT_INVOICE,
    Permission.POS_VIEW_ORDERS,
    Permission.POS_PREPARE_ORDERS,
    Permission.POS_SERVE_ORDERS,
    Permission.POS_CANCEL_ORDERS,
    Permission.POS_COLLECT_PAYMENT,
    Permission.POS_REQUEST_REVERSAL,
})
_MANAGER_PERMISSIONS = _STAFF_PERMISSIONS | frozenset({
    Permission.VIEW_REVENUE,
    Permission.MANAGE_MACHINES,
    Permission.LOCK_CUSTOMERS,
    Permission.MANAGE_EMPLOYEES,
    Permission.MANAGE_PROMOTIONS,
    Permission.MANAGE_MENU,
    Permission.POS_APPROVE_REVERSAL,
})
ROLE_PERMISSIONS = {
    Role.STAFF: _STAFF_PERMISSIONS,
    Role.KITCHEN: frozenset({
        Permission.POS_VIEW_ORDERS,
        Permission.POS_PREPARE_ORDERS,
        Permission.POS_SERVE_ORDERS,
    }),
    Role.MANAGER: _MANAGER_PERMISSIONS,
    Role.ADMIN: _MANAGER_PERMISSIONS | frozenset({
        Permission.MANAGE_STORES,
        Permission.SWITCH_STORE,
        Permission.MANAGE_EMPLOYEE_CREDENTIALS,
    }),
    Role.DIRECTOR: frozenset({
        Permission.MANAGE_STORES,
        Permission.SWITCH_STORE,
        Permission.VIEW_REVENUE,
        Permission.VIEW_CUSTOMERS,
        Permission.MANAGE_EMPLOYEES,
        Permission.MANAGE_PROMOTIONS,
        Permission.EXPORT_INVOICE,
    }),
}


# Existing ADMIN accounts keep their grants until an operator explicitly opts in
# after reviewing and migrating each account. No role is rewritten by this switch.
SEPARATED_ADMIN_PERMISSIONS = frozenset({
    Permission.MANAGE_EMPLOYEE_CREDENTIALS,
})


def separated_rbac() -> bool:
    return os.getenv("CYBERHUB_RBAC_POLICY", "legacy").lower() == "separated"


def permissions_for(role: Role) -> frozenset[Permission]:
    if role == Role.ADMIN and separated_rbac():
        return SEPARATED_ADMIN_PERMISSIONS
    return ROLE_PERMISSIONS.get(role, frozenset())


def can(role: Role, permission: Permission) -> bool:
    return permission in permissions_for(role)


def business_manager(role: Role) -> bool:
    """Local operations; a chain director does not become a cashier."""
    return role == Role.MANAGER or (role == Role.ADMIN and not separated_rbac())


def chain_director(role: Role) -> bool:
    """Chain-wide business scope, with a temporary legacy ADMIN bridge."""
    return role == Role.DIRECTOR or (role == Role.ADMIN and not separated_rbac())


@dataclass(frozen=True)
class StoreSummary:
    id: int
    code: str
    name: str
    address: str
    status: str


@dataclass(frozen=True)
class EmployeeSummary:
    id: int
    code: str
    store_id: int
    full_name: str
    username: str
    role: str
    status: str
    credential_update_required: bool = False


@dataclass(frozen=True)
class Promotion:
    id: int
    code: str
    name: str
    store_id: int | None
    minimum_amount: int
    bonus_percent: int
    starts_at: datetime
    ends_at: datetime
    is_active: bool = True


@dataclass(frozen=True)
class CustomerSession:
    customer_id: int
    account_id: int
    full_name: str
    username: str
    auth_version: int = 0


@dataclass(frozen=True)
class TopUpQuote:
    amount: int
    bonus_amount: int
    promotion: Promotion | None


def quote_top_up(
    amount: int,
    policies: list[Promotion],
    store_id: int,
    now: datetime,
) -> TopUpQuote:
    if type(amount) is not int or not 1 <= amount <= 100_000_000:
        raise ValidationError(
            field_errors={"amount": "Số tiền phải từ 1 đến 100.000.000 VND"}
        )
    eligible = [
        p
        for p in policies
        if p.is_active
        and p.store_id in (None, store_id)
        and p.minimum_amount <= amount
        and p.starts_at <= now < p.ends_at
    ]
    # Highest threshold; a local policy overrides a global policy at the same threshold.
    policy = max(
        eligible,
        key=lambda p: (
            p.minimum_amount,
            p.store_id == store_id,
            p.id,
        ),
        default=None,
    )
    return TopUpQuote(
        amount, amount * policy.bonus_percent // 100 if policy else 0, policy
    )


def debit_split(balance: int, bonus_balance: int, cost: int) -> tuple[int, int, int]:
    """Return bonus used, principal used, resulting bonus; never pay cash change from bonus."""
    if type(cost) is not int or cost < 0 or bonus_balance < 0:
        raise ValueError("Invalid wallet debit")
    used = min(bonus_balance, cost)
    return used, cost - used, bonus_balance - used
