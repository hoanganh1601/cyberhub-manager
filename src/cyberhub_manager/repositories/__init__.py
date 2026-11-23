"""MySQL repository layer — pure domain-oriented persistence classes."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .account_repository import AccountRepository
    from .auth_repository import AuthRepository
    from .customer_repository import CustomerRepository
    from .invoice_repository import InvoiceRepository
    from .machine_repository import MachineRepository
    from .management_repository import ManagementRepository
    from .menu_repository import MenuRepository
    from .portal_repository import PortalRepository
    from .session_repository import SessionRepository

_EXPORTS = {
    "AccountRepository": ".account_repository",
    "AuthRepository": ".auth_repository",
    "CustomerRepository": ".customer_repository",
    "InvoiceRepository": ".invoice_repository",
    "MachineRepository": ".machine_repository",
    "ManagementRepository": ".management_repository",
    "MenuRepository": ".menu_repository",
    "PortalRepository": ".portal_repository",
    "SessionRepository": ".session_repository",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(module_name, __name__), name)
