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
from .background import TaskRunner, default_runner
from .components import ToastManager
from .components.stitch_button import stitch_button
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
ROW_HEIGHT = 40
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


def page_caption(page: Page) -> str:
    return f"Hiển thị {page.first} - {page.last} trên {page.total} hóa đơn"


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


def _configure_columns(frame: Any) -> None:
    for index, (_title, weight, _anchor) in enumerate(_COLUMNS):
        frame.grid_columnconfigure(index, weight=weight, uniform="invoice")


def _badge(master: Any, badge: Badge) -> ctk.CTkFrame:
    box = ctk.CTkFrame(master, fg_color=badge.bg, border_width=1, border_color=badge.border, corner_radius=10)
    ctk.CTkLabel(box, text=f"● {badge.label}", font=FONT_ST_MONO_XS_STRONG, text_color=badge.text_color, height=18).pack(padx=8)
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

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build_header()
        self._build_kpis()
        self._build_filter_row()
        self._build_body()
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
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="Hóa đơn", font=FONT_ST_PAGE_TITLE, text_color=STITCH_TEXT_STRONG, height=24, anchor="w").pack(anchor="w")
        ctk.CTkLabel(
            titles,
            text="Tra cứu hóa đơn của cửa hàng theo ngày, khách hàng và trạng thái",
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
            height=16,
            anchor="w",
        ).pack(anchor="w")
        store = ctk.CTkFrame(header, fg_color=STITCH_NAV_ACTIVE_BG, border_width=1, border_color=STITCH_NAV_ACTIVE_BORDER, corner_radius=STITCH_RADIUS)
        store.pack(side="left", padx=14, anchor="n", pady=(2, 0))
        ctk.CTkLabel(store, text=f"Cơ sở: {self._context.session.store_name}", font=FONT_ST_MONO_11, text_color=STITCH_CYAN, height=20).pack(padx=8)
        self._refresh_button = stitch_button(header, "⟳  Làm mới", kind="secondary", command=self.reload, width=100, height=30)
        self._refresh_button.pack(side="right")

    def _build_kpis(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        specs = (
            ("count", "SỐ HÓA ĐƠN", STITCH_TEXT_STRONG, "Theo bộ lọc hiện tại"),
            ("paid", "TỔNG TIỀN ĐÃ THANH TOÁN", STITCH_CYAN, "Chỉ hóa đơn ĐÃ THANH TOÁN"),
            ("void", "HÓA ĐƠN ĐÃ HỦY", STITCH_DANGER, "Không tính vào doanh thu"),
        )
        for index, (key, title, color, note) in enumerate(specs):
            row.grid_columnconfigure(index, weight=1, uniform="kpi")
            card = ctk.CTkFrame(row, fg_color=STITCH_CARD_BG, border_width=1, border_color=STITCH_CARD_BORDER, corner_radius=STITCH_RADIUS_LG)
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 6, 0))
            ctk.CTkLabel(card, text=title, font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED, height=16, anchor="w").pack(
                anchor="w", padx=14, pady=(10, 0)
            )
            self._kpi_labels[key] = ctk.CTkLabel(card, text="—", font=FONT_ST_KPI_VALUE, text_color=color, height=28, anchor="w")
            self._kpi_labels[key].pack(anchor="w", padx=14)
            ctk.CTkLabel(card, text=note, font=FONT_ST_MONO_11, text_color=STITCH_TEXT_DIM, height=16, anchor="w").pack(
                anchor="w", padx=14, pady=(0, 10)
            )

    def _build_filter_row(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=STITCH_BG_CHROME, border_width=1, border_color=STITCH_CARD_BORDER, corner_radius=STITCH_RADIUS_LG)
        bar.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        line = ctk.CTkFrame(bar, fg_color="transparent")
        line.pack(fill="x", padx=8, pady=(8, 0))
        ctk.CTkLabel(line, text="Từ ngày:", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(side="left")
        self._from_entry = _date_entry(line)
        self._from_entry.pack(side="left", padx=(6, 12))
        ctk.CTkLabel(line, text="Đến ngày:", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(side="left")
        self._to_entry = _date_entry(line)
        self._to_entry.pack(side="left", padx=(6, 12))
        self._search_entry = ctk.CTkEntry(
            line,
            width=260,
            height=30,
            placeholder_text="⌕  Mã hóa đơn hoặc tên khách",
            fg_color=STITCH_INPUT_BG,
            border_color=STITCH_INPUT_BORDER,
            border_width=1,
            corner_radius=STITCH_RADIUS,
            text_color=STITCH_TEXT,
            font=FONT_ST_BODY,
        )
        self._search_entry.pack(side="left")
        for entry in (self._from_entry, self._to_entry, self._search_entry):
            entry.bind("<Return>", lambda _e: self.apply_filters(), add="+")
        self._apply_button = stitch_button(line, "Áp dụng", kind="primary", command=self.apply_filters, width=80, height=30)
        self._apply_button.pack(side="left", padx=(10, 0))
        stitch_button(line, "Xóa bộ lọc", kind="ghost", command=self.clear_filters, width=90, height=30).pack(side="left", padx=(6, 0))

        second = ctk.CTkFrame(bar, fg_color="transparent")
        second.pack(fill="x", padx=8, pady=(6, 8))
        tabs = ctk.CTkFrame(second, fg_color="transparent")
        tabs.pack(side="left")
        for status, _label in _TAB_SPECS:
            button = ctk.CTkButton(
                tabs, text="", height=28, width=110, corner_radius=STITCH_RADIUS, border_width=1, font=FONT_ST_BODY,
                command=lambda s=status: self.set_status_filter(s),
            )
            button.pack(side="left", padx=(0, 6))
            self._tab_buttons[status] = button
        self._filter_error = ctk.CTkLabel(second, text="", font=FONT_ST_MONO_11, text_color=STITCH_DANGER, height=16, anchor="e")
        self._filter_error.pack(side="right")
        self._update_tabs()

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=64, uniform="split")
        body.grid_columnconfigure(1, weight=36, uniform="split")

        table = ctk.CTkFrame(body, fg_color=STITCH_CARD_BG, border_width=1, border_color=STITCH_CARD_BORDER, corner_radius=STITCH_RADIUS_LG)
        table.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        head = ctk.CTkFrame(table, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(8, 0))
        _configure_columns(head)
        for index, (title, _weight, anchor) in enumerate(_COLUMNS):
            ctk.CTkLabel(head, text=title, font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED, anchor=anchor, height=26).grid(
                row=0, column=index, sticky="ew", padx=4
            )
        ctk.CTkFrame(table, fg_color=STITCH_CARD_BORDER, height=1, corner_radius=0).pack(fill="x", padx=12)
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

        self._detail_frame = ctk.CTkFrame(body, fg_color=STITCH_CARD_BG, border_width=1, border_color=STITCH_CARD_BORDER, corner_radius=STITCH_RADIUS_LG)
        self._detail_frame.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self._render_detail()

    # ------------------------------------------------------------------
    # Lọc + tải dữ liệu
    # ------------------------------------------------------------------
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
        self._kpi_labels["count"].configure(text=f"{totals.count} đơn" if loaded else "—")
        self._kpi_labels["paid"].configure(text=format_money(totals.paid_total) if loaded else "—")
        self._kpi_labels["void"].configure(text=f"{totals.void_count} đơn" if loaded else "—")

    def _update_tabs(self) -> None:
        counts = count_by_status(self._invoices)
        loaded = self._state in (ViewState.READY, ViewState.EMPTY)
        for status, label in _TAB_SPECS:
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
            self._build_row(invoice)
        self._caption_label.configure(text=page_caption(page))
        build_pager(self._pager, page, self.go_to_page)

    def _build_row(self, invoice: InvoiceSummary) -> None:
        selected = invoice.invoice_id == self._selected_id
        void = invoice.status == InvoiceStatus.VOID
        base = ROW_SELECTED_BG if selected else "transparent"
        row = ctk.CTkFrame(self._rows_frame, fg_color=base, height=ROW_HEIGHT, corner_radius=0)
        row.pack(fill="x")
        row.grid_propagate(False)
        row.grid_rowconfigure(0, weight=1)
        _configure_columns(row)
        if selected:
            tk.Frame(row, bg=STITCH_CYAN, width=2).place(x=0, y=0, relheight=1)
        text_color = STITCH_TEXT_MUTED if void else STITCH_TEXT
        cells = [
            ctk.CTkLabel(row, text=invoice.invoice_code, font=FONT_ST_MONO_SM, text_color=STITCH_CYAN if selected else text_color),
            ctk.CTkLabel(row, text=format_datetime(invoice.created_at), font=FONT_ST_MONO_BODY, text_color=text_color),
            ctk.CTkLabel(row, text=invoice.customer_name, font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT_STRONG if selected else text_color),
            ctk.CTkLabel(row, text=invoice.employee_name, font=FONT_ST_BODY, text_color=text_color),
            ctk.CTkLabel(row, text=format_money(invoice.total_amount), font=FONT_ST_MONO_SM, text_color=STITCH_TEXT_MUTED if void else STITCH_TEXT_STRONG),
            _badge(row, invoice_badge(invoice.status)),
        ]
        for index, widget in enumerate(cells):
            widget.grid(row=0, column=index, sticky=_COLUMNS[index][2] if index != 5 else "", padx=4)
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
            ctk.CTkLabel(panel, text="Chọn một hóa đơn để xem chi tiết.", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(pady=40)
            return

        head = ctk.CTkFrame(panel, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text="CHI TIẾT HÓA ĐƠN", font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED, height=16).pack(side="left")
        _badge(head, invoice_badge(invoice.status)).pack(side="right")
        code_line = ctk.CTkFrame(panel, fg_color="transparent")
        code_line.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(code_line, text=invoice.invoice_code, font=FONT_ST_KPI_VALUE, text_color=STITCH_CYAN, height=28).pack(side="left")
        self._copy_button = stitch_button(code_line, "📋 Sao chép", kind="secondary", command=self.copy_invoice_code, width=90, height=26)
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
        info = ctk.CTkFrame(panel, fg_color=STITCH_BG_CHROME, border_width=1, border_color=STITCH_CARD_BORDER, corner_radius=STITCH_RADIUS_LG)
        info.pack(fill="x")
        rows = (
            ("Thời gian:", format_datetime(detail.invoice.created_at), STITCH_TEXT),
            ("Thu ngân:", detail.invoice.employee_name, STITCH_TEXT),
            ("Khách hàng:", f"{session.customer_name} — {session.customer_code}", STITCH_TEXT_STRONG),
            ("Mã phiên:", session.session_code, STITCH_TEXT),
            ("Máy:", f"{session.machine_code} — {session.machine_name}", STITCH_TEXT),
            ("Bắt đầu:", format_datetime(session.started_at), STITCH_TEXT),
            ("Kết thúc:", format_datetime(detail.ended_at), STITCH_TEXT),
            ("Thời lượng tính phí:", format_duration(detail.billed_minutes * 60), STITCH_TEXT),
            ("Đơn giá:", f"{format_money(session.hourly_rate)}/giờ", STITCH_TEXT),
        )
        for index, (label, value, color) in enumerate(rows):
            line = ctk.CTkFrame(info, fg_color="transparent")
            line.pack(fill="x", padx=10, pady=(8 if index == 0 else 2, 8 if index == len(rows) - 1 else 2))
            ctk.CTkLabel(line, text=label, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=18).pack(side="left")
            ctk.CTkLabel(line, text=value, font=FONT_ST_MONO_BODY, text_color=color, height=18).pack(side="right")

        money = ctk.CTkFrame(panel, fg_color="transparent")
        money.pack(fill="x", pady=(10, 0))
        inv = detail.invoice
        for label, value, color in (
            ("Chi phí sử dụng:", format_money(inv.usage_cost), STITCH_TEXT),
            ("Trong đó khách bù (tiền mặt/CK):", format_money(inv.settlement_amount), STITCH_TEXT),
        ):
            line = ctk.CTkFrame(money, fg_color="transparent")
            line.pack(fill="x", pady=2)
            ctk.CTkLabel(line, text=label, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=18).pack(side="left")
            ctk.CTkLabel(line, text=value, font=FONT_ST_MONO_SM, text_color=color, height=18).pack(side="right")
        ctk.CTkFrame(money, fg_color=STITCH_CARD_BORDER, height=1, corner_radius=0).pack(fill="x", pady=(6, 6))
        total = ctk.CTkFrame(money, fg_color="transparent")
        total.pack(fill="x")
        ctk.CTkLabel(total, text="Tổng tiền hóa đơn:", font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT_STRONG, height=22).pack(side="left")
        self._total_label = ctk.CTkLabel(
            total, text=format_money(inv.total_amount), font=FONT_ST_KPI_VALUE, text_color=STITCH_DANGER if inv.status == InvoiceStatus.VOID else STITCH_SUCCESS, height=26
        )
        self._total_label.pack(side="right")
        if inv.status == InvoiceStatus.VOID:
            note = ctk.CTkFrame(panel, fg_color=STITCH_BADGE_DANGER_BG, border_width=1, border_color=STITCH_BADGE_DANGER_BORDER, corner_radius=STITCH_RADIUS)
            note.pack(fill="x", pady=(10, 0))
            ctk.CTkLabel(
                note, text="⚠  Hóa đơn đã hủy — không tính vào doanh thu.", font=FONT_ST_BODY_STRONG, text_color=STITCH_DANGER, anchor="w"
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
