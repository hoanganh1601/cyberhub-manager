"""Khung dialog modal theo Stitch, dùng chung cho các dialog NG-04 trở đi.

- Header: ô icon + tiêu đề + phụ đề + nút ✕ (Stitch: header nền tối hơn, gạch dưới).
- Body: `self.body` để lớp con xếp nội dung.
- Footer: gợi ý phím tắt bên trái ("Nhấn Enter để … • Esc để hủy"), nút Hủy + nút chính bên phải.
- Enter = nút chính, Esc / ✕ = Hủy; đang gửi thì khóa Hủy/✕ và nút chính hiện "Processing…".
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ..components.action_button import ActionButton
from ..components.stitch_button import stitch_button
from ..theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_LABEL_CAPS,
    FONT_ST_MONO_11,
    FONT_ST_MONO_SM,
    FONT_ST_MONO_XS_STRONG,
    FONT_ST_PAGE_TITLE,
    STITCH_BG_CANVAS,
    STITCH_BG_CHROME,
    STITCH_BORDER,
    STITCH_CARD_BG,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_ICON_CYAN_BG,
    STITCH_ICON_CYAN_BORDER,
    STITCH_ICON_DANGER_BG,
    STITCH_ICON_DANGER_BORDER,
    STITCH_ICON_SUCCESS_BG,
    STITCH_ICON_SUCCESS_BORDER,
    STITCH_INPUT_BORDER,
    STITCH_RADIUS,
    STITCH_RADIUS_LG,
    STITCH_SUCCESS,
    STITCH_TAB_HOVER,
    STITCH_TEXT,
    STITCH_TEXT_DIM,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
)

# tone -> (màu icon, nền ô icon, viền ô icon)
_ICON_TONES = {
    "cyan": (STITCH_CYAN, STITCH_ICON_CYAN_BG, STITCH_ICON_CYAN_BORDER),
    "danger": (STITCH_DANGER, STITCH_ICON_DANGER_BG, STITCH_ICON_DANGER_BORDER),
    "success": (STITCH_SUCCESS, STITCH_ICON_SUCCESS_BG, STITCH_ICON_SUCCESS_BORDER),
}


def divider(master: Any, *, pady: tuple[int, int] = (0, 0)) -> None:
    ctk.CTkFrame(master, fg_color=STITCH_BORDER, height=1, corner_radius=0).pack(fill="x", pady=pady)


def chip(master: Any, text: str, color: str, bg: str, border: str, *, pill: bool = False) -> ctk.CTkFrame:
    """Nhãn trạng thái nhỏ "● Hoạt động"."""
    box = ctk.CTkFrame(master, fg_color=bg, border_width=1, border_color=border, corner_radius=10 if pill else STITCH_RADIUS)
    ctk.CTkLabel(box, text=f"● {text}", font=FONT_ST_MONO_XS_STRONG, text_color=color, height=18).pack(padx=8)
    return box


def info_panel(master: Any, title: str = "", *, right_note: str = "", locked: bool = False) -> ctk.CTkFrame:
    """Hộp thông tin nền tối viền mảnh (Stitch: "THÔNG TIN HỆ THỐNG…"). Trả frame nội dung."""
    panel = ctk.CTkFrame(master, fg_color=STITCH_BG_CANVAS, border_width=1, border_color=STITCH_BORDER, corner_radius=STITCH_RADIUS_LG)
    panel.pack(fill="x")
    inner = ctk.CTkFrame(panel, fg_color="transparent")
    inner.pack(fill="x", padx=14, pady=10)
    if title:
        head = ctk.CTkFrame(inner, fg_color="transparent")
        head.pack(fill="x")
        prefix = "🔒 " if locked else "● "
        ctk.CTkLabel(head, text=prefix, font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED if locked else STITCH_CYAN, height=16).pack(side="left")
        ctk.CTkLabel(head, text=title.upper(), font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT, height=16).pack(side="left")
        if right_note:
            ctk.CTkLabel(head, text=right_note.upper(), font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_DIM, height=16).pack(side="right")
        divider(inner, pady=(8, 6))
    return inner


def info_row(master: Any, label: str, value: Any, *, value_color: str = STITCH_TEXT, mono: bool = True, italic: bool = False) -> None:
    """Một dòng "Nhãn: giá trị" trong info_panel; value là chuỗi hoặc widget tạo bởi hàm (master) -> widget."""
    line = ctk.CTkFrame(master, fg_color="transparent")
    line.pack(fill="x", pady=2)
    ctk.CTkLabel(line, text=label, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=20).pack(side="left")
    if callable(value):
        value(line).pack(side="right")
        return
    font = FONT_ST_MONO_11 if italic else (FONT_ST_MONO_SM if mono else FONT_ST_BODY_STRONG)
    ctk.CTkLabel(line, text=value, font=font, text_color=value_color, height=20).pack(side="right")


class StitchDialog(ctk.CTkToplevel):
    """Dialog modal theo Stitch. Lớp con dựng nội dung trong `self.body` rồi gọi `self.finish()`."""

    def __init__(
        self,
        parent: Any,
        *,
        title: str,
        subtitle: str,
        icon: str,
        icon_tone: str = "cyan",
        width: int = 560,
        hint: str = "",
        confirm_text: str = "Lưu",
        confirm_kind: str = "primary",
        cancel_text: str = "Hủy",
    ) -> None:
        super().__init__(parent)
        self._submitting = False
        self._width = width
        self.title(title)
        self.configure(fg_color=STITCH_BG_CANVAS)
        self.resizable(False, False)
        self.transient(parent)

        shell = ctk.CTkFrame(self, width=width, fg_color=STITCH_CARD_BG, border_width=1, border_color=STITCH_INPUT_BORDER, corner_radius=12)
        shell.pack(fill="both", expand=True, padx=8, pady=8)

        # Header
        header = ctk.CTkFrame(shell, fg_color="transparent")
        header.pack(fill="x", padx=22, pady=(18, 14))
        color, bg, border = _ICON_TONES.get(icon_tone, _ICON_TONES["cyan"])
        icon_box = ctk.CTkFrame(header, width=40, height=40, fg_color=bg, border_width=1, border_color=border, corner_radius=STITCH_RADIUS_LG)
        icon_box.pack(side="left")
        icon_box.pack_propagate(False)
        ctk.CTkLabel(icon_box, text=icon, font=("Segoe UI Symbol", 16), text_color=color).pack(expand=True)
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left", padx=12, fill="x", expand=True)
        ctk.CTkLabel(titles, text=title, font=FONT_ST_PAGE_TITLE, text_color=STITCH_TEXT_STRONG, anchor="w", height=24).pack(fill="x")
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
        divider(shell)

        self.body = ctk.CTkFrame(shell, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=22, pady=16)

        # Footer
        divider(shell)
        footer = ctk.CTkFrame(shell, fg_color=STITCH_BG_CHROME, corner_radius=0)
        footer.pack(fill="x", padx=1, pady=(0, 12))
        inner = ctk.CTkFrame(footer, fg_color="transparent")
        inner.pack(fill="x", padx=22, pady=(12, 0))
        ctk.CTkLabel(inner, text=hint, font=FONT_ST_MONO_11, text_color=STITCH_TEXT_DIM).pack(side="left")
        self.confirm_button: ActionButton = stitch_button(inner, confirm_text, kind=confirm_kind, command=self.submit, width=160, height=34)
        self.confirm_button.pack(side="right")
        self.cancel_button: ActionButton = stitch_button(inner, cancel_text, kind="secondary", command=self.cancel, width=72, height=34)
        self.cancel_button.pack(side="right", padx=(0, 10))

        self.bind("<Escape>", lambda _e: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)

    # ------------------------------------------------------------------
    def finish(self, focus: Callable[[], None] | None = None) -> None:
        """Gọi cuối __init__ của lớp con: chốt kích thước, grab và focus ô đầu tiên."""
        self.minsize(self._width, 1)
        self.bind("<Return>", lambda _e: self.submit())

        def grab() -> None:
            try:
                self.grab_set()
            except tk.TclError:
                pass  # Cửa sổ chưa hiện (vd. trong test) — bỏ qua.
            if focus is not None:
                focus()

        self.after(0, grab)

    @property
    def is_submitting(self) -> bool:
        return self._submitting

    def set_submitting(self, submitting: bool) -> None:
        self._submitting = submitting
        self.confirm_button.set_busy(submitting)
        self.cancel_button.set_enabled(not submitting)
        self._close_button.configure(state="disabled" if submitting else "normal")

    def submit(self) -> None:  # lớp con ghi đè
        raise NotImplementedError

    def cancel(self) -> None:
        if not self._submitting:
            self.close()

    def close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
