"""Factory tạo ServiceBundle mock cho UI, gallery và test."""

from __future__ import annotations

from cyberhub_manager.services.contracts import ServiceBundle

from .application_services import (
    MockAuthService,
    MockCustomerService,
    MockMachineService,
    MockReportService,
    MockSessionService,
    MockWalletService,
)
from .clock import MockClock
from .demo_data import DEMO_PASSWORD, MockDataStore, MockScenario, seed_empty, seed_success
from .repositories import (
    MemoryMenuRepository,
    MemoryP1Repository,
)


# Demo prices in VND per hour for each PC. Change these values, restart the
# demo server and sign in again to create a workspace with the new rates.
# Real MySQL machine prices are managed separately in Machine management.
DEMO_ROOM_HOURLY_RATES = {
    "STANDARD": 10_000,
    "VIP": 20_000,
    "COUPLE": 25_000,
    "SUPER_VIP": 35_000,
}


def build_mock_services(
    scenario: MockScenario = MockScenario.SUCCESS,
    *,
    clock: MockClock | None = None,
    p1: bool = False,
    customer_offers: bool = False,
    pos_samples: bool = False,
) -> ServiceBundle:
    """Tạo một bộ dữ liệu demo mới và sáu mock service dùng chung bộ dữ liệu đó.

    Mỗi lần gọi trả bundle độc lập; gọi lại factory để reset dữ liệu.
    Truyền `clock` khi cần điều khiển thời gian từ bên ngoài.
    """

    scenario = MockScenario(scenario)
    if clock is None:
        clock = MockClock()
    data = MockDataStore()
    seed = seed_empty if scenario == MockScenario.EMPTY else seed_success
    seed(data, clock.now())
    from cyberhub_manager.services.management_service import ManagementService
    from cyberhub_manager.services.portal_service import PortalService
    if p1:
        from cyberhub_manager.domain.models import Employee, Store
        from cyberhub_manager.domain.enums import EmployeeStatus, Role, StoreStatus
        from cyberhub_manager.security import hash_password
        admin_id = data.next_id("employee")
        data.employees[admin_id] = Employee(admin_id,data.make_code("employee",admin_id),"Quản trị CyberHub",1,"admin01",Role.ADMIN,EmployeeStatus.ACTIVE)
        data.employee_passwords["admin01"] = DEMO_PASSWORD
        director_id = data.next_id("employee")
        data.employees[director_id] = Employee(director_id,data.make_code("employee",director_id),"Giám đốc CyberHub",1,"giamdoc01",Role.DIRECTOR,EmployeeStatus.ACTIVE)
        data.employee_passwords["giamdoc01"] = DEMO_PASSWORD
        store_id = data.next_id("store")
        data.stores[store_id] = Store(store_id,data.make_code("store",store_id),"CyberHub Hà Đông","Hà Đông, Hà Nội",StoreStatus.ACTIVE,clock.now(),clock.now())
        password_hash = hash_password(DEMO_PASSWORD)
        data.customer_password_hashes.update({c.account.id:password_hash for c in data.customers.values()})
        if customer_offers:
            from datetime import timedelta
            from cyberhub_manager.domain.p1 import Promotion

            for code, threshold, percent in (("DEMO100", 100000, 10), ("DEMO200", 200000, 20)):
                entity_id = data.next_id("promotion")
                data.promotions[entity_id] = Promotion(
                    entity_id, code, "CyberHub " + str(percent) + "%", None,
                    threshold, percent, clock.now()-timedelta(days=1), clock.now()+timedelta(days=7))
    repo = MemoryP1Repository(data)
    if p1:
        # Demo location: eight standard PCs, two four-PC VIP rooms, one
        # two-PC couple room and two private single-PC super-VIP rooms.
        repo.room_types.update({machine.id: (
            "SUPER_VIP" if machine.id in (19, 20) else
            "COUPLE" if machine.id in (17, 18) else
            "VIP" if 9 <= machine.id <= 16 else
            "STANDARD"
        ) for machine in data.machines.values()})
        for machine in data.machines.values():
            machine.update_info(
                machine.name, DEMO_ROOM_HOURLY_RATES[repo.room_types[machine.id]]
            )
    # Đợt 1: menu demo cho mọi cơ sở, dùng chung khóa/transaction với repo P1.
    from cyberhub_manager.services.menu_service import MenuService
    menu_repo = MemoryMenuRepository(data, repo, clock=clock.now)
    menu_repo.seed_demo()
    if pos_samples and scenario == MockScenario.SUCCESS:
        menu_repo.seed_pos_orders()
    # Đợt 2: danh mục phần thưởng + voucher mẫu.
    return ServiceBundle(
        auth=MockAuthService(data, clock, scenario),
        customers=MockCustomerService(data, clock, scenario),
        wallet=MockWalletService(data, clock, scenario),
        machines=MockMachineService(data, clock, scenario),
        sessions=MockSessionService(data, clock, scenario),
        reports=MockReportService(data, clock, scenario),
        management=ManagementService(repo=repo,transaction_factory=repo.transaction),
        portal=PortalService(repo=repo,transaction_factory=repo.transaction,clock=clock.now),
        menu=MenuService(repo=menu_repo,p1_repo=repo,
                         transaction_factory=menu_repo.transaction,clock=clock.now),

    )
