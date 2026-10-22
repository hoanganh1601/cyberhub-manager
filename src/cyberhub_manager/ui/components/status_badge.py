"""StatusBadge component cho CyberHub Manager.

Quy định: docs/07_DTO_UI_HANDOFF.md mục 7 & 8.
- StatusBadge.set_status(status) nhận enum nghiệp vụ, tự chọn nhãn / icon / token màu.
- Luôn hiển thị chữ + icon, không chỉ dùng màu.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

import customtkinter as ctk

from ...domain.enums import (
    AccountStatus,
    CustomerStatus,
    EmployeeStatus,
    InvoiceStatus,
    MachineStatus,
    Role,
    SessionStatus,
    StoreStatus,
)
from ..theme import (
    BG_DANGER_SUBTLE,
    BG_INFO_SUBTLE,
    BG_MUTED_SUBTLE,
    BG_SUCCESS_SUBTLE,
    BG_WARNING_SUBTLE,
    BORDER,
    DANGER,
    DISABLED,
    FONT_CAPTION,
    INFO,
    RADIUS_BADGE,
    SUCCESS,
    TEXT_MUTED,
    WARNING,
)


_STYLE_MAPPING: dict[tuple[type, str], tuple[str, str, str, str]] = {
    # MachineStatus
    (MachineStatus, MachineStatus.AVAILABLE.value): ("Trống", "●", SUCCESS, BG_SUCCESS_SUBTLE),
    (MachineStatus, MachineStatus.IN_USE.value): ("Đang dùng", "●", DANGER, BG_DANGER_SUBTLE),
    (MachineStatus, MachineStatus.MAINTENANCE.value): ("Bảo trì", "▲", WARNING, BG_WARNING_SUBTLE),

    # CustomerStatus
    (CustomerStatus, CustomerStatus.ACTIVE.value): ("Hoạt động", "●", SUCCESS, BG_SUCCESS_SUBTLE),
    (CustomerStatus, CustomerStatus.INACTIVE.value): ("Ngừng hoạt động", "○", DISABLED, BG_MUTED_SUBTLE),

    # AccountStatus
    (AccountStatus, AccountStatus.ACTIVE.value): ("Hoạt động", "●", SUCCESS, BG_SUCCESS_SUBTLE),
    (AccountStatus, AccountStatus.LOCKED.value): ("Đã khóa", "🔒", DANGER, BG_DANGER_SUBTLE),

    # SessionStatus
    (SessionStatus, SessionStatus.ACTIVE.value): ("Đang chạy", "●", INFO, BG_INFO_SUBTLE),
    (SessionStatus, SessionStatus.COMPLETED.value): ("Hoàn thành", "✓", SUCCESS, BG_SUCCESS_SUBTLE),
    (SessionStatus, SessionStatus.CANCELLED.value): ("Đã hủy", "✕", DISABLED, BG_MUTED_SUBTLE),

    # InvoiceStatus
    (InvoiceStatus, InvoiceStatus.PAID.value): ("Đã thanh toán", "✓", SUCCESS, BG_SUCCESS_SUBTLE),
    (InvoiceStatus, InvoiceStatus.VOID.value): ("Đã hủy", "✕", DANGER, BG_DANGER_SUBTLE),

    # EmployeeStatus
    (EmployeeStatus, EmployeeStatus.ACTIVE.value): ("Hoạt động", "●", SUCCESS, BG_SUCCESS_SUBTLE),
    (EmployeeStatus, EmployeeStatus.INACTIVE.value): ("Nghỉ việc", "○", DISABLED, BG_MUTED_SUBTLE),
    (EmployeeStatus, EmployeeStatus.LOCKED.value): ("Đã khóa", "🔒", DANGER, BG_DANGER_SUBTLE),

    # StoreStatus
    (StoreStatus, StoreStatus.ACTIVE.value): ("Hoạt động", "●", SUCCESS, BG_SUCCESS_SUBTLE),
    (StoreStatus, StoreStatus.INACTIVE.value): ("Ngừng HĐ", "○", DISABLED, BG_MUTED_SUBTLE),

    # Role
    (Role, Role.ADMIN.value): ("Admin", "★", DANGER, BG_DANGER_SUBTLE),
    (Role, Role.MANAGER.value): ("Quản lý", "◆", INFO, BG_INFO_SUBTLE),
    (Role, Role.STAFF.value): ("Nhân viên", "●", SUCCESS, BG_SUCCESS_SUBTLE),
}


class StatusBadge(ctk.CTkFrame):
    """Badge hiển thị trạng thái nghiệp vụ kèm ký hiệu và màu tương ứng."""

    def __init__(
        self,
        master: Any,
        status: Enum | str | None = None,
        *,
        height: int = 26,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master=master,
            corner_radius=RADIUS_BADGE,
            height=height,
            border_width=1,
            **kwargs,
        )
        self._current_status: Any = None

        self._label = ctk.CTkLabel(
            self,
            text="",
            font=FONT_CAPTION,
            padx=8,
            pady=2,
        )
        self._label.pack(expand=True, fill="both")

        if status is not None:
            self.set_status(status)

    @property
    def current_status(self) -> Any:
        return self._current_status

    def set_status(self, status: Enum | str | None) -> None:
        """Cập nhật trạng thái hiển thị từ enum hoặc chuỗi."""
        self._current_status = status
        text, icon, color, bg_color = self._resolve_status_style(status)
        self.configure(
            fg_color=bg_color,
            border_color=color,
        )
        self._label.configure(
            text=f"{icon} {text}" if icon else text,
            text_color=color,
        )

    def _resolve_status_style(self, status: Any) -> tuple[str, str, str, str]:
        # Phân nhánh theo đúng type Enum trước để tránh StrEnum so sánh bằng nhau qua giá trị chuỗi
        if isinstance(status, Enum):
            lookup_key = (type(status), status.value)
            if lookup_key in _STYLE_MAPPING:
                return _STYLE_MAPPING[lookup_key]

        # Trạng thái không xác định hoặc chuỗi chưa có phân loại nghiệp vụ cụ thể
        status_str = str(status) if status is not None else "Không xác định"
        return status_str, "•", TEXT_MUTED, BG_MUTED_SUBTLE
