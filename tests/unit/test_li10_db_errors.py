"""Unit tests cho LI-10 — phân loại lỗi MySQL, đổi sang lỗi nghiệp vụ và chạy lại khi deadlock."""

from __future__ import annotations

import logging

import pytest
from mysql.connector import errorcode
from mysql.connector.errors import (
    DatabaseError,
    IntegrityError,
    InterfaceError,
    OperationalError,
    PoolError,
    ProgrammingError,
)

from cyberhub_manager.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
)
from cyberhub_manager.services import db_errors
from cyberhub_manager.services.db_errors import (
    DbErrorKind,
    classify,
    constraint_name,
    retry_on_transient,
    to_application_error,
    translate_db_errors,
    transient_kind,
)

# Thông báo giống hệt MySQL 8.4 trả về.
DUP_PHONE = IntegrityError(
    msg="Duplicate entry '0912345678' for key 'customers.uq_customers_phone'",
    errno=errorcode.ER_DUP_ENTRY,
)
FK_EMPLOYEE = IntegrityError(
    msg=(
        "Cannot add or update a child row: a foreign key constraint fails "
        "(`cyberhub_manager`.`account_transactions`, CONSTRAINT `fk_account_transactions_employee` "
        "FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`))"
    ),
    errno=errorcode.ER_NO_REFERENCED_ROW_2,
)
DEADLOCK = DatabaseError(
    msg="Deadlock found when trying to get lock; try restarting transaction",
    errno=errorcode.ER_LOCK_DEADLOCK,
)
LOCK_TIMEOUT = DatabaseError(
    msg="Lock wait timeout exceeded; try restarting transaction",
    errno=errorcode.ER_LOCK_WAIT_TIMEOUT,
)
SERVER_DOWN = InterfaceError(
    msg="Can't connect to MySQL server on '127.0.0.1:3308' (10061)",
    errno=errorcode.CR_CONN_HOST_ERROR,
)
NO_TABLE = ProgrammingError(
    msg="Table 'cyberhub_manager.employees' doesn't exist",
    errno=errorcode.ER_NO_SUCH_TABLE,
)
DUPLICATES = {"uq_customers_phone": ("phone", "Số điện thoại đã được dùng")}


@pytest.fixture
def no_wait(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Ghi lại thời gian chờ giữa các lần chạy lại thay vì sleep thật."""
    waits: list[float] = []
    monkeypatch.setattr(db_errors, "_sleep", waits.append)
    return waits


# ----------------------------------------------------------------------
# Phân loại
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (DUP_PHONE, DbErrorKind.DUPLICATE),
        (FK_EMPLOYEE, DbErrorKind.FOREIGN_KEY),
        (IntegrityError(msg="x", errno=errorcode.ER_ROW_IS_REFERENCED_2), DbErrorKind.FOREIGN_KEY),
        (DEADLOCK, DbErrorKind.DEADLOCK),
        (LOCK_TIMEOUT, DbErrorKind.LOCK_TIMEOUT),
        (SERVER_DOWN, DbErrorKind.CONNECTION),
        (OperationalError(msg="Lost connection", errno=errorcode.CR_SERVER_LOST), DbErrorKind.CONNECTION),
        (OperationalError(msg="gone away", errno=errorcode.CR_SERVER_GONE_ERROR), DbErrorKind.CONNECTION),
        (PoolError(msg="Failed getting connection; pool exhausted"), DbErrorKind.CONNECTION),
        (NO_TABLE, DbErrorKind.OTHER),
        (InterfaceError(msg="mất kết nối"), DbErrorKind.OTHER),  # không có errno
        (ValueError("không phải lỗi MySQL"), DbErrorKind.OTHER),
    ],
)
def test_classify(error: BaseException, kind: DbErrorKind) -> None:
    assert classify(error) is kind


def test_constraint_name() -> None:
    assert constraint_name(DUP_PHONE) == "uq_customers_phone"
    assert constraint_name(IntegrityError(msg="Duplicate entry for key 'uq_machines_code'", errno=1062)) == (
        "uq_machines_code"  # MySQL cũ / test cũ: không có tiền tố tên bảng
    )
    assert constraint_name(FK_EMPLOYEE) == "fk_account_transactions_employee"
    assert constraint_name(DEADLOCK) is None


# ----------------------------------------------------------------------
# Đổi sang lỗi nghiệp vụ
# ----------------------------------------------------------------------
def test_declared_duplicate_becomes_field_conflict() -> None:
    error = to_application_error(DUP_PHONE, duplicates=DUPLICATES)
    assert isinstance(error, ConflictError)
    assert error.field_errors == {"phone": "Số điện thoại đã được dùng"}


def test_undeclared_duplicate_is_unexpected(caplog: pytest.LogCaptureFixture) -> None:
    error = to_application_error(DUP_PHONE)  # service không khai báo key này
    assert isinstance(error, ServiceUnavailableError)
    assert error.details == {"db_error": "duplicate", "errno": 1062}
    assert caplog.records[-1].levelno == logging.ERROR and caplog.records[-1].exc_info


def test_foreign_key_uses_service_factory() -> None:
    assert isinstance(to_application_error(FK_EMPLOYEE, on_foreign_key=PermissionDeniedError), PermissionDeniedError)
    assert isinstance(to_application_error(FK_EMPLOYEE), ServiceUnavailableError)


@pytest.mark.parametrize("error", [SERVER_DOWN, DEADLOCK, LOCK_TIMEOUT])
def test_operational_errors_warn_without_traceback(error, caplog: pytest.LogCaptureFixture) -> None:
    result = to_application_error(error)
    assert isinstance(result, ServiceUnavailableError)
    record = caplog.records[-1]
    assert record.levelno == logging.WARNING
    assert record.exc_info is None  # không có traceback dài cho sự cố vận hành


def test_unexpected_error_logs_traceback_but_message_stays_generic(caplog: pytest.LogCaptureFixture) -> None:
    result = to_application_error(NO_TABLE)
    assert isinstance(result, ServiceUnavailableError)
    assert "employees" not in result.message  # UI không thấy tên bảng
    assert "employees" in caplog.text  # nhưng log có đủ để sửa
    assert caplog.records[-1].levelno == logging.ERROR


def test_translate_db_errors_keeps_cause_and_lets_business_errors_through() -> None:
    with pytest.raises(ConflictError) as info:
        with translate_db_errors(duplicates=DUPLICATES):
            raise DUP_PHONE
    assert info.value.__cause__ is DUP_PHONE

    with pytest.raises(NotFoundError):  # lỗi nghiệp vụ không bị đổi kiểu
        with translate_db_errors(duplicates=DUPLICATES):
            raise NotFoundError()


# ----------------------------------------------------------------------
# Chạy lại khi deadlock
# ----------------------------------------------------------------------
def test_transient_kind_follows_cause_chain() -> None:
    try:
        with translate_db_errors():
            raise DEADLOCK
    except ServiceUnavailableError as wrapped:
        assert transient_kind(wrapped) is DbErrorKind.DEADLOCK
    assert transient_kind(LOCK_TIMEOUT) is None  # mặc định không chạy lại
    assert transient_kind(LOCK_TIMEOUT, frozenset({DbErrorKind.LOCK_TIMEOUT})) is DbErrorKind.LOCK_TIMEOUT
    assert transient_kind(ServiceUnavailableError()) is None  # không có nguyên nhân MySQL
    assert transient_kind(NotFoundError()) is None


def test_retry_succeeds_after_deadlock(no_wait: list[float], caplog: pytest.LogCaptureFixture) -> None:
    calls: list[int] = []

    @retry_on_transient
    def top_up() -> str:
        calls.append(1)
        if len(calls) < 3:
            with translate_db_errors():  # giống service: lỗi MySQL đã bị đổi kiểu trước khi tới decorator
                raise DEADLOCK
        return "ok"

    assert top_up() == "ok"
    assert len(calls) == 3
    assert no_wait == list(db_errors.RETRY_DELAYS)
    assert "chạy lại lần 2/3" in caplog.text


def test_retry_gives_up_and_reraises_last_error(no_wait: list[float]) -> None:
    calls: list[int] = []

    @retry_on_transient(delays=(0.01,))
    def checkout() -> None:
        calls.append(1)
        raise DEADLOCK

    with pytest.raises(DatabaseError) as info:
        checkout()
    assert info.value is DEADLOCK
    assert len(calls) == 2
    assert no_wait == [0.01]


@pytest.mark.parametrize("error", [ConflictError("đã có người thanh toán"), LOCK_TIMEOUT, SERVER_DOWN, ValueError("bug")])
def test_no_retry_for_business_or_non_deadlock_errors(error: Exception, no_wait: list[float]) -> None:
    calls: list[int] = []

    @retry_on_transient
    def operation() -> None:
        calls.append(1)
        raise error

    with pytest.raises(type(error)):
        operation()
    assert len(calls) == 1
    assert no_wait == []


def test_retry_keeps_method_metadata_and_arguments(no_wait: list[float]) -> None:
    class Service:
        def __init__(self) -> None:
            self.attempts = 0

        @retry_on_transient
        def open_session(self, machine_id: int, *, customer_id: int) -> tuple[int, int]:
            """Mở phiên."""
            self.attempts += 1
            if self.attempts == 1:
                raise DEADLOCK
            return machine_id, customer_id

    service = Service()
    assert service.open_session(3, customer_id=7) == (3, 7)
    assert Service.open_session.__name__ == "open_session"
    assert Service.open_session.__doc__ == "Mở phiên."
