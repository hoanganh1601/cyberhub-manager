"""In-memory application-service doubles used by desktop and web demos."""

from .auth import MockAuthService
from .customers import MockCustomerService
from .machines import MockMachineService
from .reports import MockReportService
from .sessions import MockSessionService
from .wallet import MockWalletService

__all__ = [
    "MockAuthService",
    "MockCustomerService",
    "MockMachineService",
    "MockReportService",
    "MockSessionService",
    "MockWalletService",
]
