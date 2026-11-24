"""Domain repository package with PEP 562 lazy exports to keep mock mode MySQL-free."""

from __future__ import annotations

from importlib import import_module

_EXPORTS: dict[str, str] = {
    "AccountRepository": "account_repository",
    "AdRepository": "ad_repository",
    "AuthRepository": "auth_repository",
    "CashShiftRepository": "cash_shift_repository",
    "CommercialRepository": "commercial_repository",
    "CustomerEmailRepository": "customer_email_repository",
    "CustomerRepository": "customer_repository",
    "GameRepository": "game_repository",
    "InventoryRepository": "inventory_repository",
    "InvoiceRepository": "invoice_repository",
    "LoyaltyRepository": "loyalty_repository",
    "MachineRepository": "machine_repository",
    "MaintenanceRepository": "maintenance_repository",
    "ManagementRepository": "management_repository",
    "MenuRepository": "menu_repository",
    "PortalRepository": "portal_repository",
    "ProcurementRepository": "procurement_repository",
    "SessionRepository": "session_repository",
    "VoucherRepository": "voucher_repository",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f"cyberhub_manager.infrastructure.repositories.{module_name}")
    return getattr(module, name)
