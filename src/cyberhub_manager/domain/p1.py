"""P1 public contracts and deterministic money rules shared by desktop/web/DB/demo."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .enums import Role
from .exceptions import ValidationError
from .loyalty import TIERS, audience_matches


class Permission(StrEnum):
    OPERATE = "operate"
    MANAGE_MACHINES = "manage_machines"
    LOCK_CUSTOMERS = "lock_customers"
    MANAGE_EMPLOYEES = "manage_employees"
    MANAGE_PROMOTIONS = "manage_promotions"
    MANAGE_STORES = "manage_stores"
    SWITCH_STORE = "switch_store"
    EXPORT_INVOICE = "export_invoice"
    MANAGE_MENU = "manage_menu"  # Đợt 1: thêm/sửa/ẩn món, nhóm món, giá, ảnh (MANAGER/ADMIN)
    MANAGE_REWARDS = "manage_rewards"  # Đợt 2: danh mục phần thưởng, phát/thu hồi voucher (MANAGER/ADMIN)
    POS_VIEW_ORDERS = "pos_view_orders"
    POS_PREPARE_ORDERS = "pos_prepare_orders"
    POS_SERVE_ORDERS = "pos_serve_orders"
    POS_CANCEL_ORDERS = "pos_cancel_orders"
    POS_COLLECT_PAYMENT = "pos_collect_payment"
    INVENTORY_VIEW = "inventory_view"
    INVENTORY_CONFIGURE = "inventory_configure"
    INVENTORY_RECEIVE = "inventory_receive"
    INVENTORY_ISSUE = "inventory_issue"
    INVENTORY_COUNT = "inventory_count"
    INVENTORY_APPROVE = "inventory_approve"


# Grant every capability deliberately. A new Permission must not silently become
# available to MANAGER or ADMIN merely because it was added to the enum.
_STAFF_PERMISSIONS = frozenset({
    Permission.OPERATE,
    Permission.EXPORT_INVOICE,
    Permission.POS_VIEW_ORDERS,
    Permission.POS_PREPARE_ORDERS,
    Permission.POS_SERVE_ORDERS,
    Permission.POS_CANCEL_ORDERS,
    Permission.POS_COLLECT_PAYMENT,
    Permission.INVENTORY_VIEW,
    Permission.INVENTORY_COUNT,
})
_MANAGER_PERMISSIONS = _STAFF_PERMISSIONS | frozenset({
    Permission.MANAGE_MACHINES,
    Permission.LOCK_CUSTOMERS,
    Permission.MANAGE_EMPLOYEES,
    Permission.MANAGE_PROMOTIONS,
    Permission.MANAGE_MENU,
    Permission.MANAGE_REWARDS,
    Permission.INVENTORY_CONFIGURE,
    Permission.INVENTORY_RECEIVE,
    Permission.INVENTORY_ISSUE,
    Permission.INVENTORY_APPROVE,
})
ROLE_PERMISSIONS = {
    Role.STAFF: _STAFF_PERMISSIONS,
    Role.MANAGER: _MANAGER_PERMISSIONS,
    Role.ADMIN: _MANAGER_PERMISSIONS | frozenset({
        Permission.MANAGE_STORES,
        Permission.SWITCH_STORE,
    }),
}


def can(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, ())


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
    minimum_tier: str = "BRONZE"
    minimum_points: int = 0
    target_customer_id: int | None = None


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
    *,
    customer_id=None,
    member=None,
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
        and audience_matches(p, customer_id, member)
    ]
    # Highest threshold; a local policy overrides a global policy at the same threshold.
    policy = max(
        eligible,
        key=lambda p: (
            p.minimum_amount,
            p.store_id == store_id,
            p.target_customer_id is not None,
            TIERS.index(p.minimum_tier),
            p.minimum_points,
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
