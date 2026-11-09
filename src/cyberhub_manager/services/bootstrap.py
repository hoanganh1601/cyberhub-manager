"""Composition shared by desktop and web; importing it does not require Tk."""

from collections.abc import Callable

from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.services.contracts import ServiceBundle


def create_service_bundle(
    *,
    mock: bool = False,
    actor_provider: Callable[[], EmployeeSession | None] | None = None,
) -> ServiceBundle:
    if mock:
        from .mocks.factory import build_mock_services

        from .mocks.clock import RunningClock
        return build_mock_services(p1=True,clock=RunningClock())

    from .auth_service import AuthService
    from .customer_service import CustomerService
    from .machine_service import MachineService
    from .report_service import ReportService
    from .session_service import SessionService
    from .wallet_service import WalletService
    from .management_service import ManagementService
    from .portal_service import PortalService
    from .menu_service import MenuService

    return ServiceBundle(
        auth=AuthService(),
        customers=CustomerService(actor_provider=actor_provider),
        wallet=WalletService(actor_provider=actor_provider),
        machines=MachineService(actor_provider=actor_provider),
        sessions=SessionService(actor_provider=actor_provider),
        reports=ReportService(actor_provider=actor_provider),
        management=ManagementService(actor_provider=actor_provider),
        portal=PortalService(),
        menu=MenuService(actor_provider=actor_provider),
    )
