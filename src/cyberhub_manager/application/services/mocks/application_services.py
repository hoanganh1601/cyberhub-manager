"""In-memory application-service doubles used by desktop and web demos."""

from cyberhub_manager.application.services.mocks.auth import MockAuthService
from cyberhub_manager.application.services.mocks.customers import MockCustomerService
from cyberhub_manager.application.services.mocks.machines import MockMachineService
from cyberhub_manager.application.services.mocks.reports import MockReportService
from cyberhub_manager.application.services.mocks.sessions import MockSessionService
from cyberhub_manager.application.services.mocks.wallet import MockWalletService

__all__ = [
    "MockAuthService",
    "MockCustomerService",
    "MockMachineService",
    "MockReportService",
    "MockSessionService",
    "MockWalletService",
]
