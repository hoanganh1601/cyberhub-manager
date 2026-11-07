"""Ô nhập theo Stitch, dùng chung cho các dialog NG-03/NG-04.

Nhãn in hoa + dấu * cyan, ô nền tối viền cyan khi focus / đỏ khi lỗi, đuôi đơn vị (tùy chọn),
nút hiện/ẩn mật khẩu (tùy chọn), chú thích xám và dòng lỗi đỏ bên dưới.
Cùng API với FormField (NG-01): get_value / set_value / set_error / focus / bind_return.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ..theme import (
    FONT_ST_BODY,
    FONT_ST_LABEL_CAPS,
    FONT_ST_MONO_11,
    FONT_ST_MONO_BODY,
    STITCH_BG_CANVAS,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_INPUT_BORDER,
    STITCH_RADIUS_LG,
    STITCH_TAB_HOVER,
    STITCH_TEXT,
    STITCH_TEXT_DIM,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
)


class StitchField(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        label: str,
        *,
        placeholder: str = "",
        hint: str = "",
        suffix: str = "",
        mono: bool = False,
        required: bool = True,
        password: bool = False,
        justify: str = "left",
        uppercase_label: bool = True,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._has_error = False
        self._password = password
        self._revealed = False

        title = ctk.CTkFrame(self, fg_color="transparent")
        title.pack(fill="x")
        ctk.CTkLabel(
            title,
            text=label.upper() if uppercase_label else label,
            font=FONT_ST_LABEL_CAPS,
            text_color=STITCH_TEXT,
            height=16,
        ).pack(side="left")
        if required:
            ctk.CTkLabel(title, text=" *", font=FONT_ST_LABEL_CAPS, text_color=STITCH_CYAN, height=16).pack(side="left")

        self._box = ctk.CTkFrame(
            self, fg_color=STITCH_BG_CANVAS, border_width=1, border_color=STITCH_INPUT_BORDER, corner_radius=STITCH_RADIUS_LG
        )
        self._box.pack(fill="x", pady=(6, 0))
        self._entry = ctk.CTkEntry(
            self._box,
            height=34,
            border_width=0,
            corner_radius=0,  # khung bo góc là self._box; entry vuông để không lộ mép
            fg_color=STITCH_BG_CANVAS,
            text_color=STITCH_TEXT_STRONG,
            placeholder_text=placeholder,
            placeholder_text_color=STITCH_TEXT_DIM,
            font=FONT_ST_MONO_BODY if mono else FONT_ST_BODY,
            show="•" if password else "",
            justify=justify,
        )
        self._entry.pack(side="left", fill="x", expand=True, padx=(8, 4), pady=2)
        self._toggle: ctk.CTkButton | None = None
        if password:
            self._toggle = ctk.CTkButton(
                self._box,
                text="👁",
                width=30,
                height=28,
                fg_color="transparent",
                hover_color=STITCH_TAB_HOVER,
                text_color=STITCH_TEXT_MUTED,
                font=FONT_ST_BODY,
                command=self.toggle_password,
            )
            self._toggle.pack(side="right", padx=(0, 6))
        elif suffix:
            ctk.CTkLabel(self._box, text=suffix, font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED).pack(side="right", padx=(0, 12))
        self._entry.bind("<FocusIn>", lambda _e: self._paint_border(focused=True), add="+")
        self._entry.bind("<FocusOut>", lambda _e: self._paint_border(focused=False), add="+")

        if hint:
            ctk.CTkLabel(self, text=hint, font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED, anchor="w", height=16).pack(
                fill="x", pady=(4, 0)
            )
        self._error_label = ctk.CTkLabel(
            self, text="", font=FONT_ST_MONO_11, text_color=STITCH_DANGER, anchor="w", justify="left", height=16, wraplength=320
        )
        # Dòng lỗi xuống dòng theo đúng bề rộng ô (ô nửa cột hay cả dòng đều vừa).
        self.bind("<Configure>", lambda event: self._error_label.configure(wraplength=max(event.width - 8, 120)), add="+")

    # ------------------------------------------------------------------
    @property
    def entry(self) -> ctk.CTkEntry:
        return self._entry

    @property
    def is_revealed(self) -> bool:
        return self._revealed

    def _paint_border(self, *, focused: bool) -> None:
        if self._has_error:
            color = STITCH_DANGER
        else:
            color = STITCH_CYAN if focused else STITCH_INPUT_BORDER
        self._box.configure(border_color=color)

    def toggle_password(self) -> None:
        if not self._password:
            return
        self._revealed = not self._revealed
        self._entry.configure(show="" if self._revealed else "•")

    def get_value(self) -> str:
        return self._entry.get()

    def set_value(self, value: str) -> None:
        self._entry.delete(0, "end")
        self._entry.insert(0, value)

    def set_error(self, message: str | None) -> None:
        self._has_error = bool(message)
        self._error_label.configure(text=message or "")
        # winfo_manager() thay vì winfo_ismapped(): đúng cả khi cửa sổ chưa hiện (test).
        if message and not self._error_label.winfo_manager():
            self._error_label.pack(fill="x", pady=(4, 0))
        elif not message and self._error_label.winfo_manager():
            self._error_label.pack_forget()
        self._paint_border(focused=False)

    def focus(self) -> None:
        self._entry.focus_set()

    def bind_return(self, callback: Callable[[], None]) -> None:
        self._entry.bind("<Return>", lambda _event: callback())

    def bind_change(self, callback: Callable[[], None]) -> None:
        """Gọi callback mỗi lần người dùng gõ (dùng cho xem trước số dư mới)."""
        self._entry.bind("<KeyRelease>", lambda _event: callback(), add="+")
