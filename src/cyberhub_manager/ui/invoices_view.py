"""NG-07 — Màn Hóa đơn (INV-04/05).

Stitch không có màn danh sách hóa đơn riêng, nên màn này theo cùng ngôn ngữ thiết kế với màn
Khách hàng (NG-04) và hóa đơn "Thanh toán thành công" (NG-06):
- Header + 3 thẻ tóm tắt (số hóa đơn, tổng tiền đã thanh toán, số hóa đơn đã hủy).
- Hàng lọc: Từ ngày / Đến ngày (dd/mm/yyyy, giờ Việt Nam), từ khóa (mã HĐ, tên khách), Áp dụng / Xóa bộ lọc,
  tab Tất cả / Đã thanh toán / Đã hủy.
- Trái: bảng hóa đơn phân trang (mới nhất trước). Phải: chi tiết hóa đơn (ReportService.get_invoice).
- Loading / empty / error + Thử lại; ngày sai định dạng hoặc ngược thứ tự báo ngay trên ô.
- UI không tự tính tiền hóa đơn: chỉ cộng tổng các số service trả về để hiện thẻ tóm tắt.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

import customtkinter as ctk

from ..domain.dtos import InvoiceDetail, InvoiceFilters, InvoiceSummary
from ..domain.enums import InvoiceStatus
from ..domain.exceptions import ValidationError
from .app_shell import ViewContext
from .i18n import UIStrings
from .background import TaskRunner, default_runner
from .components import ToastManager
from .components.stitch_button import stitch_button
from .components.workspace import PageHeader, MetricTile, icon_action, surface
from . import theme as workspace_theme
from .formatters import format_datetime, format_duration, format_money
from .messages import MSG_LOADING, MSG_NO_DATA, MSG_RETRY, get_field_errors_safe, get_user_friendly_error
from .report_filters import default_range, format_vn_date, local_today, validate_range
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
    STITCH_BADGE_DANGER_BG,
    STITCH_BADGE_DANGER_BORDER,
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
ROW_HEIGHT = 52
ROW_SELECTED_BG = "#10293A"
CODE_COPIED = "Invoice code copied."


# ----------------------------------------------------------------------
# Hàm thuần (test được không cần Tk)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Badge:
    label: str
    text_color: str
    bg: str
    border: str


def invoice_badge(status: InvoiceStatus) -> Badge:
    if status == InvoiceStatus.PAID:
        return Badge("Đã thanh toán", STITCH_SUCCESS, STITCH_BADGE_SUCCESS_BG, STITCH_BADGE_SUCCESS_BORDER)
    return Badge("Đã hủy", STITCH_DANGER, STITCH_BADGE_DANGER_BG, STITCH_BADGE_DANGER_BORDER)


def filter_by_status(invoices: Iterable[InvoiceSummary], status: InvoiceStatus | None) -> list[InvoiceSummary]:
    return [i for i in invoices if status is None or i.status == status]


def count_by_status(invoices: Iterable[InvoiceSummary]) -> dict[InvoiceStatus | None, int]:
    invoices = list(invoices)
    counts: dict[InvoiceStatus | None, int] = {None: len(invoices)}
    for status in InvoiceStatus:
        counts[status] = sum(1 for i in invoices if i.status == status)
    return counts


@dataclass(frozen=True)
class InvoiceTotals:
    count: int
    paid_total: int  # chỉ hóa đơn PAID (hóa đơn hủy không tính doanh thu)
    void_count: int


def invoice_totals(invoices: Iterable[InvoiceSummary]) -> InvoiceTotals:
    invoices = list(invoices)
    paid = [i for i in invoices if i.status == InvoiceStatus.PAID]
    return InvoiceTotals(len(invoices), sum(i.total_amount for i in paid), len(invoices) - len(paid))


def page_caption(page: Page, language: str = "vi") -> str:
    return UIStrings(language)("Hiển thị {v0} - {v1} trên {v2} hóa đơn", v0=page.first, v1=page.last, v2=page.total)


_TAB_SPECS: tuple[tuple[InvoiceStatus | None, str], ...] = (
    (None, "Tất cả"),
    (InvoiceStatus.PAID, "Đã thanh toán"),
    (InvoiceStatus.VOID, "Đã hủy"),
)
# (tiêu đề, tỉ lệ độ rộng, căn lề)
_COLUMNS = (
    ("MÃ HĐ", 3, "w"),
    ("THỜI GIAN", 5, "w"),
    ("KHÁCH HÀNG", 6, "w"),
    ("THU NGÂN", 5, "w"),
    ("TỔNG TIỀN", 4, "e"),
    ("TRẠNG THÁI", 5, "center"),
)


def _configure_columns(frame: Any, compact: bool = False) -> None:
    for index, (_title, weight, _anchor) in enumerate(_COLUMNS):
        hidden = compact and index == 3
        frame.grid_columnconfigure(index, weight=0 if hidden else weight,
                                   uniform="" if hidden else "invoice", minsize=0)


def _badge(master: Any, badge: Badge, language: str = "vi") -> ctk.CTkFrame:
    box = ctk.CTkFrame(master, fg_color=badge.bg, border_width=1, border_color=badge.border, corner_radius=10)
    ctk.CTkLabel(box, text=f"● {UIStrings(language)(badge.label)}", font=FONT_ST_MONO_XS_STRONG, text_color=badge.text_color, height=18).pack(padx=8)
    return box


def _date_entry(master: Any, width: int = 108) -> ctk.CTkEntry:
    return ctk.CTkEntry(
        master,
        width=width,
        height=30,
        placeholder_text="dd/mm/yyyy",
        fg_color=STITCH_INPUT_BG,
        border_color=STITCH_INPUT_BORDER,
        border_width=1,
        corner_radius=STITCH_RADIUS,
        text_color=STITCH_TEXT_STRONG,
        font=FONT_ST_MONO_BODY,
    )


class InvoicesView(ctk.CTkFrame):
    def __init__(self, master: Any, context: ViewContext, *, runner: TaskRunner | None = None) -> None:
        super().__init__(master, fg_color="transparent")
        self._context = context
        self._t = UIStrings(context.language)
        self._runner = runner or default_runner()
        self._invoices: list[InvoiceSummary] = []
        self._status_filter: InvoiceStatus | None = None
        self._page = 1
        self._selected_id: int | None = None
        self._detail: InvoiceDetail | None = None
        self._state = ViewState.LOADING
        self._closed = False
        self._load_request = 0
        self._detail_request = 0
        self._applied: InvoiceFilters | None = None
        self._tab_buttons: dict[InvoiceStatus | None, ctk.CTkButton] = {}
        self._kpi_labels: dict[str, ctk.CTkLabel] = {}
        self._compact = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build_header()
        self._build_kpis()
        self._build_filter_row()
        self._build_body()
        self.bind("<Configure>", self._resize_table, add="+")
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
    def invoices(self) -> list[InvoiceSummary]:
        return list(self._invoices)

    @property
    def applied_filters(self) -> InvoiceFilters | None:
        return self._applied

    @property
    def current_page(self) -> Page:
        return paginate(filter_by_status(self._invoices, self._status_filter), self._page, PAGE_SIZE)

    @property
    def visible_invoice_ids(self) -> list[int]:
        return [i.invoice_id for i in self.current_page.items]

    @property
    def selected_invoice(self) -> InvoiceSummary | None:
        return next((i for i in self._invoices if i.invoice_id == self._selected_id), None)

    @property
    def detail(self) -> InvoiceDetail | None:
        return self._detail

    @property
    def filter_error(self) -> str:
        return self._filter_error.cget("text")

    # ------------------------------------------------------------------
    # Dựng giao diện
    # ------------------------------------------------------------------
    def _build_header(self) -> None:
        header = PageHeader(self, self._t('Hóa đơn'), self._t('Tra cứu giao dịch và kiểm tra chi tiết thanh toán tại ') + self._context.session.store_name + ".",
                            eyebrow=self._t('TÀI CHÍNH & GIAO DỊCH'))
        header.grid(row=0, column=0, sticky="ew")
        self._refresh_button = icon_action(header.actions, self._t('Làm mới'), "refresh", command=self.reload)
        self._refresh_button.pack(side="right")

    def _build_kpis(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        specs = (("count", self._t('TỔNG HÓA ĐƠN'), "invoices", STITCH_TEXT_STRONG, self._t('Trong khoảng thời gian đã chọn')),
                 ("paid", self._t('DOANH THU ĐÃ THANH TOÁN'), "money", STITCH_CYAN, self._t('Chỉ cộng các hóa đơn đã thanh toán')),
                 ("void", self._t('HÓA ĐƠN ĐÃ HỦY'), "archive", STITCH_DANGER, self._t('Được loại khỏi doanh thu')))
        for index, (key, title, icon, color, note) in enumerate(specs):
            row.grid_columnconfigure(index, weight=1, uniform="kpi")
            tile = MetricTile(row, title, icon=icon, color=color, note=note, accent=key == "paid")
            tile.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 10, 0))
            self._kpi_labels[key] = tile.value

    def _build_filter_row(self) -> None:
        bar = surface(self)
        bar.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        line = ctk.CTkFrame(bar, fg_color="transparent")
        line.pack(fill="x", padx=14, pady=(10, 0))
        for label, attr in ((self._t('Từ ngày'), "_from_entry"), (self._t('Đến ngày'), "_to_entry")):
            ctk.CTkLabel(line, text=label, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(side="left", padx=(0, 8))
            entry = _date_entry(line)
            entry.configure(height=34, corner_radius=6)
            entry.pack(side="left", padx=(0, 16))
            setattr(self, attr, entry)
        self._apply_button = icon_action(line, self._t('Áp dụng'), "check", kind="primary", command=self.apply_filters, width=96)
        self._apply_button.pack(side="left")
        icon_action(line, self._t('Đặt lại'), "restore", command=self.clear_filters, width=88).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(line, text=self._t('Giờ Việt Nam'), font=FONT_ST_MONO_11,
                     text_color=STITCH_TEXT_DIM).pack(side="right")
        second = ctk.CTkFrame(bar, fg_color="transparent")
        second.pack(fill="x", padx=14, pady=(10, 10))
        tabs = ctk.CTkFrame(second, fg_color="transparent")
        tabs.pack(side="right")
        for status, _label in _TAB_SPECS:
            button = ctk.CTkButton(tabs, text="", height=32, width=106, corner_radius=6,
                                   border_width=1, font=FONT_ST_BODY,
                                   command=lambda s=status: self.set_status_filter(s))
            button.pack(side="left", padx=(6, 0))
            self._tab_buttons[status] = button
        self._search_entry = ctk.CTkEntry(second, width=240, height=34,
                                          placeholder_text=self._t('Tìm mã hóa đơn hoặc tên khách hàng…'),
                                          fg_color=STITCH_INPUT_BG, border_color=STITCH_INPUT_BORDER,
                                          border_width=1, corner_radius=6, text_color=STITCH_TEXT, font=FONT_ST_BODY)
        self._search_entry.pack(side="left", fill="x", expand=True, padx=(0, 12))
        for entry in (self._from_entry, self._to_entry, self._search_entry):
            entry.bind("<Return>", lambda _e: self.apply_filters(), add="+")
        self._filter_error = ctk.CTkLabel(bar, text="", font=FONT_ST_MONO_11,
                                         text_color=STITCH_DANGER, height=18, anchor="w")
        self._update_tabs()

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=64, uniform="split")
        body.grid_columnconfigure(1, weight=36, uniform="split")
        table = surface(body)
        table.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        title = ctk.CTkFrame(table, fg_color="transparent")
        title.pack(fill="x", padx=14, pady=(12, 8))
        ctk.CTkLabel(title, text=self._t('Lịch sử hóa đơn'), font=workspace_theme.FONT_WORKSPACE_SECTION,
                     text_color=STITCH_TEXT_STRONG).pack(side="left")
        ctk.CTkLabel(title, text=self._t('Mới nhất trước'), font=FONT_ST_MONO_11,
                     text_color=STITCH_TEXT_DIM).pack(side="right")
        head = ctk.CTkFrame(table, fg_color=workspace_theme.WORKSPACE_HEAD, corner_radius=6)
        self._table_head = head
        self._head_labels: list[ctk.CTkLabel] = []
        head.pack(fill="x", padx=(12, 26))
        _configure_columns(head)
        for index, (title, _weight, anchor) in enumerate(_COLUMNS):
            label = ctk.CTkLabel(head, text=self._t(title), font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED,
                                  anchor=anchor, height=36)
            label.grid(row=0, column=index, sticky="ew", padx=6)
            self._head_labels.append(label)
        footer = ctk.CTkFrame(table, fg_color="transparent")
        footer.pack(fill="x", side="bottom", padx=12, pady=8)
        self._caption_label = ctk.CTkLabel(footer, text="", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED)
        self._caption_label.pack(side="left")
        self._pager = ctk.CTkFrame(footer, fg_color="transparent")
        self._pager.pack(side="right")
        self._rows_frame = ctk.CTkScrollableFrame(table, fg_color="transparent", corner_radius=0,
                                                  scrollbar_button_color=STITCH_CHIP_BORDER)
        self._rows_frame.pack(fill="both", expand=True, padx=12)
        self._state_frame = ctk.CTkFrame(table, fg_color="transparent")
        self._state_label = ctk.CTkLabel(self._state_frame, text="", font=FONT_ST_BODY,
                                         text_color=STITCH_TEXT_MUTED, wraplength=360)
        self._state_label.pack(pady=(40, 10))
        self._retry_button = stitch_button(self._state_frame, MSG_RETRY, command=self.reload, width=100)
        self._detail_frame = ctk.CTkScrollableFrame(body, fg_color=STITCH_CARD_BG, border_width=1,
                                                    border_color=STITCH_CARD_BORDER,
                                                    corner_radius=workspace_theme.WORKSPACE_RADIUS,
                                                    scrollbar_button_color=STITCH_CHIP_BORDER)
        self._detail_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._render_detail()

    def _resize_table(self, event: Any) -> None:
        compact = event.width < self._apply_widget_scaling(900)
        if self._closed or compact == self._compact:
            return
        self._compact = compact
        _configure_columns(self._table_head, compact)
        self._head_labels[3].grid_remove() if compact else self._head_labels[3].grid()
        if self._state in (ViewState.READY, ViewState.EMPTY):
            self._render()

    def apply_filters(self) -> None:
        """Đọc bộ lọc trên thanh lọc; hợp lệ thì gọi list_invoices."""
        checked = validate_range(self._from_entry.get(), self._to_entry.get(), required=False)
        self._paint_date_errors(checked.errors)
        if not checked.ok:
            return
        self._applied = InvoiceFilters(date_from=checked.date_from, date_to=checked.date_to, keyword=self._search_entry.get().strip())
        self._page = 1
        self._selected_id = None
        self.reload()

    def clear_filters(self) -> None:
        """Về khoảng mặc định 30 ngày, bỏ từ khóa và tab trạng thái."""
        start, end = default_range(local_today(self._context.services))
        for entry, value in ((self._from_entry, format_vn_date(start)), (self._to_entry, format_vn_date(end)), (self._search_entry, "")):
            entry.delete(0, "end")
            if value:
                entry.insert(0, value)
        self._status_filter = None
        self.apply_filters()

    def set_dates(self, date_from: date | None, date_to: date | None) -> None:
        for entry, value in ((self._from_entry, date_from), (self._to_entry, date_to)):
            entry.delete(0, "end")
            if value:
                entry.insert(0, format_vn_date(value))

    def handle_search(self, text: str) -> None:
        """Từ khóa từ ô tìm kiếm trên topbar (NG-02)."""
        self._search_entry.delete(0, "end")
        if text:
            self._search_entry.insert(0, text)
        self.apply_filters()

    def reload(self) -> None:
        if self._closed or self._applied is None:
            return
        self._load_request += 1
        request = self._load_request
        self._show_state(ViewState.LOADING, MSG_LOADING)
        self._apply_button.set_busy(True, busy_text="…")
        self._refresh_button.set_enabled(False)
        reports, store_id, filters = self._context.services.reports, self._context.session.store_id, self._applied
        self._runner.submit(
            self,
            lambda: reports.list_invoices(store_id, filters),
            lambda invoices: self._on_loaded(request, invoices),
            lambda error: self._on_load_failed(request, error),
        )

    def _loading_done(self) -> None:
        self._apply_button.set_busy(False)
        self._refresh_button.set_enabled(True)

    def _on_loaded(self, request: int, invoices: list[InvoiceSummary]) -> None:
        if self._closed or request != self._load_request:
            return
        self._loading_done()
        self._invoices = list(invoices)
        self._state = ViewState.READY
        visible = filter_by_status(self._invoices, self._status_filter)
        if self.selected_invoice is None or self.selected_invoice not in visible:
            self._selected_id = visible[0].invoice_id if visible else None
        self._update_kpis()
        self._render()
        self._load_detail()

    def _on_load_failed(self, request: int, error: Exception) -> None:
        if self._closed or request != self._load_request:
            return
        self._loading_done()
        if isinstance(error, ValidationError):  # service kiểm tra lại khoảng ngày
            self._paint_date_errors(get_field_errors_safe(error))
        self._invoices = []
        self._selected_id = None
        self._detail = None
        self._update_kpis()
        self._update_tabs()
        self._show_state(ViewState.ERROR, get_user_friendly_error(error))
        self._render_detail()

    def _paint_date_errors(self, errors: dict[str, str]) -> None:
        for key, entry in (("date_from", self._from_entry), ("date_to", self._to_entry)):
            entry.configure(border_color=STITCH_DANGER if key in errors else STITCH_INPUT_BORDER)
        message = errors.get("date_from") or errors.get("date_to") or ""
        self._filter_error.configure(text=f"⚠ {message}" if message else "")
        if message:
            self._filter_error.pack(fill="x", padx=14, pady=(0, 8))
        else:
            self._filter_error.pack_forget()

    def _load_detail(self) -> None:
        invoice = self.selected_invoice
        self._detail = None
        self._detail_request += 1
        request = self._detail_request
        self._render_detail(loading=invoice is not None)
        if invoice is None:
            return
        reports = self._context.services.reports
        invoice_id = invoice.invoice_id

        def done(detail: InvoiceDetail) -> None:
            if self._closed or request != self._detail_request:
                return
            self._detail = detail
            self._render_detail()

        def failed(error: Exception) -> None:
            if self._closed or request != self._detail_request:
                return
            self._render_detail(error=get_user_friendly_error(error))

        self._runner.submit(self, lambda: reports.get_invoice(invoice_id), done, failed)

    # ------------------------------------------------------------------
    # Tab / chọn / phân trang
    # ------------------------------------------------------------------
    def set_status_filter(self, status: InvoiceStatus | None) -> None:
        self._status_filter = status
        self._page = 1
        if self._state in (ViewState.READY, ViewState.EMPTY):
            visible = filter_by_status(self._invoices, status)
            if self.selected_invoice not in visible:
                self._selected_id = visible[0].invoice_id if visible else None
                self._load_detail()
            self._render()
        else:
            self._update_tabs()

    def go_to_page(self, number: int) -> None:
        self._page = number
        self._render()

    def select(self, invoice_id: int) -> None:
        if invoice_id == self._selected_id:
            return
        self._selected_id = invoice_id
        self._render()
        self._load_detail()

    # ------------------------------------------------------------------
    # Vẽ
    # ------------------------------------------------------------------
    def _update_kpis(self) -> None:
        totals = invoice_totals(self._invoices)
        loaded = self._state == ViewState.READY
        self._kpi_labels["count"].configure(text=self._t('{v0} đơn', v0=f'{totals.count}') if loaded else "—")
        self._kpi_labels["paid"].configure(text=format_money(totals.paid_total, language=self._t.language) if loaded else "—")
        self._kpi_labels["void"].configure(text=self._t('{v0} đơn', v0=f'{totals.void_count}') if loaded else "—")

    def _update_tabs(self) -> None:
        counts = count_by_status(self._invoices)
        loaded = self._state in (ViewState.READY, ViewState.EMPTY)
        for status, label in _TAB_SPECS:
            label = self._t(label)
            active = status == self._status_filter
            self._tab_buttons[status].configure(
                text=f"{label} ({counts[status]})" if loaded else label,
                fg_color=STITCH_NAV_ACTIVE_BG if active else STITCH_INPUT_BG,
                hover_color=STITCH_NAV_ACTIVE_BG if active else STITCH_CHIP_BG,
                border_color=STITCH_NAV_ACTIVE_BORDER if active else STITCH_CHIP_BORDER,
                text_color=STITCH_CYAN if active else STITCH_TEXT_MUTED,
                font=FONT_ST_BODY_STRONG if active else FONT_ST_BODY,
            )

    def _render(self) -> None:
        self._state = ViewState.READY if self._state in (ViewState.READY, ViewState.EMPTY) else self._state
        self._update_tabs()
        page = self.current_page
        self._page = page.number
        for child in self._rows_frame.winfo_children():
            child.destroy()
        if not page.items:
            self._show_state(ViewState.EMPTY, MSG_NO_DATA)
            self._render_detail()
            return
        self._state_frame.pack_forget()
        self._rows_frame.pack(fill="both", expand=True, padx=12)
        for index, invoice in enumerate(page.items):
            if index:
                ctk.CTkFrame(self._rows_frame, fg_color=STITCH_CARD_BORDER, height=1, corner_radius=0).pack(fill="x")
            self._build_row(invoice, index)
        self._caption_label.configure(text=page_caption(page, language=self._t.language))
        build_pager(self._pager, page, self.go_to_page)

    def _build_row(self, invoice: InvoiceSummary, index: int = 0) -> None:
        selected = invoice.invoice_id == self._selected_id
        void = invoice.status == InvoiceStatus.VOID
        base = ROW_SELECTED_BG if selected else workspace_theme.WORKSPACE_ROW_ALT if index % 2 else STITCH_CARD_BG
        row = ctk.CTkFrame(self._rows_frame, fg_color=base, height=ROW_HEIGHT, corner_radius=0)
        row.pack(fill="x")
        row.grid_propagate(False)
        row.grid_rowconfigure(0, weight=1)
        _configure_columns(row, self._compact)
        if selected:
            tk.Frame(row, bg=STITCH_CYAN, width=2).place(x=0, y=0, relheight=1)
        text_color = STITCH_TEXT_MUTED if void else STITCH_TEXT
        timestamp = ctk.CTkFrame(row, fg_color="transparent")
        time_text, date_text = format_datetime(invoice.created_at).split(" ", 1)
        ctk.CTkLabel(timestamp, text=date_text, font=FONT_ST_MONO_11, text_color=text_color, height=18).pack(anchor="w")
        ctk.CTkLabel(timestamp, text=time_text, font=FONT_ST_MONO_11, text_color=STITCH_TEXT_DIM, height=16).pack(anchor="w")
        cells = [
            ctk.CTkLabel(row, text=invoice.invoice_code, font=FONT_ST_MONO_SM, text_color=STITCH_CYAN if selected else text_color),
            timestamp,
            ctk.CTkLabel(row, text=invoice.customer_name, wraplength=96, justify="left", font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT_STRONG if selected else text_color),
            ctk.CTkLabel(row, text=invoice.employee_name, wraplength=80, justify="left", font=FONT_ST_BODY, text_color=text_color),
            ctk.CTkLabel(row, text=format_money(invoice.total_amount, language=self._t.language), wraplength=78, justify="right", font=FONT_ST_MONO_SM, text_color=STITCH_TEXT_MUTED if void else STITCH_TEXT_STRONG),
            _badge(row, invoice_badge(invoice.status), language=self._t.language),
        ]
        for index, widget in enumerate(cells):
            if self._compact and index == 3:
                continue  # Cashier remains available in the invoice detail panel.
            widget.grid(row=0, column=index, sticky=_COLUMNS[index][2] if index != 5 else "", padx=6)
        bind_hover(row, base_color=base, hover_color=ROW_SELECTED_BG if selected else STITCH_TAB_HOVER)
        self._bind_click(row, invoice.invoice_id)

    def _bind_click(self, widget: Any, invoice_id: int) -> None:
        widget.bind("<Button-1>", lambda _e: self.select(invoice_id), add="+")
        for child in widget.winfo_children():
            self._bind_click(child, invoice_id)

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

    def _render_detail(self, *, loading: bool = False, error: str | None = None) -> None:
        for child in self._detail_frame.winfo_children():
            child.destroy()
        panel = ctk.CTkFrame(self._detail_frame, fg_color="transparent")
        panel.pack(fill="both", expand=True, padx=14, pady=12)
        invoice = self.selected_invoice
        if invoice is None:
            ctk.CTkLabel(panel, text=self._t('Chọn một hóa đơn để xem chi tiết.'), font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(pady=40)
            return

        head = ctk.CTkFrame(panel, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text=self._t('Chi tiết hóa đơn'), font=workspace_theme.FONT_WORKSPACE_SECTION, text_color=STITCH_TEXT_STRONG, height=20).pack(side="left")
        _badge(head, invoice_badge(invoice.status), language=self._t.language).pack(side="right")
        code_line = ctk.CTkFrame(panel, fg_color="transparent")
        code_line.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(code_line, text=invoice.invoice_code, font=FONT_ST_KPI_VALUE, text_color=STITCH_CYAN, height=28).pack(side="left")
        self._copy_button = icon_action(code_line, self._t('Sao chép'), "copy", command=self.copy_invoice_code, width=90, height=30)
        self._copy_button.pack(side="right")
        ctk.CTkFrame(panel, fg_color=STITCH_CARD_BORDER, height=1, corner_radius=0).pack(fill="x", pady=(8, 8))

        if loading:
            ctk.CTkLabel(panel, text=MSG_LOADING, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(pady=20)
            return
        if error:
            ctk.CTkLabel(panel, text=error, font=FONT_ST_BODY, text_color=STITCH_DANGER, wraplength=280).pack(pady=20)
            return
        detail = self._detail
        if detail is None:
            return
        session = detail.session
        inv = detail.invoice
        from .p1_views import export_detail
        exports = ctk.CTkFrame(panel,fg_color="transparent")
        exports.pack(fill="x",pady=(0,10))
        icon_action(exports,self._t("Xuất hóa đơn"),"invoices",command=lambda:export_detail(self,detail,self._t.language),width=130).pack(side="left")
        icon_action(exports,self._t("In / Lưu PDF"),"copy",command=lambda:export_detail(self,detail,self._t.language,True),width=130).pack(side="right")
        summary = ctk.CTkFrame(panel, fg_color=STITCH_BADGE_DANGER_BG if inv.status == InvoiceStatus.VOID else STITCH_NAV_ACTIVE_BG,
                               border_width=1, border_color=STITCH_CARD_BORDER, corner_radius=10)
        summary.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(summary, text=self._t('GIÁ TRỊ HÓA ĐƠN'), font=FONT_ST_LABEL_CAPS,
                     text_color=STITCH_TEXT_MUTED, anchor="w").pack(fill="x", padx=12, pady=(8, 0))
        self._total_label = ctk.CTkLabel(summary, text=format_money(inv.total_amount, language=self._t.language),
                                         font=workspace_theme.FONT_WORKSPACE_METRIC,
                                         text_color=STITCH_DANGER if inv.status == InvoiceStatus.VOID else STITCH_SUCCESS,
                                         anchor="w")
        self._total_label.pack(fill="x", padx=12, pady=(0, 2))
        ctk.CTkLabel(summary, text=self._t('Đã hủy · Không tính doanh thu') if inv.status == InvoiceStatus.VOID else self._t('Đã thanh toán hoàn tất'),
                     font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED, anchor="w").pack(fill="x", padx=12, pady=(0, 10))
        info = ctk.CTkFrame(panel, fg_color=STITCH_BG_CHROME, border_width=1, border_color=STITCH_CARD_BORDER, corner_radius=STITCH_RADIUS_LG)
        info.pack(fill="x")
        rows = (
            (self._t('Thời gian:'), format_datetime(detail.invoice.created_at), STITCH_TEXT),
            (self._t('Thu ngân:'), detail.invoice.employee_name, STITCH_TEXT),
            (self._t('Khách hàng:'), f"{session.customer_name} — {session.customer_code}", STITCH_TEXT_STRONG),
            (self._t('Mã phiên:'), session.session_code, STITCH_TEXT),
            (self._t('Máy:'), f"{session.machine_code} — {session.machine_name}", STITCH_TEXT),
            (self._t('Bắt đầu:'), format_datetime(session.started_at), STITCH_TEXT),
            (self._t('Kết thúc:'), format_datetime(detail.ended_at), STITCH_TEXT),
            (self._t('Thời lượng tính phí:'), format_duration(detail.billed_minutes * 60, language=self._t.language), STITCH_TEXT),
            (self._t('Đơn giá:'), self._t('{v0}/giờ', v0=f'{format_money(session.hourly_rate, language=self._t.language)}'), STITCH_TEXT),
        )
        for index, (label, value, color) in enumerate(rows):
            line = ctk.CTkFrame(info, fg_color="transparent")
            line.pack(fill="x", padx=10, pady=(8 if index == 0 else 2, 8 if index == len(rows) - 1 else 2))
            line.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(line, text=label, font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED, height=18).grid(row=0, column=0, sticky="nw", padx=(0, 8))
            value_label = ctk.CTkLabel(line, text=value, font=FONT_ST_MONO_BODY, text_color=color,
                                       height=18, wraplength=170, justify="right")
            value_label.grid(row=0, column=1, sticky="e")
            line.bind("<Configure>", lambda event, widget=value_label: widget.configure(
                wraplength=max(100, event.width / self._get_widget_scaling() - 105)), add="+")

        money = ctk.CTkFrame(panel, fg_color="transparent")
        money.pack(fill="x", pady=(10, 0))
        inv = detail.invoice
        for label, value, color in (
            (self._t('Chi phí sử dụng:'), format_money(inv.usage_cost, language=self._t.language), STITCH_TEXT),
            (self._t('Khuyến mãi đã sử dụng:'), format_money(inv.bonus_used,language=self._t.language), STITCH_CYAN),
            (self._t('Trong đó khách bù (tiền mặt/CK):'), format_money(inv.settlement_amount, language=self._t.language), STITCH_TEXT),
        ):
            line = ctk.CTkFrame(money, fg_color="transparent")
            line.pack(fill="x", pady=2)
            ctk.CTkLabel(line, text=label, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=18).pack(side="left")
            ctk.CTkLabel(line, text=value, font=FONT_ST_MONO_SM, text_color=color, height=18).pack(side="right")
        ctk.CTkFrame(money, fg_color=STITCH_CARD_BORDER, height=1, corner_radius=0).pack(fill="x", pady=(6, 6))
        if inv.status == InvoiceStatus.VOID:
            note = ctk.CTkFrame(panel, fg_color=STITCH_BADGE_DANGER_BG, border_width=1, border_color=STITCH_BADGE_DANGER_BORDER, corner_radius=STITCH_RADIUS)
            note.pack(fill="x", pady=(10, 0))
            ctk.CTkLabel(
                note, text=self._t('⚠  Hóa đơn đã hủy — không tính vào doanh thu.'), font=FONT_ST_BODY_STRONG, text_color=STITCH_DANGER, anchor="w"
            ).pack(fill="x", padx=10, pady=6)

    # ------------------------------------------------------------------
    def copy_invoice_code(self) -> None:
        invoice = self.selected_invoice
        if invoice is None:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(invoice.invoice_code)
        except tk.TclError:
            return
        ToastManager.show(self, CODE_COPIED, kind="success")

    def shutdown(self) -> None:
        self._closed = True


invoices_view_factory = InvoicesView
