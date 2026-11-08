"""Factory tạo ServiceBundle mock cho UI, gallery và test."""

from __future__ import annotations

from cyberhub_manager.services.contracts import ServiceBundle

from .auth import MockAuthService
from .clock import MockClock
from .customers import MockCustomerService
from .fixtures import seed_empty, seed_success
from .machines import MockMachineService
from .reports import MockReportService
from .scenarios import MockScenario
from .sessions import MockSessionService
from .store import MockDataStore
from .wallet import MockWalletService


def build_mock_services(
    scenario: MockScenario = MockScenario.SUCCESS,
    *,
    clock: MockClock | None = None,
    p1: bool = False,
    customer_offers: bool = False,
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
    from .p1 import MemoryP1Repository
    from cyberhub_manager.services.management_service import ManagementService
    from cyberhub_manager.services.portal_service import PortalService
    if p1:
        from cyberhub_manager.domain.models import Employee, Store
        from cyberhub_manager.domain.enums import EmployeeStatus, Role, StoreStatus
        from cyberhub_manager.security import hash_password
        from .fixtures import DEMO_PASSWORD
        admin_id = data.next_id("employee")
        data.employees[admin_id] = Employee(admin_id,data.make_code("employee",admin_id),"Quản trị CyberHub",1,"admin01",Role.ADMIN,EmployeeStatus.ACTIVE)
        data.employee_passwords["admin01"] = DEMO_PASSWORD
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
    if customer_offers:
        repo.room_types.update({machine.id:'VIP' for machine in data.machines.values() if machine.id>15})
    return ServiceBundle(
        auth=MockAuthService(data, clock, scenario),
        customers=MockCustomerService(data, clock, scenario),
        wallet=MockWalletService(data, clock, scenario),
        machines=MockMachineService(data, clock, scenario),
        sessions=MockSessionService(data, clock, scenario),
        reports=MockReportService(data, clock, scenario),
        management=ManagementService(repo=repo,transaction_factory=repo.transaction),
        portal=PortalService(repo=repo,transaction_factory=repo.transaction,clock=clock.now),
    )
