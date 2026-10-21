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
    return ServiceBundle(
        auth=MockAuthService(data, clock, scenario),
        customers=MockCustomerService(data, clock, scenario),
        wallet=MockWalletService(data, clock, scenario),
        machines=MockMachineService(data, clock, scenario),
        sessions=MockSessionService(data, clock, scenario),
        reports=MockReportService(data, clock, scenario),
    )
