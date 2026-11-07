"""FilterBar component cho CyberHub Manager theo phong cách Stitch.

Hiển thị thanh lọc phân đoạn (segmented tabs/pills) cho các màn hình danh sách và lưới máy.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ..theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_MONO_SM,
    STITCH_CARD_BG,
    STITCH_CARD_BORDER,
    STITCH_CHIP_BG,
    STITCH_CHIP_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_RADIUS,
    STITCH_RADIUS_LG,
    STITCH_SUCCESS,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_ON_CYAN,
    STITCH_WARNING,
)

_TONE_COLORS: dict[str, str] = {
    "default": STITCH_TEXT_MUTED,
    "cyan": STITCH_CYAN,
    "emerald": STITCH_SUCCESS,
    "rose": STITCH_DANGER,
    "amber": STITCH_WARNING,
}

_TONE_BORDERS: dict[str, str] = {
    "default": STITCH_CHIP_BORDER,
    "cyan": "#0E4057",
    "emerald": "#164E33",
    "rose": "#4C1D24",
    "amber": "#4D3814",
}


class FilterBar(ctk.CTkFrame):
    """Thanh lọc trạng thái với các nút pill bo tròn và nhãn telemetry bên phải."""

    def __init__(
        self,
        master: Any,
        options: list[tuple[str, str, int, str]],
        *,
        on_filter_changed: Callable[[str], None] | None = None,
        right_hint: str = "● Cập nhật tự động: 5s",
        initial_key: str = "all",
        height: int = 42,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master=master,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
            height=height,
            **kwargs,
        )
        self.pack_propagate(False)

        self._filter_options = options
        self._on_filter_changed = on_filter_changed
        self._current_key = initial_key
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._raw_labels: dict[str, tuple[str, str]] = {}  # key -> (label, tone)

        # Left container: Filter pills
        self._pills_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._pills_frame.pack(side="left", padx=10, pady=5)

        for key, label, count, tone in options:
            self._raw_labels[key] = (label, tone)
            btn = ctk.CTkButton(
                self._pills_frame,
                text=f"{label} ({count})",
                height=28,
                corner_radius=STITCH_RADIUS,
                font=FONT_ST_BODY_STRONG if key == initial_key else FONT_ST_BODY,
                command=lambda k=key: self._on_btn_click(k),
            )
            btn.pack(side="left", padx=(0, 6))
            self._buttons[key] = btn

        # Right container: Auto-refresh telemetry indicator
        self._right_label = ctk.CTkLabel(
            self,
            text=right_hint,
            font=FONT_ST_MONO_SM,
            text_color=STITCH_TEXT_MUTED,
        )
        self._right_label.pack(side="right", padx=(0, 14))

        self._refresh_styles()

    def _on_btn_click(self, key: str) -> None:
        if key == self._current_key:
            return
        self._current_key = key
        self._refresh_styles()
        if self._on_filter_changed:
            self._on_filter_changed(key)

    def _refresh_styles(self) -> None:
        for key, btn in self._buttons.items():
            label, tone = self._raw_labels.get(key, ("", "default"))
            active = key == self._current_key
            if active:
                btn.configure(
                    fg_color=STITCH_CYAN,
                    hover_color=STITCH_CYAN,
                    border_width=0,
                    text_color=STITCH_TEXT_ON_CYAN,
                    font=FONT_ST_BODY_STRONG,
                )
            else:
                normal_text = _TONE_COLORS.get(tone, STITCH_TEXT_MUTED)
                border_color = _TONE_BORDERS.get(tone, STITCH_CHIP_BORDER)
                btn.configure(
                    fg_color=STITCH_CHIP_BG,
                    hover_color="#1F2A3D",
                    border_width=1,
                    border_color=border_color,
                    text_color=normal_text,
                    font=FONT_ST_BODY,
                )

    def set_counts(self, counts: dict[str, int]) -> None:
        """Cập nhật số đếm trong ngoặc cho từng nút."""
        for key, btn in self._buttons.items():
            label, _ = self._raw_labels.get(key, ("", "default"))
            count = counts.get(key, 0)
            btn.configure(text=f"{label} ({count})")

    def set_right_hint(self, hint: str) -> None:
        self._right_label.configure(text=hint)

    @property
    def current_key(self) -> str:
        return self._current_key
