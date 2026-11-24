"""Compatibility facade for CyberHub domain entities.

The concrete entities live in focused modules. Existing imports from
cyberhub_manager.domain.models remain supported.
"""

from cyberhub_manager.domain.account_models import Account, Customer
from cyberhub_manager.domain.billing_models import AccountTransaction, Invoice
from cyberhub_manager.domain.machine_models import Machine
from cyberhub_manager.domain.model_base import Entity, Person
from cyberhub_manager.domain.organization_models import Employee, Store
from cyberhub_manager.domain.usage_models import (
    MINIMUM_SESSION_MINUTES,
    LiveEstimate,
    UsageSession,
    estimate_live_usage,
    estimate_play_minutes,
    minimum_balance,
)

__all__ = [
    "Account",
    "AccountTransaction",
    "Customer",
    "Employee",
    "Entity",
    "Invoice",
    "LiveEstimate",
    "MINIMUM_SESSION_MINUTES",
    "Machine",
    "Person",
    "Store",
    "UsageSession",
    "estimate_live_usage",
    "estimate_play_minutes",
    "minimum_balance",
]
