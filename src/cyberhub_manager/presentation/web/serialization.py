"""JSON-safe projections used by the Flask adapter."""

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


def serialize(value: Any) -> Any:
    """Serialize DTOs only. Domain models use explicit public projections."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        data = asdict(value)
        if hasattr(value, "cash_balance"):
            data["cash_balance"] = value.cash_balance
        return serialize(data)
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [serialize(item) for item in value]
    return value


def customer_public(customer: Any) -> dict[str, Any]:
    account = customer.account
    return {
        "customer_id": customer.id,
        "customer_code": customer.code,
        "full_name": customer.full_name,
        "phone": customer.phone,
        "customer_status": customer.status,
        "account_id": account.id,
        "account_code": account.code,
        "username": account.username,
        "balance": account.balance,
        "cash_balance": account.cash_balance,
        "bonus_balance": account.bonus_balance,
        "account_status": account.status,
    }


def machine_public(machine: Any) -> dict[str, Any]:
    return {
        "machine_id": machine.id,
        "machine_code": machine.code,
        "store_id": machine.store_id,
        "name": machine.name,
        "status": machine.status,
        "hourly_rate": machine.hourly_rate,
        "is_active": machine.is_active,
        "updated_at": machine.updated_at,
    }
