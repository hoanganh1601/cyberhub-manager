"""Mock services dùng chung cho UI/gallery — owner: Linh (LI-02)."""

from .clock import DEFAULT_NOW, MockClock
from .scenarios import MockScenario

__all__ = ["DEFAULT_NOW", "MockClock", "MockScenario"]
