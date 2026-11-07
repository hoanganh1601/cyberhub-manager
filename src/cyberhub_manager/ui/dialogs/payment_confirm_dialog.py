"""PaymentConfirmDialog — Modal xác nhận thanh toán và kết thúc phiên sử dụng.

Tuân thủ thiết kế Stitch:
- Tham chiếu: docs/ui-reference/x_c_nh_n_thanh_to_n_unified_v2/code.html
- Tham chiếu Tiền mặt: docs/ui-reference/x_c_nh_n_thanh_to_n_ti_n_m_t/code.html
- Tham chiếu Chuyển khoản QR: docs/ui-reference/x_c_nh_n_thanh_to_n_chuy_n_kho_n_qr/code.html
- Kích thước: 700x560, nền STITCH_BG_CHROME (#121824), viền #273147.
- Khối 1: Thông tin phiên sử dụng (Mã máy, Tên máy, Trạng thái, Khách hàng, Thời gian, Thời lượng, Đơn giá).
- Khối 2: Chi tiết chi phí (Chi phí sử dụng, Số dư hiện tại, Trừ tài khoản, Cần thanh toán thêm, Số dư sau kết thúc).
- Khối 3: Phương thức thanh toán (Khi cần thu thêm: Tiền mặt hoặc Chuyển khoản QR).
- Chân trang: Phím tắt Enter/Esc, Nút Hủy, Nút Xác nhận thanh toán.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import customtkinter as ctk

from ...domain.dtos import CheckoutPreview, CheckoutResult, CustomerSummary, EmployeeSession, SessionSummary
from ...domain.enums import PaymentMethod
from ...domain.exceptions import ApplicationError
from ..components import ActionButton, ToastManager
from ..formatters import format_datetime, format_money
from ..messages import MSG_OPERATION_FAILED, get_user_friendly_error
from ..theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_METRIC_LG,
    FONT_ST_MONO_BODY,
    FONT_ST_MONO_SM,
    FONT_ST_MONO_XS,
    FONT_ST_MONO_XS_STRONG,
    FONT_ST_PAGE_TITLE,
    RADIUS_DIALOG,
    STITCH_BG_CANVAS,
    STITCH_BG_CHROME,
    STITCH_BORDER,
    STITCH_CARD_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_EMERALD,
    STITCH_INPUT_BG,
    STITCH_INPUT_BORDER,
    STITCH_NAV_ACTIVE_BG,
    STITCH_SUNKEN_BG,
    STITCH_TEXT,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_ON_CYAN,
    STITCH_TEXT_STRONG,
    STITCH_WARNING,
)

logger = logging.getLogger(__name__)


class PaymentConfirmDialog(ctk.CTkToplevel):
    """Hộp thoại modal xác nhận thanh toán và kết thúc phiên sử dụng."""

    def __init__(
        self,
        parent: Any,
        services: Any = None,
        machine_id: int = 0,
        *,
        context: Any = None,
        actor: EmployeeSession | None = None,
        language: str = "vi",
        on_success: Any = None,
    ) -> None:
        super().__init__(parent)
        if context is not None:
            services = context.services
            actor = context.session
            language = context.language
        self._services = services
        self._machine_id = machine_id
        self._actor = actor
        self._language = language
        self._on_success = on_success

        self._is_submitting = False
        self._selected_method: PaymentMethod = PaymentMethod.CASH
        self._qr_confirmed = False
        self._received_amount: int = 0

        # Load checkout preview data
        now = datetime.now(timezone.utc)
        self._preview: CheckoutPreview = self._services.sessions.preview_checkout(
            machine_id=machine_id,
            current_time=now,
        )

        # Lấy thông tin tài khoản khách hàng nếu có
        self._customer_username: str = ""
        try:
            cust = self._services.customers.get_customer(self._preview.session.customer_id)
            self._customer_username = cust.username
        except Exception:
            pass

        self._settlement_required = self._preview.settlement_required
        self._received_amount = self._settlement_required

        is_vi = language == "vi"
        self.title("Xác nhận thanh toán" if is_vi else "Confirm Checkout")
        self.geometry("700x560")
        self.resizable(False, False)
        self.configure(fg_color=STITCH_BG_CANVAS)

        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._update_calculation_and_state()

        self.bind("<Escape>", lambda _e: self._handle_close())
        self.bind("<Return>", lambda _e: self._handle_confirm_pressed())
        self.after(
            50,
            lambda: (
                self._cash_input.focus_set()
                if hasattr(self, "_cash_input") and self._selected_method == PaymentMethod.CASH and self._settlement_required > 0
                else (self._btn_confirm.focus_set() if hasattr(self, "_btn_confirm") else None)
            ),
        )

    def _handle_close(self) -> None:
        if not self._is_submitting and self.winfo_exists():
            self.destroy()

    def _handle_confirm_pressed(self) -> None:
        if self._can_confirm():
            self._handle_confirm()

    def _can_confirm(self) -> bool:
        if self._is_submitting:
            return False
        if self._settlement_required <= 0:
            return True
        if self._selected_method == PaymentMethod.CASH:
            return self._received_amount >= self._settlement_required
        if self._selected_method == PaymentMethod.TRANSFER:
            return self._qr_confirmed
        return True

    def _build_ui(self) -> None:
        is_vi = self._language == "vi"
        sess = self._preview.session

        container = ctk.CTkFrame(
            self,
            fg_color=STITCH_BG_CHROME,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=RADIUS_DIALOG,
        )
        container.pack(fill="both", expand=True, padx=12, pady=12)

        # ------------------------------------------------------------------
        # Header: Icon badge + Title + Subtitle + Close button
        # ------------------------------------------------------------------
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 10))

        icon_box = ctk.CTkFrame(
            header,
            width=36,
            height=36,
            fg_color=STITCH_NAV_ACTIVE_BG,
            border_width=1,
            border_color=STITCH_CYAN,
            corner_radius=8,
        )
        icon_box.pack(side="left", padx=(0, 10))
        icon_box.pack_propagate(False)

        ctk.CTkLabel(
            icon_box,
            text="💳",
            font=FONT_ST_PAGE_TITLE,
            text_color=STITCH_CYAN,
        ).pack(expand=True)

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            title_box,
            text="Xác nhận thanh toán" if is_vi else "Payment Confirmation",
            font=FONT_ST_PAGE_TITLE,
            text_color=STITCH_TEXT_STRONG,
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Kiểm tra chi phí trước khi kết thúc phiên sử dụng"
            if is_vi
            else "Verify usage cost before terminating workstation session",
            font=FONT_ST_MONO_SM,
            text_color=STITCH_TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        close_btn = ctk.CTkButton(
            header,
            text="✕",
            width=28,
            height=28,
            corner_radius=6,
            fg_color="transparent",
            hover_color=STITCH_BORDER,
            text_color=STITCH_TEXT_MUTED,
            font=FONT_ST_BODY_STRONG,
            command=self._handle_close,
        )
        close_btn.pack(side="right", anchor="n")

        # Divider
        ctk.CTkFrame(container, fg_color=STITCH_BORDER, height=1).pack(fill="x", padx=16, pady=(0, 10))

        # ------------------------------------------------------------------
        # SECTION 1: KHỐI THÔNG TIN PHIÊN SỬ DỤNG
        # ------------------------------------------------------------------
        session_card = ctk.CTkFrame(
            container,
            fg_color=STITCH_SUNKEN_BG,
            border_width=1,
            border_color=STITCH_BORDER,
            corner_radius=8,
        )
        session_card.pack(fill="x", padx=16, pady=(0, 10))

        s_inner = ctk.CTkFrame(session_card, fg_color="transparent")
        s_inner.pack(fill="both", expand=True, padx=12, pady=8)

        # Top line: Machine code & name + Status pill
        top_row = ctk.CTkFrame(s_inner, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 6))

        mach_lbl = ctk.CTkFrame(top_row, fg_color="transparent")
        mach_lbl.pack(side="left")

        ctk.CTkLabel(mach_lbl, text="🖥  ", font=FONT_ST_MONO_SM, text_color=STITCH_CYAN).pack(side="left")
        ctk.CTkLabel(
            mach_lbl,
            text=f"{sess.machine_code} — {sess.machine_name}",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT_STRONG,
        ).pack(side="left")

        st_pill = ctk.CTkFrame(top_row, fg_color="#381E28", border_width=1, border_color="#5C1D2E", corner_radius=10, height=20)
        st_pill.pack(side="right")
        ctk.CTkLabel(st_pill, text="● ĐANG DÙNG" if is_vi else "● IN USE", font=FONT_ST_MONO_XS_STRONG, text_color=STITCH_DANGER).pack(padx=8, pady=1)

        # Divider inside session card
        ctk.CTkFrame(s_inner, fg_color=STITCH_BORDER, height=1).pack(fill="x", pady=(0, 6))

        # 2-column Grid of Details
        grid_f = ctk.CTkFrame(s_inner, fg_color="transparent")
        grid_f.pack(fill="x")
        grid_f.grid_columnconfigure(0, weight=1)
        grid_f.grid_columnconfigure(1, weight=1)

        # Row 0: Khách hàng / Tài khoản
        r0_l = self._make_pair_row(grid_f, "Khách hàng:" if is_vi else "Customer:", f"{sess.customer_name} ({sess.customer_code})")
        r0_l.grid(row=0, column=0, sticky="w", padx=(0, 8), pady=2)

        tk_display = self._customer_username or sess.customer_name.lower().replace(" ", ".")
        r0_r = self._make_pair_row(grid_f, "Tài khoản:" if is_vi else "Username:", tk_display, val_color=STITCH_CYAN)
        r0_r.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=2)

        # Row 1: Bắt đầu / Kết thúc
        start_fmt = format_datetime(sess.started_at)
        r1_l = self._make_pair_row(grid_f, "Bắt đầu:" if is_vi else "Started:", start_fmt)
        r1_l.grid(row=1, column=0, sticky="w", padx=(0, 8), pady=2)

        end_fmt = format_datetime(self._preview.calculated_at)
        r1_r = self._make_pair_row(grid_f, "Kết thúc:" if is_vi else "Ended:", end_fmt)
        r1_r.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=2)

        # Row 2: Thời lượng / Đơn giá
        mins = self._preview.billed_minutes
        h = mins // 60
        m = mins % 60
        dur_str = f"{h} giờ {m} phút" if is_vi else f"{h}h {m}m"
        r2_l = self._make_pair_row(grid_f, "Thời lượng:" if is_vi else "Duration:", dur_str, val_color=STITCH_EMERALD)
        r2_l.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=2)

        rate_str = f"{format_money(sess.hourly_rate)}/giờ"
        r2_r = self._make_pair_row(grid_f, "Đơn giá:" if is_vi else "Rate:", rate_str)
        r2_r.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=2)

        # ------------------------------------------------------------------
        # SECTION 2: CHI TIẾT CHI PHÍ & PHƯƠNG THỨC (2 Columns Split)
        # ------------------------------------------------------------------
        mid_split = ctk.CTkFrame(container, fg_color="transparent")
        mid_split.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        mid_split.grid_columnconfigure(0, weight=1, uniform="mid_split")
        mid_split.grid_columnconfigure(1, weight=1, uniform="mid_split")
        mid_split.grid_rowconfigure(0, weight=1)

        # ---------------- LEFT: Chi tiết chi phí ----------------
        cost_box = ctk.CTkFrame(
            mid_split,
            fg_color=STITCH_SUNKEN_BG,
            border_width=1,
            border_color=STITCH_BORDER,
            corner_radius=8,
        )
        cost_box.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        c_inner = ctk.CTkFrame(cost_box, fg_color="transparent")
        c_inner.pack(fill="both", expand=True, padx=10, pady=8)

        ctk.CTkLabel(
            c_inner,
            text="CHI TIẾT CHI PHÍ" if is_vi else "COST BREAKDOWN",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 4))

        # Usage cost
        self._row_usage = self._make_table_row(c_inner, "Chi phí sử dụng:" if is_vi else "Usage fee:", format_money(self._preview.usage_cost))

        # Balance before
        self._row_bal_before = self._make_table_row(c_inner, "Số dư hiện tại:" if is_vi else "Current balance:", format_money(self._preview.balance_before))

        # Deducted from wallet
        deducted = self._preview.usage_cost - self._preview.settlement_required
        self._row_deducted = self._make_table_row(
            c_inner,
            "Trừ tài khoản:" if is_vi else "Wallet deducted:",
            f"-{format_money(deducted)}",
            val_color=STITCH_DANGER,
        )

        # Settlement required
        self._settle_wrap = ctk.CTkFrame(c_inner, fg_color="#2D151F" if self._settlement_required > 0 else "transparent", corner_radius=6)
        self._settle_wrap.pack(fill="x", pady=2)
        sw_inner = ctk.CTkFrame(self._settle_wrap, fg_color="transparent")
        sw_inner.pack(fill="x", padx=4, pady=2)
        ctk.CTkLabel(
            sw_inner,
            text="Cần thanh toán thêm:" if is_vi else "Additional required:",
            font=FONT_ST_BODY_STRONG if self._settlement_required > 0 else FONT_ST_BODY,
            text_color=STITCH_DANGER if self._settlement_required > 0 else STITCH_TEXT_MUTED,
        ).pack(side="left")
        self._lbl_settle_val = ctk.CTkLabel(
            sw_inner,
            text=format_money(self._settlement_required),
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_DANGER if self._settlement_required > 0 else STITCH_TEXT_STRONG,
        )
        self._lbl_settle_val.pack(side="right")

        ctk.CTkFrame(c_inner, fg_color=STITCH_BORDER, height=1).pack(fill="x", pady=4)

        # Balance after
        post_bal = self._preview.projected_balance
        self._make_table_row(
            c_inner,
            "Số dư sau khi kết thúc:" if is_vi else "Remaining balance:",
            format_money(post_bal),
            val_color=STITCH_EMERALD,
            is_bold=True,
        )

        # ---------------- RIGHT: Phương thức hoặc Thông báo đủ số dư ----------------
        self._right_box = ctk.CTkFrame(
            mid_split,
            fg_color=STITCH_SUNKEN_BG,
            border_width=1,
            border_color=STITCH_BORDER,
            corner_radius=8,
        )
        self._right_box.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        self._r_inner = ctk.CTkFrame(self._right_box, fg_color="transparent")
        self._r_inner.pack(fill="both", expand=True, padx=10, pady=8)

        # Render case A or case B
        self._build_right_content()

        # ------------------------------------------------------------------
        # SECTION 3: FOOTER ACTIONS
        # ------------------------------------------------------------------
        ctk.CTkFrame(container, fg_color=STITCH_BORDER, height=1).pack(fill="x", padx=16, pady=(0, 10))

        footer = ctk.CTkFrame(container, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(0, 14))

        self._shortcut_hint = ctk.CTkLabel(
            footer,
            text="Enter để xác nhận • Esc để hủy" if is_vi else "Enter to confirm • Esc to cancel",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        )
        self._shortcut_hint.pack(side="left")

        btns_f = ctk.CTkFrame(footer, fg_color="transparent")
        btns_f.pack(side="right")

        self._btn_cancel = ActionButton(
            btns_f,
            text="Hủy" if is_vi else "Cancel",
            kind="ghost",
            width=80,
            height=34,
            command=self._handle_close,
        )
        self._btn_cancel.pack(side="left", padx=(0, 8))

        self._btn_confirm = ActionButton(
            btns_f,
            text="Xác nhận thanh toán" if is_vi else "Confirm Payment",
            kind="danger" if self._settlement_required > 0 else "primary",
            width=160,
            height=34,
            command=self._handle_confirm,
        )
        self._btn_confirm.pack(side="left")

    def _make_pair_row(self, parent: Any, label: str, value: str, val_color: str = STITCH_TEXT) -> ctk.CTkFrame:
        f = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(f, text=label + " ", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED).pack(side="left")
        ctk.CTkLabel(f, text=value, font=FONT_ST_MONO_XS_STRONG, text_color=val_color).pack(side="left")
        return f

    def _make_table_row(self, parent: Any, label: str, value: str, val_color: str = STITCH_TEXT_STRONG, is_bold: bool = False) -> ctk.CTkFrame:
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", pady=1.5)
        ctk.CTkLabel(
            f,
            text=label,
            font=FONT_ST_BODY_STRONG if is_bold else FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left")
        ctk.CTkLabel(
            f,
            text=value,
            font=FONT_ST_BODY_STRONG if is_bold else FONT_ST_MONO_BODY,
            text_color=val_color,
        ).pack(side="right")
        return f

    # ------------------------------------------------------------------
    # Right Box Content: Case A (Sufficient) vs Case B (Insufficient)
    # ------------------------------------------------------------------
    def _build_right_content(self) -> None:
        for child in self._r_inner.winfo_children():
            child.destroy()

        is_vi = self._language == "vi"

        if self._settlement_required <= 0:
            # Case A: Số dư đủ
            banner = ctk.CTkFrame(
                self._r_inner,
                fg_color="#132E27",
                border_width=1,
                border_color="#1B4D3E",
                corner_radius=8,
            )
            banner.pack(fill="x", pady=(10, 8))

            b_in = ctk.CTkFrame(banner, fg_color="transparent")
            b_in.pack(fill="both", expand=True, padx=10, pady=8)

            ctk.CTkLabel(b_in, text="✓ ĐÃ THANH TOÁN ĐỦ", font=FONT_ST_MONO_XS_STRONG, text_color=STITCH_EMERALD).pack(anchor="w")
            ctk.CTkLabel(
                b_in,
                text="Số dư tài khoản đủ thanh toán. Phiên sẽ kết thúc, máy chuyển về Trống và hóa đơn được tạo sau khi xác nhận."
                if is_vi
                else "Account balance is sufficient. Session will close, machine sets to Available and invoice generated.",
                font=FONT_ST_MONO_XS,
                text_color="#6EE7B7",
                justify="left",
                wraplength=280,
            ).pack(anchor="w", pady=(4, 0))

        else:
            # Case B: Cần thanh toán thêm (Tiền mặt / Chuyển khoản QR)
            alert = ctk.CTkFrame(
                self._r_inner,
                fg_color="#2D151F",
                border_width=1,
                border_color=STITCH_DANGER,
                corner_radius=8,
            )
            alert.pack(fill="x", pady=(0, 6))
            al_in = ctk.CTkFrame(alert, fg_color="transparent")
            al_in.pack(fill="both", expand=True, padx=8, pady=6)
            ctk.CTkLabel(
                al_in,
                text=f"⚠ Cần thanh toán thêm {format_money(self._settlement_required)}"
                if is_vi
                else f"⚠ Need additional {format_money(self._settlement_required)}",
                font=FONT_ST_MONO_XS_STRONG,
                text_color=STITCH_DANGER,
            ).pack(anchor="w")

            # Method switch header
            sw_hdr = ctk.CTkFrame(self._r_inner, fg_color="transparent")
            sw_hdr.pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(
                sw_hdr,
                text="Phương thức:" if is_vi else "Method:",
                font=FONT_ST_MONO_XS_STRONG,
                text_color=STITCH_TEXT_MUTED,
            ).pack(side="left")

            sw_btns = ctk.CTkFrame(sw_hdr, fg_color="#111726", border_width=1, border_color=STITCH_BORDER, corner_radius=6)
            sw_btns.pack(side="right")

            self._btn_cash = ctk.CTkButton(
                sw_btns,
                text="Tiền mặt" if is_vi else "Cash",
                width=65,
                height=22,
                corner_radius=4,
                font=FONT_ST_MONO_XS_STRONG,
                command=lambda: self._select_payment_method(PaymentMethod.CASH),
            )
            self._btn_cash.pack(side="left", padx=1, pady=1)

            self._btn_qr = ctk.CTkButton(
                sw_btns,
                text="Chuyển khoản QR" if is_vi else "QR Transfer",
                width=100,
                height=22,
                corner_radius=4,
                font=FONT_ST_MONO_XS_STRONG,
                command=lambda: self._select_payment_method(PaymentMethod.TRANSFER),
            )
            self._btn_qr.pack(side="left", padx=1, pady=1)

            # Sub-container for chosen method
            self._method_container = ctk.CTkFrame(
                self._r_inner,
                fg_color="#0E1424",
                border_width=1,
                border_color=STITCH_BORDER,
                corner_radius=8,
            )
            self._method_container.pack(fill="both", expand=True, pady=(2, 0))

            self._render_method_form()

    def _select_payment_method(self, method: PaymentMethod) -> None:
        self._selected_method = method
        self._render_method_form()
        self._update_calculation_and_state()

    def _render_method_form(self) -> None:
        for c in self._method_container.winfo_children():
            c.destroy()

        is_vi = self._language == "vi"

        # Update button styles
        is_cash = self._selected_method == PaymentMethod.CASH
        self._btn_cash.configure(
            fg_color=STITCH_NAV_ACTIVE_BG if is_cash else "transparent",
            text_color=STITCH_CYAN if is_cash else STITCH_TEXT_MUTED,
            border_width=1 if is_cash else 0,
            border_color=STITCH_CYAN if is_cash else STITCH_BORDER,
        )
        self._btn_qr.configure(
            fg_color=STITCH_NAV_ACTIVE_BG if not is_cash else "transparent",
            text_color=STITCH_CYAN if not is_cash else STITCH_TEXT_MUTED,
            border_width=1 if not is_cash else 0,
            border_color=STITCH_CYAN if not is_cash else STITCH_BORDER,
        )

        wrap = ctk.CTkFrame(self._method_container, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=8, pady=6)

        if is_cash:
            # TIỀN MẶT FORM
            kh_row = ctk.CTkFrame(wrap, fg_color="transparent")
            kh_row.pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(kh_row, text="Khách đưa:" if is_vi else "Cash Received:", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED).pack(side="left")

            inp_box = ctk.CTkFrame(kh_row, fg_color=STITCH_INPUT_BG, border_width=1, border_color=STITCH_CYAN, corner_radius=6, height=26)
            inp_box.pack(side="right")
            inp_box.pack_propagate(False)

            self._entry_received = ctk.CTkEntry(
                inp_box,
                font=FONT_ST_MONO_XS_STRONG,
                text_color=STITCH_CYAN,
                fg_color="transparent",
                border_width=0,
                width=80,
            )
            self._entry_received.pack(side="left", padx=4)
            self._entry_received.insert(0, str(self._received_amount))
            self._entry_received.bind("<KeyRelease>", lambda _e: self._on_received_key())

            ctk.CTkLabel(inp_box, text="VND", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED).pack(side="right", padx=(0, 4))

            # Calculation table
            calc_b = ctk.CTkFrame(wrap, fg_color="#121824", border_width=1, border_color=STITCH_BORDER, corner_radius=6)
            calc_b.pack(fill="x", pady=2)
            cb_in = ctk.CTkFrame(calc_b, fg_color="transparent")
            cb_in.pack(fill="x", padx=6, pady=4)

            self._make_table_row(cb_in, "Cần thu:" if is_vi else "Required:", format_money(self._settlement_required))
            self._lbl_entered_val = self._make_table_row(cb_in, "Tiền khách đưa:" if is_vi else "Received:", format_money(self._received_amount))

            ctk.CTkFrame(cb_in, fg_color=STITCH_BORDER, height=1).pack(fill="x", pady=2)

            self._lbl_change = self._make_table_row(
                cb_in,
                "Tiền thừa trả khách:" if is_vi else "Change to return:",
                "0 VND",
                val_color=STITCH_EMERALD,
                is_bold=True,
            )

            # Status pill
            st_b = ctk.CTkFrame(wrap, fg_color="transparent")
            st_b.pack(fill="x", pady=(4, 0))
            self._lbl_cash_status = ctk.CTkLabel(
                st_b,
                text="● Đã nhận đủ tiền" if is_vi else "● Exact cash received",
                font=FONT_ST_MONO_XS_STRONG,
                text_color=STITCH_EMERALD,
            )
            self._lbl_cash_status.pack(side="left")

            ctk.CTkLabel(
                st_b,
                text="Xác nhận tiền mặt tại quầy" if is_vi else "Cash verified",
                font=FONT_ST_MONO_XS,
                text_color=STITCH_TEXT_MUTED,
            ).pack(side="right")

        else:
            # CHUYỂN KHOẢN QR FORM
            qr_row = ctk.CTkFrame(wrap, fg_color="transparent")
            qr_row.pack(fill="x", pady=2)

            # QR Code Box
            qr_box = ctk.CTkFrame(qr_row, width=64, height=64, fg_color="#FFFFFF", corner_radius=6)
            qr_box.pack(side="left", padx=(0, 8))
            qr_box.pack_propagate(False)

            # QR visual glyph simulation
            ctk.CTkLabel(qr_box, text="▣\nQR", font=FONT_ST_PAGE_TITLE, text_color="#090E19").pack(expand=True)

            qr_info = ctk.CTkFrame(qr_row, fg_color="transparent")
            qr_info.pack(side="left", fill="both", expand=True)

            ctk.CTkLabel(qr_info, text="Số tiền cần quét:" if is_vi else "Scan Amount:", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED).pack(anchor="w")
            ctk.CTkLabel(qr_info, text=format_money(self._settlement_required), font=FONT_ST_BODY_STRONG, text_color=STITCH_CYAN).pack(anchor="w")

            content_ref = f"{self._preview.session.machine_code}-{self._preview.session.customer_code}"
            ctk.CTkLabel(qr_info, text=f"Nội dung: {content_ref}", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT).pack(anchor="w", pady=(1, 0))

            # Confirmation Checkbox
            self._chk_qr = ctk.CTkCheckBox(
                wrap,
                text="Đã xác nhận giao dịch thành công" if is_vi else "Verified transfer success",
                font=FONT_ST_MONO_XS_STRONG,
                text_color=STITCH_TEXT_STRONG,
                fg_color=STITCH_CYAN,
                hover_color="#0884A8",
                checkmark_color="#090E19",
                height=22,
                command=self._on_qr_checked,
            )
            self._chk_qr.pack(anchor="w", pady=(6, 2))

            ctk.CTkLabel(
                wrap,
                text="* Ghi nhận chuyển khoản thủ công tại quầy." if is_vi else "* Manual bank transfer verification at counter.",
                font=FONT_ST_MONO_XS,
                text_color=STITCH_TEXT_MUTED,
            ).pack(anchor="w")

    def _on_received_key(self) -> None:
        val_str = self._entry_received.get().strip().replace(".", "").replace(",", "")
        try:
            self._received_amount = int(val_str)
        except ValueError:
            self._received_amount = 0

        self._update_calculation_and_state()

    def _on_qr_checked(self) -> None:
        self._qr_confirmed = bool(self._chk_qr.get())
        self._update_calculation_and_state()

    def _update_calculation_and_state(self) -> None:
        is_vi = self._language == "vi"

        if self._settlement_required > 0 and self._selected_method == PaymentMethod.CASH:
            if hasattr(self, "_lbl_entered_val"):
                self._lbl_entered_val.winfo_children()[-1].configure(text=format_money(self._received_amount))

            change = max(0, self._received_amount - self._settlement_required)
            if hasattr(self, "_lbl_change"):
                self._lbl_change.winfo_children()[-1].configure(text=format_money(change))

            is_enough = self._received_amount >= self._settlement_required
            if hasattr(self, "_lbl_cash_status"):
                if is_enough:
                    self._lbl_cash_status.configure(
                        text="● Đã nhận đủ tiền" if is_vi else "● Exact cash received",
                        text_color=STITCH_EMERALD,
                    )
                else:
                    self._lbl_cash_status.configure(
                        text=f"○ Chưa đủ tiền (thiếu {format_money(self._settlement_required - self._received_amount)})"
                        if is_vi
                        else f"○ Insufficient cash (short {format_money(self._settlement_required - self._received_amount)})",
                        text_color=STITCH_DANGER,
                    )

        # Enable/Disable Confirm button
        can_confirm = self._can_confirm()
        self._btn_confirm.set_enabled(can_confirm)

    # ------------------------------------------------------------------
    # Actions: Confirm & Submit
    # ------------------------------------------------------------------
    def _handle_confirm(self) -> None:
        if self._is_submitting or not self._can_confirm():
            return

        self._set_submitting(True)
        is_vi = self._language == "vi"

        method = None
        if self._settlement_required > 0:
            method = self._selected_method

        try:
            res: CheckoutResult = self._services.sessions.complete_checkout(
                machine_id=self._machine_id,
                actor=self._actor,
                settlement_amount=self._settlement_required,
                method=method,
            )

            code = self._preview.session.machine_code
            ToastManager.show(
                self.master,
                f"Đã hoàn tất thanh toán máy {code}!" if is_vi else f"Checkout completed for machine {code}!",
                kind="success",
            )
            if self._on_success:
                self._on_success(res)
            if self.winfo_exists():
                self.destroy()

        except ApplicationError as err:
            logger.warning("Lỗi thanh toán: %s", err)
            ToastManager.show(self, get_user_friendly_error(err), kind="error")
        except Exception:
            logger.exception("Lỗi không mong muốn khi thanh toán")
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")
        finally:
            if self.winfo_exists():
                self._set_submitting(False)

    def _set_submitting(self, busy: bool) -> None:
        self._is_submitting = busy
        self._btn_confirm.set_busy(busy)
        self._btn_cancel.set_enabled(not busy)
        if hasattr(self, "_entry_received") and self._entry_received.winfo_exists():
            self._entry_received.configure(state="disabled" if busy else "normal")
        if hasattr(self, "_chk_qr") and self._chk_qr.winfo_exists():
            self._chk_qr.configure(state="disabled" if busy else "normal")
