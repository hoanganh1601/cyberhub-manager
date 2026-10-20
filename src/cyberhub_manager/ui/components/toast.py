"""ToastManager component cho CyberHub Manager.

Quy định: docs/07_DTO_UI_HANDOFF.md mục 7 và docs/03_UI_THEME.md mục 3.4.
- API: ToastManager.show(message: str, kind: str = "info"); kind info/success/warning/error.
- Hiển thị góc trên bên phải màn hình, tự động ẩn sau 3–5 giây.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any

import customtkinter as ctk

from ..theme import (
    BORDER,
    DANGER,
    FONT_BODY,
    FONT_CAPTION,
    INFO,
    RADIUS_CARD,
    SPACING_MD,
    SPACING_SM,
    SUCCESS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)


class ToastNotification(ctk.CTkFrame):
    """Một thông báo nổi góc trên bên phải."""

    def __init__(
        self,
        master: Any,
        message: str,
        *,
        kind: str = "info",
        duration_ms: int = 3500,
        on_close: Any = None,
        **kwargs: Any,
    ) -> None:
        icon, fg_color, border_color = self._resolve_kind(kind)

        super().__init__(
            master=master,
            fg_color=fg_color,
            border_width=1,
            border_color=border_color,
            corner_radius=RADIUS_CARD,
            **kwargs,
        )
        self._on_close = on_close
        self._timer_id: str | None = None

        # Icon
        self._icon_label = ctk.CTkLabel(
            self,
            text=icon,
            font=FONT_BODY,
            text_color=border_color,
            width=24,
        )
        self._icon_label.pack(side="left", padx=(SPACING_MD, SPACING_SM), pady=SPACING_MD)

        # Message text
        self._message_label = ctk.CTkLabel(
            self,
            text=message,
            font=FONT_BODY,
            text_color=TEXT_PRIMARY,
            anchor="w",
            justify="left",
            wraplength=320,
        )
        self._message_label.pack(side="left", fill="both", expand=True, pady=SPACING_MD)

        # Nút đóng
        self._close_btn = ctk.CTkButton(
            self,
            text="✕",
            width=24,
            height=24,
            font=FONT_CAPTION,
            fg_color="transparent",
            hover_color="#1E293B",
            text_color=TEXT_SECONDARY,
            command=self.dismiss,
        )
        self._close_btn.pack(side="right", padx=(SPACING_SM, SPACING_MD), pady=SPACING_MD)

        # Tự đóng sau duration_ms (nếu duration_ms > 0)
        if duration_ms > 0:
            self._timer_id = self.after(duration_ms, self.dismiss)

    def _resolve_kind(self, kind: str) -> tuple[str, str, str]:
        if kind == "success":
            return "✓", "#0A2918", SUCCESS
        if kind == "warning":
            return "⚠", "#352309", WARNING
        if kind == "error":
            return "✕", "#331317", DANGER
        # Default info
        return "ℹ", "#0C2A38", INFO

    def dismiss(self) -> None:
        """Đóng và gỡ bỏ toast."""
        if self._timer_id is not None:
            self.after_cancel(self._timer_id)
            self._timer_id = None
        if self._on_close:
            self._on_close(self)
        try:
            self.destroy()
        except tk.TclError:
            pass


class ToastManager:
    """Quản lý hiển thị và xếp chồng các thông báo Toast."""

    _active_toasts: list[ToastNotification] = []

    @classmethod
    def show(
        cls,
        target_or_message: Any,
        message: str | None = None,
        *,
        kind: str = "info",
        duration_ms: int = 3500,
    ) -> ToastNotification:
        """Hiển thị toast notification.

        Hỗ trợ cả 2 cách gọi:
        1. ToastManager.show(message, kind="success")
        2. ToastManager.show(parent, message, kind="success")
        """
        if message is None:
            msg = str(target_or_message)
            parent = tk._get_default_root("ToastManager.show")
        else:
            msg = message
            parent = target_or_message

        toast = ToastNotification(
            master=parent,
            message=msg,
            kind=kind,
            duration_ms=duration_ms,
            on_close=cls._remove_toast,
        )
        cls._active_toasts.append(toast)
        cls._reposition_toasts()
        return toast

    @classmethod
    def _remove_toast(cls, toast: ToastNotification) -> None:
        if toast in cls._active_toasts:
            cls._active_toasts.remove(toast)
            cls._reposition_toasts()

    @classmethod
    def _reposition_toasts(cls) -> None:
        y_offset = 20
        for toast in cls._active_toasts:
            try:
                if toast.winfo_exists():
                    toast.place(relx=0.98, y=y_offset, anchor="ne")
                    toast.lift()
                    y_offset += toast.winfo_reqheight() + 10
            except tk.TclError:
                pass
