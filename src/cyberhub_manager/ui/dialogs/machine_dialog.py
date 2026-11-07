"""NG-03 — Dialog thêm / sửa máy (Manager/Admin) theo Stitch `th_m_m_y_cyberhub_manager_1280x720`.

- Thêm: mã máy, tên máy, giá theo giờ -> machines.create_machine(...)
- Sửa: tên máy, giá theo giờ (mã máy chỉ hiển thị) -> machines.update_machine(...)
- Bố cục Stitch: tiêu đề + phụ đề + nút ✕, nhãn in hoa có dấu * cyan, chú thích dưới ô,
  đuôi "VND/giờ" trong ô giá, hộp thông tin cửa hàng / trạng thái, nút Hủy + Thêm máy.
- Kiểm tra sơ bộ ở UI (bắt buộc nhập, đơn giá nguyên dương); service vẫn kiểm tra lại.
- Lỗi Validation/Conflict gắn vào đúng field qua get_field_errors_safe(); giữ dữ liệu đã nhập.
- Thông báo lỗi giữ tiếng Anh theo quy định chung trong messages.py.
- Đang lưu: nút "Processing…", chặn double click/Enter (07 mục 7).
"""

from __future__ import annotations

import re
import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ...domain.dtos import MachineSummary
from ...domain.enums import MachineStatus
from ...domain.models import Machine
from ..app_shell import ViewContext
from ..background import TaskRunner, default_runner
from ..components import ToastManager
from ..components.stitch_button import stitch_button
from ..components.stitch_field import StitchField
from ..feedback import notify_error
from ..messages import FIELD_ERROR_MESSAGES, get_field_errors_safe, get_user_friendly_error
from ..theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_LABEL_CAPS,
    FONT_ST_MONO_11,
    FONT_ST_MONO_BODY,
    FONT_ST_MONO_XS_STRONG,
    FONT_ST_PAGE_TITLE,
    STITCH_BADGE_DANGER_BG,
    STITCH_BADGE_DANGER_BORDER,
    STITCH_BADGE_SUCCESS_BG,
    STITCH_BADGE_SUCCESS_BORDER,
    STITCH_BADGE_WARNING_BG,
    STITCH_BADGE_WARNING_BORDER,
    STITCH_BG_CANVAS,
    STITCH_BORDER,
    STITCH_CARD_BG,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_INPUT_BORDER,
    STITCH_RADIUS_LG,
    STITCH_SUCCESS,
    STITCH_TAB_HOVER,
    STITCH_TEXT,
    STITCH_TEXT_DIM,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
    STITCH_WARNING,
)

REQUIRED = FIELD_ERROR_MESSAGES["REQUIRED"]
INVALID_RATE = FIELD_ERROR_MESSAGES["INVALID_HOURLY_RATE"]
_MONEY_SEPARATORS = re.compile(r"[\s.,_]|vnd|đ", re.IGNORECASE)
DIALOG_WIDTH = 500

# status -> (nhãn, chữ, nền, viền) cho ô "Trạng thái"
_STATUS_CHIPS: dict[MachineStatus, tuple[str, str, str, str]] = {
    MachineStatus.AVAILABLE: ("Trống", STITCH_SUCCESS, STITCH_BADGE_SUCCESS_BG, STITCH_BADGE_SUCCESS_BORDER),
    MachineStatus.IN_USE: ("Đang dùng", STITCH_DANGER, STITCH_BADGE_DANGER_BG, STITCH_BADGE_DANGER_BORDER),
    MachineStatus.MAINTENANCE: ("Bảo trì", STITCH_WARNING, STITCH_BADGE_WARNING_BG, STITCH_BADGE_WARNING_BORDER),
}


def parse_positive_int(text: str) -> int | None:
    """'12.000' / '12,000 VND' / '12000' -> 12000; rỗng, âm, 0, chữ -> None."""
    cleaned = _MONEY_SEPARATORS.sub("", text)
    if not cleaned.isdigit():
        return None
    value = int(cleaned)
    return value if value > 0 else None


class MachineDialog(ctk.CTkToplevel):
    """Dialog modal. Truyền `machine` để sửa, bỏ trống để thêm mới."""

    def __init__(
        self,
        parent: Any,
        context: ViewContext,
        *,
        machine: MachineSummary | None = None,
        runner: TaskRunner | None = None,
        on_saved: Callable[[Machine], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._machine = machine
        self._runner = runner or default_runner()
        self._on_saved = on_saved
        self._submitting = False
        self._is_edit = machine is not None
        store_name = context.session.store_name

        self.title("Sửa máy" if self._is_edit else "Thêm máy")
        self.configure(fg_color=STITCH_BG_CANVAS)
        self.resizable(False, False)
        self.transient(parent)

        box = ctk.CTkFrame(
            self,
            width=DIALOG_WIDTH,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_INPUT_BORDER,
            corner_radius=12,
        )
        box.pack(fill="both", expand=True, padx=8, pady=8)
        body = ctk.CTkFrame(box, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=20)

        # Header: tiêu đề + phụ đề, nút ✕
        header = ctk.CTkFrame(body, fg_color="transparent")
        header.pack(fill="x")
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            titles,
            text="Sửa máy" if self._is_edit else "Thêm máy",
            font=FONT_ST_PAGE_TITLE,
            text_color=STITCH_TEXT_STRONG,
            anchor="w",
            height=24,
        ).pack(fill="x")
        subtitle = (
            f"Cập nhật máy {machine.machine_code} tại cửa hàng {store_name}"
            if machine is not None
            else f"Thêm máy mới vào cửa hàng {store_name}"
        )
        ctk.CTkLabel(titles, text=subtitle, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, anchor="w", height=18).pack(fill="x")
        self._close_button = ctk.CTkButton(
            header,
            text="✕",
            width=30,
            height=30,
            corner_radius=STITCH_RADIUS_LG,
            fg_color="transparent",
            hover_color=STITCH_TAB_HOVER,
            text_color=STITCH_TEXT_MUTED,
            font=FONT_ST_BODY_STRONG,
            command=self.cancel,
        )
        self._close_button.pack(side="right", anchor="n")
        self._divider(body, pady=(12, 16))

        # Các ô nhập
        self._fields: dict[str, StitchField] = {}
        if machine is not None:
            self._read_only(body, "Mã máy", machine.machine_code)
        else:
            self._add_field(body, "code", "Mã máy", placeholder="VD: PC-21", hint="Mã máy phải duy nhất trong hệ thống", mono=True)
        self._add_field(body, "name", "Tên máy", placeholder="Ví dụ: Máy VIP 21")
        self._add_field(
            body,
            "hourly_rate",
            "Giá theo giờ",
            placeholder="10000",
            suffix="VND/giờ",
            mono=True,
            hint="Đổi đơn giá không ảnh hưởng phiên đang chạy" if machine is not None else "",
        )
        if machine is not None:
            self._fields["name"].set_value(machine.name)
            self._fields["hourly_rate"].set_value(str(machine.hourly_rate))

        self._build_info_box(body, store_name, machine.status if machine is not None else MachineStatus.AVAILABLE)
        self._divider(body, pady=(18, 14))

        # Nút
        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x")
        self._save_button = stitch_button(
            buttons,
            "✓  Lưu thay đổi" if self._is_edit else "＋  Thêm máy",
            kind="primary",
            command=self.submit,
            width=130,
            height=34,
        )
        self._save_button.pack(side="right")
        self._cancel_button = stitch_button(buttons, "Hủy", kind="secondary", command=self.cancel, width=72, height=34)
        self._cancel_button.pack(side="right", padx=(0, 10))

        for field in self._fields.values():
            field.bind_return(self.submit)
        self.bind("<Escape>", lambda _e: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        # Không cố định chiều cao: dialog tự giãn khi hiện lỗi dưới field (tránh cắt nút).
        self.minsize(DIALOG_WIDTH, 1)
        self.after(0, self._grab_and_focus)

    # ------------------------------------------------------------------
    @property
    def fields(self) -> dict[str, StitchField]:
        return self._fields

    @property
    def is_submitting(self) -> bool:
        return self._submitting

    # ------------------------------------------------------------------
    # Dựng giao diện
    # ------------------------------------------------------------------
    @staticmethod
    def _divider(master: Any, *, pady: tuple[int, int]) -> None:
        ctk.CTkFrame(master, fg_color=STITCH_BORDER, height=1, corner_radius=0).pack(fill="x", pady=pady)

    def _add_field(self, master: Any, key: str, label: str, **options: Any) -> None:
        field = StitchField(master, label, **options)
        field.pack(fill="x", pady=(0, 14))
        self._fields[key] = field

    @staticmethod
    def _read_only(master: Any, label: str, value: str) -> None:
        """Mã máy khi sửa: chỉ hiển thị, không cho đổi."""
        wrapper = ctk.CTkFrame(master, fg_color="transparent")
        wrapper.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(wrapper, text=label.upper(), font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT, anchor="w", height=16).pack(fill="x")
        box = ctk.CTkFrame(wrapper, fg_color=STITCH_CARD_BG, border_width=1, border_color=STITCH_BORDER, corner_radius=STITCH_RADIUS_LG)
        box.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(box, text=value, font=FONT_ST_MONO_BODY, text_color=STITCH_CYAN, anchor="w", height=34).pack(
            side="left", padx=14
        )
        ctk.CTkLabel(box, text="Không thể đổi", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_DIM).pack(side="right", padx=12)

    def _build_info_box(self, master: Any, store_name: str, status: MachineStatus) -> None:
        info = ctk.CTkFrame(master, fg_color=STITCH_BG_CANVAS, border_width=1, border_color=STITCH_BORDER, corner_radius=STITCH_RADIUS_LG)
        info.pack(fill="x", pady=(2, 0))
        info.grid_columnconfigure((0, 1), weight=1, uniform="info")

        store = ctk.CTkFrame(info, fg_color="transparent")
        store.grid(row=0, column=0, sticky="w", padx=14, pady=10)
        ctk.CTkLabel(store, text="Cửa hàng", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED, anchor="w", height=16).pack(anchor="w")
        store_line = ctk.CTkFrame(store, fg_color="transparent")
        store_line.pack(anchor="w")
        ctk.CTkLabel(store_line, text="●", font=FONT_ST_BODY_STRONG, text_color=STITCH_CYAN, height=18).pack(side="left")
        ctk.CTkLabel(
            store_line, text=f" {store_name}", font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT_STRONG, height=18
        ).pack(side="left")

        state = ctk.CTkFrame(info, fg_color="transparent")
        state.grid(row=0, column=1, sticky="w", padx=14, pady=10)
        ctk.CTkLabel(
            state,
            text="Trạng thái hiện tại" if self._is_edit else "Trạng thái ban đầu",
            font=FONT_ST_MONO_11,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
            height=16,
        ).pack(anchor="w")
        label, color, bg, border = _STATUS_CHIPS[status]
        chip = ctk.CTkFrame(state, fg_color=bg, border_width=1, border_color=border, corner_radius=10)
        chip.pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(chip, text=f"● {label}", font=FONT_ST_MONO_XS_STRONG, text_color=color, height=18).pack(padx=8)

    def _grab_and_focus(self) -> None:
        try:
            self.grab_set()
        except tk.TclError:
            pass  # Cửa sổ chưa hiện (vd. trong test) — bỏ qua.
        first = self._fields.get("code") or self._fields["name"]
        first.focus()

    # ------------------------------------------------------------------
    # Kiểm tra + lưu
    # ------------------------------------------------------------------
    def validate(self) -> tuple[dict[str, Any], dict[str, str]]:
        """Trả (giá trị đã chuẩn hóa, lỗi theo field)."""
        values: dict[str, Any] = {}
        errors: dict[str, str] = {}
        if not self._is_edit:
            values["code"] = self._fields["code"].get_value().strip().upper()
            if not values["code"]:
                errors["code"] = REQUIRED
        values["name"] = self._fields["name"].get_value().strip()
        if not values["name"]:
            errors["name"] = REQUIRED
        rate = parse_positive_int(self._fields["hourly_rate"].get_value())
        if rate is None:
            errors["hourly_rate"] = INVALID_RATE
        values["hourly_rate"] = rate
        return values, errors

    def submit(self) -> None:
        if self._submitting:
            return
        for field in self._fields.values():
            field.set_error(None)
        values, errors = self.validate()
        if errors:
            self._show_field_errors(errors)
            return

        self._set_submitting(True)
        machines, session = self._context.services.machines, self._context.session
        editing = self._machine

        def call() -> Machine:  # chạy ở luồng nền: chỉ gọi service, không chạm widget
            if editing is None:
                return machines.create_machine(
                    values["code"], session.store_id, values["name"], values["hourly_rate"], session
                )
            return machines.update_machine(
                editing.machine_id, values["name"], values["hourly_rate"], session
            )

        self._runner.submit(self, call, self._on_success, self._on_error)

    def _on_success(self, machine: Machine) -> None:
        self._set_submitting(False)
        callback = self._on_saved
        self.close()
        if callback is not None:
            callback(machine)

    def _on_error(self, error: Exception) -> None:
        self._set_submitting(False)
        field_errors = {k: v for k, v in get_field_errors_safe(error).items() if k in self._fields}
        if field_errors:
            # Lỗi gắn được vào field: viền đỏ + 1 Toast tổng quát, giữ dữ liệu đã nhập.
            self._show_field_errors(field_errors)
            ToastManager.show(self, get_user_friendly_error(error), kind="error")
            return
        notify_error(self, error)

    def _show_field_errors(self, errors: dict[str, str]) -> None:
        for key, message in errors.items():
            self._fields[key].set_error(message)
        self._fields[next(iter(errors))].focus()

    def _set_submitting(self, submitting: bool) -> None:
        self._submitting = submitting
        self._save_button.set_busy(submitting)
        self._cancel_button.set_enabled(not submitting)
        self._close_button.configure(state="disabled" if submitting else "normal")

    def cancel(self) -> None:
        if not self._submitting:
            self.close()

    def close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
