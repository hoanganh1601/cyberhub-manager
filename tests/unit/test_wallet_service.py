"""LI-04 — Unit test cho WalletService, dùng repository giả nên không cần MySQL."""

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from mysql.connector import errorcode
from mysql.connector.errors import IntegrityError, InterfaceError

from cyberhub_manager.domain.dtos import EmployeeSession, TransactionSummary
from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    PaymentMethod,
    Role,
    TransactionType,
)
from cyberhub_manager.domain.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationError,
)
from cyberhub_manager.domain.models import Account, Customer
from cyberhub_manager.services.contracts import WalletServiceProtocol
from cyberhub_manager.services.wallet_service import (
    MAX_TOP_UP_AMOUNT,
    WalletService,
    new_transaction_code,
)

CUSTOMER_ID = 1
ACCOUNT_ID = 10
EMPLOYEE_ID = 5
STORE_ID = 3
OTHER_STORE_ID = 4


# ----- Đồ giả ----------------------------------------------------------------


def make_actor(employee_id=EMPLOYEE_ID, store_id=STORE_ID, role=Role.STAFF):
    return EmployeeSession(
        employee_id=employee_id,
        employee_code="NV005",
        full_name="Nhân viên test",
        username="staff05",
        store_id=store_id,
        store_code="CH01",
        store_name="Cửa hàng test",
        role=role,
    )


STAFF = make_actor()


def make_customer(balance=5_000, account_status=AccountStatus.ACTIVE):
    account = Account(
        id=ACCOUNT_ID,
        code="ACC001",
        customer_id=CUSTOMER_ID,
        username="khach01",
        balance=balance,
        status=account_status,
    )
    return Customer(
        id=CUSTOMER_ID,
        code="KH001",
        full_name="Nguyễn Văn A",
        phone="0900000001",
        status=CustomerStatus.ACTIVE,
        account=account,
    )


class FakeCustomerRepository:
    def __init__(self, customer):
        self.customer = customer
        self.calls = 0

    def get_by_id(self, conn, customer_id):
        self.calls += 1
        if self.customer is not None and self.customer.id == customer_id:
            return self.customer
        return None


class FakeAccountRepository:
    def __init__(self, account):
        self.account = account
        self.locked_for_update = False
        self.credits = []
        self.inserted = []
        self.history = []
        self.insert_error = None

    def get_by_id(self, conn, account_id, *, for_update=False):
        self.locked_for_update = for_update
        return self.account

    def credit_balance(self, conn, account_id, amount):
        self.credits.append(amount)
        return True

    def insert_top_up_transaction(
        self, conn, *, code, account_id, employee_id, amount, method
    ):
        if self.insert_error is not None:
            raise self.insert_error
        transaction_id = len(self.inserted) + 1
        self.inserted.append(
            {"code": code, "employee_id": employee_id, "method": method}
        )
        self.history.insert(
            0,
            TransactionSummary(
                transaction_id=transaction_id,
                transaction_code=code,
                account_id=account_id,
                session_id=None,
                type=TransactionType.TOP_UP,
                amount=amount,
                method=method,
                employee_id=employee_id,
                employee_name="Nhân viên test",
                created_at=datetime.now(timezone.utc),
            ),
        )
        return transaction_id

    def list_transactions(self, conn, account_id, *, limit=50):
        return self.history[:limit]


class FakeAuthRepository:
    """Giả HA-05: trả None khi nhân viên hoặc cửa hàng không còn ACTIVE."""

    def __init__(self, current):
        self.current = current
        self.lookups = []

    def get_active_session_by_id(self, conn, employee_id):
        self.lookups.append(employee_id)
        if self.current is None or self.current.employee_id != employee_id:
            return None
        return self.current


class FakeTransaction:
    """Thay database.transaction.transaction(); ghi lại số lần mở và rollback."""

    def __init__(self):
        self.calls = 0
        self.rolled_back = False

    @contextmanager
    def __call__(self):
        self.calls += 1
        try:
            yield object()
        except BaseException:
            self.rolled_back = True
            raise


def build_wallet(customer=None, actor=STAFF, current=STAFF, with_provider=True):
    """actor: provider trả về gì; current: HA-05 tra DB thấy gì."""

    customer = customer if customer is not None else make_customer()
    customers = FakeCustomerRepository(customer)
    accounts = FakeAccountRepository(customer.account)
    auth = FakeAuthRepository(current)
    tx = FakeTransaction()
    service = WalletService(
        customer_repo=customers,
        account_repo=accounts,
        auth_repo=auth,
        actor_provider=(lambda: actor) if with_provider else None,
        transaction_factory=tx,
    )
    return SimpleNamespace(
        service=service, customers=customers, accounts=accounts, auth=auth, tx=tx
    )


@pytest.fixture
def wallet():
    return build_wallet()

# ----- Contract --------------------------------------------------------------


def test_wallet_service_matches_protocol():
    assert isinstance(WalletService(), WalletServiceProtocol)


def test_transaction_code_is_prefixed_unique_and_fits_column():
    codes = {new_transaction_code() for _ in range(1_000)}

    assert len(codes) == 1_000
    for code in codes:
        assert code.startswith("TX-")
        assert len(code) == 20
        int(code[3:], 16)  # phần còn lại là hex


# ----- Validation ------------------------------------------------------------


@pytest.mark.parametrize(
    "amount", [0, -1, MAX_TOP_UP_AMOUNT + 1, True, False, 1.5, "10000", None]
)
def test_top_up_rejects_invalid_amount_before_touching_database(wallet, amount):
    with pytest.raises(ValidationError) as exc_info:
        wallet.service.top_up(CUSTOMER_ID, amount, PaymentMethod.CASH, EMPLOYEE_ID)

    assert set(exc_info.value.field_errors) == {"amount"}
    assert wallet.tx.calls == 0


@pytest.mark.parametrize("amount", [1, MAX_TOP_UP_AMOUNT])
def test_top_up_accepts_amount_boundaries(wallet, amount):
    result = wallet.service.top_up(
        CUSTOMER_ID, amount, PaymentMethod.CASH, EMPLOYEE_ID
    )

    assert result.transaction.amount == amount


@pytest.mark.parametrize(
    "method",
    [
        PaymentMethod.ACCOUNT_BALANCE,
        PaymentMethod.PROMOTION,
        None,
        "CASH",
        "TRANSFER",
        "MOMO",
        [],
        {},
    ],
)
def test_top_up_rejects_invalid_method(wallet, method):
    with pytest.raises(ValidationError) as exc_info:
        wallet.service.top_up(CUSTOMER_ID, 10_000, method, EMPLOYEE_ID)

    assert set(exc_info.value.field_errors) == {"method"}
    assert wallet.tx.calls == 0
    assert wallet.accounts.credits == []
    assert wallet.accounts.inserted == []


def test_top_up_reports_amount_and_method_errors_together(wallet):
    with pytest.raises(ValidationError) as exc_info:
        wallet.service.top_up(CUSTOMER_ID, 0, None, EMPLOYEE_ID)

    assert set(exc_info.value.field_errors) == {"amount", "method"}


# def test_top_up_accepts_method_as_string(wallet):
#     result = wallet.service.top_up(CUSTOMER_ID, 10_000, "TRANSFER", EMPLOYEE_ID)

#     assert wallet.accounts.inserted[0]["method"] is PaymentMethod.TRANSFER
#     assert result.transaction.method is PaymentMethod.TRANSFER


@pytest.mark.parametrize("employee_id", [0, -1, True, "5", None])
def test_top_up_rejects_invalid_employee_id(wallet, employee_id):
    with pytest.raises(PermissionDeniedError):
        wallet.service.top_up(CUSTOMER_ID, 10_000, PaymentMethod.CASH, employee_id)

    assert wallet.tx.calls == 0


# ----- Luồng nạp tiền --------------------------------------------------------


def test_top_up_locks_account_credits_and_records_transaction(wallet):
    result = wallet.service.top_up(
        CUSTOMER_ID, 20_000, PaymentMethod.CASH, EMPLOYEE_ID
    )

    assert wallet.tx.calls == 1
    assert wallet.accounts.locked_for_update is True
    assert wallet.accounts.credits == [20_000]
    assert wallet.accounts.inserted[0]["employee_id"] == EMPLOYEE_ID
    assert wallet.accounts.inserted[0]["code"].startswith("TX-")

    assert result.customer_id == CUSTOMER_ID
    assert result.account_id == ACCOUNT_ID
    assert result.balance_before == 5_000
    assert result.balance_after == 25_000
    assert result.transaction.transaction_id == 1
    assert result.transaction.employee_id == EMPLOYEE_ID


def test_top_up_allows_locked_account_to_pay_debt():
    wallet = build_wallet(
        customer=make_customer(balance=-3_000, account_status=AccountStatus.LOCKED)
    )

    result = wallet.service.top_up(
        CUSTOMER_ID, 10_000, PaymentMethod.CASH, EMPLOYEE_ID
    )

    assert result.balance_before == -3_000
    assert result.balance_after == 7_000


def test_top_up_raises_not_found_for_unknown_customer(wallet):
    with pytest.raises(NotFoundError):
        wallet.service.top_up(999, 10_000, PaymentMethod.CASH, EMPLOYEE_ID)

    assert wallet.accounts.credits == []


# ----- Actor -----------------------------------------------------------------

DENIED_ACTORS = pytest.mark.parametrize(
    "options",
    [
        {"with_provider": False},
        {"actor": None},
        # HA-05 trả None khi nhân viên INACTIVE/LOCKED hoặc cửa hàng INACTIVE.
        {"current": None},
        {"current": make_actor(store_id=OTHER_STORE_ID)},
    ],
    ids=["no-provider", "provider-none", "not-active", "store-changed"],
)


def assert_nothing_touched(wallet):
    assert wallet.customers.calls == 0
    assert wallet.accounts.credits == []
    assert wallet.accounts.inserted == []


@DENIED_ACTORS
def test_top_up_denies_invalid_actor_without_writing(options):
    wallet = build_wallet(**options)

    with pytest.raises(PermissionDeniedError):
        wallet.service.top_up(CUSTOMER_ID, 10_000, PaymentMethod.CASH, EMPLOYEE_ID)

    assert_nothing_touched(wallet)
    assert wallet.tx.rolled_back is True


@DENIED_ACTORS
def test_get_history_denies_invalid_actor(options):
    wallet = build_wallet(**options)

    with pytest.raises(PermissionDeniedError):
        wallet.service.get_history(CUSTOMER_ID)

    assert wallet.customers.calls == 0


def test_top_up_denies_employee_id_different_from_actor(wallet):
    with pytest.raises(PermissionDeniedError):
        wallet.service.top_up(
            CUSTOMER_ID, 10_000, PaymentMethod.CASH, EMPLOYEE_ID + 1
        )

    assert_nothing_touched(wallet)
    assert wallet.auth.lookups == []


def test_top_up_rechecks_actor_against_database(wallet):
    result = wallet.service.top_up(
        CUSTOMER_ID, 10_000, PaymentMethod.CASH, EMPLOYEE_ID
    )

    assert wallet.auth.lookups == [EMPLOYEE_ID]
    assert result.balance_after == 15_000


def test_get_history_rechecks_actor_against_database(wallet):
    wallet.service.get_history(CUSTOMER_ID)

    assert wallet.auth.lookups == [EMPLOYEE_ID]


def test_top_up_maps_missing_employee_foreign_key_to_permission_error(wallet):
    wallet.accounts.insert_error = IntegrityError(
        msg="FK fail", errno=errorcode.ER_NO_REFERENCED_ROW_2
    )

    with pytest.raises(PermissionDeniedError):
        wallet.service.top_up(CUSTOMER_ID, 10_000, PaymentMethod.CASH, EMPLOYEE_ID)

    assert wallet.tx.rolled_back is True


def test_top_up_rolls_back_when_recording_transaction_fails(wallet):
    wallet.accounts.insert_error = RuntimeError("ghi giao dịch lỗi")

    with pytest.raises(RuntimeError):
        wallet.service.top_up(CUSTOMER_ID, 10_000, PaymentMethod.CASH, EMPLOYEE_ID)

    assert wallet.tx.rolled_back is True


def test_top_up_maps_database_error_to_service_unavailable(wallet):
    wallet.accounts.insert_error = InterfaceError(msg="mất kết nối")

    with pytest.raises(ServiceUnavailableError):
        wallet.service.top_up(CUSTOMER_ID, 10_000, PaymentMethod.CASH, EMPLOYEE_ID)


# ----- Lịch sử ---------------------------------------------------------------


def test_get_history_returns_empty_list_without_transactions(wallet):
    assert wallet.service.get_history(CUSTOMER_ID) == []


def test_get_history_returns_newest_first(wallet):
    wallet.service.top_up(CUSTOMER_ID, 10_000, PaymentMethod.CASH, EMPLOYEE_ID)
    wallet.service.top_up(CUSTOMER_ID, 20_000, PaymentMethod.TRANSFER, EMPLOYEE_ID)

    history = wallet.service.get_history(CUSTOMER_ID)

    assert [item.amount for item in history] == [20_000, 10_000]


@pytest.mark.parametrize("customer_id", [999, 0, True])
def test_get_history_raises_not_found_for_unknown_customer(wallet, customer_id):
    with pytest.raises(NotFoundError):
        wallet.service.get_history(customer_id)
