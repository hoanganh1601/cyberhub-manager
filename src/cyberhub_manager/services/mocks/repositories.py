"""Public namespace for in-memory repository adapters.

The concrete adapters remain small feature modules; composition code imports
them through this boundary instead of mixing repositories with service doubles.
"""

from .ad import MemoryAdRepository
from .game import MemoryGameRepository
from .inventory import MemoryInventoryRepository
from .menu import MemoryMenuRepository
from .p1 import MemoryP1Repository
from .voucher import MemoryVoucherRepository

__all__ = [
    "MemoryAdRepository",
    "MemoryGameRepository",
    "MemoryInventoryRepository",
    "MemoryMenuRepository",
    "MemoryP1Repository",
    "MemoryVoucherRepository",
]
