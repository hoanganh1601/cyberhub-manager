"""Lớp cha và helper kiểm tra dùng chung cho sáu mock service.

Thứ tự kiểm tra trong mỗi operation: quyền → kịch bản → tìm đối tượng →
validate → xung đột → ghi dữ liệu. Chỉ ghi khi mọi kiểm tra đã qua để thao tác
thất bại không để lại thay đổi dở dang.
"""

from __future__ import annotations

import re
from datetime import datetime

from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.enums import (
    EmployeeStatus,
    PaymentMethod,
    Role,
    TransactionType,
)
from cyberhub_manager.domain.exceptions import (
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.models import AccountTransaction, Employee

from .clock import MockClock
from .scenarios import MockScenario, scenario_error
from .store import MockDataStore

MANAGER_ROLES = frozenset({Role.MANAGER, Role.ADMIN})
CASH_METHODS = frozenset({PaymentMethod.CASH, PaymentMethod.TRANSFER})

_PHONE_PATTERN = re.compile(r"0[0-9]{9}")
_USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_.]{4,30}")


# ----- Validate từng trường, trả thông báo lỗi hoặc None --------------------


def full_name_error(value: str) -> str | None:
    if not 2 <= len(value) <= 100:
        return "Họ tên phải có từ 2 đến 100 ký tự"
    return None


def phone_error(value: str) -> str | None:
    if _PHONE_PATTERN.fullmatch(value) is None:
        return "Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0"
    return None


def username_error(value: str) -> str | None:
    if _USERNAME_PATTERN.fullmatch(value) is None:
        return (
            "Tên đăng nhập phải dài 4-30 ký tự và chỉ gồm "
            "chữ, số, dấu gạch dưới hoặc dấu chấm"
        )
    return None


def password_error(value: str) -> str | None:
    if not isinstance(value, str) or len(value) < 6:
        return "Mật khẩu phải có ít nhất 6 ký tự"
    return None


def positive_int_error(
    value: int, label: str, *, maximum: int | None = None
) -> str | None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return f"{label} phải là số nguyên lớn hơn 0"
    if maximum is not None and value > maximum:
        return f"{label} không được vượt quá {maximum:,}".replace(",", ".")
    return None


def cash_method_error(method: PaymentMethod | None) -> str | None:
    if method not in CASH_METHODS:
        return "Phương thức chỉ được là tiền mặt hoặc chuyển khoản"
    return None


def raise_if_errors(errors: dict[str, str | None]) -> None:
    """Gom mọi lỗi trường vào một ValidationError để UI đánh dấu cùng lúc."""

    field_errors = {
        field: message for field, message in errors.items() if message
    }
    if field_errors:
        raise ValidationError(field_errors=field_errors)


def clean_text(value: str) -> str:
    return value.strip() if isinstance(value, str) else ""


# ----- Lớp cha ---------------------------------------------------------------


class MockServiceBase:
    def __init__(
        self,
        data: MockDataStore,
        clock: MockClock,
        scenario: MockScenario,
    ) -> None:
        self._data = data
        self._clock = clock
        self._scenario = scenario

    def _check_scenario(self, operation: str) -> None:
        error = scenario_error(self._scenario, operation)
        if error is not None:
            raise error

    def _require_actor(self, actor: EmployeeSession) -> Employee:
        """Không tin actor tùy ý: phải khớp nhân viên ACTIVE trong kho."""

        employee = self._data.employees.get(getattr(actor, "employee_id", None))
        if (
            employee is None
            or employee.status != EmployeeStatus.ACTIVE
            or employee.store_id != actor.store_id
            or employee.role != actor.role
        ):
            raise PermissionDeniedError()
        return employee

    def _require_manager(self, actor: EmployeeSession) -> Employee:
        employee = self._require_actor(actor)
        if employee.role not in MANAGER_ROLES:
            raise PermissionDeniedError()
        return employee

    @staticmethod
    def _require_store(actor: EmployeeSession, store_id: int) -> None:
        if actor.store_id != store_id:
            raise PermissionDeniedError(
                "Bạn chỉ được thao tác dữ liệu của cửa hàng hiện tại"
            )

    def _new_transaction(
        self,
        account_id: int,
        employee_id: int,
        session_id: int | None,
        type: TransactionType,
        amount: int,
        method: PaymentMethod,
        at: datetime,
    ) -> AccountTransaction:
        """Dựng giao dịch nhưng chưa lưu; caller lưu sau khi mọi bước hợp lệ."""

        transaction_id = self._data.next_id("transaction")
        return AccountTransaction(
            id=transaction_id,
            code=self._data.make_code("transaction", transaction_id),
            account_id=account_id,
            employee_id=employee_id,
            session_id=session_id,
            type=type,
            amount=amount,
            method=method,
            created_at=at,
        )
