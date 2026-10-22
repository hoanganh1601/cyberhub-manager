"""MachineCard component cho CyberHub Manager.

Quy định: docs/07_DTO_UI_HANDOFF.md mục 4, 7, 8 và docs/03_UI_THEME.md mục 3.5.
- Hiển thị thông tin máy, phiên đang chạy và số dư dự kiến live.
- Cảnh báo âm: sử dụng active_session.projected_balance (không dùng account_balance).
- Phân quyền theo role của actor: STAFF chỉ xem máy bảo trì, MANAGER/ADMIN có nút 'Bật lại'.
- API: render(machine, actor), set_busy(busy), set_on_open(cb), set_on_checkout(cb), set_on_maintenance(cb).
- Callbacks nhận machine_id: int.
"""

from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from ...domain.dtos import EmployeeSession, MachineSummary
from ...domain.enums import MachineStatus, Role
from ..formatters import format_duration, format_money
from ..theme import (
    BG_ALERT_DANGER,
    BG_SURFACE,
    BORDER,
    DANGER,
    FONT_BODY,
    FONT_BODY_STRONG,
    FONT_CAPTION,
    RADIUS_CARD,
    SPACING_MD,
    SPACING_SM,
    SUCCESS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)
from .action_button import ActionButton
from .status_badge import StatusBadge


class MachineCard(ctk.CTkFrame):
    """Card hiển thị trạng thái và thông tin phiên của một máy tính."""

    def __init__(
        self,
        master: Any,
        machine: MachineSummary | None = None,
        actor: EmployeeSession | None = None,
        *,
        on_open: Callable[[int], None] | None = None,
        on_checkout: Callable[[int], None] | None = None,
        on_maintenance: Callable[[int], None] | None = None,
        width: int = 240,
        height: int = 190,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master=master,
            fg_color=BG_SURFACE,
            border_width=1,
            border_color=BORDER,
            corner_radius=RADIUS_CARD,
            width=width,
            height=height,
            **kwargs,
        )
        self.pack_propagate(False)

        self._machine: MachineSummary | None = None
        self._actor: EmployeeSession | None = None
        self._on_open: Callable[[int], None] | None = on_open
        self._on_checkout: Callable[[int], None] | None = on_checkout
        self._on_maintenance: Callable[[int], None] | None = on_maintenance

        # Container bên trong có padding
        self._inner = ctk.CTkFrame(self, fg_color="transparent")
        self._inner.pack(fill="both", expand=True, padx=SPACING_MD, pady=SPACING_MD)

        # Hàng 1: Tên máy + Badge trạng thái
        self._row1 = ctk.CTkFrame(self._inner, fg_color="transparent")
        self._row1.pack(fill="x", side="top")

        self._name_label = ctk.CTkLabel(
            self._row1,
            text="",
            font=FONT_BODY_STRONG,
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self._name_label.pack(side="left", fill="x", expand=True)

        self._status_badge = StatusBadge(self._row1)
        self._status_badge.pack(side="right")

        # Hàng 2: Khách hàng đang dùng hoặc 'Sẵn sàng'
        self._customer_label = ctk.CTkLabel(
            self._inner,
            text="",
            font=FONT_BODY,
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self._customer_label.pack(fill="x", side="top", pady=(6, 2))

        # Hàng 3: Thời gian chơi + Đơn giá / giờ
        self._row3 = ctk.CTkFrame(self._inner, fg_color="transparent")
        self._row3.pack(fill="x", side="top")

        self._duration_label = ctk.CTkLabel(
            self._row3,
            text="",
            font=FONT_CAPTION,
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self._duration_label.pack(side="left")

        self._rate_label = ctk.CTkLabel(
            self._row3,
            text="",
            font=FONT_CAPTION,
            text_color=TEXT_MUTED,
            anchor="e",
        )
        self._rate_label.pack(side="right")

        # Hàng 4: Box cảnh báo số dư dự kiến
        self._balance_alert_frame = ctk.CTkFrame(
            self._inner,
            fg_color="transparent",
            corner_radius=6,
            height=28,
        )
        self._balance_alert_frame.pack(fill="x", side="top", pady=(6, 0))

        self._balance_label = ctk.CTkLabel(
            self._balance_alert_frame,
            text="",
            font=FONT_CAPTION,
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self._balance_label.pack(fill="both", expand=True, padx=6, pady=2)

        # Footer: Nút bấm hành động
        self._footer = ctk.CTkFrame(self._inner, fg_color="transparent")
        self._footer.pack(fill="x", side="bottom")

        self._action_btn = ActionButton(
            self._footer,
            text="",
            height=34,
            width=100,
        )
        self._action_btn.pack(fill="x")

        self._maintenance_text_label = ctk.CTkLabel(
            self._footer,
            text="Đang bảo trì",
            font=FONT_CAPTION,
            text_color=WARNING,
        )

        if machine is not None and actor is not None:
            self.render(machine, actor)

    def set_on_open(self, callback: Callable[[int], None] | None) -> None:
        self._on_open = callback

    def set_on_checkout(self, callback: Callable[[int], None] | None) -> None:
        self._on_checkout = callback

    def set_on_maintenance(self, callback: Callable[[int], None] | None) -> None:
        self._on_maintenance = callback

    def set_busy(self, busy: bool) -> None:
        """Đặt trạng thái bận cho nút bấm thao tác trên card."""
        self._action_btn.set_busy(busy)

    @property
    def action_button(self) -> ActionButton:
        """Truy xuất nút thao tác footer."""
        return self._action_btn

    def render(self, machine: MachineSummary, actor: EmployeeSession) -> None:
        """Hiển thị toàn bộ thông tin máy theo DTO MachineSummary và quyền của actor."""
        self._machine = machine
        self._actor = actor

        # 1. Tên máy & badge
        self._name_label.configure(text=machine.name)
        self._status_badge.set_status(machine.status)

        # Đổi viền card theo trạng thái
        if machine.status == MachineStatus.AVAILABLE:
            self.configure(border_color=SUCCESS)
        elif machine.status == MachineStatus.IN_USE:
            self.configure(border_color=DANGER)
        elif machine.status == MachineStatus.MAINTENANCE:
            self.configure(border_color=WARNING)
        else:
            self.configure(border_color=BORDER)

        # 2. Hàng thông tin chi tiết & số dư
        rate_str = f"{format_money(machine.hourly_rate)}/h"
        self._rate_label.configure(text=rate_str)

        if machine.status == MachineStatus.IN_USE and machine.active_session is not None:
            session = machine.active_session.session
            cust_name = session.customer_name if session else "Khách hàng"
            self._customer_label.configure(
                text=f"Khách: {cust_name}",
                text_color=TEXT_PRIMARY,
            )
            elapsed_str = format_duration(machine.active_session.elapsed_seconds)
            self._duration_label.configure(text=f"Đã chơi: {elapsed_str}")

            # Cảnh báo số dư dự kiến (projected_balance)
            proj_bal = machine.active_session.projected_balance
            if proj_bal < 0:
                # Cảnh báo âm: nền đỏ nhạt, icon cảnh báo, chữ đỏ
                self._balance_alert_frame.configure(fg_color=BG_ALERT_DANGER)
                self._balance_label.configure(
                    text=f"⚠  Âm {format_money(abs(proj_bal))}",
                    text_color=DANGER,
                )
            else:
                self._balance_alert_frame.configure(fg_color="transparent")
                self._balance_label.configure(
                    text=f"Dư: {format_money(proj_bal)}",
                    text_color=SUCCESS,
                )
        elif machine.status == MachineStatus.AVAILABLE:
            self._customer_label.configure(text="Sẵn sàng phục vụ", text_color=TEXT_SECONDARY)
            self._duration_label.configure(text="Máy trống")
            self._balance_alert_frame.configure(fg_color="transparent")
            self._balance_label.configure(text="", text_color=TEXT_SECONDARY)
        elif machine.status == MachineStatus.MAINTENANCE:
            self._customer_label.configure(text="Tạm ngừng hoạt động", text_color=WARNING)
            self._duration_label.configure(text="Đang bảo trì")
            self._balance_alert_frame.configure(fg_color="transparent")
            self._balance_label.configure(text="", text_color=TEXT_SECONDARY)

        # 3. Phân quyền và nút bấm hành động ở footer
        self._render_action_button(machine, actor)

    def _render_action_button(self, machine: MachineSummary, actor: EmployeeSession) -> None:
        """Render nút bấm footer theo trạng thái máy và quyền của actor."""
        # Ẩn cả 2 widget trước khi render lại
        self._action_btn.pack_forget()
        self._maintenance_text_label.pack_forget()

        m_id = machine.machine_id

        if machine.status == MachineStatus.AVAILABLE:
            self._action_btn.configure(
                text="Mở máy",
                kind="success",
                command=lambda: self._on_open(m_id) if self._on_open else None,
            )
            self._action_btn.pack(fill="x")

        elif machine.status == MachineStatus.IN_USE:
            self._action_btn.configure(
                text="Checkout",
                kind="danger",
                command=lambda: self._on_checkout(m_id) if self._on_checkout else None,
            )
            self._action_btn.pack(fill="x")

        elif machine.status == MachineStatus.MAINTENANCE:
            # Chỉ Manager hoặc Admin mới có quyền bật lại máy bảo trì
            if actor.role in (Role.MANAGER, Role.ADMIN):
                self._action_btn.configure(
                    text="Bật lại",
                    kind="secondary",
                    command=lambda: self._on_maintenance(m_id) if self._on_maintenance else None,
                )
                self._action_btn.pack(fill="x")
            else:
                # Staff chỉ xem, không có action bật lại
                self._maintenance_text_label.pack(fill="x", pady=6)
