"""Unit test cho mock auth, customer và wallet service."""

from dataclasses import dataclass, replace

import pytest

from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    PaymentMethod,
    Role,
    TransactionType,
)
from cyberhub_manager.domain.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationError,
)
from cyberhub_manager.services.mocks.auth import MockAuthService
from cyberhub_manager.services.mocks.clock import MockClock
from cyberhub_manager.services.mocks.customers import MockCustomerService
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD, seed_success
from cyberhub_manager.services.mocks.scenarios import MockScenario
from cyberhub_manager.services.mocks.store import MockDataStore
from cyberhub_manager.services.mocks.wallet import MockWalletService


@dataclass
class Services:
    data: MockDataStore
    clock: MockClock
    auth: MockAuthService
    customers: MockCustomerService
    wallet: MockWalletService


def make_services(scenario: MockScenario = MockScenario.SUCCESS) -> Services:
    data = MockDataStore()
    clock = MockClock()
    seed_success(data, clock.now())
    return Services(
        data=data,
        clock=clock,
        auth=MockAuthService(data, clock, scenario),
        customers=MockCustomerService(data, clock, scenario),
        wallet=MockWalletService(data, clock, scenario),
    )


# ----- Auth ------------------------------------------------------------------


def test_login_returns_employee_session_for_demo_accounts() -> None:
    services = make_services()

    manager = services.auth.login("  quanly01 ", DEMO_PASSWORD)
    staff = services.auth.login("nhanvien01", DEMO_PASSWORD)

    assert manager.role == Role.MANAGER
    assert staff.role == Role.STAFF
    assert manager.store_id == staff.store_id


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("quanly01", "sai-mat-khau"),
        ("quanly01", f" {DEMO_PASSWORD}"),
        ("khongtontai", DEMO_PASSWORD),
        ("", ""),
    ],
)
def test_login_failures_use_generic_message(username: str, password: str) -> None:
    services = make_services()

    with pytest.raises(AuthenticationError) as error:
        services.auth.login(username, password)

    assert error.value.message == "Tên đăng nhập hoặc mật khẩu không đúng"


# ----- Customer --------------------------------------------------------------


def test_create_customer_is_searchable_with_zero_balance() -> None:
    services = make_services()

    customer = services.customers.create_customer(
        "Đỗ Thị Hoa", "0987654321", "dothihoa", "matkhau1"
    )
    found = services.customers.search_customers("0987654321")

    assert customer.code == "KH006"
    assert customer.account.balance == 0
    assert [c.customer_id for c in found] == [customer.id]
    assert services.wallet.get_history(customer.id) == []


def test_create_customer_reports_every_invalid_field_without_saving() -> None:
    services = make_services()

    with pytest.raises(ValidationError) as error:
        services.customers.create_customer("A", "123", "ab", "12345")

    assert set(error.value.field_errors) == {
        "full_name",
        "phone",
        "username",
        "password",
    }
    assert len(services.data.customers) == 5
    created = services.customers.create_customer(
        "Đỗ Thị Hoa", "0987654321", "dothihoa", "matkhau1"
    )
    assert created.code == "KH006"


def test_create_customer_rejects_duplicate_phone_and_username() -> None:
    services = make_services()

    with pytest.raises(ConflictError) as error:
        services.customers.create_customer(
            "Khách Trùng", "0901000001", "NguyenVanAn", "matkhau1"
        )

    assert set(error.value.field_errors) == {"phone", "username"}
    assert len(services.data.customers) == 5


def test_get_customer_returns_copy_and_missing_raises_not_found() -> None:
    services = make_services()

    customer = services.customers.get_customer(1)
    customer.deactivate()

    assert services.customers.get_customer(1).status == CustomerStatus.ACTIVE
    with pytest.raises(NotFoundError):
        services.customers.get_customer(999)


def test_search_matches_code_name_phone_username_case_insensitively() -> None:
    services = make_services()

    def codes(keyword: str) -> list[str]:
        return [c.customer_code for c in services.customers.search_customers(keyword)]

    assert codes("") == ["KH001", "KH002", "KH003", "KH004", "KH005"]
    assert codes("kh003") == ["KH003"]
    assert codes("PHẠM thị") == ["KH004"]
    assert codes("0901000005") == ["KH005"]
    assert codes("lethibinh") == ["KH002"]
    assert codes("không có ai") == []


def test_update_customer_rejects_phone_of_another_customer() -> None:
    services = make_services()

    with pytest.raises(ConflictError) as error:
        services.customers.update_customer(1, "Nguyễn Văn An", "0901000002")

    assert error.value.field_errors == {"phone": "Số điện thoại đã được sử dụng"}
    assert services.customers.get_customer(1).phone == "0901000001"

    updated = services.customers.update_customer(1, "Nguyễn Văn An Mới", "0901000001")
    assert updated.full_name == "Nguyễn Văn An Mới"


def test_staff_cannot_change_customer_status() -> None:
    services = make_services()
    staff = services.auth.login("nhanvien01", DEMO_PASSWORD)

    with pytest.raises(PermissionDeniedError):
        services.customers.set_customer_status(1, CustomerStatus.INACTIVE, staff)

    assert services.customers.get_customer(1).status == CustomerStatus.ACTIVE


def test_manager_deactivates_customer_and_locks_account() -> None:
    services = make_services()
    manager = services.auth.login("quanly01", DEMO_PASSWORD)

    customer = services.customers.set_customer_status(
        1, CustomerStatus.INACTIVE, manager
    )

    assert customer.status == CustomerStatus.INACTIVE
    assert customer.account.status == AccountStatus.LOCKED


def test_forged_actor_is_rejected() -> None:
    services = make_services()
    staff = services.auth.login("nhanvien01", DEMO_PASSWORD)
    forged = replace(staff, role=Role.MANAGER)

    with pytest.raises(PermissionDeniedError):
        services.customers.set_customer_status(1, CustomerStatus.INACTIVE, forged)


# ----- Wallet ----------------------------------------------------------------


def test_top_up_is_visible_in_customer_search_and_history() -> None:
    services = make_services()
    staff = services.auth.login("nhanvien01", DEMO_PASSWORD)

    result = services.wallet.top_up(1, 20_000, PaymentMethod.CASH, staff.employee_id)

    assert (result.balance_before, result.balance_after) == (50_000, 70_000)
    assert services.customers.search_customers("KH001")[0].balance == 70_000
    assert services.customers.get_customer(1).account.balance == 70_000
    latest = services.wallet.get_history(1)[0]
    assert latest == result.transaction
    assert latest.type == TransactionType.TOP_UP
    assert latest.created_at == services.clock.now()


@pytest.mark.parametrize(
    ("amount", "method", "field"),
    [
        (0, PaymentMethod.CASH, "amount"),
        (100_000_001, PaymentMethod.CASH, "amount"),
        (True, PaymentMethod.CASH, "amount"),
        (10_000, PaymentMethod.ACCOUNT_BALANCE, "method"),
        (10_000, None, "method"),
    ],
)
def test_invalid_top_up_changes_nothing(amount, method, field: str) -> None:
    services = make_services()
    history_before = services.wallet.get_history(1)

    with pytest.raises(ValidationError) as error:
        services.wallet.top_up(1, amount, method, 2)

    assert field in error.value.field_errors
    assert services.customers.get_customer(1).account.balance == 50_000
    assert services.wallet.get_history(1) == history_before


def test_top_up_unknown_customer_or_employee() -> None:
    services = make_services()

    with pytest.raises(NotFoundError):
        services.wallet.top_up(999, 10_000, PaymentMethod.CASH, 2)
    with pytest.raises(PermissionDeniedError):
        services.wallet.top_up(1, 10_000, PaymentMethod.CASH, 999)


# ----- Kịch bản --------------------------------------------------------------


def test_validation_scenario_only_breaks_declared_operations() -> None:
    services = make_services(MockScenario.VALIDATION_ERROR)

    with pytest.raises(ValidationError) as error:
        services.customers.create_customer(
            "Đỗ Thị Hoa", "0987654321", "dothihoa", "matkhau1"
        )
    with pytest.raises(ValidationError):
        services.wallet.top_up(1, 10_000, PaymentMethod.CASH, 2)

    assert "phone" in error.value.field_errors
    assert len(services.customers.search_customers("")) == 5
    assert services.customers.get_customer(1).account.balance == 50_000


def test_unavailable_scenario_keeps_login_working() -> None:
    services = make_services(MockScenario.UNAVAILABLE)

    assert services.auth.login("quanly01", DEMO_PASSWORD).role == Role.MANAGER
    with pytest.raises(ServiceUnavailableError):
        services.customers.search_customers("")
    with pytest.raises(ServiceUnavailableError):
        services.wallet.get_history(1)
