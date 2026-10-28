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
    "UNAVAILABLE": "Service is temporarily unavailable. Please try again later.",
}

# ==============================================================================
# 3. ÁNH XẠ MÃ / NỘI DUNG LỖI TRƯỜNG (FIELD ERROR MAPPINGS TO ENGLISH)
# ==============================================================================
FIELD_ERROR_MESSAGES: dict[str, str] = {
    # Mã lỗi chuẩn (contract codes)
    "REQUIRED": "This field is required.",
    "INVALID_FORMAT": "Invalid format.",
    "ALREADY_EXISTS": "Already exists.",
    "NOT_FOUND": "Not found.",
    "INVALID_VALUE": "Invalid value.",
    "MIN_LENGTH": "Value is too short.",
    "MAX_LENGTH": "Value is too long.",
    "DUPLICATE": "Already in use.",
    "OUT_OF_RANGE": "Value is out of range.",
    "INVALID_PHONE": "Phone number must have 10 digits starting with 0.",
    "INVALID_PASSWORD": "Password must have at least 6 characters.",
    "INVALID_FULL_NAME": "Full name must be between 2 and 100 characters.",
    "INVALID_AMOUNT": "Amount must be a positive integer.",
    "INVALID_HOURLY_RATE": "Hourly rate must be a positive integer.",
    "PHONE_TAKEN": "Phone number is already in use.",
    "MACHINE_BUSY": "Machine already has an active session.",
    "MACHINE_CODE_TAKEN": "Machine code already exists.",
    "INSUFFICIENT_FUNDS": "Insufficient balance.",

    # Các câu lỗi mock tiếng Việt hiện hữu trong mock service / scenarios (chuẩn hóa contract)
    "Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0": "Phone number must have 10 digits starting with 0.",
    "Mật khẩu phải có ít nhất 6 ký tự": "Password must have at least 6 characters.",
    "Họ tên phải có từ 2 đến 100 ký tự": "Full name must be between 2 and 100 characters.",
    "Số tiền nạp phải là số nguyên lớn hơn 0": "Top-up amount must be a positive integer.",
    "Đơn giá phải là số nguyên lớn hơn 0": "Hourly rate must be a positive integer.",
    "Số điện thoại đã được sử dụng": "Phone number is already in use.",
    "Máy đã có phiên đang hoạt động": "Machine already has an active session.",
    "Mã máy đã tồn tại": "Machine code already exists.",
    "Thời gian tính phí phải có timezone": "Calculation time must include timezone.",
    "Trạng thái khách hàng không hợp lệ": "Invalid customer status.",
    "Thời gian không hợp lệ": "Invalid date or time.",
    "ID phải là số nguyên dương": "ID must be a positive integer.",
    "Tên đăng nhập hoặc mật khẩu không đúng": "Invalid username or password.",
    "Số dư không đủ": "Insufficient balance.",
    "Cần thanh toán phần tiền còn thiếu": "Outstanding balance settlement is required.",
    "Dịch vụ hiện không khả dụng": "Service is temporarily unavailable.",
    "Không tải được dữ liệu, vui lòng thử lại": "Service is temporarily unavailable.",
    # Lỗi nghiệp vụ từ LI-03 (CustomerService) và LI-04 (WalletService)
    "USERNAME_TAKEN": "Username is already in use.",
    "INVALID_USERNAME": "Username must be 4-30 characters (letters, numbers, underscore, dot).",
    "PASSWORD_TOO_LONG": "Password is too long (maximum 72 bytes).",
    "MAX_TOP_UP_EXCEEDED": "Top-up amount must not exceed 100,000,000 VND.",
    "INVALID_METHOD": "Payment method must be cash or transfer.",
    "Tên đăng nhập đã được sử dụng": "Username is already in use.",
    "Tên đăng nhập phải dài 4-30 ký tự và chỉ gồm chữ, số, dấu gạch dưới hoặc dấu chấm": "Username must be 4-30 characters (letters, numbers, underscore, dot).",
    "Mật khẩu quá dài": "Password is too long (maximum 72 bytes).",
    "Số tiền nạp không được vượt quá 100.000.000": "Top-up amount must not exceed 100,000,000 VND.",
    "Phương thức chỉ được là tiền mặt hoặc chuyển khoản": "Payment method must be cash or transfer.",
    "Invalid phone": "Invalid phone number.",
}

# Fallback thông báo tiếng Anh chuẩn theo tên trường (field key) khi mã lỗi trường không nằm trong bảng trên
FIELD_KEY_DEFAULT_MESSAGES: dict[str, str] = {
    "phone": "Invalid phone number.",
    "password": "Invalid password.",
    "full_name": "Invalid full name.",
    "amount": "Invalid amount.",
    "hourly_rate": "Invalid hourly rate.",
    "machine_id": "Invalid machine selection.",
    "code": "Invalid code.",
    "username": "Invalid username.",
    "customer_id": "Invalid customer.",
    "balance": "Invalid balance.",
    "status": "Invalid status.",
    "role": "Invalid role.",
    "store_id": "Invalid store.",
    "current_time": "Invalid time.",
    "settlement_amount": "Invalid settlement amount.",
    "method": "Invalid payment method.",
    "date_from": "Invalid start date.",
    "date_to": "Invalid end date.",
}

MSG_FIELD_INVALID_FALLBACK = "Invalid value."


def get_user_friendly_error(error: Exception | str | None) -> str:
    """Chuyển đổi exception hoặc error code sang câu tiếng Anh an toàn cho người dùng.

    Chỉ ánh xạ ApplicationError.code hoặc mã lỗi nghiệp vụ đã thống nhất sang tiếng Anh.
    Mã không xác định hoặc exception hệ thống sẽ dùng fallback chung an toàn (MSG_OPERATION_FAILED),
    tuyệt đối không bao giờ để lộ SQL query, stack trace, exception message nội bộ hoặc tiếng Việt ra giao diện.
    """
    if error is None:
        return ""

    if isinstance(error, ApplicationError):
        code = getattr(error, "code", None)
        if code and code in ERROR_CODE_MESSAGES:
            return ERROR_CODE_MESSAGES[code]
        return MSG_OPERATION_FAILED

    if isinstance(error, str):
        if error in ERROR_CODE_MESSAGES:
            return ERROR_CODE_MESSAGES[error]
        return MSG_OPERATION_FAILED

    return MSG_OPERATION_FAILED


def get_field_errors_safe(error: Exception | None) -> dict[str, str]:
    """Trích xuất và ánh xạ lỗi từng trường sang thông báo tiếng Anh an toàn cho người dùng.

    Tra cứu theo bảng mã/chuỗi chuẩn hóa (FIELD_ERROR_MESSAGES),
    nếu không khớp sẽ fallback theo tên trường (FIELD_KEY_DEFAULT_MESSAGES),
    hoặc fallback chung (MSG_FIELD_INVALID_FALLBACK).
    Không bao giờ trả raw message hoặc chuỗi tự do không xác định.
    """
    if not isinstance(error, ApplicationError) or not error.field_errors:
        return {}

    safe_errors: dict[str, str] = {}
    for field_key, raw_msg in error.field_errors.items():
        if not isinstance(raw_msg, str):
            safe_errors[field_key] = FIELD_KEY_DEFAULT_MESSAGES.get(field_key, MSG_FIELD_INVALID_FALLBACK)
            continue

        raw_str = raw_msg.strip()
        if raw_str in FIELD_ERROR_MESSAGES:
            safe_errors[field_key] = FIELD_ERROR_MESSAGES[raw_str]
        elif field_key in FIELD_KEY_DEFAULT_MESSAGES:
            safe_errors[field_key] = FIELD_KEY_DEFAULT_MESSAGES[field_key]
        else:
            safe_errors[field_key] = MSG_FIELD_INVALID_FALLBACK

    return safe_errors
