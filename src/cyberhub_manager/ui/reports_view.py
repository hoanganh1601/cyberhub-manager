"""NG-07 — Màn Doanh thu theo Stitch `doanh_thu_unified_app_shell` (REP-01..03).

- Header "Doanh thu" + chip cơ sở; bên phải "Cập nhật: HH:MM:SS" + Làm mới.
- Thanh lọc: Từ ngày / Đến ngày (bắt buộc cả hai, giờ Việt Nam), chip "Asia/Ho_Chi_Minh", Áp dụng, Xóa bộ lọc,
  ghi chú "Chỉ tính hóa đơn ĐÃ THANH TOÁN".
- 4 KPI: Tổng doanh thu, HĐ đã thanh toán, Doanh thu TB / HĐ, Ngày cao nhất.
- Trái: bảng "Doanh thu theo ngày" (mới nhất trước, tỷ trọng %, phân trang 10 ngày).
  Phải: "Tổng kết kỳ báo cáo" (phạm vi, chỉ số tổng hợp, nguyên tắc ghi nhận, trạng thái dữ liệu).
- Không vẽ chart (MVP). Số liệu ngày lấy nguyên từ ReportService.daily_revenue (chỉ hóa đơn PAID,
  chỉ những ngày có hóa đơn); UI chỉ cộng tổng / chia trung bình để hiển thị KPI.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import customtkinter as ctk

from ..domain.dtos import DailyRevenue
from ..domain.exceptions import ValidationError
from .app_shell import ViewContext
from .background import TaskRunner, default_runner
from .components.stitch_button import stitch_button
from .formatters import format_money
from .messages import MSG_LOADING, MSG_RETRY, get_field_errors_safe, get_user_friendly_error
from .report_filters import default_range, format_vn_date, local_today, range_caption, validate_range
from .state import ViewState
from .table_kit import Page, bind_hover, build_pager, paginate
from .theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_KPI_VALUE,
    FONT_ST_LABEL_CAPS,
    FONT_ST_MONO_11,
    FONT_ST_MONO_BODY,
    FONT_ST_MONO_SM,
    FONT_ST_MONO_XS_STRONG,
    FONT_ST_PAGE_TITLE,
    STITCH_BADGE_SUCCESS_BG,
    STITCH_BADGE_SUCCESS_BORDER,
    STITCH_BG_CHROME,
    STITCH_CARD_BG,
    STITCH_CARD_BORDER,
    STITCH_CHIP_BG,
    STITCH_CHIP_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_INPUT_BG,
    STITCH_INPUT_BORDER,
    STITCH_NAV_ACTIVE_BG,
    STITCH_NAV_ACTIVE_BORDER,
    STITCH_RADIUS,
    STITCH_RADIUS_LG,
    STITCH_SUCCESS,
    STITCH_TAB_HOVER,
    STITCH_TEXT,
    STITCH_TEXT_DIM,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
)

PAGE_SIZE = 10
ROW_HEIGHT = 34
NO_REVENUE = "Không có hóa đơn đã thanh toán trong khoảng ngày này."


# ----------------------------------------------------------------------
# Hàm thuần (test được không cần Tk)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class RevenueSummary:
    total: int
    invoice_count: int
    days_with_revenue: int
    average_per_invoice: int
    average_per_day: int
    best_day: DailyRevenue | None
    best_share: float  # % của ngày cao nhất trên tổng kỳ


def summarize_revenue(days: Iterable[DailyRevenue]) -> RevenueSummary:
    days = list(days)
    total = sum(d.revenue for d in days)
    count = sum(d.invoice_count for d in days)
    best = max(days, key=lambda d: (d.revenue, d.date)) if days else None
    return RevenueSummary(
        total=total,
        invoice_count=count,
        days_with_revenue=len(days),
        average_per_invoice=round(total / count) if count else 0,
        average_per_day=round(total / len(days)) if days else 0,
        best_day=best,
        best_share=share_percent(best.revenue, total) if best else 0.0,
    )


def share_percent(revenue: int, total: int) -> float:
    return round(revenue * 100 / total, 1) if total else 0.0


def format_percent(value: float) -> str:
    return f"{value:.1f}%"


def newest_first(days: Iterable[DailyRevenue]) -> list[DailyRevenue]:
    return sorted(days, key=lambda d: d.date, reverse=True)


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def page_caption(page: Page) -> str:
    return f"Hiển thị {page.first} - {page.last} trên {page.total} ngày"


_COLUMNS = (("NGÀY", 5, "w"), ("SỐ HĐ ĐÃ THANH TOÁN", 5, "e"), ("DOANH THU (VND)", 5, "e"), ("TỶ TRỌNG (%)", 4, "e"))


def _configure_columns(frame: Any) -> None:
    for index, (_title, weight, _anchor) in enumerate(_COLUMNS):
        frame.grid_columnconfigure(index, weight=weight, uniform="revenue")


def _card(master: Any, **kwargs: Any) -> ctk.CTkFrame:
    return ctk.CTkFrame(master, fg_color=STITCH_CARD_BG, border_width=1, border_color=STITCH_CARD_BORDER, corner_radius=STITCH_RADIUS_LG, **kwargs)


def _date_entry(master: Any) -> ctk.CTkEntry:
    return ctk.CTkEntry(
        master,
        width=110,
        height=30,
        placeholder_text="dd/mm/yyyy",
        fg_color=STITCH_INPUT_BG,
        border_color=STITCH_INPUT_BORDER,
        border_width=1,
        corner_radius=STITCH_RADIUS,
        text_color=STITCH_TEXT_STRONG,
        font=FONT_ST_MONO_BODY,
    )


class ReportsView(ctk.CTkFrame):
    def __init__(self, master: Any, context: ViewContext, *, runner: TaskRunner | None = None) -> None:
        super().__init__(master, fg_color="transparent")
        self._context = context
        self._runner = runner or default_runner()
        self._days: list[DailyRevenue] = []
        self._range: tuple[date, date] | None = None
        self._page = 1
        self._state = ViewState.LOADING
        self._closed = False
        self._request = 0
        self._synced_at = ""
        self._kpi_labels: dict[str, ctk.CTkLabel] = {}
        self._kpi_notes: dict[str, ctk.CTkLabel] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build_header()
        self._build_filter_row()
        self._build_kpis()
        self._build_body()
        self._build_footer()
        start, end = default_range(local_today(context.services))
        self._from_entry.insert(0, format_vn_date(start))
        self._to_entry.insert(0, format_vn_date(end))
        self.apply_filters()

    # ------------------------------------------------------------------
    # Thuộc tính công khai (test)
    # ------------------------------------------------------------------
    @property
    def state(self) -> ViewState:
        return self._state

    @property
    def days(self) -> list[DailyRevenue]:
        return newest_first(self._days)

    @property
    def summary(self) -> RevenueSummary:
        return summarize_revenue(self._days)

    @property
    def applied_range(self) -> tuple[date, date] | None:
        return self._range

    @property
    def current_page(self) -> Page:
        return paginate(self.days, self._page, PAGE_SIZE)

    @property
    def filter_error(self) -> str:
        return self._filter_error.cget("text")

    # ------------------------------------------------------------------
    # Dựng giao diện
    # ------------------------------------------------------------------
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(header, text="Doanh thu", font=FONT_ST_PAGE_TITLE, text_color=STITCH_TEXT_STRONG, height=26).pack(side="left")
        ctk.CTkLabel(header, text="Theo dõi doanh thu hóa đơn đã thanh toán", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED, height=26).pack(
            side="left", padx=(10, 0)
        )
        store = ctk.CTkFrame(header, fg_color=STITCH_NAV_ACTIVE_BG, border_width=1, border_color=STITCH_NAV_ACTIVE_BORDER, corner_radius=STITCH_RADIUS)
        store.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(store, text=f"Cơ sở: {self._context.session.store_name}", font=FONT_ST_MONO_11, text_color=STITCH_CYAN, height=20).pack(padx=8)
        self._refresh_button = stitch_button(header, "⟳  Làm mới", kind="secondary", command=self.reload, width=100, height=30)
        self._refresh_button.pack(side="right")
        self._synced_label = ctk.CTkLabel(header, text="", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED, height=26)
        self._synced_label.pack(side="right", padx=(0, 10))

    def _build_filter_row(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=STITCH_BG_CHROME, border_width=1, border_color=STITCH_CARD_BORDER, corner_radius=STITCH_RADIUS_LG)
        bar.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        line = ctk.CTkFrame(bar, fg_color="transparent")
        line.pack(fill="x", padx=10, pady=(8, 0))
        ctk.CTkLabel(line, text="Từ ngày:", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(side="left")
        self._from_entry = _date_entry(line)
        self._from_entry.pack(side="left", padx=(6, 12))
        ctk.CTkLabel(line, text="Đến ngày:", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(side="left")
        self._to_entry = _date_entry(line)
        self._to_entry.pack(side="left", padx=(6, 10))
        for entry in (self._from_entry, self._to_entry):
            entry.bind("<Return>", lambda _e: self.apply_filters(), add="+")
        tz = ctk.CTkFrame(line, fg_color=STITCH_CHIP_BG, border_width=1, border_color=STITCH_CHIP_BORDER, corner_radius=STITCH_RADIUS)
        tz.pack(side="left")
        ctk.CTkLabel(tz, text="Asia/Ho_Chi_Minh", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED, height=22).pack(padx=8)
        self._apply_button = stitch_button(line, "Áp dụng", kind="primary", command=self.apply_filters, width=80, height=30)
        self._apply_button.pack(side="left", padx=(10, 0))
        stitch_button(line, "Xóa bộ lọc", kind="ghost", command=self.clear_filters, width=90, height=30).pack(side="left", padx=(6, 0))
        ctk.CTkLabel(line, text="ⓘ Chỉ tính hóa đơn ĐÃ THANH TOÁN", font=FONT_ST_MONO_11, text_color=STITCH_SUCCESS).pack(side="right")
        self._filter_error = ctk.CTkLabel(bar, text="", font=FONT_ST_MONO_11, text_color=STITCH_DANGER, height=16, anchor="w")
        self._filter_error.pack(fill="x", padx=12, pady=(2, 4))

    def _build_kpis(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        specs = (
            ("total", "TỔNG DOANH THU", STITCH_CYAN),
            ("count", "HĐ ĐÃ THANH TOÁN", STITCH_TEXT_STRONG),
            ("average", "DOANH THU TB / HĐ", STITCH_TEXT_STRONG),
            ("best", "NGÀY CAO NHẤT", STITCH_TEXT_STRONG),
        )
        for index, (key, title, color) in enumerate(specs):
            row.grid_columnconfigure(index, weight=1, uniform="kpi")
            card = _card(row)
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 6, 0))
            ctk.CTkLabel(card, text=title, font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED, height=16, anchor="w").pack(
                anchor="w", padx=14, pady=(10, 0)
            )
            self._kpi_labels[key] = ctk.CTkLabel(card, text="—", font=FONT_ST_KPI_VALUE, text_color=color, height=28, anchor="w")
            self._kpi_labels[key].pack(anchor="w", padx=14)
            self._kpi_notes[key] = ctk.CTkLabel(card, text="", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_DIM, height=16, anchor="w")
            self._kpi_notes[key].pack(anchor="w", padx=14, pady=(0, 10))

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=64, uniform="split")
        body.grid_columnconfigure(1, weight=36, uniform="split")

        table = _card(body)
        table.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        title = ctk.CTkFrame(table, fg_color="transparent")
        title.pack(fill="x", padx=14, pady=(10, 6))
        ctk.CTkLabel(title, text="Doanh thu theo ngày", font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT_STRONG, height=20).pack(side="left")
        ctk.CTkLabel(title, text="  (Mới nhất trước)", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED, height=20).pack(side="left")
        period = ctk.CTkFrame(title, fg_color=STITCH_NAV_ACTIVE_BG, border_width=1, border_color=STITCH_NAV_ACTIVE_BORDER, corner_radius=STITCH_RADIUS)
        period.pack(side="right")
        self._period_label = ctk.CTkLabel(period, text="Kỳ: —", font=FONT_ST_MONO_11, text_color=STITCH_CYAN, height=20)
        self._period_label.pack(padx=8)
        head = ctk.CTkFrame(table, fg_color=STITCH_BG_CHROME, corner_radius=STITCH_RADIUS)
        head.pack(fill="x", padx=12)
        _configure_columns(head)
        for index, (text, _weight, anchor) in enumerate(_COLUMNS):
            ctk.CTkLabel(head, text=text, font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED, anchor=anchor, height=30).grid(
                row=0, column=index, sticky="ew", padx=8
            )
        self._rows_frame = ctk.CTkFrame(table, fg_color="transparent")
        self._rows_frame.pack(fill="both", expand=True, padx=12)
        self._state_frame = ctk.CTkFrame(table, fg_color="transparent")
        self._state_label = ctk.CTkLabel(self._state_frame, text="", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, wraplength=420)
        self._state_label.pack(pady=(40, 10))
        self._retry_button = stitch_button(self._state_frame, MSG_RETRY, command=self.reload, width=100)
        footer = ctk.CTkFrame(table, fg_color="transparent")
        footer.pack(fill="x", side="bottom", padx=12, pady=(0, 8))
        ctk.CTkFrame(footer, fg_color=STITCH_CARD_BORDER, height=1, corner_radius=0).pack(fill="x", pady=(0, 8))
        self._caption_label = ctk.CTkLabel(footer, text="", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED)
        self._caption_label.pack(side="left")
        self._pager = ctk.CTkFrame(footer, fg_color="transparent")
        self._pager.pack(side="right")

        self._side = _card(body)
        self._side.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        ctk.CTkLabel(
            footer,
            text=f"●  Dữ liệu báo cáo doanh thu • {self._context.session.store_name}",
            font=FONT_ST_MONO_11,
            text_color=STITCH_TEXT_MUTED,
            height=16,
        ).pack(side="left")

    # ------------------------------------------------------------------
    # Lọc + tải
    # ------------------------------------------------------------------
    def apply_filters(self) -> None:
        checked = validate_range(self._from_entry.get(), self._to_entry.get(), required=True)
        self._paint_date_errors(checked.errors)
        if not checked.ok:
            return
        assert checked.date_from is not None and checked.date_to is not None
        self._range = (checked.date_from, checked.date_to)
        self._page = 1
        self.reload()

    def clear_filters(self) -> None:
        start, end = default_range(local_today(self._context.services))
        self.set_dates(start, end)
        self.apply_filters()

    def set_dates(self, date_from: date | None, date_to: date | None) -> None:
        for entry, value in ((self._from_entry, date_from), (self._to_entry, date_to)):
            entry.delete(0, "end")
            if value:
                entry.insert(0, format_vn_date(value))

    def reload(self) -> None:
        if self._closed or self._range is None:
            return
        self._request += 1
        request = self._request
        self._show_state(ViewState.LOADING, MSG_LOADING)
        self._apply_button.set_busy(True, busy_text="…")
        self._refresh_button.set_enabled(False)
        reports, store_id = self._context.services.reports, self._context.session.store_id
        start, end = self._range
        self._runner.submit(
            self,
            lambda: reports.daily_revenue(store_id, start, end),
            lambda days: self._on_loaded(request, days),
            lambda error: self._on_failed(request, error),
        )

    def _loading_done(self) -> None:
        self._apply_button.set_busy(False)
        self._refresh_button.set_enabled(True)

    def _on_loaded(self, request: int, days: list[DailyRevenue]) -> None:
        if self._closed or request != self._request:
            return
        self._loading_done()
        self._days = list(days)
        self._synced_at = datetime.now().strftime("%H:%M:%S")  # giờ thật lúc tải xong, như dashboard
        self._synced_label.configure(text=f"Cập nhật: {self._synced_at}")
        self._state = ViewState.READY
        self._render()

    def _on_failed(self, request: int, error: Exception) -> None:
        if self._closed or request != self._request:
            return
        self._loading_done()
        if isinstance(error, ValidationError):
            self._paint_date_errors(get_field_errors_safe(error))
        self._days = []
        self._show_state(ViewState.ERROR, get_user_friendly_error(error))
        self._render_kpis()
        self._render_side()

    def _paint_date_errors(self, errors: dict[str, str]) -> None:
        for key, entry in (("date_from", self._from_entry), ("date_to", self._to_entry)):
            entry.configure(border_color=STITCH_DANGER if key in errors else STITCH_INPUT_BORDER)
        message = errors.get("date_from") or errors.get("date_to") or ""
        self._filter_error.configure(text=f"⚠ {message}" if message else "")

    def go_to_page(self, number: int) -> None:
        self._page = number
        self._render_rows()

    # ------------------------------------------------------------------
    # Vẽ
    # ------------------------------------------------------------------
    def _render(self) -> None:
        start, end = self._range or (None, None)
        self._period_label.configure(text=f"Kỳ: {range_caption(start, end)}" if start and end else "Kỳ: —")
        self._render_kpis()
        self._render_rows()
        self._render_side()

    def _render_kpis(self) -> None:
        loaded = self._state in (ViewState.READY, ViewState.EMPTY)
        summary = self.summary
        best = summary.best_day
        values = {
            "total": (format_money(summary.total), f"Từ {summary.invoice_count} HĐ thành công"),
            "count": (f"{summary.invoice_count} đơn", "Đã thu hoàn tất"),
            "average": (format_money(summary.average_per_invoice), "TB mỗi hóa đơn đã thanh toán"),
            "best": (
                format_vn_date(best.date) if best else "—",
                f"{format_money(best.revenue)} • {format_percent(summary.best_share)} tổng kỳ" if best else "Chưa có doanh thu",
            ),
        }
        for key, (value, note) in values.items():
            self._kpi_labels[key].configure(text=value if loaded else "—")
            self._kpi_notes[key].configure(
                text=note if loaded else "", text_color=STITCH_SUCCESS if key in ("count", "best") and loaded and best else STITCH_TEXT_DIM
            )

    def _render_rows(self) -> None:
        for child in self._rows_frame.winfo_children():
            child.destroy()
        if not self._days:
            self._show_state(ViewState.EMPTY, NO_REVENUE)
            return
        self._state = ViewState.READY
        self._state_frame.pack_forget()
        self._rows_frame.pack(fill="both", expand=True, padx=12)
        page = self.current_page
        self._page = page.number
        total = self.summary.total
        today = local_today(self._context.services)
        best = self.summary.best_day
        for index, day in enumerate(page.items):
            if index:
                ctk.CTkFrame(self._rows_frame, fg_color=STITCH_CARD_BORDER, height=1, corner_radius=0).pack(fill="x")
            row = ctk.CTkFrame(self._rows_frame, fg_color="transparent", height=ROW_HEIGHT, corner_radius=0)
            row.pack(fill="x")
            row.grid_propagate(False)
            row.grid_rowconfigure(0, weight=1)
            _configure_columns(row)
            date_cell = ctk.CTkFrame(row, fg_color="transparent")
            date_cell.grid(row=0, column=0, sticky="w", padx=8)
            ctk.CTkLabel(date_cell, text=format_vn_date(day.date), font=FONT_ST_MONO_BODY, text_color=STITCH_TEXT_STRONG).pack(side="left")
            if day.date == today:
                tag = ctk.CTkFrame(date_cell, fg_color=STITCH_NAV_ACTIVE_BG, border_width=1, border_color=STITCH_NAV_ACTIVE_BORDER, corner_radius=STITCH_RADIUS)
                tag.pack(side="left", padx=(8, 0))
                ctk.CTkLabel(tag, text="HÔM NAY", font=FONT_ST_MONO_XS_STRONG, text_color=STITCH_CYAN, height=16).pack(padx=6)
            ctk.CTkLabel(row, text=f"{day.invoice_count} HĐ", font=FONT_ST_MONO_BODY, text_color=STITCH_TEXT).grid(row=0, column=1, sticky="e", padx=8)
            ctk.CTkLabel(
                row,
                text=format_number(day.revenue),
                font=FONT_ST_MONO_SM,
                text_color=STITCH_SUCCESS if best is not None and day.date == best.date else STITCH_TEXT_STRONG,
            ).grid(row=0, column=2, sticky="e", padx=8)
            ctk.CTkLabel(row, text=format_percent(share_percent(day.revenue, total)), font=FONT_ST_MONO_BODY, text_color=STITCH_TEXT_MUTED).grid(
                row=0, column=3, sticky="e", padx=8
            )
            bind_hover(row, base_color="transparent", hover_color=STITCH_TAB_HOVER)
        self._caption_label.configure(text=page_caption(page))
        build_pager(self._pager, page, self.go_to_page)

    def _render_side(self) -> None:
        for child in self._side.winfo_children():
            child.destroy()
        panel = ctk.CTkFrame(self._side, fg_color="transparent")
        panel.pack(fill="both", expand=True, padx=14, pady=12)
        ctk.CTkLabel(panel, text="Tổng kết kỳ báo cáo", font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT_STRONG, anchor="w", height=20).pack(fill="x")
        loaded = self._state in (ViewState.READY, ViewState.EMPTY)
        summary = self.summary
        start, end = self._range or (None, None)

        def block(title: str, rows: list[tuple[str, str, str]]) -> None:
            box = ctk.CTkFrame(panel, fg_color=STITCH_BG_CHROME, border_width=1, border_color=STITCH_CARD_BORDER, corner_radius=STITCH_RADIUS_LG)
            box.pack(fill="x", pady=(8, 0))
            ctk.CTkLabel(box, text=title.upper(), font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED, anchor="w", height=16).pack(
                fill="x", padx=12, pady=(8, 2)
            )
            for label, value, color in rows:
                line = ctk.CTkFrame(box, fg_color="transparent")
                line.pack(fill="x", padx=12, pady=2)
                ctk.CTkLabel(line, text=label, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=18).pack(side="left")
                ctk.CTkLabel(line, text=value if loaded else "—", font=FONT_ST_MONO_SM, text_color=color, height=18).pack(side="right")
            ctk.CTkFrame(box, fg_color="transparent", height=4).pack()

        block(
            "Phạm vi báo cáo",
            [
                ("Cơ sở áp dụng:", self._context.session.store_name, STITCH_TEXT),
                ("Khoảng thời gian:", range_caption(start, end) if start and end else "—", STITCH_TEXT),
                ("Số ngày có doanh thu:", f"{summary.days_with_revenue} ngày", STITCH_TEXT),
                ("Tổng hóa đơn PAID:", f"{summary.invoice_count} hóa đơn", STITCH_TEXT),
            ],
        )
        block(
            "Chỉ số tài chính tổng hợp",
            [
                ("Tổng thu trong kỳ:", format_money(summary.total), STITCH_CYAN),
                ("Doanh thu TB / ngày:", format_money(summary.average_per_day), STITCH_TEXT),
                ("Doanh thu TB / HĐ:", format_money(summary.average_per_invoice), STITCH_TEXT),
            ],
        )
        rule = ctk.CTkFrame(panel, fg_color=STITCH_BADGE_SUCCESS_BG, border_width=1, border_color=STITCH_BADGE_SUCCESS_BORDER, corner_radius=STITCH_RADIUS_LG)
        rule.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(rule, text="🛡  Nguyên tắc ghi nhận", font=FONT_ST_BODY_STRONG, text_color=STITCH_SUCCESS, anchor="w", height=20).pack(
            fill="x", padx=12, pady=(8, 0)
        )
        ctk.CTkLabel(
            rule,
            text="Hóa đơn đã hủy không được tính vào doanh thu. Chỉ tính các hóa đơn trạng thái ĐÃ THANH TOÁN.",
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT,
            wraplength=300,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=12, pady=(2, 8))
        status = ctk.CTkFrame(panel, fg_color=STITCH_BG_CHROME, border_width=1, border_color=STITCH_CARD_BORDER, corner_radius=STITCH_RADIUS_LG)
        status.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(status, text="TRẠNG THÁI DỮ LIỆU", font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED, anchor="w", height=16).pack(
            fill="x", padx=12, pady=(8, 2)
        )
        ok = self._state != ViewState.ERROR
        line = ctk.CTkFrame(status, fg_color="transparent")
        line.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(
            line, text="● Đã đồng bộ" if ok else "● Lỗi tải dữ liệu", font=FONT_ST_MONO_11, text_color=STITCH_SUCCESS if ok else STITCH_DANGER, height=18
        ).pack(side="left")
        ctk.CTkLabel(line, text=f"Lần cuối: {self._synced_at or '—'}", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_DIM, height=18).pack(side="right")

    def _show_state(self, state: ViewState, message: str) -> None:
        self._state = state
        self._rows_frame.pack_forget()
        for child in self._rows_frame.winfo_children():
            child.destroy()
        self._state_label.configure(text=message, text_color=STITCH_DANGER if state == ViewState.ERROR else STITCH_TEXT_MUTED)
        if state == ViewState.ERROR:
            self._retry_button.pack()
        else:
            self._retry_button.pack_forget()
        self._state_frame.pack(fill="both", expand=True)
        self._caption_label.configure(text="")
        for child in self._pager.winfo_children():
            child.destroy()

    def shutdown(self) -> None:
        self._closed = True


reports_view_factory = ReportsView
