"""Các exception nghiệp vụ dùng chung giữa service và UI."""


class ApplicationError(Exception):
    """Lớp gốc cho các lỗi nghiệp vụ có cấu trúc."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        field_errors: dict[str, str] | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field_errors = dict(field_errors or {})
        self.details = dict(details or {})


class ValidationError(ApplicationError):
    def __init__(
        self,
        message: str = "Dữ liệu không hợp lệ",
        *,
        field_errors: dict[str, str] | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            "VALIDATION_ERROR",
            message,
            field_errors=field_errors,
            details=details,
        )


class AuthenticationError(ApplicationError):
    def __init__(
        self,
        message: str = "Tên đăng nhập hoặc mật khẩu không đúng",
        *,
        field_errors: dict[str, str] | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            "AUTH_INVALID_CREDENTIALS",
            message,
            field_errors=field_errors,
            details=details,
        )


class NotFoundError(ApplicationError):
    def __init__(
        self,
        message: str = "Không tìm thấy dữ liệu",
        *,
        field_errors: dict[str, str] | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            "NOT_FOUND",
            message,
            field_errors=field_errors,
            details=details,
        )


class ConflictError(ApplicationError):
    def __init__(
        self,
        message: str = "Dữ liệu bị xung đột",
        *,
        field_errors: dict[str, str] | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            "CONFLICT",
            message,
            field_errors=field_errors,
            details=details,
        )


class PermissionDeniedError(ApplicationError):
    def __init__(
        self,
        message: str = "Bạn không có quyền thực hiện thao tác này",
        *,
        field_errors: dict[str, str] | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            "PERMISSION_DENIED",
            message,
            field_errors=field_errors,
            details=details,
        )


class InsufficientBalanceError(ApplicationError):
    def __init__(
        self,
        message: str = "Số dư không đủ",
        *,
        field_errors: dict[str, str] | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            "INSUFFICIENT_BALANCE",
            message,
            field_errors=field_errors,
            details=details,
        )


class SettlementRequiredError(ApplicationError):
    def __init__(
        self,
        message: str = "Cần thanh toán phần tiền còn thiếu",
        *,
        field_errors: dict[str, str] | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            "SETTLEMENT_REQUIRED",
            message,
            field_errors=field_errors,
            details=details,
        )


class ServiceUnavailableError(ApplicationError):
    def __init__(
        self,
        message: str = "Dịch vụ hiện không khả dụng",
        *,
        field_errors: dict[str, str] | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            "SERVICE_UNAVAILABLE",
            message,
            field_errors=field_errors,
            details=details,
        )