"""KpiCard component cho CyberHub Manager theo phong cách Stitch.

Hiển thị chỉ số KPI đo lường dạng card ngang có biểu tượng, tiêu đề và số liệu to.
Tái sử dụng cho Dashboard, Quản lý máy và Doanh thu.
"""

from __future__ import annotations

from typing import Any, Literal

import customtkinter as ctk

from ..icons import get_icon
from ..theme import (
    FONT_ST_BODY_STRONG,
    FONT_ST_METRIC_XL,
    FONT_ST_MONO_SM,
    FONT_ST_MONO_XS_STRONG,
    STITCH_CARD_BG,
    STITCH_CARD_BORDER,
    STITCH_CHIP_BG,
    STITCH_CHIP_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_RADIUS_LG,
    STITCH_SUCCESS,
    STITCH_TEXT,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
    STITCH_WARNING,
)

KpiTone = Literal["default", "emerald", "rose", "amber", "cyan"]

_TONE_CONFIGS: dict[KpiTone, dict[str, str]] = {
    "default": {
        "border": STITCH_CARD_BORDER,
        "title": STITCH_TEXT_MUTED,
        "value": STITCH_TEXT_STRONG,
        "icon": STITCH_TEXT,
        "icon_bg": STITCH_CHIP_BG,
        "icon_border": STITCH_CHIP_BORDER,
    },
    "emerald": {
        "border": "#134E35",
        "title": STITCH_SUCCESS,
        "value": STITCH_SUCCESS,
        "icon": STITCH_SUCCESS,
        "icon_bg": "#0D3322",
        "icon_border": "#1B6644",
    },
    "rose": {
        "border": STITCH_CARD_BORDER,
        "title": STITCH_DANGER,
        "value": STITCH_DANGER,
        "icon": STITCH_DANGER,
        "icon_bg": "#38151D",
        "icon_border": "#61212E",
    },
    "amber": {
        "border": STITCH_CARD_BORDER,
        "title": STITCH_WARNING,
        "value": STITCH_WARNING,
        "icon": STITCH_WARNING,
        "icon_bg": "#36240C",
        "icon_border": "#5E3D12",
    },
    "cyan": {
        "border": STITCH_CARD_BORDER,
        "title": STITCH_CYAN,
        "value": STITCH_CYAN,
        "icon": STITCH_CYAN,
        "icon_bg": "#0C2E40",
        "icon_border": "#085B78",
    },
}


class KpiCard(ctk.CTkFrame):
    """Card hiển thị một chỉ số vận hành (KPI telemetry metric)."""

    def __init__(
        self,
        master: Any,
        title: str,
        value: int | str = 0,
        *,
        icon: str | ctk.CTkImage = "▦",
        icon_name: str | None = None,
        tone: KpiTone = "default",
        subtext: str | None = None,
        height: int = 68,
        **kwargs: Any,
    ) -> None:
        cfg = _TONE_CONFIGS.get(tone, _TONE_CONFIGS["default"])
        super().__init__(
            master=master,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=cfg["border"],
            corner_radius=STITCH_RADIUS_LG,
            height=height,
            **kwargs,
        )
        self.pack_propagate(False)
        self._tone = tone
        self._cfg = cfg

        # Layout trong: Bên trái là text, bên phải là icon box
        self._inner = ctk.CTkFrame(self, fg_color="transparent")
        self._inner.pack(fill="both", expand=True, padx=12, pady=8)

        # Cột trái (Text)
        self._text_col = ctk.CTkFrame(self._inner, fg_color="transparent")
        self._text_col.pack(side="left", fill="both", expand=True)

        self._title_label = ctk.CTkLabel(
            self._text_col,
            text=title,
            font=FONT_ST_MONO_XS_STRONG,
            text_color=cfg["title"],
            anchor="w",
            height=14,
        )
        self._title_label.pack(fill="x", anchor="w")

        self._value_label = ctk.CTkLabel(
            self._text_col,
            text=str(value),
            font=FONT_ST_METRIC_XL,
            text_color=cfg["value"],
            anchor="w",
            height=26,
        )
        self._value_label.pack(fill="x", anchor="w", pady=(1, 0))

        self._subtext_label: ctk.CTkLabel | None = None
        if subtext:
            self._subtext_label = ctk.CTkLabel(
                self._text_col,
                text=subtext,
                font=FONT_ST_MONO_SM,
                text_color=STITCH_TEXT_MUTED,
                anchor="w",
                height=14,
            )
            self._subtext_label.pack(fill="x", anchor="w")

        # Cột phải (Icon box hình vuông bo tròn)
        self._icon_box = ctk.CTkFrame(
            self._inner,
            width=32,
            height=32,
            fg_color=cfg["icon_bg"],
            border_width=1,
            border_color=cfg["icon_border"],
            corner_radius=STITCH_RADIUS_LG,
        )
        self._icon_box.pack(side="right", padx=(6, 0))
        self._icon_box.pack_propagate(False)

        if icon_name is not None:
            icon_img = get_icon(icon_name, cfg["icon"], (16, 16))
            self._icon_label = ctk.CTkLabel(
                self._icon_box,
                text="",
                image=icon_img,
            )
        elif isinstance(icon, ctk.CTkImage):
            self._icon_label = ctk.CTkLabel(
                self._icon_box,
                text="",
                image=icon,
            )
        else:
            self._icon_label = ctk.CTkLabel(
                self._icon_box,
                text=icon,
                font=FONT_ST_BODY_STRONG,
                text_color=cfg["icon"],
            )
        self._icon_label.place(relx=0.5, rely=0.5, anchor="center")

    def set_value(self, value: int | str, subtext: str | None = None) -> None:
        """Cập nhật giá trị hiển thị."""
        self._value_label.configure(text=str(value))
        if subtext is not None and self._subtext_label is not None:
            self._subtext_label.configure(text=subtext)

    def set_title(self, title: str) -> None:
        """Cập nhật tiêu đề."""
        self._title_label.configure(text=title)

