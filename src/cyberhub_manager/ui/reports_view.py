"""NG-07 — Màn Doanh thu theo Stitch `doanh_thu_unified_app_shell` (REP-01..03).

- Header "Doanh thu" + chip cơ sở; bên phải "Cập nhật: HH:MM:SS" + Làm mới.
- Thanh lọc: Từ ngày / Đến ngày (bắt buộc cả hai, giờ Việt Nam), chip "Asia/Ho_Chi_Minh", Áp dụng, Xóa bộ lọc,
  ghi chú "Chỉ tính hóa đơn ĐÃ THANH TOÁN".
- 4 KPI: Tổng doanh thu, HĐ đã thanh toán, Doanh thu TB / HĐ, Ngày cao nhất.
- Trái: bảng "Doanh thu theo ngày" (mới nhất trước, tỷ trọng %, phân trang 10 ngày).
  Phải: "Tổng kết kỳ báo cáo" (phạm vi, chỉ số tổng hợp, nguyên tắc ghi nhận, trạng thái dữ liệu).
- Biểu đồ tương tác doanh thu / số hóa đơn, tổng hợp ngày-tuần-tháng và lọc chi tiết.
- Số liệu từ ReportService.daily_revenue; ngày không phát sinh được điền 0 trên biểu đồ.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import customtkinter as ctk

from ..domain.dtos import DailyRevenue
from ..domain.exceptions import ValidationError
from .app_shell import ViewContext
from .i18n import UIStrings
from .background import TaskRunner, default_runner
from .components.stitch_button import stitch_button
from .components.workspace import PageHeader, MetricTile, icon_action, surface
from .components.revenue_chart import RevenueChart
from .revenue_analysis import RevenueBucket, revenue_buckets, calendar_average
from . import theme as workspace_theme
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


def format_number(value: int, language: str = "vi") -> str:
    return f"{value:,}" if language == "en" else f"{value:,}".replace(",", ".")


def page_caption(page: Page, language: str = "vi") -> str:
    return UIStrings(language)("Hiển thị {v0} - {v1} trên {v2} ngày", v0=page.first, v1=page.last, v2=page.total)


_COLUMNS = (("NGÀY", 5, "w"), ("SỐ HĐ ĐÃ THANH TOÁN", 5, "e"), ("DOANH THU (VND)", 5, "e"), ("TỶ TRỌNG TOÀN KỲ", 4, "e"))


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
        self._t = UIStrings(context.language)
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
        self._grain = "day"
        self._chart_mode = "line"
        self._selected_bucket: RevenueBucket | None = None
        self._scroll_id: str | None = None

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
        days = self.days
        if self._selected_bucket:
            days = [d for d in days if self._selected_bucket.start <= d.date <= self._selected_bucket.end]
        return paginate(days, self._page, PAGE_SIZE)

    @property
    def filter_error(self) -> str:
        return self._filter_error.cget("text")

    # ------------------------------------------------------------------
    # Dựng giao diện
    # ------------------------------------------------------------------
    def _build_header(self) -> None:
        header = PageHeader(self, self._t('Doanh thu & phân tích'), self._t('Hiểu xu hướng kinh doanh từ các hóa đơn đã thanh toán.'),
                            eyebrow=self._t('PHÂN TÍCH KINH DOANH'))
        header.grid(row=0, column=0, sticky="ew")
        self._refresh_button = icon_action(header.actions, self._t('Làm mới'), "refresh", command=self.reload)
        self._refresh_button.pack(side="right")
        self._synced_label = ctk.CTkLabel(header.actions, text="", font=FONT_ST_MONO_11,
                                         text_color=STITCH_TEXT_DIM)
        self._synced_label.pack(side="right", padx=(0, 12))

    def _build_filter_row(self) -> None:
        bar = surface(self)
        bar.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        line = ctk.CTkFrame(bar, fg_color="transparent")
        line.pack(fill="x", padx=14, pady=(10, 0))
        for label, attr in ((self._t('Từ ngày'), "_from_entry"), (self._t('Đến ngày'), "_to_entry")):
            ctk.CTkLabel(line, text=label, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(side="left", padx=(0, 8))
            entry = _date_entry(line)
            entry.configure(height=34, corner_radius=6)
            entry.pack(side="left", padx=(0, 16))
            entry.bind("<Return>", lambda _e: self.apply_filters(), add="+")
            setattr(self, attr, entry)
        self._apply_button = icon_action(line, self._t('Áp dụng'), "check", kind="primary", command=self.apply_filters, width=96)
        self._apply_button.pack(side="left")
        icon_action(line, self._t('Đặt lại'), "restore", command=self.clear_filters, width=88).pack(side="left", padx=(8, 0))
        second = ctk.CTkFrame(bar, fg_color="transparent")
        second.pack(fill="x", padx=14, pady=(8, 10))
        ctk.CTkLabel(second, text=self._t('Giờ Việt Nam · Chỉ tính hóa đơn đã thanh toán'), font=FONT_ST_MONO_11,
                     text_color=STITCH_TEXT_DIM).pack(side="left")
        for label, period in ((self._t('Tháng này'), "month"), (self._t('30 ngày'), 30), (self._t('7 ngày'), 7)):
            stitch_button(second, label, kind="ghost", width=76, height=26,
                          command=lambda p=period: self.preset_range(p)).pack(side="right", padx=(6, 0))
        self._filter_error = ctk.CTkLabel(bar, text="", font=FONT_ST_MONO_11, text_color=STITCH_DANGER, anchor="w", height=18)

    def preset_range(self, period: int | str) -> None:
        today = local_today(self._context.services)
        start = today.replace(day=1) if period == "month" else today - timedelta(days=int(period) - 1)
        self.set_dates(start, today)
        self.apply_filters()

    def _build_kpis(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        specs = (("total", self._t('DOANH THU TRONG KỲ'), "money", STITCH_CYAN),
                 ("count", self._t('HÓA ĐƠN ĐÃ THU'), "invoices", STITCH_TEXT_STRONG),
                 ("average", self._t('GIÁ TRỊ TB / HĐ'), "reports", STITCH_TEXT_STRONG),
                 ("best", self._t('NGÀY CAO NHẤT'), "calendar", STITCH_SUCCESS))
        for index, (key, title, icon, color) in enumerate(specs):
            row.grid_columnconfigure(index, weight=1, uniform="kpi")
            tile = MetricTile(row, title, icon=icon, color=color, accent=key == "total")
            tile.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 10, 0))
            self._kpi_labels[key], self._kpi_notes[key] = tile.value, tile.note

    def _build_body(self) -> None:
        body = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0,
                                     scrollbar_button_color=STITCH_CHIP_BORDER,
                                     scrollbar_button_hover_color=STITCH_TEXT_DIM)
        self._body_scroll = body
        body.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        body.grid_columnconfigure(0, weight=1)
        charts = ctk.CTkFrame(body, fg_color="transparent")
        charts.grid(row=0, column=0, sticky="ew")
        charts.grid_columnconfigure(0, weight=2, uniform="charts")
        charts.grid_columnconfigure(1, weight=1, uniform="charts")
        controls = ctk.CTkFrame(charts, fg_color="transparent")
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self._grain_control = ctk.CTkSegmentedButton(
            controls, values=[self._t('Ngày'), self._t('Tuần'), self._t('Tháng')], height=28, font=FONT_ST_BODY,
            selected_color=STITCH_NAV_ACTIVE_BG, selected_hover_color=STITCH_NAV_ACTIVE_BG,
            text_color=STITCH_TEXT, fg_color=STITCH_CHIP_BG,
            unselected_color=STITCH_CHIP_BG, unselected_hover_color=STITCH_TAB_HOVER, corner_radius=6,
            command=lambda value: self.set_grain({self._t('Ngày'): "day", self._t('Tuần'): "week", self._t('Tháng'): "month"}[value]))
        self._grain_control.set(self._t('Ngày'))
        self._grain_control.pack(side="left")
        self._mode_control = ctk.CTkSegmentedButton(
            controls, values=[self._t('Đường'), self._t('Cột')], height=28, font=FONT_ST_BODY,
            selected_color=STITCH_NAV_ACTIVE_BG, selected_hover_color=STITCH_NAV_ACTIVE_BG,
            text_color=STITCH_TEXT, fg_color=STITCH_CHIP_BG,
            unselected_color=STITCH_CHIP_BG, unselected_hover_color=STITCH_TAB_HOVER, corner_radius=6,
            command=lambda value: self.set_chart_mode("line" if value == self._t('Đường') else "bar"))
        self._mode_control.set(self._t('Đường'))
        self._mode_control.pack(side="right")
        self.revenue_chart = RevenueChart(charts, self._t('Xu hướng doanh thu'), on_select=self.select_bucket, language=self._t.language)
        self.revenue_chart.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        self.invoice_chart = RevenueChart(charts, self._t('Số hóa đơn'), metric="invoice_count", on_select=self.select_bucket, language=self._t.language)
        self.invoice_chart.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        details = ctk.CTkFrame(body, fg_color="transparent")
        self._details_section = details
        details.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        details.grid_columnconfigure(0, weight=64, uniform="details")
        details.grid_columnconfigure(1, weight=36, uniform="details")
        details.grid_rowconfigure(0, minsize=self._apply_widget_scaling(400))
        table = surface(details, height=420)
        table.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        title = ctk.CTkFrame(table, fg_color="transparent")
        title.pack(fill="x", padx=14, pady=(12, 8))
        ctk.CTkLabel(title, text=self._t('Chi tiết doanh thu'), font=FONT_ST_BODY_STRONG,
                     text_color=STITCH_TEXT_STRONG).pack(side="left")
        self._clear_selection = stitch_button(title, self._t('Xem toàn kỳ'), kind="ghost", width=90,
                                               height=26, command=lambda: self.select_bucket(None))
        self._period_label = ctk.CTkLabel(table, text=self._t('Kỳ: —'), font=FONT_ST_MONO_11,
                                         text_color=STITCH_TEXT_DIM, anchor="w")
        self._period_label.pack(fill="x", padx=14, pady=(0, 6))
        head = ctk.CTkFrame(table, fg_color=workspace_theme.WORKSPACE_HEAD, corner_radius=6)
        head.pack(fill="x", padx=12)
        _configure_columns(head)
        for index, (text, _weight, anchor) in enumerate(_COLUMNS):
            ctk.CTkLabel(head, text=self._t(text), font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED,
                         anchor=anchor, height=34).grid(row=0, column=index, sticky="ew", padx=8)
        footer = ctk.CTkFrame(table, fg_color="transparent")
        footer.pack(fill="x", side="bottom", padx=12, pady=8)
        self._caption_label = ctk.CTkLabel(footer, text="", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED)
        self._caption_label.pack(side="left")
        self._pager = ctk.CTkFrame(footer, fg_color="transparent")
        self._pager.pack(side="right")
        # The report already scrolls as a page; a second nested scroll area would
        # consume the same wheel event and make the daily table hard to navigate.
        self._rows_frame = ctk.CTkFrame(table, fg_color="transparent", corner_radius=0)
        self._rows_frame.pack(fill="both", expand=True, padx=12)
        self._state_frame = ctk.CTkFrame(table, fg_color="transparent")
        self._state_label = ctk.CTkLabel(self._state_frame, text="", font=FONT_ST_BODY,
                                         text_color=STITCH_TEXT_MUTED, wraplength=350)
        self._state_label.pack(pady=(40, 10))
        self._retry_button = stitch_button(self._state_frame, MSG_RETRY, command=self.reload, width=100)
        self._side = surface(details)
        self._side.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        def reflow(event: Any) -> None:
            narrow = event.width < self._apply_widget_scaling(900)
            self.revenue_chart.grid_configure(columnspan=2 if narrow else 1, padx=0 if narrow else (0, 6))
            self.invoice_chart.grid_configure(row=2 if narrow else 1, column=0 if narrow else 1,
                                              columnspan=2 if narrow else 1, padx=0 if narrow else (6, 0),
                                              pady=(10, 0) if narrow else 0)
            table.grid_configure(columnspan=2 if narrow else 1, padx=0 if narrow else (0, 6))
            self._side.grid_configure(row=1 if narrow else 0, column=0 if narrow else 1,
                                      columnspan=2 if narrow else 1, padx=0 if narrow else (6, 0),
                                      pady=(12, 0) if narrow else 0)
        charts.bind("<Configure>", reflow, add="+")

    def set_grain(self, grain: str) -> None:
        if grain not in ("day", "week", "month"):
            raise ValueError("Invalid chart grouping")
        self._grain = grain
        self._selected_bucket = None
        self._update_charts()
        if self._state in (ViewState.READY, ViewState.EMPTY):
            self.select_bucket(None)

    def set_chart_mode(self, mode: str) -> None:
        if mode not in ("line", "bar"):
            raise ValueError("Invalid chart mode")
        self._chart_mode = mode
        self._update_charts()

    def _update_charts(self) -> None:
        if self._state in (ViewState.LOADING, ViewState.ERROR) or self._range is None:
            message = MSG_LOADING if self._state == ViewState.LOADING else "Unable to load chart"
            self.revenue_chart.set_message(message)
            self.invoice_chart.set_message(message)
            return
        buckets = revenue_buckets(self._days, *self._range, grain=self._grain)
        self.revenue_chart.set_data(buckets, mode=self._chart_mode)
        self.invoice_chart.set_data(buckets)
        self.revenue_chart.select(self._selected_bucket)
        self.invoice_chart.select(self._selected_bucket)

    def select_bucket(self, bucket: RevenueBucket | None) -> None:
        self._selected_bucket = None if bucket == self._selected_bucket else bucket
        self._page = 1
        self.revenue_chart.select(self._selected_bucket)
        self.invoice_chart.select(self._selected_bucket)
        self._clear_selection.pack(side="right") if self._selected_bucket else self._clear_selection.pack_forget()
        start, end = (self._selected_bucket.start, self._selected_bucket.end) if self._selected_bucket else self._range or (None, None)
        self._period_label.configure(text=self._t('Kỳ: {v0}', v0=f'{range_caption(start, end)}') if start and end else self._t('Kỳ: —'))
        self._render_rows()
        self._render_side()
        if self._selected_bucket:
            self._schedule_scroll(details=True)

    def _schedule_scroll(self, *, details: bool = False) -> None:
        if self._scroll_id:
            self.after_cancel(self._scroll_id)
        def apply() -> None:
            self._scroll_id = None
            if not self._closed:
                self._scroll_to_details() if details else self._body_scroll._parent_canvas.yview_moveto(0)
        self._scroll_id = self.after_idle(apply)

    def _scroll_to_details(self) -> None:
        if not self._closed:
            self._body_scroll._parent_canvas.yview_moveto(
                self._details_section.winfo_y() / max(1, self._body_scroll.winfo_height()))

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        ctk.CTkLabel(
            footer,
            text=self._t('●  Dữ liệu báo cáo doanh thu • {v0}', v0=f'{self._context.session.store_name}'),
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
        self._selected_bucket = None
        self._clear_selection.pack_forget()
        self._show_state(ViewState.LOADING, MSG_LOADING)
        self._render_kpis()
        self._render_side()
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
        self._synced_label.configure(text=self._t('Cập nhật: {v0}', v0=f'{self._synced_at}'))
        self._state = ViewState.READY
        self._render()
        self._schedule_scroll()

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
        if message:
            self._filter_error.pack(fill="x", padx=14, pady=(0, 8))
        else:
            self._filter_error.pack_forget()

    def go_to_page(self, number: int) -> None:
        self._page = number
        self._render_rows()

    # ------------------------------------------------------------------
    # Vẽ
    # ------------------------------------------------------------------
    def _render(self) -> None:
        start, end = self._range or (None, None)
        self._period_label.configure(text=self._t('Kỳ: {v0}', v0=f'{range_caption(start, end)}') if start and end else self._t('Kỳ: —'))
        self._render_kpis()
        self._render_rows()
        self._render_side()
        self._update_charts()

    def _render_kpis(self) -> None:
        loaded = self._state in (ViewState.READY, ViewState.EMPTY)
        summary = self.summary
        best = summary.best_day
        values = {
            "total": (format_money(summary.total, language=self._t.language), self._t('Từ {v0} HĐ thành công', v0=f'{summary.invoice_count}')),
            "count": (self._t('{v0} đơn', v0=f'{summary.invoice_count}'), self._t('Đã thu hoàn tất')),
            "average": (format_money(summary.average_per_invoice, language=self._t.language), self._t('TB mỗi hóa đơn đã thanh toán')),
            "best": (
                format_vn_date(best.date) if best else "—",
                self._t('{v0} • {v1} tổng kỳ', v0=f'{format_money(best.revenue, language=self._t.language)}', v1=f'{format_percent(summary.best_share)}') if best else self._t('Chưa có doanh thu'),
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
            self._show_state(ViewState.EMPTY, self._t(NO_REVENUE))
            return
        self._state = ViewState.READY
        self._state_frame.pack_forget()
        self._rows_frame.pack(fill="both", expand=True, padx=12)
        page = self.current_page
        self._page = page.number
        if not page.items:
            self._show_state(ViewState.EMPTY, self._t('Không có hóa đơn đã thanh toán trong khoảng chọn.'))
            return
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
                ctk.CTkLabel(tag, text=self._t('HÔM NAY'), font=FONT_ST_MONO_XS_STRONG, text_color=STITCH_CYAN, height=16).pack(padx=6)
            ctk.CTkLabel(row, text=self._t('{v0} HĐ', v0=f'{day.invoice_count}'), font=FONT_ST_MONO_BODY, text_color=STITCH_TEXT).grid(row=0, column=1, sticky="e", padx=8)
            ctk.CTkLabel(
                row,
                text=format_number(day.revenue, language=self._t.language),
                font=FONT_ST_MONO_SM,
                text_color=STITCH_SUCCESS if best is not None and day.date == best.date else STITCH_TEXT_STRONG,
            ).grid(row=0, column=2, sticky="e", padx=8)
            ctk.CTkLabel(row, text=format_percent(share_percent(day.revenue, total)), font=FONT_ST_MONO_BODY, text_color=STITCH_TEXT_MUTED).grid(
                row=0, column=3, sticky="e", padx=8
            )
            bind_hover(row, base_color="transparent", hover_color=STITCH_TAB_HOVER)
        self._caption_label.configure(text=page_caption(page, language=self._t.language))
        build_pager(self._pager, page, self.go_to_page)

    def _render_side(self) -> None:
        for child in self._side.winfo_children():
            child.destroy()
        panel = ctk.CTkFrame(self._side, fg_color="transparent")
        panel.pack(fill="both", expand=True, padx=16, pady=14)
        loaded = self._state in (ViewState.READY, ViewState.EMPTY)
        if not loaded:
            ctk.CTkLabel(panel, text=MSG_LOADING if self._state == ViewState.LOADING else self._t('Không thể tải báo cáo. Nhấn Làm mới để thử lại.'),
                         font=FONT_ST_BODY, text_color=STITCH_DANGER if self._state == ViewState.ERROR else STITCH_TEXT_MUTED,
                         wraplength=240, justify="left").pack(fill="x", pady=20)
            return
        focus = self._selected_bucket
        start, end = (focus.start, focus.end) if focus else self._range or (None, None)
        days = [d for d in self._days if start and end and start <= d.date <= end]
        summary = summarize_revenue(days)
        ctk.CTkLabel(panel, text=self._t('Phân tích khoảng chọn') if focus else self._t('Phân tích nhanh'),
                     font=workspace_theme.FONT_WORKSPACE_SECTION, text_color=STITCH_TEXT_STRONG, anchor="w").pack(fill="x")
        ctk.CTkLabel(panel, text=self._context.session.store_name, font=FONT_ST_BODY,
                     text_color=STITCH_TEXT_MUTED, anchor="w").pack(fill="x", pady=(0, 12))
        count = (end - start).days + 1 if start and end else 0
        average = calendar_average(days, start, end) if start and end else 0
        box = ctk.CTkFrame(panel, fg_color=STITCH_NAV_ACTIVE_BG, corner_radius=8)
        box.pack(fill="x")
        ctk.CTkLabel(box, text=self._t('TRUNG BÌNH / NGÀY LỊCH'), font=FONT_ST_LABEL_CAPS,
                     text_color=STITCH_CYAN, anchor="w").pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(box, text=format_money(average, language=self._t.language) if loaded else "—",
                     font=FONT_ST_KPI_VALUE, text_color=STITCH_TEXT_STRONG, anchor="w").pack(fill="x", padx=12)
        ctk.CTkLabel(box, text=self._t('Tính đủ {v0} ngày, kể cả ngày không phát sinh', v0=f'{count}'), font=FONT_ST_MONO_11,
                     text_color=STITCH_TEXT_MUTED, anchor="w", wraplength=250).pack(fill="x", padx=12, pady=(2, 10))
        rows = ((self._t('Số ngày có doanh thu'), self._t('{v0} / {v1} ngày', v0=f'{summary.days_with_revenue}', v1=f'{count}')),
                (self._t('Trung bình / ngày có thu'), format_money(summary.average_per_day, language=self._t.language)),
                (self._t('Giá trị trung bình / HĐ'), format_money(summary.average_per_invoice, language=self._t.language)))
        for label, value in rows:
            line = ctk.CTkFrame(panel, fg_color="transparent")
            line.pack(fill="x", pady=(10, 0))
            ctk.CTkLabel(line, text=label, font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED).pack(side="left")
            ctk.CTkLabel(line, text=value if loaded else "—", font=FONT_ST_BODY_STRONG,
                         text_color=STITCH_TEXT).pack(side="right")
        progress = ctk.CTkProgressBar(panel, height=5, progress_color=STITCH_CYAN, fg_color=STITCH_CHIP_BG)
        progress.pack(fill="x", pady=(10, 12))
        progress.set(summary.days_with_revenue / count if loaded and count else 0)
        best = summary.best_day
        ctk.CTkLabel(panel, text=self._t('ĐÓNG GÓP NGÀY CAO NHẤT'), font=FONT_ST_LABEL_CAPS,
                     text_color=STITCH_TEXT_DIM, anchor="w").pack(fill="x")
        ctk.CTkLabel(panel, text=f"{format_vn_date(best.date)} · {format_money(best.revenue, language=self._t.language)}" if best and loaded else "—",
                     font=FONT_ST_BODY_STRONG, text_color=STITCH_SUCCESS, anchor="w").pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(panel, text=self._t('{v0}% doanh thu trong khoảng chọn', v0=f'{summary.best_share:.1f}') if best else self._t('Chưa có doanh thu'),
                     font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED, anchor="w").pack(fill="x")
        ctk.CTkLabel(panel, text=self._t('Chỉ tính hóa đơn đã thanh toán. Biểu đồ tổng hợp theo ngày, tuần hoặc tháng; ngày không phát sinh có giá trị 0.'),
                     font=FONT_ST_MONO_11, text_color=STITCH_TEXT_DIM, justify="left", wraplength=270,
                     anchor="w").pack(fill="x", pady=(14, 0))

    def _show_state(self, state: ViewState, message: str) -> None:
        self._state = state
        if state in (ViewState.LOADING, ViewState.ERROR):
            self._update_charts()
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
        if self._scroll_id:
            self.after_cancel(self._scroll_id)
            self._scroll_id = None

    def destroy(self) -> None:
        self.shutdown()
        super().destroy()


reports_view_factory = ReportsView
