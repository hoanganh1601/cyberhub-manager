"""Compatibility checks for the architecture-cleanup facades."""

from cyberhub_manager.domain.account_models import Account as AccountModel
from cyberhub_manager.domain.models import Account
from cyberhub_manager.infrastructure.repositories import (
    LoyaltyRepository,
    ManagementRepository,
    PortalRepository,
)
from cyberhub_manager.infrastructure.repositories.loyalty_repository import (
    LoyaltyRepository as LoyaltyRepositoryImpl,
)
from cyberhub_manager.infrastructure.repositories.management_repository import (
    ManagementRepository as ManagementRepositoryImpl,
)
from cyberhub_manager.infrastructure.repositories.portal_repository import (
    PortalRepository as PortalRepositoryImpl,
)
from cyberhub_manager.application.services.menu_catalog_service import MenuCatalogMixin
from cyberhub_manager.application.services.menu_inventory_service import MenuInventoryMixin
from cyberhub_manager.application.services.menu_order_service import MenuOrderMixin
from cyberhub_manager.application.services.menu_service import MenuService
from cyberhub_manager.application.services.mocks.application_services import MockAuthService
from cyberhub_manager.application.services.mocks.demo_data import MockScenario
from cyberhub_manager.application.services.mocks.repositories import MemoryManagementRepository


def test_domain_models_keeps_the_legacy_import_contract():
    assert Account is AccountModel


def test_menu_service_composes_focused_capabilities():
    assert issubclass(MenuService, MenuCatalogMixin)
    assert issubclass(MenuService, MenuInventoryMixin)
    assert issubclass(MenuService, MenuOrderMixin)


def test_domain_repositories_are_standalone_classes():
    assert ManagementRepository is ManagementRepositoryImpl
    assert PortalRepository is PortalRepositoryImpl
    assert LoyaltyRepository is LoyaltyRepositoryImpl
    assert ManagementRepository.__bases__ == (object,)
    assert PortalRepository.__bases__ == (object,)
    assert LoyaltyRepository.__bases__ == (object,)


def test_demo_namespaces_expose_services_data_and_repositories():
    assert MockAuthService.__name__ == "MockAuthService"
    assert MockScenario.SUCCESS.value == "SUCCESS"
    assert MemoryManagementRepository.__name__ == "MemoryManagementRepository"
