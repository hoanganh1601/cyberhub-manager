"""Chuẩn hóa thông báo phản hồi (feedback messages) bằng tiếng Anh cho UI CyberHub Manager.

Quy định bổ sung theo review NG01-08:
- Mọi thông báo Toast, dialog xác nhận, loading, empty, error, retry, validation đều dùng tiếng Anh nhất quán.
- Cung cấp hàm ánh xạ an toàn từ ApplicationError sang thông báo người dùng,
  không làm lộ raw traceback, exception message nội bộ hoặc câu lệnh SQL.
"""

from __future__ import annotations

from typing import Any

from ..domain.exceptions import ApplicationError

# ==============================================================================
# 1. CÁC THÔNG BÁO PHẢN HỒI MẪU (FEEDBACK & STATUS STRINGS)
# ==============================================================================
MSG_PROCESSING = "Processing…"
MSG_LOADING = "Loading data…"
MSG_NO_DATA = "No matching data found"
MSG_UNABLE_TO_LOAD = "Unable to load data"
MSG_RETRY = "Retry"
MSG_CONFIRM = "Confirm"
MSG_CANCEL = "Cancel"
MSG_ARE_YOU_SURE = "Are you sure you want to proceed?"
MSG_INVALID_CREDENTIALS = "Invalid username or password"
MSG_ACTION_SUCCESS = "Operation completed successfully."
MSG_OPERATION_FAILED = "Operation failed. Please try again."

# ==============================================================================
# 2. ÁNH XẠ MÃ LỖI NGHIỆP VỤ (ERROR CODES TO ENGLISH USER-FACING MESSAGES)
# ==============================================================================
ERROR_CODE_MESSAGES: dict[str, str] = {
    "AUTH_INVALID_CREDENTIALS": "Invalid username or password.",
    "VALIDATION_ERROR": "Invalid data provided. Please check the highlighted fields.",
    "NOT_FOUND": "Requested resource was not found.",
    "CONFLICT": "Operation conflict. Another transaction or update may have occurred.",
    "PERMISSION_DENIED": "You do not have permission to perform this action.",
    "INSUFFICIENT_BALANCE": "Insufficient balance to perform this operation.",
    "SETTLEMENT_REQUIRED": "Outstanding balance settlement is required before proceeding.",
    "SERVICE_UNAVAILABLE": "Service is temporarily unavailable. Please try again later.",
}


def get_user_friendly_error(error: Exception | str | None) -> str:
    """Chuyển đổi exception hoặc error code sang câu tiếng Anh an toàn cho người dùng.

    Không bao giờ để lộ SQL query, stack trace hoặc lỗi kỹ thuật sâu ra giao diện.
    """
    if error is None:
        return ""
    if isinstance(error, ApplicationError):
        if error.code in ERROR_CODE_MESSAGES:
            return ERROR_CODE_MESSAGES[error.code]
        # Nếu có thông điệp tiếng Anh an toàn định sẵn
        return error.message or MSG_OPERATION_FAILED

    if isinstance(error, str):
        if error in ERROR_CODE_MESSAGES:
            return ERROR_CODE_MESSAGES[error]
        return error

    # Fallback cho các ngoại lệ chưa định danh hoặc lỗi hệ thống
    return MSG_OPERATION_FAILED


def get_field_errors_safe(error: Exception | None) -> dict[str, str]:
    """Trích xuất lỗi từng trường nếu có từ ApplicationError/ValidationError."""
    if isinstance(error, ApplicationError) and error.field_errors:
        return dict(error.field_errors)
    return {}
