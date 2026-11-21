"""In-memory adapters used by the reduced core and POS demo."""

from .menu import MemoryMenuRepository
from .p1 import MemoryP1Repository

__all__ = ["MemoryMenuRepository", "MemoryP1Repository"]
