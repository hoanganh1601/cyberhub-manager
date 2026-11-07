"""TopUpDialog — Hộp thoại nạp tiền vào ví khách hàng theo thiết kế Stitch.

Tuân thủ thiết kế Stitch:
- Tham chiếu: docs/ui-reference/n_p_ti_n_default/code.html
- Thẻ tóm tắt thông tin khách hàng (mã KH, tên, mã TK, số dư hiện tại, dual status pills).
- Ô nhập tiền với chip đơn vị VND, note kiểm tra hợp lệ.
- 4 phím nạp nhanh preset: 10.000, 20.000, 50.000, 100.000.
- Chọn phương thức thanh toán: Tiền mặt vs Chuyển khoản QR.
- Thẻ tính toán trước số dư mới (Số dư hiện tại + Tiền nạp = Số dư mới).
- Gọi service wallet: top_up().
"""

from __future__ import annotations

import logging
from typing import Any

import customtkinter as ctk

from ...domain.dtos import CustomerSummary
from ...domain.enums import AccountStatus, CustomerStatus, PaymentMethod
from ...domain.exceptions import ApplicationError
from ..components import ActionButton, ToastManager
from ..formatters import format_money
from ..icons import get_icon
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
    STITCH_CHIP_BG,
    STITCH_CHIP_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_INPUT_BG,
    STITCH_INPUT_BORDER,
    STITCH_NAV_ACTIVE_BG,
    STITCH_NAV_ACTIVE_BORDER,
    STITCH_RADIUS,
    STITCH_SUCCESS,
    STITCH_SUNKEN_BG,
    STITCH_SUNKEN_BORDER,
    STITCH_TEXT,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_ON_CYAN,
    STITCH_TEXT_STRONG,
)

logger = logging.getLogger(__name__)

PRESET_AMOUNTS = [10_000, 20_000, 50_000, 100_000]


class TopUpDialog(ctk.CTkToplevel):
    """Hộp thoại modal nạp tiền vào ví khách hàng."""

    def __init__(
        self,
        parent: Any,
        services: Any,
        customer: CustomerSummary,
        *,
        employee_id: int,
        language: str = "vi",
        on_success: Any = None,
    ) -> None:
        super().__init__(parent)
        self._services = services
        self._customer = customer
        self._employee_id = employee_id
        self._language = language
        self._on_success = on_success

        self._selected_method = PaymentMethod.CASH
        self._selected_amount = 0
        self._is_submitting = False

        is_vi = language == "vi"
        self.title("Nạp tiền vào tài khoản" if is_vi else "Top Up Account")
        self.geometry("540x600")
        self.resizable(False, False)
        self.configure(fg_color=STITCH_BG_CANVAS)

        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self.bind("<Escape>", lambda _e: self._on_escape())
        self.bind("<Return>", lambda _e: self._handle_top_up())
        self.after(50, lambda: self._amount_entry.focus_set() if hasattr(self, "_amount_entry") else None)

    def _on_escape(self) -> None:
        if not self._is_submitting:
            self.destroy()

    def _build_ui(self) -> None:
        is_vi = self._language == "vi"

        # Khung viền ngoài (w-[540px] bg-[#0E131E] border border-[#232938] rounded-xl)
        card = ctk.CTkFrame(
            self,
            fg_color="#0E131E",
            border_width=1,
            border_color="#232938",
            corner_radius=12,
        )
        card.pack(fill="both", expand=True, padx=8, pady=8)

        # 1. Header (px-5 py-4 border-b border-[#212b3e] bg-[#111726])
        header = ctk.CTkFrame(card, fg_color="#111726", corner_radius=0, height=58)
        header.pack(fill="x")
        header.pack_propagate(False)

        h_inner = ctk.CTkFrame(header, fg_color="transparent")
        h_inner.pack(fill="both", expand=True, padx=16, pady=10)

        # Icon box
        icon_box = ctk.CTkLabel(
            h_inner,
            text="",
            image=get_icon("wallet", STITCH_CYAN, size=(18, 18)),
            width=36,
            height=36,
            corner_radius=8,
            fg_color="#0C2E40",
        )
        icon_box.pack(side="left")

        # Title & Subtitle
        text_box = ctk.CTkFrame(h_inner, fg_color="transparent")
        text_box.pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            text_box,
            text="Nạp tiền" if is_vi else "Top Up",
            font=FONT_ST_PAGE_TITLE,
            text_color=STITCH_TEXT_STRONG,
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            text_box,
            text="Cộng số dư và ghi nhận lịch sử giao dịch" if is_vi else "Add balance and record transaction history",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w")

        # Close X button
        close_btn = ctk.CTkButton(
            h_inner,
            text="",
            image=get_icon("close", STITCH_TEXT_MUTED, size=(14, 14)),
            width=28,
            height=28,
            corner_radius=6,
            fg_color="transparent",
            hover_color="#1E273A",
            command=self.destroy,
        )
        close_btn.pack(side="right")

        # 2. Form Body (p-5 space-y-4)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # Khối thông tin khách hàng (bg-[#141926] border border-[#232938] rounded-lg p-3)
        cust_box = ctk.CTkFrame(
            body,
            fg_color="#141926",
            border_width=1,
            border_color="#232938",
            corner_radius=8,
        )
        cust_box.pack(fill="x", pady=(0, 10))

        c_inner = ctk.CTkFrame(cust_box, fg_color="transparent")
        c_inner.pack(fill="x", padx=12, pady=8)

        # Row 1: Khách hàng & Mã KH
        c_row1 = ctk.CTkFrame(c_inner, fg_color="transparent")
        c_row1.pack(fill="x", pady=1)

        left1 = ctk.CTkFrame(c_row1, fg_color="transparent")
        left1.pack(side="left")
        ctk.CTkLabel(left1, text="Khách hàng: " if is_vi else "Customer: ", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(side="left")
        ctk.CTkLabel(left1, text=self._customer.full_name, font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT_STRONG).pack(side="left")

        cust_code = getattr(self._customer, "customer_code", getattr(self._customer, "code", "CUS-0001"))
        ctk.CTkLabel(
            c_row1,
            text=cust_code,
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_CYAN,
            fg_color="#171F30",
            corner_radius=4,
            padx=6,
            pady=2,
        ).pack(side="right")

        # Row 2: Tài khoản & Mã TK
        c_row2 = ctk.CTkFrame(c_inner, fg_color="transparent")
        c_row2.pack(fill="x", pady=1)

        left2 = ctk.CTkFrame(c_row2, fg_color="transparent")
        left2.pack(side="left")
        ctk.CTkLabel(left2, text="Tài khoản: " if is_vi else "Account: ", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(side="left")
        cust_user = getattr(self._customer, "username", "—")
        ctk.CTkLabel(left2, text=cust_user, font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT).pack(side="left")

        acc_id = getattr(self._customer, "account_id", 0)
        ctk.CTkLabel(
            c_row2,
            text=f"Mã TK: ACC-{acc_id:04d}",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="right")

        # Row 3 (Divider): Số dư hiện tại & Trạng thái KH/TK
        c_row3 = ctk.CTkFrame(c_inner, fg_color="transparent")
        c_row3.pack(fill="x", pady=(4, 0))

        left3 = ctk.CTkFrame(c_row3, fg_color="transparent")
        left3.pack(side="left")
        ctk.CTkLabel(left3, text="Số dư hiện tại: " if is_vi else "Current Balance: ", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(side="left")
        ctk.CTkLabel(left3, text=format_money(self._customer.balance), font=FONT_ST_BODY_STRONG, text_color=STITCH_CYAN).pack(side="left")

        right3 = ctk.CTkFrame(c_row3, fg_color="transparent")
        right3.pack(side="right")

        is_cust_active = self._customer.customer_status == CustomerStatus.ACTIVE
        st_cust_txt = "KH: Hoạt động" if is_cust_active else "KH: Ngừng HĐ"
        st_cust_fg = STITCH_SUCCESS if is_cust_active else STITCH_DANGER
        st_cust_bg = "#0A2918" if is_cust_active else "#251724"

        is_acc_active = self._customer.account_status == AccountStatus.ACTIVE
        st_acc_txt = "TK: Hoạt động" if is_acc_active else "TK: Đã khóa"
        st_acc_fg = STITCH_SUCCESS if is_acc_active else STITCH_DANGER
        st_acc_bg = "#0A2918" if is_acc_active else "#251724"

        ctk.CTkLabel(
            right3,
            text=st_acc_txt,
            font=FONT_ST_MONO_XS_STRONG,
            text_color=st_acc_fg,
            fg_color=st_acc_bg,
            corner_radius=4,
            padx=6,
            pady=1,
        ).pack(side="right", padx=(4, 0))

        ctk.CTkLabel(
            right3,
            text=st_cust_txt,
            font=FONT_ST_MONO_XS_STRONG,
            text_color=st_cust_fg,
            fg_color=st_cust_bg,
            corner_radius=4,
            padx=6,
            pady=1,
        ).pack(side="right")

        # Section: Số tiền nạp
        amt_sec = ctk.CTkFrame(body, fg_color="transparent")
        amt_sec.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            amt_sec,
            text="Số tiền nạp *" if is_vi else "Amount to top up *",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT,
            anchor="w",
        ).pack(anchor="w", pady=(0, 4))

        # Entry row with right VND chip
        self._entry_wrap = ctk.CTkFrame(
            amt_sec,
            fg_color="#131926",
            border_width=1,
            border_color="#263147",
            corner_radius=6,
            height=34,
        )
        self._entry_wrap.pack(fill="x")
        self._entry_wrap.pack_propagate(False)

        self._amount_entry = ctk.CTkEntry(
            self._entry_wrap,
            font=FONT_ST_METRIC_LG,
            text_color=STITCH_TEXT_STRONG,
            placeholder_text="Nhập số tiền" if is_vi else "Enter amount",
            fg_color="transparent",
            border_width=0,
            justify="right",
        )
        self._amount_entry.pack(side="left", fill="both", expand=True, padx=(8, 4))
        if self._selected_amount > 0:
            self._amount_entry.insert(0, f"{self._selected_amount:,}".replace(",", "."))
        self._amount_entry.bind("<KeyRelease>", lambda _e: self._on_entry_changed())

        # Chip VND
        ctk.CTkLabel(
            self._entry_wrap,
            text="VND",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_TEXT_MUTED,
            fg_color="#1C2436",
            corner_radius=4,
            padx=8,
            pady=2,
        ).pack(side="right", padx=6)

        self._note_label = ctk.CTkLabel(
            amt_sec,
            text="Số tiền phải là số nguyên dương và không vượt quá 100.000.000 VND." if is_vi else "Amount must be a positive integer and not exceed 100,000,000 VND.",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
        )
        self._note_label.pack(anchor="w", pady=(2, 0))

        self._err_label = ctk.CTkLabel(
            amt_sec,
            text="",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_DANGER,
            anchor="w",
        )
        self._err_label.pack(anchor="w", pady=(2, 0))
        self._err_label.pack_forget()

        # 4 Quick Preset Buttons
        preset_row = ctk.CTkFrame(body, fg_color="transparent")
        preset_row.pack(fill="x", pady=(0, 10))
        for col_idx in range(len(PRESET_AMOUNTS)):
            preset_row.grid_columnconfigure(col_idx, weight=1)

        self._preset_buttons: dict[int, ctk.CTkButton] = {}
        for idx, amt in enumerate(PRESET_AMOUNTS):
            lbl_txt = f"{amt:,}".replace(",", ".")
            b = ctk.CTkButton(
                preset_row,
                text=lbl_txt,
                height=28,
                corner_radius=STITCH_RADIUS,
                font=FONT_ST_MONO_SM,
                command=lambda a=amt: self._on_preset_click(a),
            )
            b.grid(row=0, column=idx, padx=3, sticky="nsew")
            self._preset_buttons[amt] = b

        # Section: Phương thức thanh toán
        m_sec = ctk.CTkFrame(body, fg_color="transparent")
        m_sec.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            m_sec,
            text="Phương thức thanh toán" if is_vi else "Payment Method",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT,
            anchor="w",
        ).pack(anchor="w", pady=(0, 4))

        m_btn_row = ctk.CTkFrame(m_sec, fg_color="transparent")
        m_btn_row.pack(fill="x")
        m_btn_row.grid_columnconfigure(0, weight=1)
        m_btn_row.grid_columnconfigure(1, weight=1)

        self._btn_cash = ctk.CTkButton(
            m_btn_row,
            text="💵  Tiền mặt" if is_vi else "💵  Cash",
            height=32,
            corner_radius=STITCH_RADIUS,
            command=lambda: self._set_method(PaymentMethod.CASH),
        )
        self._btn_cash.grid(row=0, column=0, padx=(0, 4), sticky="nsew")

        self._btn_transfer = ctk.CTkButton(
            m_btn_row,
            text="📱  Chuyển khoản QR" if is_vi else "📱  QR Transfer",
            height=32,
            corner_radius=STITCH_RADIUS,
            command=lambda: self._set_method(PaymentMethod.TRANSFER),
        )
        self._btn_transfer.grid(row=0, column=1, padx=(4, 0), sticky="nsew")

        # Preview calculation box (bg-[#0a0e17] border border-[#1f273a] rounded-lg p-3)
        prev_box = ctk.CTkFrame(
            body,
            fg_color="#0A0E17",
            border_width=1,
            border_color="#1F273A",
            corner_radius=8,
        )
        prev_box.pack(fill="x")

        p_inner = ctk.CTkFrame(prev_box, fg_color="transparent")
        p_inner.pack(fill="x", padx=12, pady=8)

        # Row: Số dư hiện tại
        pr1 = ctk.CTkFrame(p_inner, fg_color="transparent")
        pr1.pack(fill="x", pady=1)
        ctk.CTkLabel(pr1, text="Số dư hiện tại" if is_vi else "Current Balance", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(side="left")
        ctk.CTkLabel(pr1, text=format_money(self._customer.balance), font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT).pack(side="right")

        # Row: Số tiền nạp
        pr2 = ctk.CTkFrame(p_inner, fg_color="transparent")
        pr2.pack(fill="x", pady=1)
        ctk.CTkLabel(pr2, text="Số tiền nạp" if is_vi else "Top-up Amount", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED).pack(side="left")
        amt_text = f"+{format_money(self._selected_amount)}" if self._selected_amount > 0 else "—"
        amt_color = STITCH_SUCCESS if self._selected_amount > 0 else STITCH_TEXT_MUTED
        self._preview_amount_lbl = ctk.CTkLabel(pr2, text=amt_text, font=FONT_ST_BODY_STRONG, text_color=amt_color)
        self._preview_amount_lbl.pack(side="right")

        # Row: Số dư mới (border-t)
        pr3 = ctk.CTkFrame(p_inner, fg_color="transparent")
        pr3.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(pr3, text="Số dư mới" if is_vi else "New Balance", font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT_STRONG).pack(side="left")
        new_bal = self._customer.balance + self._selected_amount
        bal_text = format_money(new_bal) if self._selected_amount > 0 else "—"
        bal_color = STITCH_CYAN if self._selected_amount > 0 else STITCH_TEXT_MUTED
        self._preview_new_bal_lbl = ctk.CTkLabel(pr3, text=bal_text, font=FONT_ST_BODY_STRONG, text_color=bal_color)
        self._preview_new_bal_lbl.pack(side="right")

        # 3. Footer (px-5 py-3.5 bg-[#0b101b] border-t border-[#212b3e])
        footer = ctk.CTkFrame(card, fg_color="#0B101B", corner_radius=0, height=50)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        foot_inner = ctk.CTkFrame(footer, fg_color="transparent")
        foot_inner.pack(fill="both", expand=True, padx=16, pady=8)

        self._hint_lbl = ctk.CTkLabel(
            foot_inner,
            text="Nhấn Enter để nạp • Esc để hủy" if is_vi else "Press Enter to top up • Esc to cancel",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        )
        self._hint_lbl.pack(side="left")

        self._cancel_btn = ActionButton(
            foot_inner,
            text="Hủy" if is_vi else "Cancel",
            kind="ghost",
            width=80,
            command=self.destroy,
        )
        self._cancel_btn.pack(side="right", padx=(8, 0))

        self._submit_btn = ActionButton(
            foot_inner,
            text="Xác nhận nạp tiền" if is_vi else "Confirm Top Up",
            kind="primary",
            width=150,
            command=self._handle_top_up,
        )
        self._submit_btn.pack(side="right")

        self._refresh_styles()
        if self._selected_amount == 0:
            self._submit_btn.set_enabled(False)

    def _on_preset_click(self, amount: int) -> None:
        self._selected_amount = amount
        self._amount_entry.delete(0, "end")
        self._amount_entry.insert(0, f"{amount:,}".replace(",", "."))
        self._entry_wrap.configure(border_color="#263147")
        self._err_label.configure(text="")
        self._err_label.pack_forget()
        self._note_label.pack(anchor="w", pady=(2, 0))
        self._update_preview(amount)
        self._refresh_styles()
        self._submit_btn.set_enabled(True)

    def _on_entry_changed(self) -> None:
        is_vi = self._language == "vi"
        raw = self._amount_entry.get().replace(".", "").replace(",", "").strip()
        if not raw:
            self._entry_wrap.configure(border_color="#263147")
            self._err_label.configure(text="")
            self._err_label.pack_forget()
            self._note_label.pack(anchor="w", pady=(2, 0))
            self._selected_amount = 0
            self._update_preview(0)
            self._submit_btn.set_enabled(False)
            self._refresh_styles()
            return

        try:
            val = int(raw)
            if val <= 0 or val > 100_000_000:
                self._entry_wrap.configure(border_color=STITCH_DANGER)
                err_text = (
                    "Số tiền nạp phải từ 1 đến 100.000.000 VND."
                    if is_vi
                    else "Amount must be from 1 to 100.000.000 VND."
                )
                self._note_label.pack_forget()
                self._err_label.configure(text=f"⚠  {err_text}")
                self._err_label.pack(anchor="w", pady=(2, 0))
                self._selected_amount = 0
                self._update_preview(0)
                self._submit_btn.set_enabled(False)
            else:
                self._entry_wrap.configure(border_color="#263147")
                self._err_label.configure(text="")
                self._err_label.pack_forget()
                self._note_label.pack(anchor="w", pady=(2, 0))
                self._selected_amount = val
                self._update_preview(val)
                self._submit_btn.set_enabled(True)
        except ValueError:
            self._entry_wrap.configure(border_color=STITCH_DANGER)
            err_text = "Vui lòng nhập số hợp lệ" if is_vi else "Please enter a valid amount"
            self._note_label.pack_forget()
            self._err_label.configure(text=f"⚠  {err_text}")
            self._err_label.pack(anchor="w", pady=(2, 0))
            self._selected_amount = 0
            self._update_preview(0)
            self._submit_btn.set_enabled(False)
        self._refresh_styles()

    def _update_preview(self, amount: int) -> None:
        if amount > 0:
            self._preview_amount_lbl.configure(text=f"+{format_money(amount)}", text_color=STITCH_SUCCESS)
            new_bal = self._customer.balance + amount
            self._preview_new_bal_lbl.configure(text=format_money(new_bal), text_color=STITCH_CYAN)
        else:
            self._preview_amount_lbl.configure(text="—", text_color=STITCH_TEXT_MUTED)
            self._preview_new_bal_lbl.configure(text="—", text_color=STITCH_TEXT_MUTED)

    def _set_method(self, method: PaymentMethod) -> None:
        self._selected_method = method
        self._refresh_styles()

    def _refresh_styles(self) -> None:
        # Presets styles
        for amt, btn in self._preset_buttons.items():
            active = amt == self._selected_amount
            btn.configure(
                fg_color=STITCH_CYAN if active else "#171D2B",
                hover_color=STITCH_CYAN if active else "#1F273A",
                border_width=0 if active else 1,
                border_color="#2A3246",
                text_color=STITCH_TEXT_ON_CYAN if active else STITCH_TEXT,
            )

        # Payment method styles
        is_cash = self._selected_method == PaymentMethod.CASH
        self._btn_cash.configure(
            fg_color="#0C2E40" if is_cash else "#171D2B",
            hover_color="#0C2E40" if is_cash else "#1F273A",
            border_width=1,
            border_color=STITCH_CYAN if is_cash else "#2A3246",
            text_color=STITCH_CYAN if is_cash else STITCH_TEXT_MUTED,
            font=FONT_ST_BODY_STRONG,
        )
        self._btn_transfer.configure(
            fg_color="#0C2E40" if not is_cash else "#171D2B",
            hover_color="#0C2E40" if not is_cash else "#1F273A",
            border_width=1,
            border_color=STITCH_CYAN if not is_cash else "#2A3246",
            text_color=STITCH_CYAN if not is_cash else STITCH_TEXT_MUTED,
            font=FONT_ST_BODY_STRONG,
        )

    def _handle_top_up(self) -> None:
        if self._is_submitting:
            return

        is_vi = self._language == "vi"
        raw_val = self._amount_entry.get().replace(".", "").replace(",", "").strip()
        try:
            amount = int(raw_val)
            if amount <= 0 or amount > 100_000_000:
                raise ValueError()
        except ValueError:
            self._entry_wrap.configure(border_color=STITCH_DANGER)
            err_text = (
                "Số tiền nạp phải từ 1 đến 100.000.000 VND."
                if is_vi
                else "Amount must be from 1 to 100.000.000 VND."
            )
            self._note_label.pack_forget()
            self._err_label.configure(text=f"⚠  {err_text}")
            self._err_label.pack(anchor="w", pady=(2, 0))
            self._submit_btn.set_enabled(False)
            return

        self._is_submitting = True
        self._amount_entry.configure(state="disabled")
        for btn in self._preset_buttons.values():
            btn.configure(state="disabled")
        self._btn_cash.configure(state="disabled")
        self._btn_transfer.configure(state="disabled")

        self._entry_wrap.configure(border_color="#263147")
        self._err_label.configure(text="")
        self._err_label.pack_forget()
        self._note_label.pack(anchor="w", pady=(2, 0))

        self._hint_lbl.configure(text="Đang xử lý giao dịch..." if is_vi else "Processing transaction...")
        self._cancel_btn.set_enabled(False)
        self._submit_btn.configure(text="Đang nạp…")
        self._submit_btn.set_busy(True)

        try:
            self._services.wallet.top_up(
                customer_id=self._customer.customer_id,
                amount=amount,
                method=self._selected_method,
                employee_id=self._employee_id,
            )
            ToastManager.show(
                self.master,
                f"Đã nạp thành công {format_money(amount)} cho {self._customer.full_name}!"
                if is_vi
                else f"Successfully topped up {format_money(amount)} for {self._customer.full_name}!",
                kind="success",
            )
            if self._on_success:
                self._on_success()
            self.destroy()
        except ApplicationError as err:
            logger.warning("Lỗi nạp tiền: %s", err)
            ToastManager.show(self, get_user_friendly_error(err), kind="error")
        except Exception:
            logger.exception("Lỗi không mong muốn khi nạp tiền")
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")
        finally:
            if self.winfo_exists():
                self._is_submitting = False
                self._amount_entry.configure(state="normal")
                for btn in self._preset_buttons.values():
                    btn.configure(state="normal")
                self._btn_cash.configure(state="normal")
                self._btn_transfer.configure(state="normal")
                self._cancel_btn.set_enabled(True)
                self._submit_btn.set_busy(False)
                self._submit_btn.configure(text="Xác nhận nạp tiền" if is_vi else "Confirm Top Up")
                self._hint_lbl.configure(text="Nhấn Enter để nạp • Esc để hủy" if is_vi else "Press Enter to top up • Esc to cancel")
