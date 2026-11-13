"""Dedicated POS roles grant only the capabilities needed for each job."""

from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.p1 import Permission, can
from cyberhub_manager.domain.exceptions import PermissionDeniedError
from cyberhub_manager.services.mocks.factory import build_mock_services
import pytest


def test_kitchen_and_inventory_permissions_are_explicit():
    assert can(Role.KITCHEN, Permission.POS_PREPARE_ORDERS)
    assert can(Role.KITCHEN, Permission.POS_SERVE_ORDERS)
    assert not can(Role.KITCHEN, Permission.POS_COLLECT_PAYMENT)
    assert not can(Role.KITCHEN, Permission.INVENTORY_ISSUE)
    assert can(Role.INVENTORY, Permission.INVENTORY_RECEIVE)
    assert can(Role.INVENTORY, Permission.INVENTORY_ISSUE)
    assert not can(Role.INVENTORY, Permission.INVENTORY_APPROVE)
    assert not can(Role.INVENTORY, Permission.POS_COLLECT_PAYMENT)


def test_specialist_accounts_are_created_by_admin_and_enforced_in_service():
    bundle = build_mock_services(p1=True)
    admin = bundle.auth.login("admin01", "demo123")
    manager = bundle.auth.login("quanly01", "demo123")
    with pytest.raises(PermissionDeniedError):
        bundle.management.save_employee(manager, None, 1, "Bếp", "bep0001",
                                        role="KITCHEN", password="demo123")
    bundle.management.save_employee(admin, None, 1, "Bếp", "bep0001",
                                    role="KITCHEN", password="demo123")
    bundle.management.save_employee(admin, None, 1, "Thủ kho", "kho0001",
                                    role="INVENTORY", password="demo123")
    kitchen = bundle.auth.login("bep0001", "demo123")
    stock = bundle.auth.login("kho0001", "demo123")
    assert bundle.menu.list_orders(kitchen, "ALL") == []
    assert bundle.menu.inventory_overview(stock)["can_receive"] is True
    with pytest.raises(PermissionDeniedError):
        bundle.menu.pay_order(kitchen, 1, "CASH")
    with pytest.raises(PermissionDeniedError):
        bundle.menu.pay_order(stock, 1, "CASH")
