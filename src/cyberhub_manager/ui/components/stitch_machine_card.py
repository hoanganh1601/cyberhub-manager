"""NG-03 — Card máy theo Stitch export (lưới Dashboard).

Cùng API với MachineCard (NG-01) để có thể thay thế nhau:
render(machine, actor), set_busy(busy), set_on_open/set_on_checkout/set_on_maintenance(cb).
Callback nhận machine_id: int.

Quy tắc hiển thị (docs/07_DTO_UI_HANDOFF.md mục 8):
- Cảnh báo âm dùng active_session.projected_balance, không dùng account_balance.
- STAFF thấy máy bảo trì nhưng không có nút "Kết thúc bảo trì".
- Trạng thái luôn có chữ, không chỉ có màu.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ...domain.dtos import EmployeeSession, MachineSummary
from ...domain.enums import MachineStatus
from ..formatters import format_duration, format_money
from ..messages import MSG_PROCESSING
from ..navigation import MANAGEMENT_ROLES
from ..theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_CARD_CODE,
    FONT_ST_MONO_11,
    FONT_ST_MONO_VALUE,
    FONT_ST_MONO_XS,
    FONT_ST_MONO_XS_STRONG,
    STITCH_AMBER,
    STITCH_AMBER_HOVER,
    STITCH_BADGE_DANGER_BG,
    STITCH_BADGE_DANGER_BORDER,
    STITCH_BADGE_SUCCESS_BG,
    STITCH_BADGE_SUCCESS_BORDER,
    STITCH_BADGE_WARNING_BG,
    STITCH_BADGE_WARNING_BORDER,
    STITCH_CARD_BG,
    STITCH_CARD_BORDER,
    STITCH_DANGER,
    STITCH_EMERALD,
    STITCH_EMERALD_HOVER,
    STITCH_INFO_BOX_BG,
    STITCH_INFO_BOX_BORDER,
    STITCH_MACHINE_CARD_HEIGHT,
    STITCH_MAINT_BOX_BG,
    STITCH_RADIUS,
    STITCH_RADIUS_LG,
    STITCH_ROSE,
    STITCH_ROSE_HOVER,
    STITCH_SUCCESS,
    STITCH_TEXT,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_ON_CYAN,
    STITCH_TEXT_STRONG,
    STITCH_WARNING,
)

# status -> (nhãn, chữ, nền badge, viền badge)
_BADGE_STYLE: dict[MachineStatus, tuple[str, str, str, str]] = {
    MachineStatus.AVAILABLE: ("Trống", STITCH_SUCCESS, STITCH_BADGE_SUCCESS_BG, STITCH_BADGE_SUCCESS_BORDER),
    MachineStatus.IN_USE: ("Đang dùng", STITCH_DANGER, STITCH_BADGE_DANGER_BG, STITCH_BADGE_DANGER_BORDER),
    MachineStatus.MAINTENANCE: ("Bảo trì", STITCH_WARNING, STITCH_BADGE_WARNING_BG, STITCH_BADGE_WARNING_BORDER),
}

# action -> (nhãn nút, nền, hover, chữ)
_ACTIONS: dict[str, tuple[str, str, str, str]] = {
    "open": ("Mở phiên", STITCH_EMERALD, STITCH_EMERALD_HOVER, STITCH_TEXT_ON_CYAN),
    "checkout": ("Thanh toán", STITCH_ROSE, STITCH_ROSE_HOVER, STITCH_TEXT_STRONG),
    "maintenance": ("Kết thúc bảo trì", STITCH_AMBER, STITCH_AMBER_HOVER, STITCH_TEXT_ON_CYAN),
}


def card_action(machine: MachineSummary, actor: EmployeeSession) -> str | None:
    """Hành động của nút trên card: 'open' | 'checkout' | 'maintenance' | None (không có nút)."""
    if machine.status == MachineStatus.AVAILABLE:
        return "open"
    if machine.status == MachineStatus.IN_USE:
        return "checkout"
    if machine.status == MachineStatus.MAINTENANCE and actor.role in MANAGEMENT_ROLES:
        return "maintenance"
    return None


class StitchMachineCard(ctk.CTkFrame):
    """Card một máy: mã + badge, tên, hộp thông tin, nút hành động."""

    def __init__(
        self,
        master: Any,
        machine: MachineSummary | None = None,
        actor: EmployeeSession | None = None,
        *,
        on_open: Callable[[int], None] | None = None,
        on_checkout: Callable[[int], None] | None = None,
        on_maintenance: Callable[[int], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
            height=STITCH_MACHINE_CARD_HEIGHT,
            **kwargs,
        )
        self.pack_propagate(False)
        self._machine: MachineSummary | None = None
        self._action: str | None = None
        self._busy = False
        self._callbacks: dict[str, Callable[[int], None] | None] = {
            "open": on_open,
            "checkout": on_checkout,
            "maintenance": on_maintenance,
        }

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=12)

        head = ctk.CTkFrame(inner, fg_color="transparent")
        head.pack(fill="x")
        self._code_label = ctk.CTkLabel(
            head, text="", font=FONT_ST_CARD_CODE, text_color=STITCH_TEXT_STRONG, height=20
        )
        self._code_label.pack(side="left")
        self._badge = ctk.CTkFrame(head, border_width=1, corner_radius=STITCH_RADIUS)
        self._badge.pack(side="right")
        self._badge_label = ctk.CTkLabel(self._badge, text="", font=FONT_ST_MONO_XS_STRONG, height=16)
        self._badge_label.pack(padx=8, pady=1)

        self._name_label = ctk.CTkLabel(
            inner, text="", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, anchor="w", height=16
        )
        self._name_label.pack(fill="x", pady=(2, 8))

        self._info_box = ctk.CTkFrame(inner, border_width=1, corner_radius=STITCH_RADIUS)
        self._info_box.pack(fill="x")

        # Nút luôn nằm ở đáy card.
        self._button = ctk.CTkButton(
            inner,
            text="",
            height=30,
            corner_radius=STITCH_RADIUS,
            font=FONT_ST_BODY_STRONG,
            command=self._on_click,
        )
        self._note_label = ctk.CTkLabel(
            inner, text="▲  Đang bảo trì", font=FONT_ST_BODY_STRONG, text_color=STITCH_WARNING, height=30
        )

        if machine is not None and actor is not None:
            self.render(machine, actor)

    # ------------------------------------------------------------------
    # API giống MachineCard
    # ------------------------------------------------------------------
    def set_on_open(self, callback: Callable[[int], None] | None) -> None:
        self._callbacks["open"] = callback

    def set_on_checkout(self, callback: Callable[[int], None] | None) -> None:
        self._callbacks["checkout"] = callback

    def set_on_maintenance(self, callback: Callable[[int], None] | None) -> None:
        self._callbacks["maintenance"] = callback

    @property
    def machine(self) -> MachineSummary | None:
        return self._machine

    @property
    def action(self) -> str | None:
        return self._action

    @property
    def action_button(self) -> ctk.CTkButton:
        return self._button

    @property
    def is_busy(self) -> bool:
        return self._busy

    def set_busy(self, busy: bool) -> None:
        """Chặn double click khi đang gọi service; trả nhãn gốc khi xong."""
        self._busy = busy
        if self._action is None:
            return
        label = _ACTIONS[self._action][0]
        self._button.configure(
            text=MSG_PROCESSING if busy else label,
            state="disabled" if busy else "normal",
        )

    def render(self, machine: MachineSummary, actor: EmployeeSession) -> None:
        self._machine = machine
        self._code_label.configure(text=machine.machine_code)
        self._name_label.configure(text=machine.name)

        label, color, bg, border = _BADGE_STYLE.get(
            machine.status, (str(machine.status), STITCH_TEXT_MUTED, STITCH_CARD_BG, STITCH_CARD_BORDER)
        )
        self._badge.configure(fg_color=bg, border_color=border)
        self._badge_label.configure(text=label, text_color=color)

        self._render_info(machine)
        self._render_action(card_action(machine, actor))

    # ------------------------------------------------------------------
    # Nội bộ
    # ------------------------------------------------------------------
    def _render_info(self, machine: MachineSummary) -> None:
        for child in self._info_box.winfo_children():
            child.destroy()
        box = self._info_box

        if machine.status == MachineStatus.MAINTENANCE:
            box.configure(fg_color=STITCH_MAINT_BOX_BG, border_color=STITCH_BADGE_WARNING_BORDER)
            self._caption(box, "TRẠNG THÁI", STITCH_WARNING).pack(fill="x", padx=8, pady=(8, 0))
            ctk.CTkLabel(
                box, text="Máy tạm ngừng phục vụ", font=FONT_ST_BODY, text_color=STITCH_TEXT, anchor="w"
            ).pack(fill="x", padx=8, pady=(0, 8))
            return

        box.configure(fg_color=STITCH_INFO_BOX_BG, border_color=STITCH_INFO_BOX_BORDER)
        active = machine.active_session
        if machine.status == MachineStatus.IN_USE and active is not None:
            balance = active.projected_balance
            rows = (
                ("Khách:", active.session.customer_name, STITCH_TEXT_STRONG, FONT_ST_BODY_STRONG),
                ("Thời gian:", format_duration(active.elapsed_seconds), STITCH_TEXT, FONT_ST_MONO_11),
                (
                    "Số dư dự kiến:",
                    format_money(balance),
                    STITCH_DANGER if balance < 0 else STITCH_SUCCESS,
                    FONT_ST_MONO_XS_STRONG,
                ),
            )
            for index, (caption, value, color, font) in enumerate(rows):
                row = ctk.CTkFrame(box, fg_color="transparent")
                row.pack(fill="x", padx=8, pady=(8 if index == 0 else 0, 8 if index == 2 else 0))
                self._caption(row, caption, STITCH_TEXT_MUTED).pack(side="left")
                ctk.CTkLabel(row, text=value, font=font, text_color=color, height=18).pack(side="right")
            return

        self._caption(box, "ĐƠN GIÁ ÁP DỤNG", STITCH_TEXT_MUTED).pack(fill="x", padx=8, pady=(8, 0))
        ctk.CTkLabel(
            box,
            text=f"{format_money(machine.hourly_rate)}/giờ",
            font=FONT_ST_MONO_VALUE,
            text_color=STITCH_TEXT_STRONG,
            anchor="w",
        ).pack(fill="x", padx=8, pady=(0, 8))

    @staticmethod
    def _caption(master: Any, text: str, color: str) -> ctk.CTkLabel:
        return ctk.CTkLabel(master, text=text, font=FONT_ST_MONO_XS, text_color=color, anchor="w", height=16)

    def _render_action(self, action: str | None) -> None:
        self._action = action
        self._button.pack_forget()
        self._note_label.pack_forget()
        if action is None:
            self._note_label.pack(side="bottom", fill="x")
            return
        _label, bg, hover, text_color = _ACTIONS[action]
        self._button.configure(fg_color=bg, hover_color=hover, text_color=text_color)
        self._button.pack(side="bottom", fill="x")
        self.set_busy(self._busy)  # gắn nhãn đúng: "Processing…" nếu đang bận, ngược lại nhãn gốc

    def _on_click(self) -> None:
        if self._busy or self._machine is None or self._action is None:
            return
        callback = self._callbacks.get(self._action)
        if callback is not None:
            callback(self._machine.machine_id)
