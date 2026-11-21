"""Composition shared by desktop and web; importing it does not require Tk."""

from collections.abc import Callable

from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.application.services.contracts import ServiceBundle


def create_service_bundle(
    *,
    mock: bool = False,
    actor_provider: Callable[[], EmployeeSession | None] | None = None,
) -> ServiceBundle:
    if mock:
        from cyberhub_manager.application.services.mocks.factory import build_mock_services

        from cyberhub_manager.application.services.mocks.clock import RunningClock
        return build_mock_services(p1=True,clock=RunningClock())

    from cyberhub_manager.application.services.auth_service import AuthService
    from cyberhub_manager.application.services.customer_service import CustomerService
    from cyberhub_manager.application.services.customer_email_service import CustomerEmailService
    from cyberhub_manager.application.services.machine_service import MachineService
    from cyberhub_manager.application.services.report_service import ReportService
    from cyberhub_manager.application.services.session_service import SessionService
    from cyberhub_manager.application.services.wallet_service import WalletService
    from cyberhub_manager.application.services.management_service import ManagementService
    from cyberhub_manager.application.services.portal_service import PortalService
    from cyberhub_manager.application.services.menu_service import MenuService
    from cyberhub_manager.application.services.voucher_service import VoucherService
    from cyberhub_manager.application.services.game_service import GameService
    from cyberhub_manager.application.services.ad_service import AdService
    from cyberhub_manager.application.services.identity_service import IdentityService
    from cyberhub_manager.application.services.cash_shift_service import CashShiftService
    from cyberhub_manager.application.services.maintenance_service import MaintenanceService
    from cyberhub_manager.application.services.procurement_service import ProcurementService
    from cyberhub_manager.application.services.commercial_service import CommercialService

    shifts = CashShiftService()
    customers = CustomerService(actor_provider=actor_provider)

    return ServiceBundle(
        auth=AuthService(),
        customers=customers,
        wallet=WalletService(actor_provider=actor_provider, shift_service=shifts),
        machines=MachineService(actor_provider=actor_provider),
        sessions=SessionService(actor_provider=actor_provider, shift_service=shifts),
        reports=ReportService(actor_provider=actor_provider),
        identity=IdentityService(),
        management=ManagementService(actor_provider=actor_provider),
        portal=PortalService(),
        menu=MenuService(actor_provider=actor_provider, shift_service=shifts),
        vouchers=(vouchers := VoucherService(actor_provider=actor_provider)),
        games=GameService(vouchers=vouchers, actor_provider=actor_provider),
        ads=AdService(vouchers=vouchers, actor_provider=actor_provider),
        shifts=shifts,
        maintenance=MaintenanceService(),
        procurement=ProcurementService(shifts=shifts),
        commercial=CommercialService(),
        customer_email=CustomerEmailService(customers),
    )
