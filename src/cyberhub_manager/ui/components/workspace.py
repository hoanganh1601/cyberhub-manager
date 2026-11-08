"""Shared desktop page headers, metric cards and action affordances."""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

from .. import theme as t
from ..sidebar_icons import sidebar_icon
from .stitch_button import stitch_button


def surface(master: Any, **kwargs: Any) -> ctk.CTkFrame:
    return ctk.CTkFrame(master, fg_color=t.STITCH_CARD_BG, border_color=t.STITCH_CARD_BORDER,
                         border_width=1, corner_radius=t.WORKSPACE_RADIUS, **kwargs)


class PageHeader(ctk.CTkFrame):
    def __init__(self, master: Any, title: str, subtitle: str, *, eyebrow: str) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        copy = ctk.CTkFrame(self, fg_color="transparent")
        copy.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(copy, text=eyebrow, height=14, font=t.FONT_ST_LABEL_CAPS,
                     text_color=t.STITCH_TEXT_DIM).pack(anchor="w")
        ctk.CTkLabel(copy, text=title, height=30, font=t.FONT_WORKSPACE_TITLE,
                     text_color=t.STITCH_TEXT_STRONG).pack(anchor="w", pady=(2, 0))
        subtitle_label = ctk.CTkLabel(copy, text=subtitle, height=18, font=t.FONT_ST_BODY,
                                     text_color=t.STITCH_TEXT_MUTED, wraplength=600, justify="left", anchor="w")
        subtitle_label.pack(fill="x", pady=(2, 0))
        self.actions = ctk.CTkFrame(self, fg_color="transparent")
        self.actions.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.bind("<Configure>", lambda event: subtitle_label.configure(
            wraplength=max(220, (event.width - self.actions.winfo_reqwidth()) / self._get_widget_scaling() - 24)), add="+")


class MetricTile(ctk.CTkFrame):
    def __init__(self, master: Any, title: str, *, icon: str, color: str,
                 note: str = "", accent: bool = False) -> None:
        super().__init__(master, fg_color=t.STITCH_KPI_SUCCESS_CARD_BG if accent else t.STITCH_CARD_BG,
                         border_width=1, border_color=t.STITCH_NAV_ACTIVE_BORDER if accent else t.STITCH_CARD_BORDER,
                         corner_radius=t.WORKSPACE_RADIUS)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=title, font=t.FONT_ST_LABEL_CAPS, text_color=t.STITCH_TEXT_MUTED,
                     height=16, anchor="w").grid(row=0, column=0, sticky="ew", padx=(16, 0), pady=(12, 2))
        ctk.CTkLabel(self, text="", image=sidebar_icon(icon, color, 22), width=28,
                     height=22).grid(row=0, column=1, padx=(8, 16), pady=(12, 0), sticky="ne")
        self.value = ctk.CTkLabel(self, text="—", font=t.FONT_WORKSPACE_METRIC, text_color=color,
                                  height=32, anchor="w")
        self.value.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16)
        self.note = ctk.CTkLabel(self, text=note, font=t.FONT_ST_MONO_11,
                                 text_color=t.STITCH_TEXT_DIM, height=16, anchor="w")
        self.note.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(2, 12))


class Tooltip:
    def __init__(self, widget: Any, text: str) -> None:
        self.widget, self.text = widget, text
        self._after: str | None = None
        self._window: ctk.CTkToplevel | None = None
        widget.bind("<Enter>", self._queue, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Button-1>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def _queue(self, _event: Any = None) -> None:
        self._hide()
        self._after = self.widget.after(400, self._show)

    def _show(self) -> None:
        self._after = None
        if not self.widget.winfo_exists():
            return
        self._window = ctk.CTkToplevel(self.widget)
        self._window.overrideredirect(True)
        self._window.attributes("-topmost", True)
        x = max(0, min(self.widget.winfo_rootx(), self.widget.winfo_screenwidth() - 340))
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        if y + 80 > self.widget.winfo_screenheight():
            y = max(0, self.widget.winfo_rooty() - 80)
        self._window.geometry(f"+{x}+{y}")
        ctk.CTkLabel(self._window, text=self.text, fg_color=t.STITCH_CHIP_BG,
                     text_color=t.STITCH_TEXT, font=t.FONT_ST_BODY, padx=10, pady=6,
                     wraplength=260, justify="left").pack()

    def _hide(self, _event: Any = None) -> None:
        if self._after:
            self.widget.after_cancel(self._after)
            self._after = None
        if self._window is not None:
            self._window.destroy()
            self._window = None


def icon_action(master: Any, text: str, icon: str, *, command: Any,
                kind: str = "secondary", width: int = 104, height: int = 34) -> Any:
    button = stitch_button(master, text, kind=kind, command=command, width=width, height=height)
    color = t.STITCH_TEXT_ON_CYAN if kind == "primary" else t.STITCH_DANGER if kind == "danger" else t.STITCH_TEXT
    button.configure(image=sidebar_icon(icon, color, 16), compound="left", corner_radius=7)
    return button


def row_action(master: Any, icon: str, text: str, *, command: Any, danger: bool = False) -> Any:
    button = icon_action(master, "", icon, command=command, kind="danger" if danger else "secondary", width=30, height=30)
    button.tooltip_text = text
    button.tooltip = Tooltip(button, text)
    return button
