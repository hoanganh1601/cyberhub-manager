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
        # MachineStatus
        if status == MachineStatus.AVAILABLE:
            return "Trống", "●", SUCCESS, "#0A2918"
        if status == MachineStatus.IN_USE:
            return "Đang dùng", "●", DANGER, "#331317"
        if status == MachineStatus.MAINTENANCE:
            return "Bảo trì", "▲", WARNING, "#352309"

        # CustomerStatus
        if status == CustomerStatus.ACTIVE:
            return "Hoạt động", "●", SUCCESS, "#0A2918"
        if status == CustomerStatus.INACTIVE:
            return "Ngừng hoạt động", "○", DISABLED, "#1E293B"

        # AccountStatus
        if status == AccountStatus.ACTIVE:
            return "Hoạt động", "●", SUCCESS, "#0A2918"
        if status == AccountStatus.LOCKED:
            return "Đã khóa", "🔒", DANGER, "#331317"

        # SessionStatus
        if status == SessionStatus.ACTIVE:
            return "Đang chạy", "●", INFO, "#0C2A38"
        if status == SessionStatus.COMPLETED:
            return "Hoàn thành", "✓", SUCCESS, "#0A2918"
        if status == SessionStatus.CANCELLED:
            return "Đã hủy", "✕", DISABLED, "#1E293B"

        # InvoiceStatus
        if status == InvoiceStatus.PAID:
            return "Đã thanh toán", "✓", SUCCESS, "#0A2918"
        if status == InvoiceStatus.VOID:
            return "Đã hủy", "✕", DANGER, "#331317"

        # EmployeeStatus
        if status == EmployeeStatus.ACTIVE:
            return "Hoạt động", "●", SUCCESS, "#0A2918"
        if status == EmployeeStatus.INACTIVE:
            return "Nghỉ việc", "○", DISABLED, "#1E293B"
        if status == EmployeeStatus.LOCKED:
            return "Đã khóa", "🔒", DANGER, "#331317"

        # StoreStatus
        if status == StoreStatus.ACTIVE:
            return "Hoạt động", "●", SUCCESS, "#0A2918"
        if status == StoreStatus.INACTIVE:
            return "Ngừng HĐ", "○", DISABLED, "#1E293B"

        # Role
        if status == Role.ADMIN:
            return "Admin", "★", DANGER, "#331317"
        if status == Role.MANAGER:
            return "Quản lý", "◆", INFO, "#0C2A38"
        if status == Role.STAFF:
            return "Nhân viên", "●", SUCCESS, "#0A2918"

        # Trạng thái không xác định
        status_str = str(status) if status is not None else "Không xác định"
        return status_str, "•", TEXT_MUTED, "#1E293B"
