"""Mock services dùng chung cho UI/gallery — owner: Linh (LI-02)."""

from cyberhub_manager.application.services.mocks.clock import DEFAULT_NOW, MockClock
from cyberhub_manager.application.services.mocks.factory import build_mock_services
from cyberhub_manager.application.services.mocks.fixtures import DEMO_ACCOUNTS, DEMO_PASSWORD
from cyberhub_manager.application.services.mocks.scenarios import AFFECTED_OPERATIONS, MockScenario

__all__ = [
    "AFFECTED_OPERATIONS",
    "DEFAULT_NOW",
    "DEMO_ACCOUNTS",
    "DEMO_PASSWORD",
    "MockClock",
    "MockScenario",
    "build_mock_services",
]
