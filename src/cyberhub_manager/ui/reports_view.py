"""Reports View — Màn hình báo cáo doanh thu theo chuẩn Google Stitch.

Tuân thủ thiết kế Stitch:
- Tham chiếu: docs/ui-reference/doanh_thu_unified_app_shell/code.html
- Bộ lọc khoảng ngày (Từ ngày - Đến ngày) kèm các nút chọn nhanh (Hôm nay, 7 ngày, 30 ngày).
- 5 thẻ tài chính chuẩn Stitch (Tổng doanh thu, HĐ đã thanh toán, Doanh thu TB/HĐ, Ngày cao nhất, Doanh thu ngày MAX với badge ĐỈNH ĐIỂM).
- Split layout: Bảng doanh thu theo ngày (68%) kèm THANH TỶ TRỌNG TRỰC QUAN + Panel 4 khối hộp phân tích tổng hợp (32%).
- Chỉ tính hóa đơn trạng thái ĐÃ THANH TOÁN (PAID).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from ..domain.dtos import DailyRevenue
from ..domain.exceptions import ApplicationError
from .components import (
    ActionButton,
    DataTable,
    TableColumn,
    TableRow,
    ToastManager,
)
from .formatters import VN_TZ, format_money
from .messages import MSG_OPERATION_FAILED, get_user_friendly_error
from .state import ViewState
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


class ReportsView(ctk.CTkFrame):
    """Màn hình Báo cáo Doanh thu chuẩn Google Stitch."""

    def __init__(self, master: Any, context: ViewContext) -> None:
        super().__init__(master, fg_color="transparent")
        self._context = context
        self._language = context.language
        self._actor = context.session
        self._services = context.services

        now_vn = datetime.now(VN_TZ).date()
        self._date_to = now_vn
        self._date_from = now_vn - timedelta(days=23)  # Mặc định ~24 ngày như Stitch
        self._daily_data: list[DailyRevenue] = []

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        is_vi = self._language == "vi"

        # ------------------------------------------------------------------
        # ROW 1: PAGE HEADER ROW
        # ------------------------------------------------------------------
        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 6))

        left = ctk.CTkFrame(header_row, fg_color="transparent")
        left.pack(side="left")

        ctk.CTkLabel(
            left,
            text="Doanh thu" if is_vi else "Revenue Analytics",
            font=FONT_ST_PAGE_TITLE,
            text_color=STITCH_TEXT_STRONG,
        ).pack(side="left")

        ctk.CTkLabel(
            left,
            text="Theo dõi doanh thu hóa đơn đã thanh toán" if is_vi else "Track paid invoice revenues",
            font=FONT_ST_MONO_SM,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left", padx=(10, 0), pady=(3, 0))

        # Store badge chip
        store_chip = ctk.CTkFrame(
            header_row,
            fg_color=STITCH_CHIP_BG,
            border_width=1,
            border_color=STITCH_CHIP_BORDER,
            corner_radius=6,
        )
        store_chip.pack(side="left", padx=(12, 0))
        store_name = self._actor.store_name or f"Cơ sở: {self._actor.store_code}"
        ctk.CTkLabel(
            store_chip,
            text=f"Cơ sở: {store_name}",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_CYAN,
        ).pack(padx=8, pady=2)

        # Right side: Last sync & Refresh button
        right_box = ctk.CTkFrame(header_row, fg_color="transparent")
        right_box.pack(side="right")

        self._lbl_header_clock = ctk.CTkLabel(
            right_box,
            text="Cập nhật: —",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        )
        self._lbl_header_clock.pack(side="left", padx=(0, 10))

        self._btn_refresh = ActionButton(
            right_box,
            text="↻  Làm mới" if is_vi else "↻  Refresh",
            kind="secondary",
            width=90,
            height=28,
            command=self.refresh,
        )
        self._btn_refresh.pack(side="left")

        # ------------------------------------------------------------------
        # ROW 2: FILTER ROW
        # ------------------------------------------------------------------
        filter_box = ctk.CTkFrame(
            self,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
            height=40,
        )
        filter_box.pack(fill="x", pady=(0, 8))
        filter_box.pack_propagate(False)

        left_filter = ctk.CTkFrame(filter_box, fg_color="transparent")
        left_filter.pack(side="left", padx=10, pady=5)

        ctk.CTkLabel(
            left_filter,
            text="Từ ngày:" if is_vi else "From:",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left", padx=(0, 4))

        self._entry_from = ctk.CTkEntry(
            left_filter,
            width=90,
            height=26,
            corner_radius=4,
            fg_color=STITCH_INPUT_BG,
            border_color=STITCH_CHIP_BORDER,
            text_color=STITCH_TEXT_STRONG,
            font=FONT_ST_MONO_XS,
        )
        self._entry_from.insert(0, self._date_from.strftime("%Y-%m-%d"))
        self._entry_from.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            left_filter,
            text="Đến ngày:" if is_vi else "To:",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left", padx=(0, 4))

        self._entry_to = ctk.CTkEntry(
            left_filter,
            width=90,
            height=26,
            corner_radius=4,
            fg_color=STITCH_INPUT_BG,
            border_color=STITCH_CHIP_BORDER,
            text_color=STITCH_TEXT_STRONG,
            font=FONT_ST_MONO_XS,
        )
        self._entry_to.insert(0, self._date_to.strftime("%Y-%m-%d"))
        self._entry_to.pack(side="left", padx=(0, 8))

        # Timezone chip
        tz_chip = ctk.CTkFrame(left_filter, fg_color="#161C2B", border_width=1, border_color="#222D42", corner_radius=4)
        tz_chip.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(tz_chip, text="Asia/Ho_Chi_Minh", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED).pack(padx=6, pady=1)

        # Nút Áp dụng
        self._btn_apply = ActionButton(
            left_filter,
            text="Áp dụng" if is_vi else "Apply",
            kind="primary",
            width=70,
            height=26,
            command=self._apply_date_filter,
        )
        self._btn_apply.pack(side="left", padx=(0, 6))

        # Quick preset buttons: Hôm nay, 7 ngày, 30 ngày
        self._create_preset_btn(left_filter, "Hôm nay" if is_vi else "Today", days=0)
        self._create_preset_btn(left_filter, "7 ngày" if is_vi else "7 days", days=7)
        self._create_preset_btn(left_filter, "30 ngày" if is_vi else "30 days", days=30)

        # Right indicator: Chỉ tính hóa đơn đã thanh toán
        right_badge = ctk.CTkFrame(filter_box, fg_color="#0A241B", border_width=1, border_color="#1B5938", corner_radius=6)
        right_badge.pack(side="right", padx=10, pady=5)
        ctk.CTkLabel(
            right_badge,
            text="● Chỉ tính hóa đơn ĐÃ THANH TOÁN" if is_vi else "● Only PAID invoices included",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_SUCCESS,
        ).pack(padx=8, pady=2)

        # ------------------------------------------------------------------
        # ROW 3: 5 FINANCIAL CARDS (Theo thiết kế Stitch chuẩn)
        # ------------------------------------------------------------------
        kpi_row = ctk.CTkFrame(self, fg_color="transparent")
        kpi_row.pack(fill="x", pady=(0, 8))
        for c in range(5):
            kpi_row.grid_columnconfigure(c, weight=1, uniform="kpi_rev")

        # Card 1: TỔNG DOANH THU
        self._card1_val, self._card1_sub = self._create_financial_card(
            kpi_row,
            col=0,
            title="TỔNG DOANH THU" if is_vi else "TOTAL REVENUE",
            val_color=STITCH_CYAN,
        )

        # Card 2: HĐ ĐÃ THANH TOÁN
        self._card2_val, self._card2_sub = self._create_financial_card(
            kpi_row,
            col=1,
            title="HĐ ĐÃ THANH TOÁN" if is_vi else "PAID INVOICES",
            val_color=STITCH_TEXT_STRONG,
            sub_color=STITCH_SUCCESS,
        )

        # Card 3: DOANH THU TB / HĐ
        self._card3_val, self._card3_sub = self._create_financial_card(
            kpi_row,
            col=2,
            title="DOANH THU TB / HĐ" if is_vi else "AVG / INVOICE",
            val_color=STITCH_TEXT_STRONG,
        )

        # Card 4: NGÀY CAO NHẤT
        self._card4_val, self._card4_sub = self._create_financial_card(
            kpi_row,
            col=3,
            title="NGÀY CAO NHẤT" if is_vi else "PEAK DATE",
            val_color=STITCH_TEXT_STRONG,
            sub_color=STITCH_SUCCESS,
        )

        # Card 5: DOANH THU NGÀY MAX (Có badge ĐỈNH ĐIỂM)
        self._card5_val, self._card5_sub = self._create_financial_card(
            kpi_row,
            col=4,
            title="DOANH THU NGÀY MAX" if is_vi else "MAX DAILY REVENUE",
            val_color=STITCH_SUCCESS,
            badge_text="ĐỈNH ĐIỂM" if is_vi else "PEAK",
            is_peak=True,
        )

        # ------------------------------------------------------------------
        # ROW 4: MAIN CONTENT SPLIT (68% Table, 32% Analytics Panel)
        # ------------------------------------------------------------------
        self._split_container = ctk.CTkFrame(self, fg_color="transparent")
        self._split_container.pack(fill="both", expand=True)

        self._split_container.grid_columnconfigure(0, weight=68, uniform="rev_split")
        self._split_container.grid_columnconfigure(1, weight=32, uniform="rev_split")
        self._split_container.grid_rowconfigure(0, weight=1)

        self._build_table_section()
        self._build_summary_panel()

    def _create_preset_btn(self, parent: Any, label: str, days: int) -> None:
        def on_click():
            now_vn = datetime.now(VN_TZ).date()
            self._date_to = now_vn
            self._date_from = now_vn if days == 0 else (now_vn - timedelta(days=days - 1))
            self._entry_from.delete(0, "end")
            self._entry_from.insert(0, self._date_from.strftime("%Y-%m-%d"))
            self._entry_to.delete(0, "end")
            self._entry_to.insert(0, self._date_to.strftime("%Y-%m-%d"))
            self.refresh()

        btn = ctk.CTkButton(
            parent,
            text=label,
            width=55,
            height=26,
            corner_radius=4,
            fg_color="#171F30",
            hover_color="#1E273A",
            border_width=1,
            border_color="#27344E",
            text_color=STITCH_TEXT_MUTED,
            font=FONT_ST_MONO_XS,
            command=on_click,
        )
        btn.pack(side="left", padx=2)

    def _create_financial_card(
        self,
        parent: Any,
        col: int,
        title: str,
        val_color: str,
        sub_color: str = STITCH_TEXT_MUTED,
        badge_text: str | None = None,
        is_peak: bool = False,
    ) -> tuple[ctk.CTkLabel, ctk.CTkLabel]:
        card = ctk.CTkFrame(
            parent,
            fg_color="#0F2022" if is_peak else STITCH_CARD_BG,
            border_width=1,
            border_color="#10B981" if is_peak else STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS,
            height=72,
        )
        card.grid(row=0, column=col, padx=4 if col not in (0, 4) else (0 if col == 0 else 4), sticky="nsew")
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=10, pady=7)

        # Header row: Title + Optional Badge
        top_h = ctk.CTkFrame(inner, fg_color="transparent")
        top_h.pack(fill="x")

        t_lbl = ctk.CTkLabel(
            top_h,
            text=title,
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_SUCCESS if is_peak else STITCH_TEXT_MUTED,
        )
        t_lbl.pack(side="left")

        if badge_text:
            badge = ctk.CTkLabel(
                top_h,
                text=badge_text,
                font=FONT_ST_MONO_XS_STRONG,
                text_color=STITCH_SUCCESS,
                fg_color="#132E27",
                corner_radius=4,
                padx=4,
                pady=1,
            )
            badge.pack(side="right")

        # Value label
        val_lbl = ctk.CTkLabel(
            inner,
            text="—",
            font=(FONT_ST_PAGE_TITLE[0], 16, "bold"),
            text_color=val_color,
        )
        val_lbl.pack(anchor="w", pady=(1, 0))

        # Subtitle label
        sub_lbl = ctk.CTkLabel(
            inner,
            text="",
            font=FONT_ST_MONO_XS,
            text_color=sub_color,
        )
        sub_lbl.pack(anchor="w")

        return val_lbl, sub_lbl

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

        # Header of table card
        t_head = ctk.CTkFrame(left_card, fg_color="transparent")
        t_head.pack(fill="x", padx=12, pady=(10, 4))

        title_wrap = ctk.CTkFrame(t_head, fg_color="transparent")
        title_wrap.pack(side="left")

        ctk.CTkLabel(
            title_wrap,
            text="Doanh thu theo ngày" if is_vi else "Daily Revenue",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT_STRONG,
        ).pack(side="left")

        ctk.CTkLabel(
            title_wrap,
            text="(Mới nhất trước)" if is_vi else "(Latest first)",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left", padx=(6, 0))

        self._lbl_period_chip = ctk.CTkLabel(
            t_head,
            text="",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_CYAN,
            fg_color="#171F30",
            corner_radius=4,
            padx=8,
            pady=2,
        )
        self._lbl_period_chip.pack(side="right")

        # DataTable
        cols = [
            TableColumn("date", "NGÀY" if is_vi else "DATE", width=140),
            TableColumn("count", "SỐ HĐ ĐÃ THANH TOÁN" if is_vi else "PAID INVOICES", align="right", width=170),
            TableColumn("revenue", "DOANH THU (VND)" if is_vi else "REVENUE (VND)", align="right", width=160),
            TableColumn("ratio", "TỶ TRỌNG (%)" if is_vi else "SHARE (%)", align="right", width=150),
        ]

        self._table = DataTable(left_card, columns=cols)
        self._table.pack(fill="both", expand=True, padx=8, pady=(4, 4))

        foot = ctk.CTkFrame(left_card, fg_color="transparent", height=26)
        foot.pack(fill="x", side="bottom", padx=10, pady=4)

        dot = ctk.CTkFrame(foot, width=6, height=6, corner_radius=3, fg_color=STITCH_CYAN)
        dot.pack(side="left", padx=(0, 6))

        self._table_count_label = ctk.CTkLabel(
            foot,
            text="",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        )
        self._table_count_label.pack(side="left")

    def _build_summary_panel(self) -> None:
        is_vi = self._language == "vi"
        right_card = ctk.CTkFrame(
            self._split_container,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
        )
        right_card.grid(row=0, column=1, padx=(6, 0), sticky="nsew")

        inner = ctk.CTkFrame(right_card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=10)

        # Panel Header: Bar chart icon + Title
        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(
            header,
            text="📊 ",
            font=FONT_ST_MONO_SM,
            text_color=STITCH_CYAN,
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text="Tổng kết kỳ báo cáo" if is_vi else "Report Summary",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT_STRONG,
        ).pack(side="left")

        # ------------------------------------------------------------------
        # KHỐI 1: PHẠM VI BÁO CÁO
        # ------------------------------------------------------------------
        box1 = self._create_card_box(inner, "PHẠM VI BÁO CÁO" if is_vi else "REPORT SCOPE")
        self._lbl_scope_store = self._create_box_row(box1, "Cơ sở áp dụng:" if is_vi else "Store:", self._actor.store_name or self._actor.store_code)
        self._lbl_scope_range = self._create_box_row(box1, "Khoảng thời gian:" if is_vi else "Date range:", "—")
        self._lbl_days = self._create_box_row(box1, "Số ngày có doanh thu:" if is_vi else "Active revenue days:", "0 ngày", is_bold_white=True)
        self._lbl_tot_invoices = self._create_box_row(box1, "Tổng hóa đơn PAID:" if is_vi else "Total paid invoices:", "0 HĐ", is_emerald=True)

        # ------------------------------------------------------------------
        # KHỐI 2: CHỈ SỐ TÀI CHÍNH TỔNG HỢP (bg #171F30, border #27344E)
        # ------------------------------------------------------------------
        box2 = self._create_card_box(
            inner,
            "CHỈ SỐ TÀI CHÍNH TỔNG HỢP" if is_vi else "FINANCIAL METRICS",
            fg_color="#171F30",
            border_color="#27344E",
        )
        self._lbl_tot_revenue = self._create_box_row(box2, "Tổng thu trong kỳ:" if is_vi else "Total revenue:", "0 VND", is_highlight=True)

        # Divider in financial box
        ctk.CTkFrame(box2, fg_color="#222D42", height=1).pack(fill="x", padx=8, pady=3)

        self._lbl_avg_day = self._create_box_row(box2, "Doanh thu TB / ngày:" if is_vi else "Daily average:", "0 VND")
        self._lbl_avg_inv = self._create_box_row(box2, "Doanh thu TB / HĐ:" if is_vi else "Invoice average:", "0 VND")

        # ------------------------------------------------------------------
        # KHỐI 3: NGUYÊN TẮC GHI NHẬN (bg-emerald-950/15)
        # ------------------------------------------------------------------
        box3 = ctk.CTkFrame(inner, fg_color="#0A241B", border_width=1, border_color="#1B5938", corner_radius=6)
        box3.pack(fill="x", pady=3)

        ctk.CTkLabel(
            box3,
            text="🛡  Nguyên tắc ghi nhận" if is_vi else "🛡  Accounting Principle",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_SUCCESS,
        ).pack(anchor="w", padx=8, pady=(4, 2))

        ctk.CTkLabel(
            box3,
            text="Lưu ý: Hóa đơn đã hủy không được tính vào doanh thu. Chỉ tính các hóa đơn trạng thái ĐÃ THANH TOÁN."
            if is_vi
            else "Notice: Cancelled invoices are not included. Only invoices marked PAID are counted.",
            font=FONT_ST_MONO_XS,
            text_color="#6EE7B7",
            wraplength=270,
            justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 6))

        # ------------------------------------------------------------------
        # KHỐI 4: TRẠNG THÁI DỮ LIỆU
        # ------------------------------------------------------------------
        box4 = self._create_card_box(inner, "TRẠNG THÁI DỮ LIỆU" if is_vi else "DATA STATUS")
        ctk.CTkLabel(
            box4,
            text="Dữ liệu được tổng hợp thời gian thực từ hóa đơn ĐÃ THANH TOÁN của cửa hàng hiện tại."
            if is_vi
            else "Aggregated in real-time from PAID invoices of current store node.",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            wraplength=270,
            justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 4))

        ctk.CTkFrame(box4, fg_color=STITCH_BORDER, height=1).pack(fill="x", padx=8, pady=2)

        sync_row = ctk.CTkFrame(box4, fg_color="transparent")
        sync_row.pack(fill="x", padx=8, pady=(0, 4))
        ctk.CTkLabel(sync_row, text="Đồng bộ lần cuối:" if is_vi else "Last synced:", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED).pack(side="left")
        self._lbl_sync = ctk.CTkLabel(sync_row, text="—", font=FONT_ST_MONO_XS_STRONG, text_color=STITCH_TEXT_STRONG)
        self._lbl_sync.pack(side="right")

    def _create_card_box(
        self,
        parent: Any,
        title: str,
        *,
        fg_color: str = "#0E131E",
        border_color: str = STITCH_BORDER,
    ) -> ctk.CTkFrame:
        box = ctk.CTkFrame(parent, fg_color=fg_color, border_width=1, border_color=border_color, corner_radius=6)
        box.pack(fill="x", pady=3)
        ctk.CTkLabel(
            box,
            text=title,
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        ).pack(anchor="w", padx=8, pady=(4, 2))
        return box

    def _create_box_row(
        self,
        parent: Any,
        label: str,
        val_text: str,
        *,
        is_highlight: bool = False,
        is_bold_white: bool = False,
        is_emerald: bool = False,
    ) -> ctk.CTkLabel:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=1)

        ctk.CTkLabel(row, text=label, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(side="left")

        text_col = STITCH_CYAN if is_highlight else (STITCH_SUCCESS if is_emerald else STITCH_TEXT_STRONG)
        font = (FONT_ST_PAGE_TITLE[0], 14, "bold") if is_highlight else (FONT_ST_BODY_STRONG if is_bold_white or is_emerald else FONT_ST_BODY)

        val = ctk.CTkLabel(
            row,
            text=val_text,
            font=font,
            text_color=text_col,
        )
        val.pack(side="right")
        return val

    # ------------------------------------------------------------------
    # Data Loading & Filter Execution
    # ------------------------------------------------------------------
    def _apply_date_filter(self) -> None:
        try:
            d_from = datetime.strptime(self._entry_from.get().strip(), "%Y-%m-%d").date()
            d_to = datetime.strptime(self._entry_to.get().strip(), "%Y-%m-%d").date()
            if d_from > d_to:
                ToastManager.show(self, "Ngày bắt đầu không được lớn hơn ngày kết thúc!", kind="warning")
                return
            self._date_from = d_from
            self._date_to = d_to
            self.refresh()
        except ValueError:
            ToastManager.show(self, "Định dạng ngày không hợp lệ! Vui lòng dùng YYYY-MM-DD", kind="error")

    def refresh(self) -> None:
        try:
            self._table.set_state(ViewState.LOADING)
            store_id = self._actor.store_id
            self._daily_data = self._services.reports.daily_revenue(
                store_id=store_id,
                date_from=self._date_from,
                date_to=self._date_to,
            )
            self._render_report()
            now_str = datetime.now(VN_TZ).strftime("%H:%M:%S")
            self._lbl_header_clock.configure(text=f"Cập nhật: {now_str}")
            self._lbl_sync.configure(text=now_str)
        except ApplicationError as err:
            logger.warning("Lỗi nạp doanh thu: %s", err)
            self._table.set_state(ViewState.ERROR, message=get_user_friendly_error(err), on_retry=self.refresh)
            ToastManager.show(self, get_user_friendly_error(err), kind="error")
        except Exception:
            logger.exception("Lỗi bất ngờ khi tải báo cáo doanh thu")
            self._table.set_state(ViewState.ERROR, message=MSG_OPERATION_FAILED, on_retry=self.refresh)
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")

    def _render_report(self) -> None:
        is_vi = self._language == "vi"
        total_rev = sum(d.revenue for d in self._daily_data)
        total_invoices = sum(d.invoice_count for d in self._daily_data)
        active_days = len(self._daily_data)

        avg_per_inv = total_rev // total_invoices if total_invoices > 0 else 0
        avg_per_day = total_rev // active_days if active_days > 0 else 0

        peak = max(self._daily_data, key=lambda d: d.revenue, default=None)
        peak_date_str = peak.date.strftime("%d/%m/%Y") if peak else "—"
        peak_rev_str = format_money(peak.revenue) if peak else "0 VND"

        peak_pct = (peak.revenue / total_rev * 100) if (peak and total_rev > 0) else 0.0

        # Cập nhật 5 thẻ tài chính
        self._card1_val.configure(text=format_money(total_rev))
        self._card1_sub.configure(text=f"Từ {total_invoices} HĐ thành công" if is_vi else f"From {total_invoices} paid inv")

        self._card2_val.configure(text=f"{total_invoices} đơn" if is_vi else f"{total_invoices} inv")
        self._card2_sub.configure(text="Đã thu hoàn tất" if is_vi else "Fully collected")

        self._card3_val.configure(text=format_money(avg_per_inv))
        self._card3_sub.configure(text="TB mỗi phiên nạp/giờ" if is_vi else "Avg per session")

        self._card4_val.configure(text=peak_date_str)
        self._card4_sub.configure(text="Đạt đỉnh kỳ" if is_vi else "Period peak")

        self._card5_val.configure(text=peak_rev_str)
        self._card5_sub.configure(text=f"Chiếm {peak_pct:.1f}% tổng kỳ" if is_vi else f"Share {peak_pct:.1f}% total")

        # Cập nhật chip kỳ báo cáo
        range_str = f"{self._date_from.strftime('%d/%m')} – {self._date_to.strftime('%d/%m/%Y')}"
        self._lbl_period_chip.configure(text=f"Kỳ: {range_str}")
        self._lbl_scope_range.configure(text=range_str)

        # Cập nhật Bảng dữ liệu theo ngày
        if not self._daily_data:
            self._table.set_rows([])
            self._table.set_state(
                ViewState.EMPTY,
                message="Không có dữ liệu doanh thu trong khoảng thời gian này."
                if is_vi
                else "No revenue data found for this period.",
            )
            self._table_count_label.configure(
                text="Hiển thị 0 ngày" if is_vi else "Displaying 0 days"
            )
        else:
            sorted_data = sorted(self._daily_data, key=lambda d: d.date, reverse=True)
            rows: list[TableRow] = []
            now_date = datetime.now(VN_TZ).date()

            for d in sorted_data:
                ratio = (d.revenue / total_rev * 100.0) if total_rev > 0 else 0.0
                date_label = d.date.strftime("%d/%m/%Y")
                is_today = (d.date == now_date)
                is_max = (peak is not None and d.date == peak.date)

                rev_color = STITCH_CYAN if (is_today or is_max) else STITCH_TEXT_STRONG

                inline_tags: dict[str, tuple[str, str, str]] = {}
                if is_today:
                    inline_tags["date"] = ("HÔM NAY" if is_vi else "TODAY", "#34D399", "#132E27")

                ratio_bars: dict[str, tuple[float, str]] = {
                    "ratio": (ratio, f"{ratio:.1f}%")
                }

                rows.append(
                    TableRow(
                        key=d.date.isoformat(),
                        cells={
                            "date": date_label,
                            "count": f"{d.invoice_count} HĐ" if is_vi else f"{d.invoice_count} inv",
                            "revenue": format_money(d.revenue),
                            "ratio": f"{ratio:.1f}%",
                        },
                        cell_colors={
                            "revenue": rev_color,
                        },
                        ratio_bars=ratio_bars,
                        inline_tags=inline_tags,
                    )
                )

            self._table.set_rows(rows)
            self._table.set_state(ViewState.READY)
            self._table_count_label.configure(
                text=f"Đang hiển thị {len(rows)} ngày có phát sinh doanh thu"
                if is_vi
                else f"Displaying {len(rows)} active revenue days"
            )

        # Cập nhật Summary Panel 4 khối
        self._lbl_days.configure(text=f"{active_days} ngày" if is_vi else f"{active_days} days")
        self._lbl_tot_invoices.configure(text=f"{total_invoices} hóa đơn" if is_vi else f"{total_invoices} invoices")
        self._lbl_tot_revenue.configure(text=format_money(total_rev))
        self._lbl_avg_day.configure(text=format_money(avg_per_day))
        self._lbl_avg_inv.configure(text=format_money(avg_per_inv))


def reports_view_factory(master: Any, context: ViewContext) -> ctk.CTkFrame:
    """Factory khởi tạo ReportsView từ AppShell."""
    return ReportsView(master, context)
