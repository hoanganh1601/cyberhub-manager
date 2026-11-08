"""Interactive native Tk charts: zero-filled axes, hover details and click drill-down."""

from __future__ import annotations

from collections.abc import Callable
from math import ceil, floor, log10
import tkinter as tk
from typing import Any

import customtkinter as ctk

from .. import theme as t
from ..formatters import format_money
from ..i18n import UIStrings
from ..revenue_analysis import RevenueBucket


def compact_number(value: float, language: str = "vi") -> str:
    if abs(value) >= 1_000_000_000:
        return UIStrings(language)("{v0} tỷ", v0=f"{value / 1_000_000_000:g}")
    if abs(value) >= 1_000_000:
        return UIStrings(language)("{v0} tr", v0=f"{value / 1_000_000:g}")
    if abs(value) >= 1_000:
        return f"{value / 1_000:g}k"
    return f"{value:g}"


def axis_ceiling(value: int) -> int:
    if value <= 1:
        return 1
    unit = 10 ** floor(log10(value))
    return int(next(step for step in (1, 2, 2.5, 5, 10) if step * unit >= value) * unit)


class RevenueChart(ctk.CTkFrame):
    def __init__(self, master: Any, title: str, *, metric: str = "revenue",
                 on_select: Callable[[RevenueBucket], None] | None = None, language: str = "vi") -> None:
        super().__init__(master, fg_color=t.STITCH_CARD_BG, border_width=1,
                         border_color=t.STITCH_CARD_BORDER, corner_radius=t.WORKSPACE_RADIUS)
        self.metric = metric
        self._t = UIStrings(language)
        self.mode = "line" if metric == "revenue" else "bar"
        self._data: list[RevenueBucket] = []
        self._hover: int | None = None
        self._selected: RevenueBucket | None = None
        self._on_select = on_select
        self._message = "Loading data…"
        self._draw_id: str | None = None
        self._plot: tuple[float, float, float, float] = (0, 0, 1, 1)
        self.color = t.STITCH_CYAN if metric == "revenue" else t.WORKSPACE_VIOLET
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 0))
        ctk.CTkLabel(head, text=title, text_color=t.STITCH_TEXT_STRONG,
                     font=t.FONT_WORKSPACE_SECTION, height=22).pack(side="left")
        ctk.CTkLabel(head, text="● VND" if metric == "revenue" else self._t('● Hóa đơn'),
                     text_color=self.color, font=t.FONT_ST_MONO_11, height=22).pack(side="right")
        self.canvas = tk.Canvas(self, height=200, bg=t.STITCH_CARD_BG, highlightthickness=0,
                                 cursor="crosshair", takefocus=True)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=(2, 0))
        self.detail = ctk.CTkLabel(self, text=self._t('Di chuột để xem chi tiết · nhấn để lọc bảng'),
                                   text_color=t.STITCH_TEXT_MUTED, font=t.FONT_ST_MONO_11,
                                   height=28, anchor="w")
        self.detail.pack(fill="x", padx=16, pady=(0, 8))
        self.detail.bind("<Configure>", lambda event: self.detail.configure(
            wraplength=max(140, event.width / self._get_widget_scaling())), add="+")
        self.canvas.bind("<Configure>", self._queue_draw)
        self.canvas.bind("<Motion>", self._motion)
        self.canvas.bind("<Leave>", self._leave)
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<Left>", lambda _e: self._move(-1))
        self.canvas.bind("<Right>", lambda _e: self._move(1))
        self.canvas.bind("<Return>", self._click)

    @property
    def buckets(self) -> list[RevenueBucket]:
        return list(self._data)

    def set_data(self, buckets: list[RevenueBucket], *, mode: str | None = None) -> None:
        self._data = list(buckets)
        if mode:
            self.mode = mode
        self._hover = None
        self._selected = None
        self._message = self._t('Không có dữ liệu trong kỳ này') if not any(b.invoice_count or b.revenue for b in buckets) else ""
        self._update_detail()
        if self._message:
            self.detail.configure(text=self._t('Thử chọn khoảng thời gian khác'))
        self._draw_chart()

    def set_message(self, message: str) -> None:
        self._data = []
        self._hover = None
        self._selected = None
        self._message = message
        self.detail.configure(text="")
        self._draw_chart()

    def select(self, bucket: RevenueBucket | None) -> None:
        self._selected = bucket
        self._update_detail()
        self._draw_chart()

    def _queue_draw(self, _event: Any = None) -> None:
        if self._draw_id:
            self.after_cancel(self._draw_id)
        self._draw_id = self.after(25, self._draw_chart)

    def _draw_chart(self) -> None:
        if self._draw_id:
            self.after_cancel(self._draw_id)
            self._draw_id = None
        cv = self.canvas
        cv.delete("all")
        width, height = cv.winfo_width(), cv.winfo_height()
        scale = self._get_widget_scaling()
        font = (t.STITCH_FONT, -max(9, round(10 * scale)))
        if self._message or not self._data:
            cv.create_text(width / 2, height / 2, text=self._message or self._t('Chưa có dữ liệu'),
                            fill=t.STITCH_TEXT_MUTED, font=font, width=max(100, width - 40))
            return
        left, top, right, bottom = 52 * scale, 20 * scale, width - 16 * scale, height - 30 * scale
        if right <= left or bottom <= top:
            return
        self._plot = left, top, right, bottom
        values = [getattr(bucket, self.metric) for bucket in self._data]
        ceiling = axis_ceiling(max(values, default=0))
        if self.metric == "invoice_count":
            tick_step = max(1, ceil(ceiling / 4))
            ticks = ceil(ceiling / tick_step)
            ceiling = ticks * tick_step
        else:
            ticks = 4
        for index in range(ticks + 1):
            value = ceiling * index / ticks
            y = bottom - (bottom - top) * index / ticks
            cv.create_line(left, y, right, y, fill=t.WORKSPACE_GRID, dash=(2, 5))
            cv.create_text(left - 8 * scale, y, text=compact_number(value, language=self._t.language), fill=t.STITCH_TEXT_DIM,
                            font=font, anchor="e")
        count = len(values)
        step = (right - left) / max(count, 1)
        points = [(left + (index + .5) * step,
                   bottom - value / ceiling * (bottom - top)) for index, value in enumerate(values)]
        if self.mode == "line":
            if count > 1:
                cv.create_polygon(points[0][0], bottom, *[v for point in points for v in point],
                                   points[-1][0], bottom, fill=t.WORKSPACE_CHART_FILL, outline="")
                cv.create_line(*[v for point in points for v in point], fill=self.color, width=2 * scale)
            for index, (x, y) in enumerate(points):
                if values[index] or count == 1:
                    radius = 2.5 * scale
                    cv.create_oval(x - radius, y - radius, x + radius, y + radius,
                                   fill=t.STITCH_CARD_BG, outline=self.color, width=1.5 * scale)
        else:
            half = min(18 * scale, step * .28)
            for index, (x, y) in enumerate(points):
                active = self._selected == self._data[index] or self._hover == index
                cv.create_rectangle(x - half, y, x + half, bottom,
                                     fill=self.color if active or values[index] else t.WORKSPACE_GRID, outline="")
        label_step = max(1, ceil(count / max(2, int((right - left) / (90 * scale)))))
        date_format = "%m/%y" if self._data[0].start.year != self._data[-1].end.year else "%d/%m"
        for index, (x, _y) in enumerate(points):
            if index % label_step == 0 or index == count - 1 and count > 1 and (count - 1) % label_step > label_step / 2:
                cv.create_text(x, bottom + 16 * scale, text=self._data[index].start.strftime(date_format),
                                fill=t.STITCH_TEXT_DIM, font=font)
        active_index = self._hover
        if active_index is None and self._selected in self._data:
            active_index = self._data.index(self._selected)
        if active_index is not None and active_index < count:
            x, y = points[active_index]
            cv.create_line(x, top, x, bottom, fill=self.color, dash=(3, 3))
            radius = 4 * scale
            cv.create_oval(x - radius, y - radius, x + radius, y + radius,
                           fill=self.color, outline=t.STITCH_CARD_BG, width=2 * scale)

    def _update_detail(self) -> None:
        bucket = self._data[self._hover] if self._hover is not None and self._hover < len(self._data) else self._selected
        text = self._t('{v0} · {v1} · {v2} hóa đơn', v0=f'{bucket.label}', v1=f'{format_money(bucket.revenue, language=self._t.language)}', v2=f'{bucket.invoice_count}') if bucket else self._t('Di chuột để xem chi tiết · nhấn để lọc bảng')
        self.detail.configure(text=text, text_color=self.color if bucket else t.STITCH_TEXT_MUTED)

    def _motion(self, event: Any) -> None:
        if not self._data or self._message:
            return
        left, top, right, bottom = self._plot
        index = max(0, min(len(self._data) - 1, int((event.x - left) / max(1, right - left) * len(self._data))))
        if left <= event.x <= right and top <= event.y <= bottom and index != self._hover:
            self._hover = index
            self._update_detail()
            self._draw_chart()

    def _leave(self, _event: Any = None) -> None:
        self._hover = None
        self._update_detail()
        self._draw_chart()

    def _move(self, direction: int) -> str:
        if self._data and not self._message:
            self._hover = max(0, min(len(self._data) - 1, (self._hover if self._hover is not None else 0) + direction))
            self._update_detail()
            self._draw_chart()
        return "break"

    def _click(self, _event: Any = None) -> str:
        if _event is not None and hasattr(_event, "x"):
            self._motion(_event)
        if self._hover is not None and self._on_select and not self._message:
            self._on_select(self._data[self._hover])
        self.canvas.focus_set()
        return "break"

    def destroy(self) -> None:
        if self._draw_id:
            self.after_cancel(self._draw_id)
        super().destroy()
