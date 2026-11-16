from contextlib import contextmanager
from uuid import uuid4

import pytest

from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.exceptions import ConflictError, PermissionDeniedError
from cyberhub_manager.repositories.sql import execute, rows
from cyberhub_manager.services.cash_shift_service import CashShiftService
from cyberhub_manager.services.maintenance_service import MaintenanceService
from cyberhub_manager.services.procurement_service import ProcurementService


def _actor(conn, scenario, *, role, name, scenario_staff=True):
    if role is Role.STAFF and scenario_staff:
        employee_id = scenario.employee_id
    else:
        token = uuid4().hex[:8]
        employee_id = execute(conn,
            "INSERT INTO employees(code,store_id,full_name,username,password_hash,role) "
            "VALUES(%s,%s,%s,%s,'x',%s)",
            (f"OP-{token}",scenario.store_id,name,f"op.{token}",role.value))
    return EmployeeSession(employee_id,f"EMP-{employee_id}",name,f"user{employee_id}",
        scenario.store_id,"STORE","Test store",role,0)


def _boundary(conn):
    @contextmanager
    def boundary():
        yield conn
    return boundary


def test_cash_shift_requires_review_for_variance(db_conn, test_scenario):
    scenario=test_scenario(db_conn); staff=_actor(db_conn,scenario,role=Role.STAFF,name="Cashier")
    manager=_actor(db_conn,scenario,role=Role.MANAGER,name="Manager")
    service=CashShiftService(transaction_factory=_boundary(db_conn))
    shift=service.open_shift(staff,100_000)
    with pytest.raises(ConflictError): service.open_shift(staff,0)
    service.record_system_entry(db_conn,staff,kind="RECEIPT",payment_method="CASH",
        amount=50_000,source_type="TEST",source_id="1")
    service.add_entry(staff,kind="EXPENSE",payment_method="CASH",amount=20_000,note="Mua vật tư")
    submitted=service.submit_close(staff,125_000)
    assert submitted["expected_cash"] == 130_000
    assert submitted["variance"] == -5_000
    assert submitted["status"] == "PENDING_REVIEW"
    other_staff=_actor(db_conn,scenario,role=Role.STAFF,name="Other cashier",scenario_staff=False)
    service.open_shift(other_staff,0)
    assert {item["employee_id"] for item in service.overview(staff)["shifts"]} == {staff.employee_id}
    assert {staff.employee_id,other_staff.employee_id}.issubset(
        {item["employee_id"] for item in service.overview(manager)["shifts"]})
    with pytest.raises(PermissionDeniedError): service.review(staff,shift["id"],"Tự duyệt")
    assert service.review(manager,shift["id"],"Đã kiểm tra biên bản")["status"] == "CLOSED"


def test_machine_incident_full_lifecycle(db_conn, test_scenario):
    scenario=test_scenario(db_conn); staff=_actor(db_conn,scenario,role=Role.STAFF,name="Technician")
    manager=_actor(db_conn,scenario,role=Role.MANAGER,name="Manager")
    service=MaintenanceService(transaction_factory=_boundary(db_conn))
    incident=service.report(staff,machine_id=scenario.machine_id,severity="HIGH",
        title="Máy không khởi động",description="Nguồn máy không phản hồi")
    service.transition(manager,incident["id"],status="ASSIGNED",assigned_to=staff.employee_id,note="Phân công kiểm tra")
    service.transition(staff,incident["id"],status="IN_PROGRESS",note="Đang kiểm tra nguồn")
    assert rows(db_conn,"SELECT status FROM machines WHERE id=%s",(scenario.machine_id,))[0]["status"] == "MAINTENANCE"
    service.transition(staff,incident["id"],status="COMPLETED",note="Đã thay nguồn",
        resolution="Thay bộ nguồn mới",labor_cost=100_000,
        parts=[{"name":"Nguồn 650W","quantity":1,"unit_cost":900_000}])
    with pytest.raises(PermissionDeniedError):
        service.transition(staff,incident["id"],status="VERIFIED",note="Tự nghiệm thu")
    verified=service.transition(manager,incident["id"],status="VERIFIED",note="Chạy ổn định")
    assert verified["parts_cost"] == 900_000
    assert rows(db_conn,"SELECT status FROM machines WHERE id=%s",(scenario.machine_id,))[0]["status"] == "AVAILABLE"


def test_procurement_receipt_updates_stock_and_payable(db_conn, test_scenario):
    scenario=test_scenario(db_conn)
    inventory=_actor(db_conn,scenario,role=Role.INVENTORY,name="Inventory")
    manager=_actor(db_conn,scenario,role=Role.MANAGER,name="Manager")
    ingredient_id=execute(db_conn,"INSERT INTO inventory_ingredients(store_id,code,name,unit,reorder_point) "
        "VALUES(%s,%s,'Cà phê','g',100)",(scenario.store_id,f"ING-{scenario.token}"))
    shifts=CashShiftService(transaction_factory=_boundary(db_conn))
    service=ProcurementService(transaction_factory=_boundary(db_conn),shifts=shifts)
    supplier=service.save_supplier(manager,code=f"SUP-{scenario.token}",name="Nhà cung cấp A",
        phone="0900000000",email=None,address=None,payment_terms_days=7,is_active=True)
    request=service.create_request(inventory,reason="Tồn kho dưới ngưỡng",
        lines=[{"ingredient_id":ingredient_id,"quantity":1000}])
    with pytest.raises(PermissionDeniedError): service.decide_request(inventory,request["id"],True)
    service.decide_request(manager,request["id"],True)
    order=service.create_order(manager,request_id=request["id"],supplier_id=supplier["id"],
        expected_at=None,lines=[{"ingredient_id":ingredient_id,"quantity":1000,"unit_cost":200}])
    receipt_request_id=str(uuid4())
    result=service.receive(inventory,order["id"],request_id=receipt_request_id,note="Nhận đủ",
        lines=[{"ingredient_id":ingredient_id,"accepted_quantity":1000,"damaged_quantity":0,"missing_quantity":0}])
    retried=service.receive(inventory,order["id"],request_id=receipt_request_id,note="Retry",
        lines=[{"ingredient_id":ingredient_id,"accepted_quantity":1000,"damaged_quantity":0,"missing_quantity":0}])
    assert retried["receipt_id"] == result["receipt_id"]
    assert rows(db_conn,"SELECT on_hand FROM inventory_ingredients WHERE id=%s",(ingredient_id,))[0]["on_hand"] == 1000
    payable=rows(db_conn,"SELECT * FROM supplier_payables WHERE receipt_id=%s",(result["receipt_id"],))[0]
    shifts.open_shift(manager,500_000)
    paid=service.pay_payable(manager,payable["id"],"CASH")
    assert paid["status"] == "PAID"
    assert rows(db_conn,"SELECT kind,amount FROM cash_shift_entries WHERE source_type='SUPPLIER_PAYABLE'",())[0] == {"kind":"EXPENSE","amount":200_000}
