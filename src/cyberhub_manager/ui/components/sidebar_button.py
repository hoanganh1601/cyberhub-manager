"""Navigation row with a fixed icon column and a stable label baseline."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from .. import theme as t
from ..sidebar_icons import sidebar_icon


class SidebarButton(ctk.CTkButton):
    # CTkButton uses this spacing to separate image and label without text padding.
    _image_label_spacing = 12

    def __init__(self, master: Any, icon: str, command: Callable[[], Any]) -> None:
        self._idle_icon = sidebar_icon(icon, t.STITCH_NAV_TEXT)
        self._active_icon = sidebar_icon(icon, t.STITCH_CYAN)
        self._active = False
        super().__init__(master, text="", image=self._idle_icon, compound="left", anchor="w",
                         height=t.STITCH_NAV_ITEM_HEIGHT, border_spacing=10, corner_radius=8,
                         border_width=1, fg_color=t.STITCH_BG_CHROME,
                         border_color=t.STITCH_BG_CHROME, hover_color=t.STITCH_NAV_HOVER,
                         font=t.FONT_ST_NAV, text_color=t.STITCH_NAV_TEXT, command=command)
        self._marker = ctk.CTkFrame(self, width=3, height=20, corner_radius=1,
                                    fg_color=t.STITCH_CYAN, bg_color=t.STITCH_NAV_ACTIVE_BG)
        self._marker.bind("<Button-1>", lambda _e: self.invoke())
        self._canvas.configure(takefocus=1)
        self._canvas.bind("<Return>", lambda _e: self.invoke())
        self._canvas.bind("<space>", lambda _e: self.invoke())
        self._canvas.bind("<FocusIn>", lambda _e: self.configure(border_color=t.STITCH_CYAN))
        self._canvas.bind("<FocusOut>", lambda _e: self.set_active(self._active))

    def _create_grid(self) -> None:
        super()._create_grid()
        # Horizontal inset must not enlarge the vertical padding and row height.
        padding = self._apply_widget_scaling(16)
        self.grid_columnconfigure(0, minsize=padding)
        self.grid_columnconfigure(4, minsize=padding)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.configure(fg_color=t.STITCH_NAV_ACTIVE_BG if active else t.STITCH_BG_CHROME,
                       hover_color=t.STITCH_NAV_ACTIVE_BG if active else t.STITCH_NAV_HOVER,
                       border_color=t.STITCH_NAV_ACTIVE_BORDER if active else t.STITCH_BG_CHROME,
                       text_color=t.STITCH_CYAN if active else t.STITCH_NAV_TEXT,
                       font=t.FONT_ST_NAV_ACTIVE if active else t.FONT_ST_NAV,
                       image=self._active_icon if active else self._idle_icon)
        if active:
            self._marker.place(x=5, rely=.5, anchor="w")
            self._marker.lift()
        else:
            self._marker.place_forget()
