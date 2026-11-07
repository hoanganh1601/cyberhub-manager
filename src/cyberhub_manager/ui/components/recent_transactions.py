"""RecentTransactionsLedger component cho CyberHub Manager theo chuẩn Google Stitch.

Hiển thị 3 giao dịch gần nhất của khách hàng đang chọn:
- Tham chiếu: docs/ui-reference/cyberhub_manager_kh_ch_h_ng_v_ti_n_1280x720/code.html (dòng 308-319).
- Tiêu đề "Lịch sử giao dịch gần đây" kèm biểu tượng history vector cyan.
- Khung chip trạng thái số lượng giao dịch / "Hôm nay".
- Danh sách tối đa 3 giao dịch thực tế từ WalletService.
- Mỗi giao dịch thể hiện:
  1. Loại giao dịch (Badge: TOP_UP cyan, PHIÊN CHƠI slate, HOÀN TIỀN amber, ĐIỀU CHỈNH rose).
  2. Thời gian: HH:mm - Hôm nay / dd/MM.
  3. Phương thức thanh toán & Nhân viên (Tiền mặt / Chuyển khoản • NV: ...).
  4. Số tiền: +Số tiền VND màu xanh ngọc hoặc -Số tiền VND màu đỏ hồng.
- Xử lý trạng thái rỗng chân thực khi khách hàng chưa có giao dịch nào (không dùng dữ liệu giả).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import customtkinter as ctk

from ...domain.dtos import TransactionSummary
from ...domain.enums import PaymentMethod, TransactionType
from ..formatters import format_money
from ..icons import get_icon
from ..theme import (
    FONT_FAMILY,
    FONT_ST_BODY_STRONG,
    FONT_ST_MONO_XS,
    FONT_ST_MONO_XS_STRONG,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_SUCCESS,
    STITCH_SUNKEN_BG,
    STITCH_TEXT,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
    STITCH_WARNING,
)


class RecentTransactionsLedger(ctk.CTkFrame):
    """Component hiển thị sổ cái 3 giao dịch gần nhất của khách hàng."""

    def __init__(
        self,
        master: Any,
        transactions: list[TransactionSummary] | None = None,
        *,
        language: str = "vi",
        max_items: int = 3,
        **kwargs: Any,
    ) -> None:
        self._language = language
        self._max_items = max_items
        self._transactions: list[TransactionSummary] = []

        super().__init__(
            master=master,
            fg_color="transparent",
            **kwargs,
        )

        self._build_ui()
        if transactions is not None:
            self.set_transactions(transactions)
        else:
            self.set_empty()

    def _build_ui(self) -> None:
        is_vi = self._language == "vi"

        # 1. Đường kẻ ngăn cách phía trên (Divider border-t border-[#222a3d])
        self._divider = ctk.CTkFrame(self, height=1, fg_color="#222A3D")
        self._divider.pack(fill="x", pady=(0, 8))

        # 2. Hàng tiêu đề: Icon history + "Lịch sử giao dịch gần đây" + Chip số lượng / Hôm nay
        self._header_row = ctk.CTkFrame(self, fg_color="transparent")
        self._header_row.pack(fill="x", pady=(0, 6))

        left = ctk.CTkFrame(self._header_row, fg_color="transparent")
        left.pack(side="left")

        ctk.CTkLabel(
            left,
            text="",
            image=get_icon("history", STITCH_CYAN, size=(14, 14)),
        ).pack(side="left", padx=(0, 6))

        ctk.CTkLabel(
            left,
            text="Lịch sử giao dịch gần đây" if is_vi else "Recent transaction ledger",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT_STRONG,
        ).pack(side="left")

        self._badge_lbl = ctk.CTkLabel(
            self._header_row,
            text="0 giao dịch" if is_vi else "0 tx",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            fg_color="#171F30",
            corner_radius=4,
            padx=6,
            pady=2,
        )
        self._badge_lbl.pack(side="right")

        # 3. Stack danh sách giao dịch
        self._stack = ctk.CTkFrame(self, fg_color="transparent")
        self._stack.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Public Methods
    # ------------------------------------------------------------------
    def set_transactions(self, transactions: list[TransactionSummary]) -> None:
        """Hiển thị tối đa 3 giao dịch mới nhất."""
        self._transactions = list(transactions)[: self._max_items]
        is_vi = self._language == "vi"

        count = len(self._transactions)
        self._badge_lbl.configure(text=f"{count} {'giao dịch' if is_vi else 'tx'}")

        self._clear_stack()

        if not self._transactions:
            self._render_empty_state("Chưa có giao dịch" if is_vi else "No transactions yet")
            return

        for tx in self._transactions:
            self._render_item(tx)

    def set_empty(self, message: str | None = None) -> None:
        """Đặt trạng thái rỗng chưa có giao dịch hoặc chưa chọn khách hàng."""
        self._transactions = []
        is_vi = self._language == "vi"
        self._badge_lbl.configure(text="0 " + ("giao dịch" if is_vi else "tx"))
        self._clear_stack()
        self._render_empty_state(message or ("Chưa có giao dịch" if is_vi else "No transactions yet"))

    def set_error(self, error_message: str) -> None:
        """Hiển thị khi không nạp được giao dịch từ service."""
        self._transactions = []
        is_vi = self._language == "vi"
        self._badge_lbl.configure(text="Lỗi" if is_vi else "Error")
        self._clear_stack()

        err_box = ctk.CTkFrame(
            self._stack,
            fg_color="#1B1217",
            border_width=1,
            border_color="#61212E",
            corner_radius=8,
        )
        err_box.pack(fill="both", expand=True, pady=4)

        inner = ctk.CTkFrame(err_box, fg_color="transparent")
        inner.pack(expand=True, pady=10)

        ctk.CTkLabel(
            inner,
            text="",
            image=get_icon("alert", STITCH_DANGER, size=(18, 18)),
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            inner,
            text=error_message,
            font=FONT_ST_MONO_XS,
            text_color=STITCH_DANGER,
            wraplength=220,
        ).pack()

    @property
    def transaction_count(self) -> int:
        """Số lượng giao dịch đang hiển thị."""
        return len(self._transactions)

    # ------------------------------------------------------------------
    # Internal Rendering
    # ------------------------------------------------------------------
    def _clear_stack(self) -> None:
        for child in self._stack.winfo_children():
            child.destroy()

    def _render_empty_state(self, message: str) -> None:
        is_vi = self._language == "vi"

        empty_box = ctk.CTkFrame(
            self._stack,
            fg_color="#0E131E",
            border_width=1,
            border_color="#212B3E",
            corner_radius=8,
        )
        empty_box.pack(fill="both", expand=True, pady=4)

        e_inner = ctk.CTkFrame(empty_box, fg_color="transparent")
        e_inner.pack(expand=True, pady=10)

        ctk.CTkLabel(
            e_inner,
            text="",
            image=get_icon("clock", STITCH_TEXT_MUTED, size=(20, 20)),
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            e_inner,
            text=message,
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT_MUTED,
        ).pack()

        ctk.CTkLabel(
            e_inner,
            text="Khách hàng chưa có lịch sử nạp tiền hoặc phiên chơi."
            if is_vi
            else "Customer has no top-up or session records.",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            wraplength=220,
        ).pack(pady=(2, 0))

    def _render_item(self, tx: TransactionSummary) -> None:
        row = ctk.CTkFrame(
            self._stack,
            fg_color="#0E131E",
            border_width=1,
            border_color="#212B3E",
            corner_radius=6,
            height=48,
        )
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)

        r_inner = ctk.CTkFrame(row, fg_color="transparent")
        r_inner.pack(fill="both", expand=True, padx=8, pady=4)

        # Trái: Loại giao dịch + Thời gian + Phương thức & Nhân viên
        left = ctk.CTkFrame(r_inner, fg_color="transparent")
        left.pack(side="left")

        l_top = ctk.CTkFrame(left, fg_color="transparent")
        l_top.pack(anchor="w")

        # Cấu hình Type Badge theo chuẩn Stitch
        if tx.type == TransactionType.TOP_UP:
            b_txt = "TOP_UP"
            b_fg = STITCH_CYAN
            b_bg = "#0C2E40"
        elif tx.type == TransactionType.USAGE_PAYMENT:
            b_txt = "PHIÊN CHƠI"
            b_fg = STITCH_TEXT_MUTED
            b_bg = "#1E273A"
        elif tx.type == TransactionType.PROMOTION:
            b_txt = "KHUYẾN MÃI"
            b_fg = STITCH_WARNING
            b_bg = "#352309"
        elif tx.type == TransactionType.DEBT_SETTLEMENT:
            b_txt = "TRẢ NỢ"
            b_fg = STITCH_SUCCESS
            b_bg = "#0A2918"
        else:
            b_txt = "GIAO DỊCH"
            b_fg = STITCH_TEXT_MUTED
            b_bg = "#1E273A"

        ctk.CTkLabel(
            l_top,
            text=b_txt,
            font=FONT_ST_MONO_XS_STRONG,
            text_color=b_fg,
            fg_color=b_bg,
            corner_radius=3,
            padx=5,
            pady=1,
        ).pack(side="left", padx=(0, 6))

        # Thời gian
        time_str = self._format_tx_time(tx.created_at)
        ctk.CTkLabel(
            l_top,
            text=time_str,
            font=(FONT_FAMILY, 11, "normal"),
            text_color=STITCH_TEXT,
        ).pack(side="left")

        # Metadata phương thức & nhân viên
        meta_str = self._format_tx_metadata(tx)
        ctk.CTkLabel(
            left,
            text=meta_str,
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(1, 0))

        # Phải: Số tiền biến động (+ tiền xanh lục, - tiền đỏ hồng)
        amt_txt = f"+{format_money(tx.amount)}" if tx.amount >= 0 else format_money(tx.amount)
        amt_color = STITCH_SUCCESS if tx.amount >= 0 else STITCH_DANGER
        ctk.CTkLabel(
            r_inner,
            text=amt_txt,
            font=FONT_ST_BODY_STRONG,
            text_color=amt_color,
        ).pack(side="right")

    def _format_tx_time(self, dt: datetime | None) -> str:
        if not dt:
            return "Hôm nay"
        # Kiểm tra xem có phải ngày hôm nay không
        try:
            from ..formatters import VN_TZ
            local_dt = dt.astimezone(VN_TZ) if dt.tzinfo else dt
            now = datetime.now(VN_TZ)
            if local_dt.date() == now.date():
                return local_dt.strftime("%H:%M - Hôm nay")
            return local_dt.strftime("%H:%M %d/%m")
        except Exception:
            return dt.strftime("%H:%M - Hôm nay")

    def _format_tx_metadata(self, tx: TransactionSummary) -> str:
        staff = tx.employee_name if tx.employee_name else "Thu ngân"
        if tx.type == TransactionType.TOP_UP:
            method_str = "Tiền mặt" if tx.method == PaymentMethod.CASH else "Chuyển khoản"
            return f"{method_str} • NV: {staff}"
        if tx.type == TransactionType.USAGE_PAYMENT:
            session_code = f"PC-0{tx.session_id}" if tx.session_id else "Phiên máy"
            return f"{session_code} • Tự động trừ"
        if tx.type == TransactionType.PROMOTION:
            return f"Khuyến mãi nạp ví • Hệ thống"
        if tx.type == TransactionType.DEBT_SETTLEMENT:
            return f"Thanh toán nợ • NV: {staff}"
        return f"NV: {staff}"
