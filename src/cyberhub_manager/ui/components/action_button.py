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
        image: Any = None,
        icon_image: Any = None,
        **kwargs: Any,
    ) -> None:
        self._original_text = text
        self._kind = kind
        self._is_busy = False
        initial_state = kwargs.get("state", "normal")
        self._is_enabled = (initial_state != "disabled")
        self._external_command = command

        btn_image = image if image is not None else icon_image

        def_fg, def_hov, def_txt, def_bw, def_bc = self._resolve_colors(kind)
        self._active_fg = kwargs.pop("fg_color", def_fg)
        self._active_hover = kwargs.pop("hover_color", def_hov)
        self._active_text = kwargs.pop("text_color", def_txt)
        self._active_border_width = kwargs.pop("border_width", def_bw)
        self._active_border_color = kwargs.pop("border_color", def_bc)
        font = kwargs.pop("font", FONT_BODY_STRONG)
        corner_radius = kwargs.pop("corner_radius", RADIUS_BUTTON)

        if not self._is_enabled:
            fg_color = "#171F30"
            hover_color = "#171F30"
            text_color = "#64748B"
            border_width = 1
            border_color = "#27344E"
        else:
            fg_color = self._active_fg
            hover_color = self._active_hover
            text_color = self._active_text
            border_width = self._active_border_width
            border_color = self._active_border_color

        super().__init__(
            master=master,
            text=text,
            font=font,
            corner_radius=corner_radius,
            height=height,
            width=width,
            image=btn_image,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            border_width=border_width,
            border_color=border_color,
            command=self._on_click,
            **kwargs,
        )

        try:
            self._canvas.configure(takefocus=1)
            self._canvas.bind("<space>", lambda _e: self._on_click() if self._is_enabled else None)
        except Exception:
            pass

    def _resolve_colors(self, kind: str) -> tuple[str, str, str, int, str]:
        if kind in ("primary_cyan", "stitch_primary"):
            return "#00C6FF", "#33D1FF", "#0B101B", 0, "#00C6FF"
        if kind == "stitch_secondary":
            return "#171F30", "#1E273A", "#E2E8F0", 1, "#27344E"
        if kind == "stitch_danger":
            return "#251218", "#381822", "#FB7185", 1, "#F43F5E"
        if kind == "stitch_success":
            return "#0B1B17", "#0F2D24", "#34D399", 1, "#10B981"
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
        def_fg, def_hov, def_txt, def_bw, def_bc = self._resolve_colors(kind)
        self._active_fg = def_fg
        self._active_hover = def_hov
        self._active_text = def_txt
        self._active_border_width = def_bw
        self._active_border_color = def_bc
        if self._is_enabled and not self._is_busy:
            super().configure(
                fg_color=self._active_fg,
                hover_color=self._active_hover,
                text_color=self._active_text,
                border_width=self._active_border_width,
                border_color=self._active_border_color,
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
            if enabled:
                super().configure(
                    state="normal",
                    fg_color=self._active_fg,
                    hover_color=self._active_hover,
                    text_color=self._active_text,
                    border_width=self._active_border_width,
                    border_color=self._active_border_color,
                )
            else:
                super().configure(
                    state="disabled",
                    fg_color="#171F30",
                    hover_color="#171F30",
                    text_color="#64748B",
                    border_width=1,
                    border_color="#27344E",
                )

    def configure(self, **kwargs: Any) -> None:
        """Cấu hình lại widget, đồng bộ nhãn gốc ngay cả khi đang busy."""
        if "text" in kwargs:
            self._original_text = kwargs["text"]
            if self._is_busy:
                # Không ghi đè chữ hiển thị khi đang busy; lưu lại để phục hồi khi set_busy(False)
                kwargs.pop("text")
        if "state" in kwargs:
            new_state = kwargs.pop("state")
            self._is_enabled = (new_state != "disabled")
            if not self._is_busy:
                kwargs["state"] = new_state
                if not self._is_enabled:
                    kwargs["fg_color"] = "#171F30"
                    kwargs["hover_color"] = "#171F30"
                    kwargs["text_color"] = "#64748B"
                    kwargs["border_width"] = 1
                    kwargs["border_color"] = "#27344E"
                else:
                    kwargs["fg_color"] = self._active_fg
                    kwargs["hover_color"] = self._active_hover
                    kwargs["text_color"] = self._active_text
                    kwargs["border_width"] = self._active_border_width
                    kwargs["border_color"] = self._active_border_color
        if "fg_color" in kwargs:
            self._active_fg = kwargs["fg_color"]
        if "hover_color" in kwargs:
            self._active_hover = kwargs["hover_color"]
        if "text_color" in kwargs:
            self._active_text = kwargs["text_color"]
        if "border_width" in kwargs:
            self._active_border_width = kwargs["border_width"]
        if "border_color" in kwargs:
            self._active_border_color = kwargs["border_color"]
        if "command" in kwargs:
            self._external_command = kwargs.pop("command")
        if "kind" in kwargs:
            kind = kwargs.pop("kind")
            self.set_kind(kind)
        super().configure(**kwargs)
