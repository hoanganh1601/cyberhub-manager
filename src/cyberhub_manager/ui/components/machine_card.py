"""MachineCard component cho CyberHub Manager theo phong cách Google Stitch.

Quy định: docs/07_DTO_UI_HANDOFF.md mục 4, 7, 8 và Stitch master_cyberhub_app_shell_1.
- Hiển thị thông tin máy, phiên đang chạy và số dư dự kiến live.
- Khối thông tin chìm (sunken box) nền STITCH_SUNKEN_BG (#0E131E) bo viền STITCH_SUNKEN_BORDER (#1E273A).
- Nút hành động phủ toàn chiều ngang (full-width) theo bảng màu Stitch (Emerald, Rose, Amber).
- Phân quyền theo role của actor: STAFF chỉ xem máy bảo trì, MANAGER/ADMIN có nút 'Bật lại'.
- Bảo toàn toàn bộ các thuộc tính công khai và nội bộ cho unit test:
  _balance_label, _action_btn, _maintenance_text_label, _name_label, _status_badge, etc.
"""

from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from ...domain.dtos import EmployeeSession, MachineSummary
from ...domain.enums import MachineStatus, Role
from ..formatters import format_duration, format_money
from ..theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_MONO_SM,
    FONT_ST_MONO_XS,
    FONT_ST_MONO_XS_STRONG,
    STITCH_AMBER,
    STITCH_CARD_BG,
    STITCH_CARD_BORDER,
    STITCH_DANGER,
    STITCH_FONT_MONO,
    STITCH_RADIUS_LG,
    STITCH_SUCCESS,
    STITCH_SUNKEN_BG,
    STITCH_SUNKEN_BORDER,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
)
from .action_button import ActionButton
from .status_badge import StatusBadge

_FONT_CODE = (STITCH_FONT_MONO, 14, "bold")
_FONT_RATE = (STITCH_FONT_MONO, 13, "bold")


class MachineCard(ctk.CTkFrame):
    """Card hiển thị trạng thái và thông tin phiên của một máy tính theo Stitch."""

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
        height: int = 188,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master=master,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
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

        # Container bên trong có padding sát Stitch (12px)
        self._inner = ctk.CTkFrame(self, fg_color="transparent")
        self._inner.pack(fill="both", expand=True, padx=12, pady=10)

        # Hàng 1: Mã máy (PC-01) + Badge trạng thái
        self._row1 = ctk.CTkFrame(self._inner, fg_color="transparent")
        self._row1.pack(fill="x", side="top")

        self._name_label = ctk.CTkLabel(
            self._row1,
            text="",
            font=_FONT_CODE,
            text_color=STITCH_TEXT_STRONG,
            anchor="w",
            height=20,
        )
        self._name_label.pack(side="left", fill="x", expand=True)

        self._status_badge = StatusBadge(self._row1, height=22)
        self._status_badge.pack(side="right")

        # Hàng 2: Tên máy phụ (ví dụ: 'Máy VIP 01')
        self._customer_label = ctk.CTkLabel(
            self._inner,
            text="",
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
            height=16,
        )
        self._customer_label.pack(fill="x", side="top", pady=(2, 6))

        # Hàng 3: Khối thông tin chìm (Sunken Box) nền tối viền chìm
        self._sunken_frame = ctk.CTkFrame(
            self._inner,
            fg_color=STITCH_SUNKEN_BG,
            border_width=1,
            border_color=STITCH_SUNKEN_BORDER,
            corner_radius=6,
            height=62,
        )
        self._sunken_frame.pack(fill="x", side="top", pady=(0, 6))
        self._sunken_frame.pack_propagate(False)

        # Các widget hiển thị bên trong sunken box
        # Dành cho AVAILABLE:
        self._rate_box = ctk.CTkFrame(self._sunken_frame, fg_color="transparent")
        self._rate_title = ctk.CTkLabel(
            self._rate_box,
            text="ĐƠN GIÁ ÁP DỤNG",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
        )
        self._rate_title.pack(fill="x", anchor="w")
        self._rate_label = ctk.CTkLabel(
            self._rate_box,
            text="",
            font=_FONT_RATE,
            text_color=STITCH_TEXT_STRONG,
            anchor="w",
        )
        self._rate_label.pack(fill="x", anchor="w", pady=(1, 0))

        # Dành cho IN_USE:
        self._in_use_box = ctk.CTkFrame(self._sunken_frame, fg_color="transparent")
        # Row A: Khách: {customer}
        self._in_use_r1 = ctk.CTkFrame(self._in_use_box, fg_color="transparent")
        self._in_use_r1.pack(fill="x")
        ctk.CTkLabel(
            self._in_use_r1, text="Khách:", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED, anchor="w", height=14
        ).pack(side="left")
        self._in_use_cust_val = ctk.CTkLabel(
            self._in_use_r1, text="", font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT_STRONG, anchor="e", height=14
        )
        self._in_use_cust_val.pack(side="right")

        # Row B: Thời gian: {duration}
        self._in_use_r2 = ctk.CTkFrame(self._in_use_box, fg_color="transparent")
        self._in_use_r2.pack(fill="x", pady=(1, 0))
        ctk.CTkLabel(
            self._in_use_r2, text="Thời gian:", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED, anchor="w", height=14
        ).pack(side="left")
        self._duration_label = ctk.CTkLabel(
            self._in_use_r2, text="", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED, anchor="e", height=14
        )
        self._duration_label.pack(side="right")

        # Row C: Số dư dự kiến: {bal}
        self._balance_alert_frame = ctk.CTkFrame(self._in_use_box, fg_color="transparent")
        self._balance_alert_frame.pack(fill="x", pady=(1, 0))
        ctk.CTkLabel(
            self._balance_alert_frame, text="Số dư dự kiến:", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED, anchor="w", height=14
        ).pack(side="left")
        self._balance_label = ctk.CTkLabel(
            self._balance_alert_frame, text="", font=FONT_ST_MONO_SM, text_color=STITCH_SUCCESS, anchor="e", height=14
        )
        self._balance_label.pack(side="right")

        # Dành cho MAINTENANCE:
        self._maint_box = ctk.CTkFrame(self._sunken_frame, fg_color="transparent")
        self._maint_title = ctk.CTkLabel(
            self._maint_box,
            text="GHI CHÚ SỰ CỐ",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_AMBER,
            anchor="w",
        )
        self._maint_title.pack(fill="x", anchor="w")
        self._maint_note_label = ctk.CTkLabel(
            self._maint_box,
            text="Bảo trì định kỳ và kiểm tra thiết bị",
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
        )
        self._maint_note_label.pack(fill="x", anchor="w", pady=(1, 0))

        # Footer: Nút bấm hành động
        self._footer = ctk.CTkFrame(self._inner, fg_color="transparent")
        self._footer.pack(fill="x", side="bottom")

        self._action_btn = ActionButton(
            self._footer,
            text="",
            height=30,
            width=100,
        )
        self._action_btn.pack(fill="x")

        self._maintenance_text_label = ctk.CTkLabel(
            self._footer,
            text="Đang bảo trì",
            font=FONT_ST_MONO_SM,
            text_color=STITCH_AMBER,
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
        # Hiển thị machine_code ở tiêu đề và tên phụ ở dòng dưới
        display_code = machine.machine_code or machine.name
        self._name_label.configure(text=display_code)
        self._status_badge.set_status(machine.status)

        # Ẩn tất cả các box con trong sunken frame trước khi render
        self._rate_box.pack_forget()
        self._in_use_box.pack_forget()
        self._maint_box.pack_forget()

        # Đổi viền card theo trạng thái
        if machine.status == MachineStatus.AVAILABLE:
            self.configure(border_color=STITCH_CARD_BORDER)
            self._sunken_frame.configure(fg_color=STITCH_SUNKEN_BG, border_color=STITCH_SUNKEN_BORDER)
            self._customer_label.configure(text=machine.name if machine.name != display_code else "Máy Standard")
            rate_str = f"{format_money(machine.hourly_rate)}/giờ"
            self._rate_label.configure(text=rate_str)
            self._rate_box.pack(fill="both", expand=True, padx=8, pady=5)
            self._duration_label.configure(text="Máy trống")
            self._balance_label.configure(text="")

        elif machine.status == MachineStatus.IN_USE:
            self.configure(border_color=STITCH_CARD_BORDER)
            self._sunken_frame.configure(fg_color=STITCH_SUNKEN_BG, border_color=STITCH_SUNKEN_BORDER)
            self._customer_label.configure(text=machine.name if machine.name != display_code else "Máy Standard")
            if machine.active_session is not None:
                session = machine.active_session.session
                cust_name = session.customer_name if session else "Khách hàng"
                self._in_use_cust_val.configure(text=cust_name)
                elapsed_str = format_duration(machine.active_session.elapsed_seconds)
                self._duration_label.configure(text=elapsed_str)

                # Cảnh báo số dư dự kiến (projected_balance)
                proj_bal = machine.active_session.projected_balance
                if proj_bal < 0:
                    self._balance_label.configure(
                        text=f"Âm {format_money(abs(proj_bal))}",
                        text_color=STITCH_DANGER,
                    )
                else:
                    self._balance_label.configure(
                        text=f"Dư: {format_money(proj_bal)}",
                        text_color=STITCH_SUCCESS,
                    )
            self._in_use_box.pack(fill="both", expand=True, padx=8, pady=5)

        elif machine.status == MachineStatus.MAINTENANCE:
            self.configure(border_color=STITCH_CARD_BORDER)
            self._sunken_frame.configure(fg_color="#1F1505", border_color="#4D3814")
            self._customer_label.configure(text=machine.name if machine.name != display_code else "Tạm ngừng hoạt động")
            self._maint_box.pack(fill="both", expand=True, padx=8, pady=5)
            self._duration_label.configure(text="Đang bảo trì")
            self._balance_label.configure(text="")

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
                fg_color="#10B981",
                hover_color="#059669",
                text_color="#020617",
                command=lambda: self._on_open(m_id) if self._on_open else None,
            )
            self._action_btn.pack(fill="x")

        elif machine.status == MachineStatus.IN_USE:
            self._action_btn.configure(
                text="Checkout",
                kind="danger",
                fg_color="#F43F5E",
                hover_color="#E11D48",
                text_color="#FFFFFF",
                command=lambda: self._on_checkout(m_id) if self._on_checkout else None,
            )
            self._action_btn.pack(fill="x")

        elif machine.status == MachineStatus.MAINTENANCE:
            if actor.role in (Role.MANAGER, Role.ADMIN):
                self._action_btn.configure(
                    text="Bật lại",
                    kind="secondary",
                    fg_color="#F59E0B",
                    hover_color="#D97706",
                    text_color="#020617",
                    command=lambda: self._on_maintenance(m_id) if self._on_maintenance else None,
                )
                self._action_btn.pack(fill="x")
            else:
                self._maintenance_text_label.pack(fill="x", pady=6)
