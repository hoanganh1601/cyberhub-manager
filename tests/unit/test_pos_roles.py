"""Dedicated POS roles grant only the capabilities needed for each job."""

from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.p1 import Permission, can
from cyberhub_manager.domain.exceptions import PermissionDeniedError, ValidationError
from cyberhub_manager.services.mocks.factory import build_mock_services
import pytest


def test_kitchen_permissions_are_explicit():
    assert can(Role.KITCHEN, Permission.POS_VIEW_ORDERS)
    assert can(Role.KITCHEN, Permission.POS_PREPARE_ORDERS)
    assert can(Role.KITCHEN, Permission.POS_SERVE_ORDERS)
    assert not can(Role.KITCHEN, Permission.POS_COLLECT_PAYMENT)
    assert not can(Role.KITCHEN, Permission.POS_CANCEL_ORDERS)
    assert not can(Role.KITCHEN, Permission.POS_REQUEST_REVERSAL)
    assert not hasattr(Role, "INVENTORY")


def test_specialist_accounts_are_created_by_admin_and_enforced_in_service():
    bundle = build_mock_services(p1=True)
    admin = bundle.auth.login("admin01", "demo123")
    manager = bundle.auth.login("quanly01", "demo123")
    with pytest.raises(PermissionDeniedError):
        bundle.management.save_employee(manager, None, 1, "Bếp", "bep0001",
                                        role="KITCHEN", password="demo1234")
    with pytest.raises(ValidationError):
        bundle.management.save_employee(admin, None, 1, "Thủ kho", "kho0001",
                                        role="INVENTORY", password="demo1234")
    bundle.management.save_employee(admin, None, 1, "Bếp", "bep0001",
                                    role="KITCHEN", password="demo1234")
    kitchen = bundle.auth.login("bep0001", "demo1234")
    assert bundle.menu.list_orders(kitchen, "ALL") == []
    with pytest.raises(PermissionDeniedError):
        bundle.menu.pay_order(kitchen, 1, "CASH")
