"""NG-03 — Dialog thêm / sửa máy (Manager/Admin).

- Thêm: mã máy, tên máy, đơn giá/giờ -> machines.create_machine(...)
- Sửa: tên máy, đơn giá/giờ (mã máy không đổi) -> machines.update_machine(...)
- Kiểm tra sơ bộ ở UI (bắt buộc nhập, đơn giá nguyên dương); service vẫn kiểm tra lại.
- Lỗi Validation/Conflict gắn vào đúng field qua get_field_errors_safe(); giữ dữ liệu đã nhập.
- Đang lưu: nút "Processing…", chặn double click/Enter (07 mục 7).
"""

from __future__ import annotations

import re
import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ...domain.dtos import MachineSummary
from ...domain.models import Machine
from ..app_shell import ViewContext
from ..background import TaskRunner, default_runner
from ..components import FormField, ToastManager
from ..components.stitch_button import stitch_button
from ..feedback import notify_error
from ..messages import (
    FIELD_ERROR_MESSAGES,
    MSG_CANCEL,
    get_field_errors_safe,
    get_user_friendly_error,
)
from ..theme import (
    DIALOG_WIDTH_MIN,
    FONT_ST_BODY,
    FONT_ST_MONO_VALUE,
    FONT_ST_MONO_XS,
    FONT_ST_PAGE_TITLE,
    STITCH_BG_CANVAS,
    STITCH_CARD_BG,
    STITCH_NAV_ACTIVE_BORDER,
    STITCH_RADIUS_LG,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
)

REQUIRED = FIELD_ERROR_MESSAGES["REQUIRED"]
INVALID_RATE = FIELD_ERROR_MESSAGES["INVALID_HOURLY_RATE"]
_MONEY_SEPARATORS = re.compile(r"[\s.,_]|vnd|đ", re.IGNORECASE)


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
        context: ViewContext | Any,
        *,
        machine: MachineSummary | None = None,
        runner: TaskRunner | None = None,
        on_saved: Callable[[Machine], None] | None = None,
        actor: Any = None,
        language: str = "vi",
        on_success: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent)
        if not isinstance(context, ViewContext):
            context = ViewContext(services=context, session=actor, language=language, navigate=lambda _: True)
        self._context = context
        self._language = getattr(context, "language", language)
        self._machine = machine
        self._runner = runner or default_runner()
        self._on_saved = on_saved or on_success
        self._submitting = False
        self._is_edit = machine is not None

        is_vi = self._language == "vi"
        if self._is_edit:
            self.title("Sửa máy" if is_vi else "Edit Machine")
        else:
            self.title("Thêm máy" if is_vi else "Add Machine")
        self.configure(fg_color=STITCH_BG_CANVAS)
        self.resizable(False, False)
        self.transient(parent)

        box = ctk.CTkFrame(
            self,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_NAV_ACTIVE_BORDER,
            corner_radius=STITCH_RADIUS_LG,
        )
        box.pack(fill="both", expand=True, padx=8, pady=8)
        body = ctk.CTkFrame(box, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(
            body,
            text="Sửa thông tin máy" if self._is_edit else "Thêm máy mới",
            font=FONT_ST_PAGE_TITLE,
            text_color=STITCH_TEXT_STRONG,
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            body,
            text=(
                "Đổi đơn giá không ảnh hưởng phiên đang chạy."
                if self._is_edit
                else "Máy mới ở trạng thái Trống."
            ),
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", pady=(2, 14))

        self._fields: dict[str, FormField] = {}
        if self._is_edit:
            assert machine is not None
            ctk.CTkLabel(body, text="MÃ MÁY", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED, anchor="w").pack(fill="x")
            ctk.CTkLabel(
                body, text=machine.machine_code, font=FONT_ST_MONO_VALUE, text_color=STITCH_TEXT_STRONG, anchor="w"
            ).pack(fill="x", pady=(0, 10))
        else:
            self._add_field(body, "code", "Mã máy", "VD: PC21")
        self._add_field(body, "name", "Tên máy", "VD: Máy VIP 21")
        self._add_field(body, "hourly_rate", "Đơn giá/giờ (VND)", "VD: 12000")
        if machine is not None:
            self._fields["name"].set_value(machine.name)
            self._fields["hourly_rate"].set_value(str(machine.hourly_rate))

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x", pady=(16, 0))
        self._save_button = stitch_button(
            buttons, "Lưu" if self._is_edit else "Thêm máy", kind="primary", command=self.submit
        )
        self._save_button.pack(side="right")
        self._cancel_button = stitch_button(buttons, MSG_CANCEL, kind="secondary", command=self.cancel, width=90)
        self._cancel_button.pack(side="right", padx=(0, 8))

        for field in self._fields.values():
            field.bind_return(self.submit)
        self.bind("<Escape>", lambda _e: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        # Không cố định chiều cao: dialog tự giãn khi hiện lỗi dưới field (tránh cắt nút).
        self.minsize(DIALOG_WIDTH_MIN, 1)
        self.after(0, self._grab_and_focus)

    # ------------------------------------------------------------------
    @property
    def fields(self) -> dict[str, FormField]:
        return self._fields

    @property
    def is_submitting(self) -> bool:
        return self._submitting

    def _add_field(self, master: Any, key: str, label: str, placeholder: str) -> None:
        field = FormField(master, label, placeholder=placeholder)
        field.pack(fill="x", pady=(0, 10))
        self._fields[key] = field

    def _grab_and_focus(self) -> None:
        try:
            self.grab_set()
        except tk.TclError:
            pass  # Cửa sổ chưa hiện (vd. trong test) — bỏ qua.
        first = self._fields.get("code") or self._fields["name"]
        first.focus()

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

    def _on_escape(self) -> None:
        self.cancel()

    def cancel(self) -> None:
        if not self._submitting:
            self.close()

    _handle_close = cancel

    def close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
