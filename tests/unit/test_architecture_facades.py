"""Compatibility checks for the architecture-cleanup facades."""

from cyberhub_manager.domain.account_models import Account as AccountModel
from cyberhub_manager.domain.models import Account
from cyberhub_manager.repositories.management_repository import ManagementRepositoryMixin
from cyberhub_manager.repositories.p1_repository import P1Repository
from cyberhub_manager.services.menu_catalog_service import MenuCatalogMixin
from cyberhub_manager.services.menu_inventory_service import MenuInventoryMixin
from cyberhub_manager.services.menu_order_service import MenuOrderMixin
from cyberhub_manager.services.menu_service import MenuService
from cyberhub_manager.services.mocks.application_services import MockAuthService
from cyberhub_manager.services.mocks.demo_data import MockScenario
from cyberhub_manager.services.mocks.repositories import MemoryP1Repository


def test_domain_models_keeps_the_legacy_import_contract():
    assert Account is AccountModel


def test_menu_service_composes_focused_capabilities():
    assert issubclass(MenuService, MenuCatalogMixin)
    assert issubclass(MenuService, MenuInventoryMixin)
    assert issubclass(MenuService, MenuOrderMixin)


def test_p1_repository_composes_management_capability():
    assert issubclass(P1Repository, ManagementRepositoryMixin)


def test_demo_namespaces_expose_services_data_and_repositories():
    assert MockAuthService.__name__ == "MockAuthService"
    assert MockScenario.SUCCESS.value == "SUCCESS"
    assert MemoryP1Repository.__name__ == "MemoryP1Repository"
