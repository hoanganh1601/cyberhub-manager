"""ActionButton component cho CyberHub Manager.

Quy định: docs/07_DTO_UI_HANDOFF.md mục 7 và docs/03_UI_THEME.md mục 3.4.
- Các kiểu (kind): primary, secondary, success, danger, ghost.
- API: set_busy(busy: bool), set_enabled(enabled: bool), set_kind(kind: str).
- Busy giữ nhãn gốc để phục hồi; chặn double click khi đang bận.
"""

from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from ..theme import (
    ACCENT,
    ACCENT_HOVER,
    BG_SURFACE,
    BG_SURFACE_HOVER,
    BORDER,
    DANGER,
    DANGER_HOVER,
    DISABLED,
    FONT_BODY_STRONG,
    HEIGHT_BUTTON,
    RADIUS_BUTTON,
    SUCCESS,
    SUCCESS_HOVER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class ActionButton(ctk.CTkButton):
    """Nút bấm có các biến thể thẩm mỹ và hỗ trợ trạng thái busy chống double-click."""

    def __init__(
        self,
        master: Any,
        text: str = "Nút",
        *,
        kind: str = "primary",
        command: Callable[[], None] | None = None,
        height: int = HEIGHT_BUTTON,
        width: int = 120,
        **kwargs: Any,
    ) -> None:
        self._original_text = text
        self._kind = kind
        self._is_busy = False
        self._is_enabled = True
        self._external_command = command

        fg_color, hover_color, text_color, border_width, border_color = self._resolve_colors(kind)

        super().__init__(
            master=master,
            text=text,
            font=FONT_BODY_STRONG,
            corner_radius=RADIUS_BUTTON,
            height=height,
            width=width,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            border_width=border_width,
            border_color=border_color,
            command=self._on_click,
            **kwargs,
        )

    def _resolve_colors(self, kind: str) -> tuple[str, str, str, int, str]:
        if kind == "primary":
            return ACCENT, ACCENT_HOVER, TEXT_PRIMARY, 0, BORDER
        if kind == "secondary":
            return BG_SURFACE, BG_SURFACE_HOVER, TEXT_PRIMARY, 1, BORDER
        if kind == "success":
            return SUCCESS, SUCCESS_HOVER, TEXT_PRIMARY, 0, BORDER
        if kind == "danger":
            return DANGER, DANGER_HOVER, TEXT_PRIMARY, 0, BORDER
        if kind == "ghost":
            return "transparent", BG_SURFACE_HOVER, TEXT_SECONDARY, 0, BORDER
        # Mặc định primary
        return ACCENT, ACCENT_HOVER, TEXT_PRIMARY, 0, BORDER

    def set_kind(self, kind: str) -> None:
        """Đổi phong cách (kind) của nút bấm."""
        self._kind = kind
        fg_color, hover_color, text_color, border_width, border_color = self._resolve_colors(kind)
        super().configure(
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            border_width=border_width,
            border_color=border_color,
        )

    @property
    def is_busy(self) -> bool:
        """Kiểm tra nút có đang trong trạng thái bận (busy) hay không."""
        return self._is_busy

    @property
    def is_enabled(self) -> bool:
        """Kiểm tra nút có đang được kích hoạt hay không."""
        return self._is_enabled

    def _on_click(self) -> None:
        """Bộ điều phối click: ngăn chặn khi đang busy hoặc disable.

        Lưu ý: ActionButton không tự chuyển busy. Caller (màn hình / service handler)
        chịu trách nhiệm gọi `button.set_busy(True)` trước khi gọi service async/chờ,
        và đảm bảo `finally: button.set_busy(False)`.
        """
        if self._is_busy or not self._is_enabled:
            return
        if self._external_command:
            self._external_command()

    def set_busy(self, busy: bool, *, busy_text: str = "Processing…") -> None:
        """Đặt trạng thái đang xử lý.

        Khi busy=True: hiện 'Processing…' (hoặc busy_text tùy biến), disable nút, chặn double click.
        Khi busy=False: phục hồi nhãn ban đầu (hoặc nhãn mới nhất đã configure) và trạng thái enabled.
        """
        self._is_busy = busy
        if busy:
            super().configure(
                text=busy_text,
                state="disabled",
            )
        else:
            super().configure(
                text=self._original_text,
                state="normal" if self._is_enabled else "disabled",
            )

    def set_enabled(self, enabled: bool) -> None:
        """Bật hoặc tắt nút bấm."""
        self._is_enabled = enabled
        if not self._is_busy:
            super().configure(state="normal" if enabled else "disabled")

    def configure(self, **kwargs: Any) -> None:
        """Cấu hình lại widget, đồng bộ nhãn gốc ngay cả khi đang busy."""
        if "text" in kwargs:
            self._original_text = kwargs["text"]
            if self._is_busy:
                # Không ghi đè chữ hiển thị khi đang busy; lưu lại để phục hồi khi set_busy(False)
                kwargs.pop("text")
        if "command" in kwargs:
            self._external_command = kwargs.pop("command")
        if "kind" in kwargs:
            kind = kwargs.pop("kind")
            self.set_kind(kind)
        super().configure(**kwargs)
