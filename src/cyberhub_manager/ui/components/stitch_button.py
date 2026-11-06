"""Nút theo Stitch, dựa trên ActionButton (NG-01) để giữ set_busy/set_enabled chống double click."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..theme import (
    FONT_ST_BODY_STRONG,
    STITCH_CHIP_BG,
    STITCH_CHIP_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_DANGER_SOFT_BG,
    STITCH_NAV_ACTIVE_BORDER,
    STITCH_RADIUS,
    STITCH_ROSE,
    STITCH_TAB_HOVER,
    STITCH_TEXT,
    STITCH_TEXT_ON_CYAN,
)
from .action_button import ActionButton

# kind -> (nền, hover, chữ, viền)
_STYLES: dict[str, tuple[str, str, str, str]] = {
    "primary": (STITCH_CYAN, "#33D1FF", STITCH_TEXT_ON_CYAN, STITCH_CYAN),
    "secondary": (STITCH_CHIP_BG, STITCH_TAB_HOVER, STITCH_TEXT, STITCH_CHIP_BORDER),
    "danger": (STITCH_DANGER_SOFT_BG, "#3A1D2C", STITCH_DANGER, STITCH_ROSE),
    "ghost": ("transparent", STITCH_TAB_HOVER, STITCH_TEXT, STITCH_NAV_ACTIVE_BORDER),
}


def stitch_button(
    master: Any,
    text: str,
    *,
    kind: str = "secondary",
    command: Callable[[], None] | None = None,
    width: int = 110,
    height: int = 30,
) -> ActionButton:
    fg, hover, text_color, border = _STYLES[kind]
    button = ActionButton(master, text=text, command=command, width=width, height=height)
    button.configure(
        fg_color=fg,
        hover_color=hover,
        text_color=text_color,
        border_width=1,
        border_color=border,
        corner_radius=STITCH_RADIUS,
        font=FONT_ST_BODY_STRONG,
    )
    return button
