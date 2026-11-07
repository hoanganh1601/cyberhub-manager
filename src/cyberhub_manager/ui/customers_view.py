"""Customers View — Màn hình quản lý khách hàng và ví tiền theo thiết kế Google Stitch.

Tuân thủ thiết kế Stitch:
- Tham chiếu: docs/ui-reference/cyberhub_manager_kh_ch_h_ng_v_ti_n_1280x720/code.html
- Layout 65% Bảng dữ liệu + 35% Panel chi tiết khách hàng đang chọn.
- Tìm kiếm tức thì, lọc trạng thái hoạt động/ngừng hoạt động với số đếm trực quan.
- Bảng hiển thị họ tên, mã KH cyan, số dư có màu trạng thái, badge trạng thái bo góc.
- Panel chi tiết: Profile Header, Sunken Metadata Grid, Glowing HUD Balance Card,
  3 nút chức năng ngang (+ Nạp tiền, Chỉnh sửa, Khóa/Mở khóa), và Lịch sử giao dịch gần đây.
- Nạp tiền (TopUpDialog), Tạo mới & Chỉnh sửa (CustomerDialog), Khóa/Mở khóa (CustomerLockDialog).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from ..domain.dtos import CustomerSummary, TransactionSummary
from ..domain.enums import CustomerStatus, Role, TransactionType
from ..domain.exceptions import ApplicationError
from .components import (
    ActionButton,
    DataTable,
    RecentTransactionsLedger,
    TableColumn,
    TableRow,
    ToastManager,
    WalletHudCard,
)
from .dialogs.customer_dialog import CustomerDialog
from .dialogs.customer_lock_dialog import CustomerLockDialog
from .dialogs.topup_dialog import TopUpDialog
from .formatters import format_money, initials
from .icons import get_icon
from .messages import MSG_OPERATION_FAILED, get_user_friendly_error
from .state import ViewState
from .theme import (
    FONT_FAMILY,
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_METRIC_LG,
    FONT_ST_METRIC_XL,
    FONT_ST_MONO_BODY,
    FONT_ST_MONO_SM,
    FONT_ST_MONO_XS,
    FONT_ST_MONO_XS_STRONG,
    FONT_ST_PAGE_TITLE,
    STITCH_AVATAR_BG,
    STITCH_BORDER,
    STITCH_CARD_BG,
    STITCH_CARD_BORDER,
    STITCH_CHIP_BG,
    STITCH_CHIP_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_DANGER_HOVER_BG,
    STITCH_EMERALD,
    STITCH_INPUT_BG,
    STITCH_INPUT_BORDER,
    STITCH_NAV_ACTIVE_BG,
    STITCH_NAV_ACTIVE_BORDER,
    STITCH_RADIUS,
    STITCH_RADIUS_LG,
    STITCH_ROSE,
    STITCH_SUCCESS,
    STITCH_SUNKEN_BG,
    STITCH_SUNKEN_BORDER,
    STITCH_TEXT,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_ON_CYAN,
    STITCH_TEXT_STRONG,
    STITCH_WARNING,
)

if TYPE_CHECKING:
    from .app_shell import ViewContext

logger = logging.getLogger(__name__)


class CustomersView(ctk.CTkFrame):
    """Màn hình Quản lý Khách hàng chuẩn Google Stitch."""

    def __init__(self, master: Any, context: ViewContext) -> None:
        super().__init__(master, fg_color="transparent")
        self._context = context
        self._language = context.language
        self._actor = context.session
        self._services = context.services

        self._all_customers: list[CustomerSummary] = []
        self._filtered_customers: list[CustomerSummary] = []
        self._selected_customer: CustomerSummary | None = None
        self._current_filter: str = "all"
        self._search_keyword: str = ""

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        is_vi = self._language == "vi"

        # ------------------------------------------------------------------
        # 1. TOP HEADER ROW (PAGE ACTION HEADER)
        # ------------------------------------------------------------------
        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 8))

        title_box = ctk.CTkFrame(header_row, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box,
            text="Khách hàng" if is_vi else "Customers",
            font=FONT_ST_PAGE_TITLE,
            text_color=STITCH_TEXT_STRONG,
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Quản lý hồ sơ, tài khoản và số dư khách hàng" if is_vi else "Manage customer profiles, accounts and balances",
            font=FONT_ST_MONO_SM,
            text_color=STITCH_TEXT_MUTED,
        ).pack(anchor="w", pady=(1, 0))

        # Nút + Tạo khách hàng (Cyan primary button with add vector icon)
        self._create_btn = ActionButton(
            header_row,
            text="+ Tạo khách hàng" if is_vi else "+ Create Customer",
            kind="primary",
            width=150,
            height=32,
            image=get_icon("add", STITCH_TEXT_ON_CYAN, size=(14, 14)),
            command=self._handle_create_customer,
        )
        self._create_btn.pack(side="right")

        # ------------------------------------------------------------------
        # 2. FILTER & SEARCH BAR ROW
        # ------------------------------------------------------------------
        filter_box = ctk.CTkFrame(
            self,
            fg_color=STITCH_SUNKEN_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
            height=42,
        )
        filter_box.pack(fill="x", pady=(0, 8))
        filter_box.pack_propagate(False)

        # Search Entry (with search vector icon)
        search_wrap = ctk.CTkFrame(filter_box, fg_color="transparent")
        search_wrap.pack(side="left", padx=8, pady=5)

        self._search_icon_lbl = ctk.CTkLabel(
            search_wrap,
            text="",
            image=get_icon("search", STITCH_TEXT_MUTED, size=(14, 14)),
            width=20,
        )
        self._search_icon_lbl.pack(side="left", padx=(4, 2))

        self._search_entry = ctk.CTkEntry(
            search_wrap,
            placeholder_text="Tìm theo mã, tên, SĐT hoặc tên đăng nhập..." if is_vi else "Search by code, name, phone or username...",
            width=360,
            height=30,
            corner_radius=6,
            fg_color=STITCH_INPUT_BG,
            border_color=STITCH_INPUT_BORDER,
            text_color=STITCH_TEXT,
            font=FONT_ST_BODY,
        )
        self._search_entry.pack(side="left")
        self._search_entry.bind("<KeyRelease>", lambda _e: self._on_search_typed())

        # Status filter segmented pills
        pills_frame = ctk.CTkFrame(filter_box, fg_color="transparent")
        pills_frame.pack(side="right", padx=8, pady=5)

        self._filter_buttons: dict[str, ctk.CTkButton] = {}
        filters_def = [
            ("all", "Tất cả" if is_vi else "All"),
            ("active", "Hoạt động" if is_vi else "Active"),
            ("inactive", "Ngừng hoạt động" if is_vi else "Inactive"),
        ]
        for key, label in filters_def:
            b = ctk.CTkButton(
                pills_frame,
                text=label,
                height=26,
                corner_radius=6,
                font=FONT_ST_BODY,
                command=lambda k=key: self._set_filter(k),
            )
            b.pack(side="left", padx=(0, 4))
            self._filter_buttons[key] = b

        self._refresh_filter_styles()

        # ------------------------------------------------------------------
        # 3. MAIN SPLIT CONTENT: Master 65% Table / Detail Rail 35%
        # ------------------------------------------------------------------
        self._split_container = ctk.CTkFrame(self, fg_color="transparent")
        self._split_container.pack(fill="both", expand=True)

        self._split_container.grid_columnconfigure(0, weight=65, uniform="split")
        self._split_container.grid_columnconfigure(1, weight=35, uniform="split")
        self._split_container.grid_rowconfigure(0, weight=1)

        self._build_table_section()
        self._build_detail_section()

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # LEFT PANEL: 65% CUSTOMER DATA TABLE
    # ------------------------------------------------------------------
    def _build_table_section(self) -> None:
        is_vi = self._language == "vi"
        self._left_card = ctk.CTkFrame(
            self._split_container,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
        )
        self._left_card.grid(row=0, column=0, padx=(0, 5), sticky="nsew")

        # 1. Main Table Container
        self._table_wrapper = ctk.CTkFrame(self._left_card, fg_color="transparent")
        self._table_wrapper.pack(fill="both", expand=True, padx=6, pady=(6, 2))

        cols = [
            TableColumn("code", "MÃ KH" if is_vi else "CODE", width=75),
            TableColumn("name", "HỌ VÀ TÊN" if is_vi else "FULL NAME", width=140),
            TableColumn("phone", "SỐ ĐIỆN THOẠI" if is_vi else "PHONE", width=100),
            TableColumn("username", "TÊN ĐĂNG NHẬP" if is_vi else "USERNAME", width=100),
            TableColumn("balance", "SỐ DƯ" if is_vi else "BALANCE", align="right", width=95),
            TableColumn("status", "TRẠNG THÁI" if is_vi else "STATUS", align="center", width=110),
        ]

        self._table = DataTable(self._table_wrapper, columns=cols, on_select=self._on_row_selected)
        self._table.pack(fill="both", expand=True)

        # 2. Empty Search Frame (Stitch kh_ch_h_ng_empty_search)
        self._empty_search_frame = ctk.CTkFrame(self._left_card, fg_color="transparent")
        e_inner = ctk.CTkFrame(self._empty_search_frame, fg_color="transparent")
        e_inner.pack(expand=True, pady=40)

        ctk.CTkLabel(
            e_inner,
            text="",
            image=get_icon("search", STITCH_TEXT_MUTED, size=(24, 24)),
            width=54,
            height=54,
            corner_radius=27,
            fg_color="#171F30",
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            e_inner,
            text="Không tìm thấy khách hàng" if is_vi else "No customers found",
            font=FONT_ST_PAGE_TITLE,
            text_color=STITCH_TEXT_STRONG,
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            e_inner,
            text="Không có khách hàng nào phù hợp với từ khóa và bộ lọc hiện tại."
            if is_vi
            else "No customers matched your search keyword and active filter.",
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
            wraplength=340,
        ).pack(pady=(0, 14))

        ActionButton(
            e_inner,
            text="✕ Xóa bộ lọc" if is_vi else "✕ Clear Filters",
            kind="secondary",
            width=120,
            command=self._clear_filters_and_search,
        ).pack()

        # 3. Service Error Frame (Stitch kh_ch_h_ng_service_error)
        self._service_error_frame = ctk.CTkFrame(self._left_card, fg_color="transparent")
        err_inner = ctk.CTkFrame(self._service_error_frame, fg_color="transparent")
        err_inner.pack(expand=True, pady=40)

        ctk.CTkLabel(
            err_inner,
            text="",
            image=get_icon("alert", STITCH_DANGER, size=(24, 24)),
            width=54,
            height=54,
            corner_radius=27,
            fg_color="#251218",
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            err_inner,
            text="Không thể tải danh sách khách hàng" if is_vi else "Unable to load customer list",
            font=FONT_ST_PAGE_TITLE,
            text_color=STITCH_TEXT_STRONG,
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            err_inner,
            text="Dịch vụ hiện không khả dụng. Vui lòng thử lại."
            if is_vi
            else "The service is temporarily unavailable. Please retry.",
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
            wraplength=340,
        ).pack(pady=(0, 14))

        ActionButton(
            err_inner,
            text="Thử lại" if is_vi else "Retry",
            kind="primary",
            width=110,
            command=self.refresh,
        ).pack()

        # Table Footer: Pagination Bar
        foot = ctk.CTkFrame(self._left_card, fg_color=STITCH_SUNKEN_BG, corner_radius=6, height=32)
        foot.pack(fill="x", side="bottom", padx=6, pady=6)
        foot.pack_propagate(False)

        foot_inner = ctk.CTkFrame(foot, fg_color="transparent")
        foot_inner.pack(fill="both", expand=True, padx=10, pady=4)

        f_left = ctk.CTkFrame(foot_inner, fg_color="transparent")
        f_left.pack(side="left")

        self._status_dot = ctk.CTkLabel(
            f_left,
            text="●",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_CYAN,
        )
        self._status_dot.pack(side="left", padx=(0, 4))

        self._table_count_label = ctk.CTkLabel(
            f_left,
            text="",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        )
        self._table_count_label.pack(side="left")

        # Compact pagination pills
        pag_wrap = ctk.CTkFrame(foot_inner, fg_color="transparent")
        pag_wrap.pack(side="right")

        self._pag_lbl = ctk.CTkLabel(
            pag_wrap,
            text="Trang 1/1" if is_vi else "Page 1/1",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        )
        self._pag_lbl.pack(side="right")

    # ------------------------------------------------------------------
    # RIGHT PANEL: 35% CUSTOMER PROFILE & DETAIL RAIL
    # ------------------------------------------------------------------
    def _build_detail_section(self) -> None:
        is_vi = self._language == "vi"
        self._detail_card = ctk.CTkFrame(
            self._split_container,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
        )
        self._detail_card.grid(row=0, column=1, padx=(5, 0), sticky="nsew")

        # Container 1: Detail Content Frame (Active Customer)
        self._detail_content_frame = ctk.CTkFrame(self._detail_card, fg_color="transparent")
        self._detail_content_frame.pack(fill="both", expand=True, padx=12, pady=12)

        # TOP CONTAINER: Profile + Meta + Balance + Actions
        top_container = ctk.CTkFrame(self._detail_content_frame, fg_color="transparent")
        top_container.pack(fill="x")

        # 1. Profile Header (Avatar + Name + Mã hồ sơ + Dual status badges)
        self._profile_header = ctk.CTkFrame(top_container, fg_color="transparent")
        self._profile_header.pack(fill="x", pady=(0, 10))

        # Avatar circle (40x40 rounded-full with initials)
        self._avatar_label = ctk.CTkLabel(
            self._profile_header,
            text="?",
            width=40,
            height=40,
            corner_radius=20,
            fg_color=STITCH_AVATAR_BG,
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_CYAN,
        )
        self._avatar_label.pack(side="left")

        # Name and Code
        name_box = ctk.CTkFrame(self._profile_header, fg_color="transparent")
        name_box.pack(side="left", padx=(10, 0))

        self._detail_name = ctk.CTkLabel(
            name_box,
            text="Chọn khách hàng" if is_vi else "Select customer",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT_STRONG,
            anchor="w",
        )
        self._detail_name.pack(anchor="w")

        self._detail_code_badge = ctk.CTkLabel(
            name_box,
            text="",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_CYAN,
            anchor="w",
        )
        self._detail_code_badge.pack(anchor="w")

        # Right Dual Status Badges
        self._dual_status_box = ctk.CTkFrame(self._profile_header, fg_color="transparent")
        self._dual_status_box.pack(side="right")

        self._badge_kh = ctk.CTkLabel(
            self._dual_status_box,
            text="KH: —",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_TEXT_MUTED,
            fg_color=STITCH_CHIP_BG,
            corner_radius=4,
            padx=6,
            pady=2,
        )
        self._badge_kh.pack(anchor="e", pady=(0, 2))

        self._badge_tk = ctk.CTkLabel(
            self._dual_status_box,
            text="TK: —",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_TEXT_MUTED,
            fg_color=STITCH_CHIP_BG,
            corner_radius=4,
            padx=6,
            pady=2,
        )
        self._badge_tk.pack(anchor="e")

        # 2. Metadata Spec Grid (3 columns sunken grid)
        self._account_box = ctk.CTkFrame(
            top_container,
            fg_color="#0E131E",
            border_width=1,
            border_color=STITCH_BORDER,
            corner_radius=8,
        )
        self._account_box.pack(fill="x", pady=(0, 10))

        acc_inner = ctk.CTkFrame(self._account_box, fg_color="transparent")
        acc_inner.pack(fill="x", padx=10, pady=8)
        acc_inner.grid_columnconfigure(0, weight=1)
        acc_inner.grid_columnconfigure(1, weight=1)
        acc_inner.grid_columnconfigure(2, weight=1)

        self._val_phone = self._create_spec_col(acc_inner, 0, "SĐT" if is_vi else "PHONE")
        self._val_user = self._create_spec_col(acc_inner, 1, "TÀI KHOẢN" if is_vi else "USERNAME")
        self._val_acc_id = self._create_spec_col(acc_inner, 2, "MÃ TK" if is_vi else "ACC ID")

        # 3. Balance Showcase Card (Dedicated WalletHudCard matching Stitch)
        self._wallet_hud = WalletHudCard(
            top_container,
            balance=0,
            language=self._language,
        )
        self._wallet_hud.pack(fill="x", pady=(0, 10))
        self._detail_balance = self._wallet_hud._num_label

        # 4. Primary Control Buttons Row (Exactly 3 action buttons matching Stitch)
        self._btn_grid = ctk.CTkFrame(top_container, fg_color="transparent")
        self._btn_grid.pack(fill="x", pady=(0, 8))
        self._btn_grid.grid_columnconfigure(0, weight=5)
        self._btn_grid.grid_columnconfigure(1, weight=4)
        self._btn_grid.grid_columnconfigure(2, weight=3)

        # Nút 1: Nạp tiền (col-span-5, Cyan fill, dark text #0B101B, add_circle icon)
        self._btn_topup = ActionButton(
            self._btn_grid,
            text="+ Nạp tiền" if is_vi else "+ Top Up",
            kind="stitch_primary",
            height=32,
            font=FONT_ST_BODY_STRONG,
            corner_radius=6,
            image=get_icon("add_circle", STITCH_TEXT_ON_CYAN, size=(14, 14)),
            command=self._handle_topup,
        )
        self._btn_topup.grid(row=0, column=0, padx=(0, 3), sticky="nsew")

        # Nút 2: Sửa / Chỉnh sửa (col-span-4, Dark surface container, border #27344E, edit icon)
        self._btn_edit = ActionButton(
            self._btn_grid,
            text="Chỉnh sửa" if is_vi else "Edit",
            kind="stitch_secondary",
            height=32,
            font=FONT_ST_BODY_STRONG,
            corner_radius=6,
            image=get_icon("edit", STITCH_TEXT_MUTED, size=(13, 13)),
            command=self._handle_edit_customer,
        )
        self._btn_edit.grid(row=0, column=1, padx=(3, 3), sticky="nsew")

        # Nút 3: Khóa tài khoản (col-span-3, Rose container when active / Emerald when locked)
        self._btn_lock = ActionButton(
            self._btn_grid,
            text="Khóa" if is_vi else "Lock",
            kind="stitch_danger",
            height=32,
            font=(FONT_FAMILY, 11, "bold"),
            corner_radius=6,
            image=get_icon("lock", STITCH_DANGER, size=(13, 13)),
            command=self._handle_toggle_lock,
        )
        self._btn_lock.grid(row=0, column=2, padx=(3, 0), sticky="nsew")

        # Đảm bảo hiển thị đầy đủ 3 nút theo layout Stitch (Staff bị disable nút Khóa)
        if self._actor.role == Role.STAFF:
            self._btn_lock.set_enabled(False)

        # BOTTOM CONTAINER: Real-time Transaction Ledger (RecentTransactionsLedger)
        self._ledger = RecentTransactionsLedger(
            self._detail_content_frame,
            language=self._language,
            max_items=3,
        )
        self._ledger.pack(fill="both", expand=True, side="bottom", pady=(8, 0))

        # Container 2: Detail Placeholder Frame (No Customer Selected)
        self._detail_placeholder_frame = ctk.CTkFrame(self._detail_card, fg_color="transparent")

        p_center = ctk.CTkFrame(self._detail_placeholder_frame, fg_color="transparent")
        p_center.pack(expand=True, pady=60)

        ctk.CTkLabel(
            p_center,
            text="",
            image=get_icon("user", STITCH_TEXT_MUTED, size=(24, 24)),
            width=50,
            height=50,
            corner_radius=25,
            fg_color="#171F30",
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            p_center,
            text="Chọn một khách hàng để xem chi tiết" if is_vi else "Select customer to view details",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT_STRONG,
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            p_center,
            text="Thông tin hồ sơ, số dư và lịch sử giao dịch sẽ hiển thị tại đây"
            if is_vi
            else "Profile info, balance and transaction history will appear here",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            wraplength=220,
        ).pack()

        p_bottom = ctk.CTkFrame(self._detail_placeholder_frame, fg_color="transparent")
        p_bottom.pack(fill="x", side="bottom", padx=12, pady=12)
        p_bottom.grid_columnconfigure(0, weight=5)
        p_bottom.grid_columnconfigure(1, weight=4)
        p_bottom.grid_columnconfigure(2, weight=3)

        b1 = ActionButton(
            p_bottom,
            text="+ Nạp tiền" if is_vi else "+ Top Up",
            kind="stitch_primary",
            height=32,
            font=FONT_ST_BODY_STRONG,
            corner_radius=6,
            image=get_icon("add_circle", "#64748B", size=(14, 14)),
            state="disabled",
        )
        b1.grid(row=0, column=0, padx=(0, 3), sticky="nsew")

        b2 = ActionButton(
            p_bottom,
            text="Chỉnh sửa" if is_vi else "Edit",
            kind="stitch_secondary",
            height=32,
            font=FONT_ST_BODY_STRONG,
            corner_radius=6,
            image=get_icon("edit", "#64748B", size=(13, 13)),
            state="disabled",
        )
        b2.grid(row=0, column=1, padx=(3, 3), sticky="nsew")

        b3 = ActionButton(
            p_bottom,
            text="Khóa" if is_vi else "Lock",
            kind="stitch_danger",
            height=32,
            font=(FONT_FAMILY, 11, "bold"),
            corner_radius=6,
            image=get_icon("lock", "#64748B", size=(13, 13)),
            state="disabled",
        )
        b3.grid(row=0, column=2, padx=(3, 0), sticky="nsew")

    def _create_spec_col(self, parent: Any, col: int, label: str) -> ctk.CTkLabel:
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.grid(row=0, column=col, padx=4, sticky="w")
        ctk.CTkLabel(
            wrap,
            text=label,
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w")
        val = ctk.CTkLabel(
            wrap,
            text="—",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT,
            anchor="w",
        )
        val.pack(anchor="w")
        return val

    # ------------------------------------------------------------------
    # Data Loading & Filtering
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Tải lại danh sách khách hàng từ service."""
        try:
            self._all_customers = self._services.customers.search_customers("")
            self._apply_filters()
        except ApplicationError as err:
            logger.warning("Không nạp được danh sách khách hàng: %s", err)
            self._show_service_error(get_user_friendly_error(err))
        except Exception:
            logger.exception("Lỗi không mong muốn khi tải khách hàng")
            self._show_service_error(MSG_OPERATION_FAILED)

    def _show_service_error(self, message: str) -> None:
        is_vi = self._language == "vi"
        self._table_wrapper.pack_forget()
        self._empty_search_frame.pack_forget()
        self._service_error_frame.pack(fill="both", expand=True, padx=6, pady=(6, 2))
        self._detail_content_frame.pack_forget()
        self._detail_placeholder_frame.pack(fill="both", expand=True)
        self._status_dot.configure(text_color=STITCH_DANGER)
        self._table_count_label.configure(
            text="Mất kết nối máy chủ • Sẵn sàng thử lại"
            if is_vi
            else "Server disconnected • Ready to retry"
        )
        ToastManager.show(self, message, kind="error")

    def _clear_filters_and_search(self) -> None:
        self._search_entry.delete(0, "end")
        self._search_keyword = ""
        self._current_filter = "all"
        self._apply_filters()

    def _on_search_typed(self) -> None:
        self._search_keyword = self._search_entry.get().strip()
        self._apply_filters()

    def handle_search(self, keyword: str) -> None:
        """Nhận từ khóa tìm kiếm từ Topbar của AppShell."""
        self._search_entry.delete(0, "end")
        self._search_entry.insert(0, keyword)
        self._search_keyword = keyword.strip()
        self._apply_filters()

    def _set_filter(self, key: str) -> None:
        self._current_filter = key
        self._refresh_filter_styles()
        self._apply_filters()

    def _refresh_filter_styles(self) -> None:
        is_vi = self._language == "vi"
        total = len(self._all_customers)
        active_count = sum(1 for c in self._all_customers if c.customer_status == CustomerStatus.ACTIVE)
        inactive_count = total - active_count

        counts = {
            "all": total,
            "active": active_count,
            "inactive": inactive_count,
        }

        labels = {
            "all": f"{'Tất cả' if is_vi else 'All'} ({counts['all']})",
            "active": f"{'Hoạt động' if is_vi else 'Active'} ({counts['active']})",
            "inactive": f"{'Ngừng hoạt động' if is_vi else 'Inactive'} ({counts['inactive']})",
        }

        for key, btn in self._filter_buttons.items():
            active = (key == self._current_filter)
            btn.configure(
                text=labels[key],
                fg_color=STITCH_NAV_ACTIVE_BG if active else STITCH_INPUT_BG,
                hover_color=STITCH_NAV_ACTIVE_BG if active else "#1A2335",
                border_width=1,
                border_color=STITCH_CYAN if active else STITCH_INPUT_BORDER,
                text_color=STITCH_CYAN if active else STITCH_TEXT_MUTED,
                font=FONT_ST_BODY_STRONG if active else FONT_ST_BODY,
            )

    def _apply_filters(self) -> None:
        filtered = self._all_customers

        # Filter theo status
        if self._current_filter == "active":
            filtered = [c for c in filtered if c.customer_status == CustomerStatus.ACTIVE]
        elif self._current_filter == "inactive":
            filtered = [c for c in filtered if c.customer_status == CustomerStatus.INACTIVE]

        # Filter theo keyword
        if self._search_keyword:
            kw = self._search_keyword.lower()
            filtered = [
                c for c in filtered
                if kw in c.customer_code.lower()
                or kw in c.full_name.lower()
                or kw in c.phone.lower()
                or kw in c.username.lower()
            ]

        self._filtered_customers = filtered
        self._refresh_filter_styles()
        self._render_table()

    def _render_table(self) -> None:
        rows: list[TableRow] = []
        is_vi = self._language == "vi"

        if not self._filtered_customers:
            # Switch to Stitch Empty State (kh_ch_h_ng_empty_search)
            self._table_wrapper.pack_forget()
            self._service_error_frame.pack_forget()
            self._empty_search_frame.pack(fill="both", expand=True, padx=6, pady=(6, 2))

            self._detail_content_frame.pack_forget()
            self._detail_placeholder_frame.pack(fill="both", expand=True)

            self._status_dot.configure(text_color="#64748B")
            self._table_count_label.configure(
                text=f"Đang hiển thị 0/{len(self._all_customers)} khách hàng"
                if is_vi
                else f"Showing 0/{len(self._all_customers)} customers"
            )
            self._select_customer(None)
            return

        # Normal table display
        self._empty_search_frame.pack_forget()
        self._service_error_frame.pack_forget()
        self._table_wrapper.pack(fill="both", expand=True, padx=6, pady=(6, 2))

        self._detail_placeholder_frame.pack_forget()
        self._detail_content_frame.pack(fill="both", expand=True, padx=12, pady=12)

        self._status_dot.configure(text_color=STITCH_CYAN)

        for c in self._filtered_customers:
            is_active = c.customer_status == CustomerStatus.ACTIVE
            st_text = ("● Hoạt động" if is_active else "Ngừng hoạt động") if is_vi else ("● Active" if is_active else "Inactive")
            b_fg = STITCH_SUCCESS if is_active else STITCH_TEXT_MUTED
            b_bg = "#0A2918" if is_active else "#1E293B"

            bal_color = STITCH_SUCCESS if c.balance > 0 else (STITCH_DANGER if c.balance < 0 else STITCH_TEXT_MUTED)
            sub_txt = (
                f"Đăng ký: {c.created_at.strftime('%d/%m/%Y')}"
                if hasattr(c, "created_at") and getattr(c, "created_at")
                else f"Đăng ký: 2026 • {c.customer_code}"
            )

            rows.append(
                TableRow(
                    key=c.customer_id,
                    cells={
                        "code": c.customer_code,
                        "name": c.full_name,
                        "phone": c.phone,
                        "username": c.username,
                        "balance": format_money(c.balance),
                        "status": st_text,
                    },
                    cell_colors={
                        "code": STITCH_CYAN,
                        "balance": bal_color,
                    },
                    cell_subtexts={
                        "name": sub_txt,
                    },
                    badges={
                        "status": (st_text, b_fg, b_bg),
                    },
                )
            )

        self._table.set_rows(rows)

        # Cập nhật nhãn phân trang
        count_txt = (
            f"Hiển thị {len(self._filtered_customers)} trên {len(self._all_customers)} khách hàng"
            if is_vi
            else f"Showing {len(self._filtered_customers)} of {len(self._all_customers)} customers"
        )
        self._table_count_label.configure(text=count_txt)

        # Tự động chọn dòng đầu tiên nếu chưa chọn hoặc khách cũ không còn trong list
        if not self._selected_customer or not any(c.customer_id == self._selected_customer.customer_id for c in self._filtered_customers):
            self._select_customer(self._filtered_customers[0])
        else:
            updated_c = next((c for c in self._filtered_customers if c.customer_id == self._selected_customer.customer_id), None)
            self._select_customer(updated_c)

    def _on_row_selected(self, row_key: int | str) -> None:
        cust = next((c for c in self._filtered_customers if c.customer_id == row_key), None)
        self._select_customer(cust)

    def _select_customer(self, customer: CustomerSummary | None) -> None:
        self._selected_customer = customer
        is_vi = self._language == "vi"

        if not customer:
            self._avatar_label.configure(text="?")
            self._detail_name.configure(text="Không có khách hàng" if is_vi else "No customer selected")
            self._detail_code_badge.configure(text="")
            self._badge_kh.configure(text="KH: —", text_color=STITCH_TEXT_MUTED, fg_color=STITCH_CHIP_BG)
            self._badge_tk.configure(text="TK: —", text_color=STITCH_TEXT_MUTED, fg_color=STITCH_CHIP_BG)
            self._val_phone.configure(text="—")
            self._val_user.configure(text="—")
            self._val_acc_id.configure(text="—")
            self._wallet_hud.set_empty()
            self._btn_topup.set_enabled(False)
            self._btn_edit.set_enabled(False)
            self._btn_lock.set_enabled(False)
            self._ledger.set_empty()
            return

        self._btn_topup.set_enabled(True)
        self._btn_edit.set_enabled(True)

        self._table.select_row(customer.customer_id)

        self._avatar_label.configure(text=initials(customer.full_name))
        self._detail_name.configure(text=customer.full_name)
        self._detail_code_badge.configure(text=f"Mã hồ sơ: {customer.customer_code}")

        self._val_phone.configure(text=customer.phone)
        self._val_user.configure(text=customer.username)
        self._val_acc_id.configure(text=f"ACC-{customer.account_id:04d}")

        is_active = customer.customer_status == CustomerStatus.ACTIVE
        st_txt = "Hoạt động" if is_active else "Đã khóa"
        st_fg = STITCH_SUCCESS if is_active else STITCH_DANGER
        st_bg = "#0A2918" if is_active else "#251724"
        self._badge_kh.configure(text=f"KH: {st_txt}", text_color=st_fg, fg_color=st_bg)
        self._badge_tk.configure(text=f"TK: {st_txt}", text_color=st_fg, fg_color=st_bg)

        self._wallet_hud.set_balance(customer.balance)

        lock_text = ("Khóa" if is_active else "Mở khóa") if is_vi else ("Lock" if is_active else "Unlock")
        lock_kind = "stitch_danger" if is_active else "stitch_success"
        lock_icon_color = STITCH_DANGER if is_active else STITCH_SUCCESS
        self._btn_lock.set_kind(lock_kind)
        self._btn_lock.configure(
            text=lock_text,
            image=get_icon("lock" if is_active else "unlock", lock_icon_color, size=(13, 13)),
        )

        if self._actor.role == Role.STAFF:
            # Theo Stitch: 'title="Chỉ dành cho Quản lý"'. Nút hiển thị nhưng disabled với Nhân viên
            self._btn_lock.set_enabled(False)
        else:
            self._btn_lock.set_enabled(True)

        # Tải lịch sử giao dịch gần đây của khách
        self._load_customer_ledger(customer.customer_id)

    def _load_customer_ledger(self, customer_id: int) -> None:
        """Tải lịch sử 3 giao dịch gần đây từ WalletService."""
        try:
            txs = self._services.wallet.get_history(customer_id)
            self._ledger.set_transactions(txs)
        except ApplicationError as err:
            logger.warning("Không nạp được lịch sử ví khách %s: %s", customer_id, err)
            self._ledger.set_error(get_user_friendly_error(err))
        except Exception:
            logger.exception("Lỗi không mong muốn khi tải lịch sử ví khách %s", customer_id)
            self._ledger.set_error("Không tải được dữ liệu giao dịch")

    # ------------------------------------------------------------------
    # Action Handlers
    # ------------------------------------------------------------------
    def _handle_create_customer(self) -> None:
        CustomerDialog(
            self.winfo_toplevel(),
            self._services,
            language=self._language,
            on_success=self.refresh,
        )

    def _handle_edit_customer(self) -> None:
        if not self._selected_customer:
            return
        CustomerDialog(
            self.winfo_toplevel(),
            self._services,
            customer=self._selected_customer,
            language=self._language,
            on_success=self.refresh,
        )

    def _handle_topup(self) -> None:
        if not self._selected_customer:
            return
        TopUpDialog(
            self.winfo_toplevel(),
            self._services,
            self._selected_customer,
            employee_id=self._actor.employee_id,
            language=self._language,
            on_success=self.refresh,
        )

    def _handle_toggle_lock(self) -> None:
        if not self._selected_customer:
            return
        if self._actor.role == Role.STAFF:
            ToastManager.show(
                self.winfo_toplevel(),
                "Chỉ Quản lý mới có quyền khóa/mở khóa tài khoản!" if self._language == "vi" else "Only Managers can lock/unlock accounts!",
                kind="warning",
            )
            return
        CustomerLockDialog(
            self.winfo_toplevel(),
            self._services,
            self._selected_customer,
            actor=self._actor,
            language=self._language,
            on_success=self.refresh,
        )


def customers_view_factory(master: Any, context: ViewContext) -> ctk.CTkFrame:
    """Factory khởi tạo CustomersView từ AppShell."""
    return CustomersView(master, context)
