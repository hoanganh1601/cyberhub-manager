"""Phần dùng chung cho các bảng theo Stitch (Quản lý máy NG-03, Khách hàng NG-04).

- paginate()/Page: cắt trang thuần, test được không cần Tk.
- build_pager(): hàng nút ‹ 1 2 3 › ở chân bảng.
- bind_hover(): tô nền dòng khi rê chuột, không tắt khi chuột đi vào ô con.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import customtkinter as ctk

from .theme import (
    FONT_ST_MONO_11,
    STITCH_CHIP_BG,
    STITCH_CYAN,
    STITCH_NAV_HOVER,
    STITCH_RADIUS,
    STITCH_TAB_HOVER,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_ON_CYAN,
)


@dataclass(frozen=True)
class Page:
    """Một trang của bảng: items + thông tin cho chân bảng."""

    items: list[Any]
    number: int  # trang hiện tại, bắt đầu từ 1
    total_pages: int
    first: int  # số thứ tự dòng đầu (1-based); 0 khi rỗng
    last: int
    total: int


def paginate(items: Iterable[Any], page: int, page_size: int) -> Page:
    """Cắt trang; page ngoài khoảng được kéo về trang hợp lệ gần nhất."""
    items = list(items)
    total = len(items)
    total_pages = max(1, math.ceil(total / page_size))
    number = min(max(page, 1), total_pages)
    start = (number - 1) * page_size
    chunk = items[start : start + page_size]
    return Page(chunk, number, total_pages, start + 1 if chunk else 0, start + len(chunk), total)


def build_pager(frame: Any, page: Page, go_to: Callable[[int], None]) -> None:
    """Vẽ lại hàng nút trang trong `frame`: ‹, tối đa 5 số quanh trang hiện tại, ›."""
    for child in frame.winfo_children():
        child.destroy()

    def button(text: str, target: int, *, active: bool = False, enabled: bool = True) -> None:
        ctk.CTkButton(
            frame,
            text=text,
            width=26,
            height=24,
            corner_radius=STITCH_RADIUS,
            font=FONT_ST_MONO_11,
            fg_color=STITCH_CYAN if active else STITCH_CHIP_BG,
            hover_color=STITCH_CYAN if active else STITCH_TAB_HOVER,
            text_color=STITCH_TEXT_ON_CYAN if active else STITCH_TEXT_MUTED,
            state="normal" if enabled else "disabled",
            command=lambda: go_to(target),
        ).pack(side="left", padx=(4, 0))

    button("‹", page.number - 1, enabled=page.number > 1)
    start = max(1, min(page.number - 2, page.total_pages - 4))
    for number in range(start, min(page.total_pages, start + 4) + 1):
        button(str(number), number, active=number == page.number)
    button("›", page.number + 1, enabled=page.number < page.total_pages)


def bind_hover(row: Any, *, base_color: str = "transparent", hover_color: str = STITCH_NAV_HOVER) -> None:
    """Tô nền dòng khi rê chuột (Stitch: hover:bg-[#161d2d]); chuột đi vào ô con không làm tắt."""

    def inside() -> bool:
        widget = row.winfo_containing(row.winfo_pointerx(), row.winfo_pointery())
        while widget is not None:
            if widget is row:
                return True
            widget = widget.master
        return False

    def enter(_event: Any = None) -> None:
        row.configure(fg_color=hover_color)

    def leave(_event: Any = None) -> None:
        if row.winfo_exists() and not inside():
            row.configure(fg_color=base_color)

    def bind_all(widget: Any) -> None:
        widget.bind("<Enter>", enter, add="+")
        widget.bind("<Leave>", leave, add="+")
        for child in widget.winfo_children():
            bind_all(child)

    bind_all(row)
