"""P1 public contracts and deterministic money rules shared by desktop/web/DB/demo."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .enums import Role
from .exceptions import ValidationError


class Permission(StrEnum):
    OPERATE = "operate"
    MANAGE_MACHINES = "manage_machines"
    LOCK_CUSTOMERS = "lock_customers"
    MANAGE_EMPLOYEES = "manage_employees"
    MANAGE_PROMOTIONS = "manage_promotions"
    MANAGE_STORES = "manage_stores"
    SWITCH_STORE = "switch_store"
    EXPORT_INVOICE = "export_invoice"


ROLE_PERMISSIONS = {
    Role.STAFF: frozenset({Permission.OPERATE, Permission.EXPORT_INVOICE}),
    Role.MANAGER: frozenset(
        set(Permission) - {Permission.MANAGE_STORES, Permission.SWITCH_STORE}
    ),
    Role.ADMIN: frozenset(Permission),
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
    amount: int, policies: list[Promotion], store_id: int, now: datetime
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
        key=lambda p: (p.minimum_amount, p.store_id == store_id, p.id),
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
