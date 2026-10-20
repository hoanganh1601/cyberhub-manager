"""FormField component cho CyberHub Manager.

Quy định: docs/07_DTO_UI_HANDOFF.md mục 7 và docs/03_UI_THEME.md mục 3.4.
- API: get_value() -> str, set_value(value: str), set_error(message: str | None), set_enabled(enabled: bool).
- Label ở trên; placeholder không thay thế cho label.
- Hỗ trợ trường mật khẩu với nút bật/tắt hiện/ẩn.
- Viền đổi sang DANGER và hiển thị message 12 px bên dưới khi có lỗi.
"""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ..theme import (
    BG_SURFACE,
    BG_SURFACE_HOVER,
    BORDER,
    DANGER,
    FONT_BODY,
    FONT_CAPTION,
    HEIGHT_INPUT,
    RADIUS_INPUT,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class FormField(ctk.CTkFrame):
    """Trường nhập liệu chuẩn gồm: Nhãn trên, Ô nhập (hỗ trợ password toggle), Nhãn lỗi dưới."""

    def __init__(
        self,
        master: Any,
        label: str,
        *,
        placeholder: str = "",
        is_password: bool = False,
        initial_value: str = "",
        height: int = HEIGHT_INPUT,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master=master,
            fg_color="transparent",
            **kwargs,
        )
        self._is_password = is_password
        self._password_visible = False

        # 1. Label ở trên
        self._label = ctk.CTkLabel(
            self,
            text=label,
            font=FONT_CAPTION,
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self._label.pack(fill="x", padx=2, pady=(0, 4))

        # 2. Khung chứa input và toggle button (nếu là password)
        self._input_container = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        self._input_container.pack(fill="x")

        entry_kwargs: dict[str, Any] = {}
        if placeholder:
            entry_kwargs["placeholder_text"] = placeholder
            entry_kwargs["placeholder_text_color"] = TEXT_MUTED

        self._entry = ctk.CTkEntry(
            self._input_container,
            text_color=TEXT_PRIMARY,
            fg_color=BG_SURFACE,
            border_color=BORDER,
            border_width=1,
            corner_radius=RADIUS_INPUT,
            height=height,
            font=FONT_BODY,
            show="*" if is_password else "",
            **entry_kwargs,
        )
        self._entry.pack(side="left", fill="x", expand=True)

        if initial_value:
            self._entry.insert(0, initial_value)

        # Nút chuyển đổi hiện/ẩn mật khẩu
        self._toggle_btn: ctk.CTkButton | None = None
        if is_password:
            self._toggle_btn = ctk.CTkButton(
                self._input_container,
                text="Hiện",
                width=48,
                height=height,
                font=FONT_CAPTION,
                fg_color=BG_SURFACE,
                hover_color=BG_SURFACE_HOVER,
                text_color=TEXT_SECONDARY,
                border_color=BORDER,
                border_width=1,
                corner_radius=RADIUS_INPUT,
                command=self._toggle_password_visibility,
            )
            self._toggle_btn.pack(side="right", padx=(6, 0))

        # 3. Label báo lỗi ở dưới (ẩn khi không có lỗi)
        self._error_label = ctk.CTkLabel(
            self,
            text="",
            font=FONT_CAPTION,
            text_color=DANGER,
            anchor="w",
        )

    def _toggle_password_visibility(self) -> None:
        """Đảo trạng thái hiển thị mật khẩu."""
        self._password_visible = not self._password_visible
        if self._password_visible:
            self._entry.configure(show="")
            if self._toggle_btn:
                self._toggle_btn.configure(text="Ẩn")
        else:
            self._entry.configure(show="*")
            if self._toggle_btn:
                self._toggle_btn.configure(text="Hiện")

    def get_value(self) -> str:
        """Lấy giá trị chuỗi đang nhập."""
        return self._entry.get()

    def set_value(self, value: str) -> None:
        """Thiết lập giá trị chuỗi."""
        self._entry.delete(0, "end")
        self._entry.insert(0, value)

    def set_error(self, message: str | None) -> None:
        """Gắn thông báo lỗi hoặc xóa lỗi.

        Khi có lỗi: đổi viền sang DANGER, hiển thị thông báo lỗi 12 px bên dưới.
        Khi xóa lỗi: trả viền về BORDER và ẩn thông báo.
        """
        if message:
            self._entry.configure(border_color=DANGER, border_width=1.5)
            self._error_label.configure(text=message)
            if not self._error_label.winfo_ismapped():
                self._error_label.pack(fill="x", padx=2, pady=(4, 0))
        else:
            self._entry.configure(border_color=BORDER, border_width=1)
            self._error_label.configure(text="")
            if self._error_label.winfo_ismapped():
                self._error_label.pack_forget()

    def set_enabled(self, enabled: bool) -> None:
        """Bật hoặc tắt khả năng tương tác của trường nhập liệu."""
        self._entry.configure(state="normal" if enabled else "disabled")
        if self._toggle_btn:
            self._toggle_btn.configure(state="normal" if enabled else "disabled")

    def focus(self) -> None:
        """Đặt focus vào ô nhập liệu."""
        self._entry.focus_set()
