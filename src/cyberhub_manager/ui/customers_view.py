"""NG-04 — Màn Khách hàng theo Stitch `kh_ch_h_ng_unified_app_shell`.

- Header + nút "Tạo khách hàng"; hàng lọc: ô tìm kiếm + tab Tất cả / Hoạt động / Ngừng hoạt động.
- Trái (65%): bảng khách phân trang, chọn dòng để xem chi tiết; số dư âm đỏ, dương xanh (CUS-04).
- Phải (35%): chi tiết khách, số dư hiện tại, nút Nạp tiền / Chỉnh sửa / Khóa, giao dịch gần đây.
- Nút Khóa / Mở khóa chỉ hiện với MANAGER/ADMIN; service vẫn kiểm tra quyền (LI-03).
- Không có "Hội viên VIP" / ngày đăng ký như Stitch: ngoài phạm vi P0 và DTO không có dữ liệu.
- UI không tự tính tiền: chỉ hiển thị số dư và giao dịch service trả về.
- Nút mở dialog: Tạo/Sửa (customer_dialog), Nạp tiền (topup_dialog), Khóa/Mở khóa (customer_lock_dialog);
  lưu xong tải lại danh sách và giữ khách vừa thao tác được chọn.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import customtkinter as ctk

from ..domain.dtos import CustomerSummary, TopUpResult, TransactionSummary
from ..domain.enums import AccountStatus, CustomerStatus, PaymentMethod, TransactionType
from ..domain.models import Customer
from .app_shell import ViewContext, initials
from .i18n import UIStrings
from .background import TaskRunner, default_runner
from .components.action_button import ActionButton
from .components.stitch_button import stitch_button
from .dialogs.customer_dialog import CustomerDialog
from .dialogs.customer_lock_dialog import CustomerLockDialog
from .dialogs.topup_dialog import TopUpDialog
from .feedback import notify_success
from .formatters import format_datetime, format_money
from .messages import MSG_LOADING, MSG_NO_DATA, MSG_RETRY, get_user_friendly_error
from .navigation import MANAGEMENT_ROLES
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
    STITCH_AVATAR_BG,
    STITCH_BADGE_DANGER_BG,
    STITCH_BADGE_DANGER_BORDER,
    STITCH_BADGE_SUCCESS_BG,
    STITCH_BADGE_SUCCESS_BORDER,
    STITCH_BADGE_WARNING_BG,
    STITCH_BADGE_WARNING_BORDER,
    STITCH_BG_CHROME,
    STITCH_CARD_BG,
    STITCH_CARD_BORDER,
    STITCH_CHIP_BG,
    STITCH_CHIP_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_INPUT_BG,
    STITCH_INPUT_BORDER,
    STITCH_KPI_SUCCESS_CARD_BG,
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
    STITCH_WARNING,
)

PAGE_SIZE = 10
RECENT_TRANSACTIONS = 4
ROW_HEIGHT = 40

ROW_SELECTED_BG = "#10293A"  # cyan 10% trên STITCH_CARD_BG (Stitch: bg-[#00c6ff]/10)
NEUTRAL_BADGE = ("#1A2130", "#2B3648")  # slate-800/80, viền slate-700/60
NEGATIVE_CARD_BG = "#1C1520"  # rose-950/20 trên STITCH_CARD_BG

TRANSACTION_LABELS = {
    TransactionType.TOP_UP: "Nạp tiền",
    TransactionType.USAGE_PAYMENT: "Thanh toán phiên",
    TransactionType.DEBT_SETTLEMENT: "Bù nợ",
    TransactionType.PROMOTION: "Khuyến mãi",
}
METHOD_LABELS = {
    PaymentMethod.CASH: "Tiền mặt",
    PaymentMethod.TRANSFER: "Chuyển khoản",
    PaymentMethod.ACCOUNT_BALANCE: "Số dư tài khoản",
    PaymentMethod.PROMOTION: "Khuyến mãi",
}


# ----------------------------------------------------------------------
# Hàm thuần (test được không cần Tk)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Badge:
    label: str
    text_color: str
    bg: str
    border: str


def filter_customers(
    customers: Iterable[CustomerSummary],
    status: CustomerStatus | None = None,
    keyword: str = "",
) -> list[CustomerSummary]:
    """Lọc theo trạng thái khách và từ khóa (mã KH, họ tên, SĐT, tên đăng nhập — CUS-02)."""
    needle = keyword.strip().casefold()
    result: list[CustomerSummary] = []
    for customer in customers:
        if status is not None and customer.customer_status != status:
            continue
        haystack = (customer.customer_code, customer.full_name, customer.phone, customer.username)
        if needle and not any(needle in value.casefold() for value in haystack):
            continue
        result.append(customer)
    return result


def count_by_status(customers: Iterable[CustomerSummary]) -> dict[CustomerStatus | None, int]:
    customers = list(customers)
    counts: dict[CustomerStatus | None, int] = {None: len(customers)}
    for status in CustomerStatus:
        counts[status] = sum(1 for c in customers if c.customer_status == status)
    return counts


def balance_color(amount: int) -> str:
    """Số dư âm đỏ (CUS-04), dương xanh, bằng 0 xám — như Stitch."""
    if amount < 0:
        return STITCH_DANGER
    if amount > 0:
        return STITCH_SUCCESS
    return STITCH_TEXT_MUTED


def customer_badge(status: CustomerStatus) -> Badge:
    if status == CustomerStatus.ACTIVE:
        return Badge("Hoạt động", STITCH_SUCCESS, STITCH_BADGE_SUCCESS_BG, STITCH_BADGE_SUCCESS_BORDER)
    return Badge("Ngừng hoạt động", STITCH_TEXT_MUTED, *NEUTRAL_BADGE)


def account_badge(status: AccountStatus) -> Badge:
    if status == AccountStatus.ACTIVE:
        return Badge("Hoạt động", STITCH_SUCCESS, STITCH_BADGE_SUCCESS_BG, STITCH_BADGE_SUCCESS_BORDER)
    return Badge("Đã khóa", STITCH_DANGER, STITCH_BADGE_DANGER_BG, STITCH_BADGE_DANGER_BORDER)


def row_badge(customer: CustomerSummary) -> Badge:
    """Cột Trạng thái của bảng: theo khách; khách hoạt động nhưng tài khoản bị khóa thì cảnh báo vàng."""
    if customer.customer_status == CustomerStatus.ACTIVE and customer.account_status == AccountStatus.LOCKED:
        return Badge("TK đã khóa", STITCH_WARNING, STITCH_BADGE_WARNING_BG, STITCH_BADGE_WARNING_BORDER)
    return customer_badge(customer.customer_status)


@dataclass(frozen=True)
class TransactionLine:
    amount: str
    color: str
    description: str
    time: str


def transaction_line(transaction: TransactionSummary, language: str = "vi") -> TransactionLine:
    """Một dòng "Giao dịch gần đây": +50.000 VND / Nạp tiền • Tiền mặt / 14:30 24/02 (giờ VN)."""
    amount = transaction.amount
    text = f"+{format_money(amount, language)}" if amount > 0 else format_money(amount, language)
    color = STITCH_SUCCESS if amount > 0 else STITCH_DANGER
    copy = UIStrings(language)
    kind = copy(TRANSACTION_LABELS.get(transaction.type, str(transaction.type)))
    method = copy(METHOD_LABELS.get(transaction.method, str(transaction.method)))
    stamp = format_datetime(transaction.created_at)  # "HH:MM dd/mm/yyyy"
    return TransactionLine(text, color, f"{kind} • {method}", stamp[:-5])


def page_caption(page: Page, language: str = "vi") -> str:
    return UIStrings(language)("Hiển thị {v0} - {v1} trên {v2} khách hàng", v0=page.first, v1=page.last, v2=page.total)


# ----------------------------------------------------------------------
# Cấu hình bảng
# ----------------------------------------------------------------------
# (status, nhãn)
_TAB_SPECS: tuple[tuple[CustomerStatus | None, str], ...] = (
    (None, "Tất cả"),
    (CustomerStatus.ACTIVE, "Hoạt động"),
    (CustomerStatus.INACTIVE, "Ngừng hoạt động"),
)
# (tiêu đề, tỉ lệ độ rộng, căn lề)
_COLUMNS = (
    ("MÃ KH", 3, "w"),
    ("HỌ VÀ TÊN", 6, "w"),
    ("SỐ ĐIỆN THOẠI", 5, "w"),
    ("TÊN ĐĂNG NHẬP", 5, "w"),
    ("SỐ DƯ", 5, "e"),
    ("TRẠNG THÁI", 6, "center"),
)


def _configure_columns(frame: Any) -> None:
    for index, (_title, weight, _anchor) in enumerate(_COLUMNS):
        frame.grid_columnconfigure(index, weight=weight, uniform="customer")


def _badge(master: Any, badge: Badge, *, pill: bool = True, language: str = "vi") -> ctk.CTkFrame:
    box = ctk.CTkFrame(
        master, fg_color=badge.bg, border_width=1, border_color=badge.border, corner_radius=10 if pill else STITCH_RADIUS
    )
    ctk.CTkLabel(box, text=f"● {UIStrings(language)(badge.label)}", font=FONT_ST_MONO_XS_STRONG, text_color=badge.text_color, height=18).pack(
        padx=8
    )
    return box


class CustomersView(ctk.CTkFrame):
    """Màn Khách hàng: bảng bên trái, chi tiết + giao dịch gần đây bên phải."""

    def __init__(self, master: Any, context: ViewContext, *, runner: TaskRunner | None = None) -> None:
        super().__init__(master, fg_color="transparent")
        self._context = context
        self._t = UIStrings(context.language)
        self._runner = runner or default_runner()
        self._customers: list[CustomerSummary] = []
        self._status_filter: CustomerStatus | None = None
        self._keyword = ""
        self._page = 1
        self._selected_id: int | None = None
        self._state = ViewState.LOADING
        self._closed = False
        self._detail_request = 0
        self._history: list[TransactionSummary] = []
        self._account_code = ""
        self._tab_buttons: dict[CustomerStatus | None, ctk.CTkButton] = {}
        self._action_buttons: dict[str, ActionButton] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build_header()
        self._build_filter_row()
        self._build_body()
        self.reload()

    # ------------------------------------------------------------------
    # Thuộc tính công khai (test)
    # ------------------------------------------------------------------
    @property
    def state(self) -> ViewState:
        return self._state

    @property
    def customers(self) -> list[CustomerSummary]:
        return list(self._customers)

    @property
    def can_manage(self) -> bool:
        return self._context.session.role in MANAGEMENT_ROLES

    @property
    def current_page(self) -> Page:
        return paginate(filter_customers(self._customers, self._status_filter, self._keyword), self._page, PAGE_SIZE)

    @property
    def visible_customer_ids(self) -> list[int]:
        return [c.customer_id for c in self.current_page.items]

    @property
    def selected_customer(self) -> CustomerSummary | None:
        return next((c for c in self._customers if c.customer_id == self._selected_id), None)

    @property
    def history(self) -> list[TransactionSummary]:
        return list(self._history)

    @property
    def action_buttons(self) -> dict[str, ActionButton]:
        """"top_up" / "edit" / "lock" (lock chỉ có với MANAGER/ADMIN)."""
        return dict(self._action_buttons)

    # ------------------------------------------------------------------
    # Dựng giao diện
    # ------------------------------------------------------------------
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(
            titles, text=self._t('Khách hàng'), font=FONT_ST_PAGE_TITLE, text_color=STITCH_TEXT_STRONG, height=24, anchor="w"
        ).pack(anchor="w")
        ctk.CTkLabel(
            titles,
            text=self._t('Quản lý hồ sơ, tài khoản và số dư khách hàng'),
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
            height=16,
            anchor="w",
        ).pack(anchor="w")
        self._create_button = stitch_button(
            header, self._t('＋  Tạo khách hàng'), kind="primary", command=self._open_create, width=150, height=32
        )
        self._create_button.pack(side="right")

    def _build_filter_row(self) -> None:
        bar = ctk.CTkFrame(
            self, fg_color=STITCH_BG_CHROME, border_width=1, border_color=STITCH_CARD_BORDER, corner_radius=STITCH_RADIUS_LG
        )
        bar.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self._search_entry = ctk.CTkEntry(
            bar,
            width=420,
            height=32,
            placeholder_text=self._t('⌕  Tìm theo mã, tên, SĐT hoặc tên đăng nhập'),
            fg_color=STITCH_INPUT_BG,
            border_color=STITCH_INPUT_BORDER,
            border_width=1,
            corner_radius=STITCH_RADIUS,
            text_color=STITCH_TEXT,
            font=FONT_ST_BODY,
        )
        self._search_entry.pack(side="left", padx=8, pady=8)
        self._search_entry.bind("<KeyRelease>", lambda _e: self._apply_search(self._search_entry.get()))
        tabs = ctk.CTkFrame(bar, fg_color="transparent")
        tabs.pack(side="right", padx=8)
        for status, _label in _TAB_SPECS:
            button = ctk.CTkButton(
                tabs,
                text="",
                height=28,
                width=90,
                corner_radius=STITCH_RADIUS,
                border_width=1,
                font=FONT_ST_BODY,
                command=lambda s=status: self.set_status_filter(s),
            )
            button.pack(side="left", padx=(6, 0))
            self._tab_buttons[status] = button
        self._update_tabs()

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=65, uniform="split")
        body.grid_columnconfigure(1, weight=35, uniform="split")

        # Trái: bảng
        table = ctk.CTkFrame(
            body, fg_color=STITCH_CARD_BG, border_width=1, border_color=STITCH_CARD_BORDER, corner_radius=STITCH_RADIUS_LG
        )
        table.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        head = ctk.CTkFrame(table, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(8, 0))
        _configure_columns(head)
        for index, (title, _weight, anchor) in enumerate(_COLUMNS):
            ctk.CTkLabel(head, text=self._t(title), font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED, anchor=anchor, height=26).grid(
                row=0, column=index, sticky="ew", padx=4
            )
        ctk.CTkFrame(table, fg_color=STITCH_CARD_BORDER, height=1, corner_radius=0).pack(fill="x", padx=12)
        self._rows_frame = ctk.CTkFrame(table, fg_color="transparent")
        self._rows_frame.pack(fill="both", expand=True, padx=12)
        self._state_frame = ctk.CTkFrame(table, fg_color="transparent")
        self._state_label = ctk.CTkLabel(self._state_frame, text="", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED)
        self._state_label.pack(pady=(40, 10))
        self._retry_button = stitch_button(self._state_frame, MSG_RETRY, command=self.reload, width=100)

        footer = ctk.CTkFrame(table, fg_color="transparent")
        footer.pack(fill="x", side="bottom", padx=12, pady=(0, 8))
        ctk.CTkFrame(footer, fg_color=STITCH_CARD_BORDER, height=1, corner_radius=0).pack(fill="x", pady=(0, 8))
        self._caption_label = ctk.CTkLabel(footer, text="", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED)
        self._caption_label.pack(side="left")
        self._pager = ctk.CTkFrame(footer, fg_color="transparent")
        self._pager.pack(side="right")

        # Phải: chi tiết
        self._detail = ctk.CTkFrame(
            body, fg_color=STITCH_CARD_BG, border_width=1, border_color=STITCH_CARD_BORDER, corner_radius=STITCH_RADIUS_LG
        )
        self._detail.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self._render_detail()

    # ------------------------------------------------------------------
    # Tải dữ liệu
    # ------------------------------------------------------------------
    def reload(self, select_id: int | None = None) -> None:
        """Tải lại danh sách; giữ (hoặc chuyển sang) khách `select_id` nếu có."""
        if self._closed:
            return
        if select_id is not None:
            self._selected_id = select_id
        if not self._customers:
            self._show_state(ViewState.LOADING, MSG_LOADING)
        services = self._context.services
        self._runner.submit(self, lambda: services.customers.search_customers(""), self._on_loaded, self._on_load_failed)

    def _on_loaded(self, customers: list[CustomerSummary]) -> None:
        if self._closed:
            return
        self._customers = list(customers)
        self._state = ViewState.READY
        if self.selected_customer is None:
            first = filter_customers(self._customers, self._status_filter, self._keyword)
            self._selected_id = first[0].customer_id if first else None
        self._render()
        self._load_detail()

    def _on_load_failed(self, error: Exception) -> None:
        if self._closed:
            return
        self._customers = []
        self._selected_id = None
        self._update_tabs()
        self._show_state(ViewState.ERROR, get_user_friendly_error(error))
        self._render_detail()

    def _load_detail(self) -> None:
        """Lịch sử giao dịch + mã tài khoản của khách đang chọn (chạy nền)."""
        customer = self.selected_customer
        self._history = []
        self._account_code = ""
        self._detail_request += 1
        request = self._detail_request
        self._render_detail(loading=customer is not None)
        if customer is None:
            return
        services = self._context.services

        def call() -> tuple[str, list[TransactionSummary]]:
            account = services.customers.get_customer(customer.customer_id).account
            return account.code, services.wallet.get_history(customer.customer_id)

        def done(result: tuple[str, list[TransactionSummary]]) -> None:
            if self._closed or request != self._detail_request:
                return  # người dùng đã chọn khách khác
            self._account_code, self._history = result[0], list(result[1])
            self._render_detail()

        def failed(error: Exception) -> None:
            if self._closed or request != self._detail_request:
                return
            self._render_detail(error=get_user_friendly_error(error))

        self._runner.submit(self, call, done, failed)

    # ------------------------------------------------------------------
    # Lọc / tìm kiếm / chọn / phân trang
    # ------------------------------------------------------------------
    def set_status_filter(self, status: CustomerStatus | None) -> None:
        self._status_filter = status
        self._page = 1
        self._render()

    def handle_search(self, text: str) -> None:
        """Nhận từ khóa từ ô tìm kiếm trên topbar (NG-02); đồng bộ vào ô tìm kiếm của màn."""
        self._search_entry.delete(0, "end")
        if text:
            self._search_entry.insert(0, text)
        self._apply_search(text)

    def _apply_search(self, text: str) -> None:
        self._keyword = text
        self._page = 1
        self._render()

    def go_to_page(self, number: int) -> None:
        self._page = number
        self._render()

    def select(self, customer_id: int) -> None:
        if customer_id == self._selected_id:
            return
        self._selected_id = customer_id
        self._render()
        self._load_detail()

    # ------------------------------------------------------------------
    # Vẽ bảng
    # ------------------------------------------------------------------
    def _render(self) -> None:
        self._update_tabs()
        if not self._customers and self._state != ViewState.READY:
            return
        page = self.current_page
        self._page = page.number
        for child in self._rows_frame.winfo_children():
            child.destroy()
        if not page.items:
            self._show_state(ViewState.EMPTY, MSG_NO_DATA)
            return
        self._state = ViewState.READY
        self._state_frame.pack_forget()
        self._rows_frame.pack(fill="both", expand=True, padx=12)
        for index, customer in enumerate(page.items):
            if index:
                ctk.CTkFrame(self._rows_frame, fg_color=STITCH_CARD_BORDER, height=1, corner_radius=0).pack(fill="x")
            self._build_row(customer)
        self._caption_label.configure(text=page_caption(page, language=self._t.language))
        build_pager(self._pager, page, self.go_to_page)

    def _build_row(self, customer: CustomerSummary) -> None:
        selected = customer.customer_id == self._selected_id
        inactive = customer.customer_status == CustomerStatus.INACTIVE
        base = ROW_SELECTED_BG if selected else "transparent"
        row = ctk.CTkFrame(self._rows_frame, fg_color=base, height=ROW_HEIGHT, corner_radius=0)
        row.pack(fill="x")
        row.grid_propagate(False)
        row.grid_rowconfigure(0, weight=1)
        _configure_columns(row)
        if selected:  # vạch cyan bên trái dòng đang chọn
            tk.Frame(row, bg=STITCH_CYAN, width=2).place(x=0, y=0, relheight=1)

        text_color = STITCH_TEXT_MUTED if inactive else STITCH_TEXT
        cells = [
            ctk.CTkLabel(
                row,
                text=customer.customer_code,
                font=FONT_ST_MONO_SM if selected else FONT_ST_MONO_BODY,
                text_color=STITCH_CYAN if selected else text_color,
            ),
            ctk.CTkLabel(
                row,
                text=customer.full_name,
                font=FONT_ST_BODY_STRONG,
                text_color=STITCH_TEXT_STRONG if selected else (STITCH_TEXT_MUTED if inactive else STITCH_TEXT),
            ),
            ctk.CTkLabel(row, text=customer.phone, font=FONT_ST_MONO_BODY, text_color=text_color),
            ctk.CTkLabel(row, text=customer.username, font=FONT_ST_MONO_BODY, text_color=text_color),
            ctk.CTkLabel(
                row,
                text=format_money(customer.balance, language=self._t.language),
                font=FONT_ST_MONO_SM,
                # CUS-04: số dư âm luôn đỏ; khách ngừng hoạt động còn lại hiện xám như Stitch
                text_color=STITCH_TEXT_MUTED if inactive and customer.balance >= 0 else balance_color(customer.balance),
            ),
            _badge(row, row_badge(customer), language=self._t.language),
        ]
        for index, widget in enumerate(cells):
            widget.grid(row=0, column=index, sticky=_COLUMNS[index][2] if index != 5 else "", padx=4)

        bind_hover(row, base_color=base, hover_color=ROW_SELECTED_BG if selected else STITCH_TAB_HOVER)
        self._bind_click(row, customer.customer_id)

    def _bind_click(self, widget: Any, customer_id: int) -> None:
        widget.bind("<Button-1>", lambda _e: self.select(customer_id), add="+")
        for child in widget.winfo_children():
            self._bind_click(child, customer_id)

    def _update_tabs(self) -> None:
        counts = count_by_status(self._customers)
        for status, label in _TAB_SPECS:
            label = self._t(label)
            active = status == self._status_filter
            self._tab_buttons[status].configure(
                text=f"{label} ({counts[status]})" if self._customers else label,
                fg_color=STITCH_NAV_ACTIVE_BG if active else STITCH_INPUT_BG,
                hover_color=STITCH_NAV_ACTIVE_BG if active else STITCH_CHIP_BG,
                border_color=STITCH_NAV_ACTIVE_BORDER if active else STITCH_CHIP_BORDER,
                text_color=STITCH_CYAN if active else STITCH_TEXT_MUTED,
                font=FONT_ST_BODY_STRONG if active else FONT_ST_BODY,
            )

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

    # ------------------------------------------------------------------
    # Vẽ chi tiết
    # ------------------------------------------------------------------
    def _render_detail(self, *, loading: bool = False, error: str | None = None) -> None:
        for child in self._detail.winfo_children():
            child.destroy()
        self._action_buttons = {}
        customer = self.selected_customer
        panel = ctk.CTkFrame(self._detail, fg_color="transparent")
        panel.pack(fill="both", expand=True, padx=14, pady=12)
        if customer is None:
            ctk.CTkLabel(panel, text=self._t('Chọn một khách hàng để xem chi tiết.'), font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(
                pady=40
            )
            return

        # Header: avatar + tên + mã
        head = ctk.CTkFrame(panel, fg_color="transparent")
        head.pack(fill="x")
        avatar = ctk.CTkFrame(head, width=36, height=36, corner_radius=18, fg_color=STITCH_AVATAR_BG, border_width=1, border_color=STITCH_CHIP_BORDER)
        avatar.pack(side="left")
        avatar.pack_propagate(False)
        ctk.CTkLabel(avatar, text=initials(customer.full_name), font=FONT_ST_BODY_STRONG, text_color=STITCH_CYAN).pack(expand=True)
        names = ctk.CTkFrame(head, fg_color="transparent")
        names.pack(side="left", padx=10)
        ctk.CTkLabel(names, text=customer.full_name, font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT_STRONG, height=18, anchor="w").pack(anchor="w")
        ctk.CTkLabel(
            names,
            text=self._t('Mã TK: {v0}', v0=f'{self._account_code}') if self._account_code else self._t('Mã TK: …'),
            font=FONT_ST_MONO_11,
            text_color=STITCH_TEXT_MUTED,
            height=14,
            anchor="w",
        ).pack(anchor="w")
        code = ctk.CTkFrame(head, fg_color=STITCH_CHIP_BG, border_width=1, border_color=STITCH_CHIP_BORDER, corner_radius=STITCH_RADIUS)
        code.pack(side="right")
        ctk.CTkLabel(code, text=customer.customer_code, font=FONT_ST_MONO_SM, text_color=STITCH_CYAN, height=20).pack(padx=8)
        ctk.CTkFrame(panel, fg_color=STITCH_CARD_BORDER, height=1, corner_radius=0).pack(fill="x", pady=(10, 10))

        # Thông tin tài khoản
        info = ctk.CTkFrame(panel, fg_color=STITCH_BG_CHROME, border_width=1, border_color=STITCH_CARD_BORDER, corner_radius=STITCH_RADIUS_LG)
        info.pack(fill="x")
        rows: list[tuple[str, Any]] = [
            (self._t('Số điện thoại:'), customer.phone),
            (self._t('Tên đăng nhập:'), customer.username),
            (self._t('Trạng thái khách hàng:'), customer_badge(customer.customer_status)),
            (self._t('Trạng thái tài khoản:'), account_badge(customer.account_status)),
        ]
        for index, (label, value) in enumerate(rows):
            line = ctk.CTkFrame(info, fg_color="transparent")
            line.pack(fill="x", padx=10, pady=(8 if index == 0 else 3, 8 if index == len(rows) - 1 else 3))
            ctk.CTkLabel(line, text=label, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=20).pack(side="left")
            if isinstance(value, Badge):
                _badge(line, value, pill=False, language=self._t.language).pack(side="right")
            else:
                ctk.CTkLabel(line, text=value, font=FONT_ST_MONO_BODY, text_color=STITCH_TEXT, height=20).pack(side="right")

        # Số dư
        negative = customer.balance < 0
        card = ctk.CTkFrame(
            panel,
            fg_color=NEGATIVE_CARD_BG if negative else STITCH_KPI_SUCCESS_CARD_BG,
            border_width=1,
            border_color=STITCH_BADGE_DANGER_BORDER if negative else STITCH_BADGE_SUCCESS_BORDER,
            corner_radius=STITCH_RADIUS_LG,
        )
        card.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(card, text=self._t('SỐ DƯ HIỆN TẠI'), font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED, height=14, anchor="w").pack(
            anchor="w", padx=12, pady=(8, 0)
        )
        self._balance_label = ctk.CTkLabel(
            card, text=format_money(customer.balance, language=self._t.language), font=FONT_ST_KPI_VALUE, text_color=balance_color(customer.balance), height=28, anchor="w"
        )
        self._balance_label.pack(anchor="w", padx=12, pady=(0, 8))
        for label,value in ((self._t("Số dư chính"),customer.cash_balance),(self._t("Số dư khuyến mãi"),customer.bonus_balance)):
            line = ctk.CTkFrame(card,fg_color="transparent")
            line.pack(fill="x",padx=12,pady=(0,6))
            ctk.CTkLabel(line,text=label,font=FONT_ST_BODY,text_color=STITCH_TEXT_MUTED).pack(side="left")
            ctk.CTkLabel(line,text=format_money(value,language=self._t.language),font=FONT_ST_BODY,text_color=STITCH_CYAN).pack(side="right")

        # Nút thao tác
        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.pack(fill="x", pady=(10, 0))
        specs = [("top_up", self._t('＋ Nạp tiền'), "primary", self._open_top_up), ("edit", self._t('✎ Chỉnh sửa'), "secondary", self._open_edit)]
        if self.can_manage:  # NG-04: STAFF không có action khóa
            locked = customer.customer_status == CustomerStatus.INACTIVE
            specs.append(("lock", self._t('Mở khóa') if locked else self._t('Khóa'), "secondary" if locked else "danger", self._open_lock))
        for index, (key, text, kind, command) in enumerate(specs):
            actions.grid_columnconfigure(index, weight=1, uniform="action")
            button = stitch_button(actions, text, kind=kind, command=command, width=10, height=30)
            button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 4, 0))
            self._action_buttons[key] = button

        # Giao dịch gần đây
        ctk.CTkFrame(panel, fg_color=STITCH_CARD_BORDER, height=1, corner_radius=0).pack(fill="x", pady=(12, 8))
        title = ctk.CTkFrame(panel, fg_color="transparent")
        title.pack(fill="x")
        ctk.CTkLabel(title, text=self._t('Giao dịch gần đây'), font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT, height=18).pack(side="left")
        count_text = "" if loading or error else self._t('{v0} giao dịch', v0=f'{len(self._history)}')
        ctk.CTkLabel(title, text=count_text, font=FONT_ST_MONO_11, text_color=STITCH_TEXT_DIM, height=18).pack(side="right")
        if loading:
            ctk.CTkLabel(panel, text=MSG_LOADING, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(pady=12)
            return
        if error:
            ctk.CTkLabel(panel, text=error, font=FONT_ST_BODY, text_color=STITCH_DANGER, wraplength=280).pack(pady=12)
            return
        if not self._history:
            ctk.CTkLabel(panel, text=self._t('Chưa có giao dịch'), font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(pady=12)
            return
        for transaction in self._history[:RECENT_TRANSACTIONS]:
            line = transaction_line(transaction, language=self._t.language)
            item = ctk.CTkFrame(panel, fg_color=STITCH_BG_CHROME, border_width=1, border_color=STITCH_CARD_BORDER, corner_radius=STITCH_RADIUS)
            item.pack(fill="x", pady=(6, 0))
            left = ctk.CTkFrame(item, fg_color="transparent")
            left.pack(side="left", padx=8, pady=4)
            ctk.CTkLabel(left, text=line.amount, font=FONT_ST_MONO_SM, text_color=line.color, height=16, anchor="w").pack(anchor="w")
            ctk.CTkLabel(left, text=line.description, font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED, height=14, anchor="w").pack(anchor="w")
            ctk.CTkLabel(item, text=line.time, font=FONT_ST_MONO_11, text_color=STITCH_TEXT_DIM).pack(side="right", padx=8)

    # ------------------------------------------------------------------
    # Hành động: mở dialog NG-04 (tạo/sửa, nạp tiền, khóa/mở khóa)
    # ------------------------------------------------------------------
    def _open_create(self) -> None:
        CustomerDialog(self.winfo_toplevel(), self._context, runner=self._runner, on_saved=self._after_created)

    def _after_created(self, customer: Customer) -> None:
        notify_success(self, "Customer created.")
        self.reload(select_id=customer.id)

    def _open_edit(self) -> None:
        customer = self.selected_customer
        if customer is None:
            return
        CustomerDialog(
            self.winfo_toplevel(),
            self._context,
            customer=customer,
            account_code=self._account_code,
            runner=self._runner,
            on_saved=self._after_updated,
        )

    def _after_updated(self, customer: Customer) -> None:
        notify_success(self, "Customer updated.")
        self.reload(select_id=customer.id)

    def _open_top_up(self) -> None:
        customer = self.selected_customer
        if customer is None:
            return
        TopUpDialog(
            self.winfo_toplevel(),
            self._context,
            customer,
            account_code=self._account_code,
            runner=self._runner,
            on_success=self._after_top_up,
        )

    def _after_top_up(self, result: TopUpResult) -> None:
        notify_success(self, f"Top-up successful. New balance: {format_money(result.balance_after, language=self._t.language)}")
        self.reload(select_id=result.customer_id)

    def _open_lock(self) -> None:
        customer = self.selected_customer
        if customer is None or not self.can_manage:
            return
        CustomerLockDialog(
            self.winfo_toplevel(),
            self._context,
            customer,
            account_code=self._account_code,
            runner=self._runner,
            on_done=self._after_status_changed,
        )

    def _after_status_changed(self, customer: Customer) -> None:
        locked = customer.status == CustomerStatus.INACTIVE
        notify_success(self, "Customer locked." if locked else "Customer unlocked.")
        self.reload(select_id=customer.id)

    def shutdown(self) -> None:
        """App Shell gọi trước khi hủy view: bỏ qua kết quả tải về sau đó."""
        self._closed = True


customers_view_factory = CustomersView
