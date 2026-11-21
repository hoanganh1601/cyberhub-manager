"""Dedicated POS roles grant only the capabilities needed for each job."""

from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.p1 import Permission, can
from cyberhub_manager.domain.exceptions import PermissionDeniedError
from cyberhub_manager.application.services.mocks.factory import build_mock_services
from uuid import uuid4
import pytest


def test_kitchen_and_inventory_permissions_are_explicit():
    assert can(Role.KITCHEN, Permission.POS_PREPARE_ORDERS)
    assert can(Role.KITCHEN, Permission.POS_SERVE_ORDERS)
    assert not can(Role.KITCHEN, Permission.POS_COLLECT_PAYMENT)
    assert not can(Role.KITCHEN, Permission.INVENTORY_ISSUE)
    assert can(Role.INVENTORY, Permission.INVENTORY_RECEIVE)
    assert can(Role.INVENTORY, Permission.INVENTORY_ISSUE)
    assert not can(Role.INVENTORY, Permission.POS_VIEW_ORDERS)
    assert not can(Role.INVENTORY, Permission.INVENTORY_APPROVE)
    assert not can(Role.INVENTORY, Permission.POS_COLLECT_PAYMENT)


def test_specialist_accounts_are_created_by_admin_and_enforced_in_service():
    bundle = build_mock_services(p1=True)
    admin = bundle.auth.login("admin01", "demo123")
    manager = bundle.auth.login("quanly01", "demo123")
    with pytest.raises(PermissionDeniedError):
        bundle.management.save_employee(manager, None, 1, "Bếp", "bep0001",
                                        role="KITCHEN", password="demo1234")
    bundle.management.save_employee(admin, None, 1, "Bếp", "bep0001",
                                    role="KITCHEN", password="demo1234")
    bundle.management.save_employee(admin, None, 1, "Thủ kho", "kho0001",
                                    role="INVENTORY", password="demo1234")
    kitchen = bundle.auth.login("bep0001", "demo1234")
    stock = bundle.auth.login("kho0001", "demo1234")
    assert bundle.menu.list_orders(kitchen, "ALL") == []
    assert bundle.menu.inventory_overview(stock)["can_receive"] is True
    with pytest.raises(PermissionDeniedError):
        bundle.menu.list_orders(stock, "ALL")
    with pytest.raises(PermissionDeniedError):
        bundle.menu.pay_order(kitchen, 1, "CASH")
    with pytest.raises(PermissionDeniedError):
        bundle.menu.pay_order(stock, 1, "CASH")


def test_demo_inventory_role_has_a_working_stock_ledger():
    bundle = build_mock_services(p1=True)
    stock = bundle.auth.login("thukho01", "demo123")

    before = bundle.menu.inventory_overview(stock)
    ingredient = before["ingredients"][0]
    assert before["enabled"] is True
    assert before["movements"]
    assert before["can_receive"] and before["can_issue"] and before["can_count"]

    updated = bundle.menu.receive_ingredient(
        stock, ingredient["id"], quantity=5, reference_code="PN-TEST-01",
        request_id=str(uuid4()), note="Kiểm thử nhập kho",
    )
    after = bundle.menu.inventory_overview(stock)
    assert updated["on_hand"] == ingredient["on_hand"] + 5
    assert after["movements"][0]["kind"] == "RECEIVE"
