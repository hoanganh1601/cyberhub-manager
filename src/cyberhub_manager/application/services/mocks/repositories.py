"""Public namespace for in-memory repository adapters.

The concrete adapters remain small feature modules; composition code imports
them through this boundary instead of mixing repositories with service doubles.
"""

from cyberhub_manager.application.services.mocks.ad import MemoryAdRepository
from cyberhub_manager.application.services.mocks.game import MemoryGameRepository
from cyberhub_manager.application.services.mocks.inventory import MemoryInventoryRepository
from cyberhub_manager.application.services.mocks.menu import MemoryMenuRepository
from cyberhub_manager.application.services.mocks.management import MemoryManagementRepository
from cyberhub_manager.application.services.mocks.voucher import MemoryVoucherRepository

__all__ = [
    "MemoryAdRepository",
    "MemoryGameRepository",
    "MemoryInventoryRepository",
    "MemoryMenuRepository",
    "MemoryManagementRepository",
    "MemoryVoucherRepository",
]
