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
    BG_DANGER_SUBTLE,
    BG_INFO_SUBTLE,
    BG_MUTED_SUBTLE,
    BG_SUCCESS_SUBTLE,
    BG_WARNING_SUBTLE,
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
        icon, fg_color, border_color, text_color, icon_bg = self._resolve_kind(kind)

        super().__init__(
            master=master,
            fg_color=fg_color,
            border_width=1,
            border_color=border_color,
            corner_radius=8,
            **kwargs,
        )
        self._on_close = on_close
        self._timer_id: str | None = None

        # Container inner with horizontal layout matching Stitch
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=8)

        # Icon pill (20x20 circular pill)
        self._icon_box = ctk.CTkLabel(
            inner,
            text=icon,
            font=("Inter", 11, "bold"),
            text_color=text_color,
            fg_color=icon_bg,
            width=22,
            height=22,
            corner_radius=11,
        )
        self._icon_box.pack(side="left", padx=(0, 10))

        # Message text
        self._message_label = ctk.CTkLabel(
            inner,
            text=message,
            font=("Inter", 12, "bold"),
            text_color=text_color,
            anchor="w",
            justify="left",
            wraplength=340,
        )
        self._message_label.pack(side="left", fill="both", expand=True)

        # Nút đóng
        self._close_btn = ctk.CTkButton(
            inner,
            text="✕",
            width=20,
            height=20,
            font=("Inter", 10, "normal"),
            fg_color="transparent",
            hover_color=icon_bg,
            text_color=text_color,
            command=self.dismiss,
        )
        self._close_btn.pack(side="right", padx=(8, 0))

        # Tự đóng sau duration_ms (nếu duration_ms > 0)
        if duration_ms > 0:
            self._timer_id = self.after(duration_ms, self.dismiss)

    def _resolve_kind(self, kind: str) -> tuple[str, str, str, str, str]:
        """Trả về (icon, bg_color, border_color, text_color, icon_bg) theo chuẩn Stitch."""
        if kind == "success":
            # Stitch: bg-[#0b1b17] border-emerald-500/40 text-emerald-400
            return "✓", "#0B1B17", "#059669", "#34D399", "#0F2D24"
        if kind == "warning":
            # Stitch warning dark amber
            return "⚠", "#261E10", "#D97706", "#FBBF24", "#3D2C14"
        if kind == "error":
            # Stitch: bg-[#251218] border-rose-500/40 text-rose-400
            return "✕", "#251218", "#E11D48", "#FB7185", "#381822"
        # Default info: Stitch Cyan
        return "ℹ", "#0C1E2B", "#0088CC", "#00C6FF", "#0E2E42"

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
        y_offset = 56
        for toast in cls._active_toasts:
            try:
                if toast.winfo_exists():
                    toast.place(relx=0.98, y=y_offset, anchor="ne")
                    toast.lift()
                    y_offset += toast.winfo_reqheight() + 10
            except tk.TclError:
                pass
