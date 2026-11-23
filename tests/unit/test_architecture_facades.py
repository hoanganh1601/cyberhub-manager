"""Architecture checks for domain-oriented repositories and service facades."""

from cyberhub_manager import repositories
from cyberhub_manager.domain.account_models import Account as AccountModel
from cyberhub_manager.domain.models import Account
from cyberhub_manager.repositories.management_repository import ManagementRepository
from cyberhub_manager.repositories.portal_repository import PortalRepository
from cyberhub_manager.services.auth_service import AuthService
from cyberhub_manager.services.identity_service import IdentityService
from cyberhub_manager.services.management_service import ManagementService
from cyberhub_manager.services.menu_catalog_service import MenuCatalogMixin
from cyberhub_manager.services.menu_order_service import MenuOrderMixin
from cyberhub_manager.services.menu_service import MenuService
from cyberhub_manager.services.mocks.application_services import MockAuthService
from cyberhub_manager.services.mocks.demo_data import MockScenario
from cyberhub_manager.services.mocks.repositories import MemoryP1Repository
from cyberhub_manager.services.operational_base import OperationalServiceBase
from cyberhub_manager.services.portal_service import PortalService
from cyberhub_manager.services.report_service import ReportService
from cyberhub_manager.services.session_service import SessionService
from cyberhub_manager.services.wallet_service import WalletService


def test_domain_models_keeps_the_legacy_import_contract():
    assert Account is AccountModel


def test_menu_service_composes_focused_capabilities():
    assert issubclass(MenuService, MenuCatalogMixin)
    assert issubclass(MenuService, MenuOrderMixin)


def test_repositories_expose_standalone_management_and_portal_classes():
    assert repositories.ManagementRepository is ManagementRepository
    assert repositories.PortalRepository is PortalRepository
    assert not issubclass(ManagementRepository, PortalRepository)
    assert not issubclass(PortalRepository, ManagementRepository)
    assert hasattr(ManagementRepository, "audit")
    assert hasattr(ManagementRepository, "list_machine_rooms")
    assert hasattr(ManagementRepository, "set_machine_room")
    assert hasattr(PortalRepository, "customer_credentials")
    assert hasattr(PortalRepository, "customer_snapshot")
    assert not hasattr(ManagementRepository, "customer_credentials")
    assert not hasattr(PortalRepository, "audit")


def test_services_wire_domain_repositories_by_default():
    assert isinstance(AuthService()._audit, ManagementRepository)
    assert isinstance(IdentityService()._stores, ManagementRepository)
    assert isinstance(ManagementService()._repo, ManagementRepository)
    assert isinstance(OperationalServiceBase()._audit, ManagementRepository)
    assert isinstance(ReportService()._audit, ManagementRepository)
    assert isinstance(SessionService()._audit, ManagementRepository)
    assert isinstance(WalletService()._promotions, ManagementRepository)

    portal = PortalService()
    assert isinstance(portal._repo, PortalRepository)
    assert isinstance(portal._management, ManagementRepository)

    menu = MenuService()
    assert isinstance(menu._management, ManagementRepository)
    assert isinstance(menu._portal, PortalRepository)


def test_demo_namespaces_expose_services_data_and_repositories():
    assert MockAuthService.__name__ == "MockAuthService"
    assert MockScenario.SUCCESS.value == "SUCCESS"
    assert MemoryP1Repository.__name__ == "MemoryP1Repository"
