"""Invoices View — Màn hình tra cứu hóa đơn và biên lai chi tiết theo thiết kế Google Stitch.

Tuân thủ thiết kế Stitch:
- Tham chiếu chính: docs/ui-reference/master_cyberhub_app_shell_2/code.html
- Tham chiếu phụ: docs/ui-reference/receipt_cyberhub_manager_1280x720/code.html
- Bố cục Split 65/35: Bảng danh sách hóa đơn (65%) và Chi tiết hóa đơn 3 khối hộp (35%).
- Khối 1: Thông tin chung (Mã phiên, Ngày tạo, Cửa hàng, Nhân viên).
- Khối 2: Khách hàng & Phiên máy (Khách hàng, Tài khoản, Máy, Thời gian, Thời lượng, Đơn giá).
- Khối 3: Chi tiết thanh toán (Tổng chi phí, Thanh toán số dư, Thanh toán bổ sung, Phương thức, Tổng đã thanh toán).
- Nút tác vụ: Sao chép mã HĐ với thông báo Toast.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from ..domain.dtos import InvoiceDetail, InvoiceFilters, InvoiceSummary
from ..domain.enums import InvoiceStatus
from ..domain.exceptions import ApplicationError
from .components import (
    ActionButton,
    DataTable,
    StatusBadge,
    TableColumn,
    TableRow,
    ToastManager,
)
from .formatters import VN_TZ, format_datetime, format_money
from .messages import MSG_OPERATION_FAILED, get_user_friendly_error
from .theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_MONO_BODY,
    FONT_ST_MONO_SM,
    FONT_ST_MONO_XS,
    FONT_ST_MONO_XS_STRONG,
    FONT_ST_PAGE_TITLE,
    STITCH_BORDER,
    STITCH_CARD_BG,
    STITCH_CARD_BORDER,
    STITCH_CHIP_BG,
    STITCH_CHIP_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_EMERALD,
    STITCH_INPUT_BG,
    STITCH_NAV_ACTIVE_BG,
    STITCH_RADIUS,
    STITCH_RADIUS_LG,
    STITCH_SUCCESS,
    STITCH_SUNKEN_BG,
    STITCH_TEXT,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_ON_CYAN,
    STITCH_TEXT_STRONG,
)

if TYPE_CHECKING:
    from .app_shell import ViewContext

logger = logging.getLogger(__name__)


class InvoicesView(ctk.CTkFrame):
    """Màn hình Tra cứu hóa đơn và chi tiết biên lai 3 khối theo Google Stitch."""

    def __init__(self, master: Any, context: ViewContext) -> None:
        super().__init__(master, fg_color="transparent")
        self._context = context
        self._language = context.language
        self._actor = context.session
        self._services = context.services

        now_vn = datetime.now(VN_TZ).date()
        self._date_to = now_vn
        self._date_from = now_vn - timedelta(days=30)
        self._current_status_filter: str = "all"
        self._search_keyword: str = ""

        self._invoices: list[InvoiceSummary] = []
        self._selected_invoice_detail: InvoiceDetail | None = None
        self._customer_usernames_cache: dict[int, str] = {}

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        is_vi = self._language == "vi"

        # ------------------------------------------------------------------
        # TOP HEADER
        # ------------------------------------------------------------------
        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 8))

        title_box = ctk.CTkFrame(header_row, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box,
            text="Hóa đơn" if is_vi else "Invoices & Receipts",
            font=FONT_ST_PAGE_TITLE,
            text_color=STITCH_TEXT_STRONG,
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Tra cứu hóa đơn và lịch sử thanh toán" if is_vi else "Lookup invoice history and session billing details",
            font=FONT_ST_MONO_SM,
            text_color=STITCH_TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        self._btn_refresh = ActionButton(
            header_row,
            text="↻  Làm mới" if is_vi else "↻  Refresh",
            kind="secondary",
            width=100,
            height=30,
            command=self.refresh,
        )
        self._btn_refresh.pack(side="right")

        # ------------------------------------------------------------------
        # FILTER ROW
        # ------------------------------------------------------------------
        filter_box = ctk.CTkFrame(
            self,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
            height=44,
        )
        filter_box.pack(fill="x", pady=(0, 8))
        filter_box.pack_propagate(False)

        left_wrap = ctk.CTkFrame(filter_box, fg_color="transparent")
        left_wrap.pack(side="left", padx=10, pady=6)

        self._search_entry = ctk.CTkEntry(
            left_wrap,
            placeholder_text="Tìm theo mã HĐ, tên khách, thu ngân…" if is_vi else "Search by invoice code, customer, staff…",
            width=280,
            height=30,
            corner_radius=6,
            fg_color=STITCH_INPUT_BG,
            border_color=STITCH_CHIP_BORDER,
            text_color=STITCH_TEXT,
            font=FONT_ST_BODY,
        )
        self._search_entry.pack(side="left", padx=(0, 10))
        self._search_entry.bind("<KeyRelease>", lambda _e: self._on_search_typed())

        # Status pills
        pills_frame = ctk.CTkFrame(filter_box, fg_color="transparent")
        pills_frame.pack(side="right", padx=10, pady=6)

        self._filter_buttons: dict[str, ctk.CTkButton] = {}
        filters_def = [
            ("all", "Tất cả" if is_vi else "All"),
            ("paid", "Đã thanh toán" if is_vi else "Paid"),
            ("cancelled", "Đã hủy" if is_vi else "Cancelled"),
        ]
        for key, label in filters_def:
            b = ctk.CTkButton(
                pills_frame,
                text=label,
                height=28,
                corner_radius=STITCH_RADIUS,
                font=FONT_ST_BODY,
                command=lambda k=key: self._set_status_filter(k),
            )
            b.pack(side="left", padx=(0, 6))
            self._filter_buttons[key] = b

        self._refresh_filter_styles()

        # ------------------------------------------------------------------
        # MAIN SPLIT CONTENT: Left 65% Table / Right 35% High-Tech 3-Box Receipt
        # ------------------------------------------------------------------
        self._split_container = ctk.CTkFrame(self, fg_color="transparent")
        self._split_container.pack(fill="both", expand=True)

        self._split_container.grid_columnconfigure(0, weight=65, uniform="inv_split")
        self._split_container.grid_columnconfigure(1, weight=35, uniform="inv_split")
        self._split_container.grid_rowconfigure(0, weight=1)

        self._build_table_section()
        self._build_receipt_section()

    def _build_table_section(self) -> None:
        is_vi = self._language == "vi"
        left_card = ctk.CTkFrame(
            self._split_container,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
        )
        left_card.grid(row=0, column=0, padx=(0, 6), sticky="nsew")

        cols = [
            TableColumn("code", "MÃ HÓA ĐƠN" if is_vi else "INVOICE CODE", width=130),
            TableColumn("created", "THỜI GIAN" if is_vi else "TIMESTAMP", width=125),
            TableColumn("customer", "KHÁCH HÀNG" if is_vi else "CUSTOMER", width=140),
            TableColumn("employee", "THU NGÂN" if is_vi else "STAFF", width=110),
            TableColumn("total", "TỔNG TIỀN" if is_vi else "TOTAL", align="right", width=110),
            TableColumn("status", "TRẠNG THÁI" if is_vi else "STATUS", align="center", width=120),
        ]

        self._table = DataTable(left_card, columns=cols, on_select=self._on_row_selected)
        self._table.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        foot = ctk.CTkFrame(left_card, fg_color="transparent", height=28)
        foot.pack(fill="x", side="bottom", padx=10, pady=6)

        dot = ctk.CTkFrame(foot, width=6, height=6, corner_radius=3, fg_color=STITCH_CYAN)
        dot.pack(side="left", padx=(0, 6))

        self._table_count_label = ctk.CTkLabel(
            foot,
            text="",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        )
        self._table_count_label.pack(side="left")

    def _build_receipt_section(self) -> None:
        is_vi = self._language == "vi"
        self._receipt_card = ctk.CTkFrame(
            self._split_container,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
        )
        self._receipt_card.grid(row=0, column=1, padx=(6, 0), sticky="nsew")

        inner = ctk.CTkFrame(self._receipt_card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=12)

        # ------------------------------------------------------------------
        # PANEL HEADER: Icon + Title + Invoice Code + Status Badge
        # ------------------------------------------------------------------
        header_f = ctk.CTkFrame(inner, fg_color="transparent")
        header_f.pack(fill="x", pady=(0, 8))

        top_h = ctk.CTkFrame(header_f, fg_color="transparent")
        top_h.pack(fill="x")

        # Left title info
        h_left = ctk.CTkFrame(top_h, fg_color="transparent")
        h_left.pack(side="left")

        title_row = ctk.CTkFrame(h_left, fg_color="transparent")
        title_row.pack(anchor="w")

        ctk.CTkLabel(
            title_row,
            text="🧾 ",
            font=FONT_ST_MONO_SM,
            text_color=STITCH_CYAN,
        ).pack(side="left")

        ctk.CTkLabel(
            title_row,
            text="CHI TIẾT HÓA ĐƠN" if is_vi else "INVOICE DETAILS",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT_STRONG,
        ).pack(side="left")

        self._lbl_rec_code = ctk.CTkLabel(
            h_left,
            text="—",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_CYAN,
        )
        self._lbl_rec_code.pack(anchor="w", pady=(1, 0))

        # Right status badge
        self._badge_container = ctk.CTkFrame(
            top_h,
            fg_color="#09231B",
            border_width=1,
            border_color="#10B981",
            corner_radius=4,
            height=22,
        )
        self._badge_container.pack(side="right", anchor="n")
        self._lbl_rec_status = ctk.CTkLabel(
            self._badge_container,
            text="—",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_EMERALD,
        )
        self._lbl_rec_status.pack(padx=8, pady=1)

        # Header bottom separator
        ctk.CTkFrame(inner, fg_color=STITCH_BORDER, height=1).pack(fill="x", pady=(4, 8))

        # ------------------------------------------------------------------
        # KHỐI 1: THÔNG TIN CHUNG
        # ------------------------------------------------------------------
        box1 = self._create_info_box(inner, "THÔNG TIN CHUNG" if is_vi else "GENERAL INFO", border_color=STITCH_BORDER)
        self._lbl_session_code = self._create_data_row(box1, "Mã phiên:" if is_vi else "Session ID:")
        self._lbl_created_at = self._create_data_row(box1, "Ngày tạo:" if is_vi else "Created at:")
        self._lbl_store = self._create_data_row(box1, "Cửa hàng:" if is_vi else "Store:")
        self._lbl_staff = self._create_data_row(box1, "Nhân viên:" if is_vi else "Staff:")

        # ------------------------------------------------------------------
        # KHỐI 2: KHÁCH HÀNG & PHIÊN MÁY
        # ------------------------------------------------------------------
        box2 = self._create_info_box(inner, "KHÁCH HÀNG & PHIÊN MÁY" if is_vi else "CUSTOMER & SESSION", border_color=STITCH_BORDER)
        self._lbl_cust = self._create_data_row(box2, "Khách hàng:" if is_vi else "Customer:")
        self._lbl_account = self._create_data_row(box2, "Tài khoản:" if is_vi else "Account:", val_color=STITCH_CYAN)
        self._lbl_machine = self._create_data_row(box2, "Máy:" if is_vi else "Station:")
        self._lbl_time_range = self._create_data_row(box2, "Thời gian:" if is_vi else "Time range:")
        self._lbl_duration = self._create_data_row(box2, "Thời lượng:" if is_vi else "Duration:")
        self._lbl_rate = self._create_data_row(box2, "Đơn giá:" if is_vi else "Hourly rate:")

        # ------------------------------------------------------------------
        # KHỐI 3: CHI TIẾT THANH TOÁN (High-tech dark cyan card)
        # ------------------------------------------------------------------
        box3 = self._create_info_box(
            inner,
            "CHI TIẾT THANH TOÁN" if is_vi else "PAYMENT BREAKDOWN",
            fg_color="#0B101B",
            border_color="#27344E",
            title_color=STITCH_CYAN,
        )
        self._lbl_usage_cost = self._create_data_row(box3, "Tổng chi phí phiên:" if is_vi else "Total session cost:")
        self._lbl_balance_pay = self._create_data_row(box3, "Thanh toán từ số dư:" if is_vi else "Paid from balance:")
        self._lbl_settle_pay = self._create_data_row(box3, "Thanh toán bổ sung:" if is_vi else "Additional settlement:")
        self._lbl_method = self._create_data_row(box3, "Phương thức bổ sung:" if is_vi else "Settlement method:")

        # Divider in payment box
        ctk.CTkFrame(box3, fg_color="#1E273A", height=1).pack(fill="x", padx=8, pady=(4, 4))

        # Total Paid Row
        tot_row = ctk.CTkFrame(box3, fg_color="transparent")
        tot_row.pack(fill="x", padx=8, pady=(0, 6))
        ctk.CTkLabel(
            tot_row,
            text="Tổng đã thanh toán:" if is_vi else "Total Paid:",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT_STRONG,
        ).pack(side="left")
        self._lbl_total_paid = ctk.CTkLabel(
            tot_row,
            text="0 VND",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_CYAN,
        )
        self._lbl_total_paid.pack(side="right")

        # ------------------------------------------------------------------
        # BOTTOM ACTION: Sao chép mã HĐ
        # ------------------------------------------------------------------
        btm_bar = ctk.CTkFrame(inner, fg_color="transparent")
        btm_bar.pack(fill="x", side="bottom", pady=(8, 0))

        self._btn_copy = ActionButton(
            btm_bar,
            text="📋  Sao chép mã HĐ" if is_vi else "📋  Copy Invoice Code",
            kind="secondary",
            height=32,
            command=self._handle_copy_invoice_code,
        )
        self._btn_copy.pack(fill="x")

    def _create_info_box(
        self,
        parent: Any,
        title: str,
        *,
        fg_color: str = "#0E131E",
        border_color: str = "#1E273A",
        title_color: str = STITCH_TEXT_MUTED,
    ) -> ctk.CTkFrame:
        box = ctk.CTkFrame(
            parent,
            fg_color=fg_color,
            border_width=1,
            border_color=border_color,
            corner_radius=6,
        )
        box.pack(fill="x", pady=3)

        ctk.CTkLabel(
            box,
            text=title,
            font=FONT_ST_MONO_XS,
            text_color=title_color,
        ).pack(anchor="w", padx=8, pady=(4, 2))
        return box

    def _create_data_row(
        self,
        parent: Any,
        label: str,
        *,
        val_color: str = STITCH_TEXT_STRONG,
    ) -> ctk.CTkLabel:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=1)

        ctk.CTkLabel(
            row,
            text=label,
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left")

        val = ctk.CTkLabel(
            row,
            text="—",
            font=FONT_ST_BODY_STRONG,
            text_color=val_color,
        )
        val.pack(side="right")
        return val

    # ------------------------------------------------------------------
    # Data Loading & Filters
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        try:
            st = None
            if self._current_status_filter == "paid":
                st = InvoiceStatus.PAID
            elif self._current_status_filter == "cancelled":
                st = InvoiceStatus.VOID

            filters = InvoiceFilters(
                date_from=self._date_from,
                date_to=self._date_to,
                keyword=self._search_keyword,
                status=st,
            )
            store_id = self._actor.store_id
            self._invoices = self._services.reports.list_invoices(store_id, filters)
            self._render_table()
        except ApplicationError as err:
            logger.warning("Lỗi nạp hóa đơn: %s", err)
            ToastManager.show(self, get_user_friendly_error(err), kind="error")
        except Exception:
            logger.exception("Lỗi bất ngờ khi tải danh sách hóa đơn")
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")

    def _on_search_typed(self) -> None:
        self._search_keyword = self._search_entry.get().strip()
        self.refresh()

    def handle_search(self, keyword: str) -> None:
        """Nhận từ khóa tìm kiếm từ Topbar của AppShell."""
        self._search_entry.delete(0, "end")
        self._search_entry.insert(0, keyword)
        self._search_keyword = keyword.strip()
        self.refresh()

    def _set_status_filter(self, key: str) -> None:
        self._current_status_filter = key
        self._refresh_filter_styles()
        self.refresh()

    def _refresh_filter_styles(self) -> None:
        for key, btn in self._filter_buttons.items():
            active = key == self._current_status_filter
            btn.configure(
                fg_color=STITCH_CYAN if active else STITCH_CHIP_BG,
                hover_color=STITCH_CYAN if active else "#1F2A3D",
                border_width=0 if active else 1,
                border_color=STITCH_CHIP_BORDER,
                text_color=STITCH_TEXT_ON_CYAN if active else STITCH_TEXT_MUTED,
                font=FONT_ST_BODY_STRONG if active else FONT_ST_BODY,
            )

    def _render_table(self) -> None:
        rows: list[TableRow] = []
        is_vi = self._language == "vi"

        for inv in self._invoices:
            st = "Đã thanh toán" if inv.status == InvoiceStatus.PAID else "Đã hủy"
            if not is_vi:
                st = "Paid" if inv.status == InvoiceStatus.PAID else "Cancelled"

            rows.append(
                TableRow(
                    key=inv.invoice_id,
                    cells={
                        "code": inv.invoice_code,
                        "created": format_datetime(inv.created_at),
                        "customer": inv.customer_name,
                        "employee": inv.employee_name,
                        "total": format_money(inv.total_amount),
                        "status": st,
                    },
                )
            )

        self._table.set_rows(rows)
        self._table_count_label.configure(
            text=f"Đang hiển thị {len(rows)} hóa đơn" if is_vi else f"Displaying {len(rows)} invoices"
        )

        if self._invoices:
            self._fetch_and_display_detail(self._invoices[0].invoice_id)
        else:
            self._clear_receipt()

    def _on_row_selected(self, row_key: int | str) -> None:
        self._fetch_and_display_detail(int(row_key))

    def _fetch_and_display_detail(self, invoice_id: int) -> None:
        try:
            detail = self._services.reports.get_invoice(invoice_id)
            self._selected_invoice_detail = detail
            self._display_detail(detail)
        except ApplicationError as err:
            logger.warning("Không nạp được chi tiết HĐ %s: %s", invoice_id, err)
        except Exception:
            logger.exception("Lỗi khi tải chi tiết HĐ %s", invoice_id)

    def _display_detail(self, detail: InvoiceDetail) -> None:
        inv = detail.invoice
        sess = detail.session
        is_vi = self._language == "vi"

        # Header Code & Status Badge
        self._lbl_rec_code.configure(text=inv.invoice_code)

        is_paid = inv.status == InvoiceStatus.PAID
        st_text = ("ĐÃ THANH TOÁN" if is_paid else "ĐÃ HỦY") if is_vi else ("PAID" if is_paid else "CANCELLED")
        st_fg = "#09231B" if is_paid else "#2D1217"
        st_border = "#10B981" if is_paid else "#DC2626"
        st_color = STITCH_EMERALD if is_paid else STITCH_DANGER

        self._badge_container.configure(fg_color=st_fg, border_color=st_border)
        self._lbl_rec_status.configure(text=st_text, text_color=st_color)

        # Khối 1: Thông tin chung
        sess_code = sess.session_code if sess else f"SES-{inv.session_id:04d}"
        self._lbl_session_code.configure(text=sess_code)
        self._lbl_created_at.configure(text=format_datetime(inv.created_at))
        self._lbl_store.configure(text=inv.store_name)
        self._lbl_staff.configure(text=inv.employee_name)

        # Khách hàng & Tài khoản lookup
        cust_name = inv.customer_name
        cust_code = sess.customer_code if sess else ""
        cust_display = f"{cust_name} ({cust_code})" if cust_code else cust_name
        self._lbl_cust.configure(text=cust_display)

        # Username lookup
        username = self._customer_usernames_cache.get(inv.customer_id, "")
        if not username:
            try:
                cust_dto = self._services.customers.get_customer(inv.customer_id)
                if cust_dto:
                    username = cust_dto.username
                    self._customer_usernames_cache[inv.customer_id] = username
            except Exception:
                username = cust_name.lower().replace(" ", ".")
        self._lbl_account.configure(text=username or "—")

        # Máy
        if sess:
            mach_text = f"{sess.machine_code} — {sess.machine_name}"
        else:
            mach_text = "—"
        self._lbl_machine.configure(text=mach_text)

        # Thời gian
        if sess and sess.started_at:
            s_dt = sess.started_at.astimezone(VN_TZ) if sess.started_at.tzinfo else sess.started_at
            if detail.ended_at:
                e_dt = detail.ended_at.astimezone(VN_TZ) if detail.ended_at.tzinfo else detail.ended_at
                time_str = f"{s_dt.strftime('%H:%M')} → {e_dt.strftime('%H:%M')}"
            else:
                time_str = s_dt.strftime("%H:%M")
        else:
            time_str = "—"
        self._lbl_time_range.configure(text=time_str)

        # Thời lượng
        mins = detail.billed_minutes
        hrs = mins // 60
        m = mins % 60
        if hrs > 0 and m > 0:
            dur_str = f"{hrs} giờ {m} phút" if is_vi else f"{hrs}h {m}m"
        elif hrs > 0:
            dur_str = f"{hrs} giờ" if is_vi else f"{hrs}h"
        else:
            dur_str = f"{mins} phút" if is_vi else f"{mins} mins"
        self._lbl_duration.configure(text=dur_str)

        # Đơn giá
        rate_val = sess.hourly_rate if sess else 0
        self._lbl_rate.configure(text=f"{format_money(rate_val)}/giờ" if rate_val else "—")

        # Khối 3: Chi tiết thanh toán
        self._lbl_usage_cost.configure(text=format_money(inv.usage_cost))

        bal_paid = max(0, inv.usage_cost - inv.settlement_amount)
        self._lbl_balance_pay.configure(text=format_money(bal_paid))

        self._lbl_settle_pay.configure(text=format_money(inv.settlement_amount))

        if inv.settlement_amount > 0:
            method_str = "Tiền mặt" if is_vi else "Cash"
        else:
            method_str = "—"
        self._lbl_method.configure(text=method_str)

        self._lbl_total_paid.configure(text=format_money(inv.total_amount))

        self._btn_copy.set_enabled(True)

    def _clear_receipt(self) -> None:
        self._lbl_rec_code.configure(text="—")
        self._badge_container.configure(fg_color="#0E131E", border_color=STITCH_BORDER)
        self._lbl_rec_status.configure(text="—", text_color=STITCH_TEXT_MUTED)

        self._lbl_session_code.configure(text="—")
        self._lbl_created_at.configure(text="—")
        self._lbl_store.configure(text="—")
        self._lbl_staff.configure(text="—")

        self._lbl_cust.configure(text="—")
        self._lbl_account.configure(text="—")
        self._lbl_machine.configure(text="—")
        self._lbl_time_range.configure(text="—")
        self._lbl_duration.configure(text="—")
        self._lbl_rate.configure(text="—")

        self._lbl_usage_cost.configure(text="0 VND")
        self._lbl_balance_pay.configure(text="0 VND")
        self._lbl_settle_pay.configure(text="0 VND")
        self._lbl_method.configure(text="—")
        self._lbl_total_paid.configure(text="0 VND")

        self._btn_copy.set_enabled(False)

    def _handle_copy_invoice_code(self) -> None:
        if not self._selected_invoice_detail:
            return

        code = self._selected_invoice_detail.invoice.invoice_code
        try:
            self.clipboard_clear()
            self.clipboard_append(code)
            is_vi = self._language == "vi"
            msg = f"Đã sao chép mã HĐ: {code}" if is_vi else f"Copied invoice code: {code}"
            ToastManager.show(self, msg, kind="info")
        except Exception as e:
            logger.warning("Không thể sao chép clipboard: %s", e)


def invoices_view_factory(master: Any, context: ViewContext) -> ctk.CTkFrame:
    """Factory khởi tạo InvoicesView từ AppShell."""
    return InvoicesView(master, context)
