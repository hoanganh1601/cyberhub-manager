"""Kịch bản mock và bảng operation bị tác động.

Đây là nguồn duy nhất quyết định operation nào lỗi trong từng kịch bản;
mock service, README và unit test đều dựa vào bảng này.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from cyberhub_manager.domain.exceptions import (
    ApplicationError,
    ConflictError,
    ServiceUnavailableError,
    ValidationError,
)


class MockScenario(StrEnum):
    SUCCESS = "SUCCESS"
    EMPTY = "EMPTY"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CONFLICT = "CONFLICT"
    UNAVAILABLE = "UNAVAILABLE"


_UNAVAILABLE_MESSAGE = "Không tải được dữ liệu, vui lòng thử lại"

# Mỗi giá trị là hàm tạo exception mới cho mỗi lần raise,
# tránh dùng lại một instance exception giữa các lần gọi.
_FAILURES: dict[MockScenario, dict[str, Callable[[], ApplicationError]]] = {
    MockScenario.SUCCESS: {},
    MockScenario.EMPTY: {},
    MockScenario.VALIDATION_ERROR: {
        "create_customer": lambda: ValidationError(
            field_errors={
                "phone": "Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0",
                "password": "Mật khẩu phải có ít nhất 6 ký tự",
            }
        ),
        "update_customer": lambda: ValidationError(
            field_errors={"full_name": "Họ tên phải có từ 2 đến 100 ký tự"}
        ),
        "top_up": lambda: ValidationError(
            field_errors={"amount": "Số tiền nạp phải là số nguyên lớn hơn 0"}
        ),
        "create_machine": lambda: ValidationError(
            field_errors={"hourly_rate": "Đơn giá phải là số nguyên lớn hơn 0"}
        ),
    },
    MockScenario.CONFLICT: {
        "create_customer": lambda: ConflictError(
            "Số điện thoại đã được sử dụng",
            field_errors={"phone": "Số điện thoại đã được sử dụng"},
        ),
        "open_session": lambda: ConflictError(
            "Máy đã có phiên đang hoạt động",
            field_errors={"machine_id": "Máy đã có phiên đang hoạt động"},
        ),
        "create_machine": lambda: ConflictError(
            "Mã máy đã tồn tại",
            field_errors={"code": "Mã máy đã tồn tại"},
        ),
    },
    MockScenario.UNAVAILABLE: {
        operation: (lambda: ServiceUnavailableError(_UNAVAILABLE_MESSAGE))
        for operation in (
            "search_customers",
            "get_history",
            "list_machines",
            "list_invoices",
            "daily_revenue",
        )
    },
}

AFFECTED_OPERATIONS: dict[MockScenario, frozenset[str]] = {
    scenario: frozenset(failures) for scenario, failures in _FAILURES.items()
}


def scenario_error(
    scenario: MockScenario, operation: str
) -> ApplicationError | None:
    """Trả exception cần raise cho operation, hoặc None nếu chạy bình thường."""

    factory = _FAILURES[scenario].get(operation)
    return None if factory is None else factory()
