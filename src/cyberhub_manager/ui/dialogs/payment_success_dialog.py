"""NG-06 — Dialog "Thanh toán thành công" (hóa đơn) theo Stitch
(`thanh_to_n_th_nh_c_ng_ti_n_m_t`, `thanh_to_n_th_nh_c_ng_chuy_n_kho_n_qr`).

Chỉ hiển thị CheckoutResult do service trả về (INV-05). Tiền khách đưa / tiền thừa là số liệu
UI-only từ CheckoutDialog, không lưu vào hóa đơn.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Any

import customtkinter as ctk

from ...domain.dtos import CheckoutResult
from ...domain.enums import PaymentMethod
from ..components import ToastManager
from ..i18n import UIStrings
from ..formatters import format_datetime, format_duration, format_money
from ..theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_LABEL_CAPS,
    FONT_ST_MONO_11,
    FONT_ST_MONO_BODY,
    FONT_ST_MONO_SM,
    STITCH_BADGE_SUCCESS_BG,
    STITCH_BADGE_SUCCESS_BORDER,
    STITCH_BORDER,
    STITCH_CYAN,
    STITCH_EMERALD,
    STITCH_EMERALD_HOVER,
    STITCH_FONT_MONO,
    STITCH_RADIUS,
    STITCH_RADIUS_LG,
    STITCH_SUCCESS,
    STITCH_TEXT,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_ON_CYAN,
    STITCH_TEXT_STRONG,
)
from .stitch_dialog import StitchDialog, chip, divider

CODE_COPIED = "Invoice code copied."
PANEL_BG = "#0D121F"
SUCCESS_PANEL_BG = "#0C1A1F"
FONT_TOTAL = (STITCH_FONT_MONO, 13, "bold")
METHOD_TEXT = {PaymentMethod.CASH: "tiền mặt", PaymentMethod.TRANSFER: "chuyển khoản"}


@dataclass(frozen=True)
class ConfirmLine:
    """Một dòng ✓ trong khung "Hệ thống xác nhận hoàn tất": (đậm, thường, mã cyan, đuôi)."""

    strong: str
    text: str
    code: str = ""
    tail: str = ""


def confirmation_lines(result: CheckoutResult, method: PaymentMethod | None, language: str = "vi") -> list[ConfirmLine]:
    invoice, session = result.invoice.invoice, result.invoice.session
    from_account = invoice.usage_cost - invoice.settlement_amount
    copy = UIStrings(language)
    lines = [
        ConfirmLine("", copy("Phiên sử dụng đã hoàn thành")),
        ConfirmLine("", copy("Máy {v0} đã chuyển về trạng thái ", v0=session.machine_code), "", copy("Trống")),
    ]
    if from_account > 0:
        lines.append(ConfirmLine(format_money(from_account, language), copy(" đã được trừ từ tài khoản khách hàng")))
    if invoice.settlement_amount > 0:
        if method == PaymentMethod.TRANSFER:
            lines.append(ConfirmLine(format_money(invoice.settlement_amount, language), copy(" chuyển khoản đã được nhân viên xác nhận")))
        else:
            lines.append(ConfirmLine(format_money(invoice.settlement_amount, language), copy(" tiền mặt đã được ghi nhận")))
    lines.append(ConfirmLine("", copy("Hóa đơn "), invoice.invoice_code, copy(" đã được tạo")))
    return lines


def _panel(master: Any, *, border: str = STITCH_BORDER, bg: str = PANEL_BG) -> ctk.CTkFrame:
    box = ctk.CTkFrame(master, fg_color=bg, border_width=1, border_color=border, corner_radius=STITCH_RADIUS_LG + 2)
    inner = ctk.CTkFrame(box, fg_color="transparent")
    inner.pack(fill="both", expand=True, padx=14, pady=11)
    return inner


def _row(master: Any, label: str, value: str, color: str = STITCH_TEXT, *, strong: bool = False) -> None:
    row = ctk.CTkFrame(master, fg_color="transparent")
    row.pack(fill="x", pady=2)
    ctk.CTkLabel(row, text=label, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=20).pack(side="left")
    ctk.CTkLabel(row, text=value, font=FONT_TOTAL if strong else FONT_ST_MONO_BODY, text_color=color, height=20).pack(side="right")


class PaymentSuccessDialog(StitchDialog):
    def __init__(
        self,
        parent: Any,
        result: CheckoutResult,
        *,
        username: str = "",
        method: PaymentMethod | None = None,
        cash_given: int | None = None,
        language: str = "vi",
    ) -> None:
        self._t = UIStrings(language)
        super().__init__(
            parent,
            language=language,
            title=self._t('Thanh toán thành công'),
            subtitle=self._t('Phiên đã kết thúc và hóa đơn đã được tạo'),
            icon="✓",
            icon_tone="success",
            width=860,
            hint=self._t('Esc để đóng'),
            confirm_text=self._t('✓  Đóng'),
            confirm_kind="primary",
            cancel_text=self._t('📋  Sao chép mã HĐ'),
            badge=self._t('ĐÃ THANH TOÁN'),
        )
        self._result = result
        self._method = method
        self.confirm_button.configure(
            width=110, fg_color=STITCH_EMERALD, hover_color=STITCH_EMERALD_HOVER, border_color=STITCH_EMERALD, text_color=STITCH_TEXT_ON_CYAN
        )
        self.cancel_button.configure(width=150, command=self.copy_invoice_code)

        detail = result.invoice
        invoice, session = detail.invoice, detail.session
        self._build_header_strip(invoice.invoice_code, session.session_code, format_datetime(invoice.created_at), invoice.employee_name)

        columns = ctk.CTkFrame(self.body, fg_color="transparent")
        columns.pack(fill="both", expand=True, pady=(12, 0))
        columns.grid_columnconfigure((0, 1), weight=1, uniform="receipt")
        left = ctk.CTkFrame(columns, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        machine = _panel(left)
        machine.master.pack(fill="x")
        top = ctk.CTkFrame(machine, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=session.machine_code, font=FONT_TOTAL, text_color=STITCH_TEXT_STRONG, height=22).pack(side="left")
        ctk.CTkLabel(top, text=f"  —  {session.machine_name}", font=FONT_ST_BODY, text_color=STITCH_TEXT, height=22).pack(side="left")
        chip(top, self._t('ĐÃ KẾT THÚC & TRỐNG'), STITCH_SUCCESS, STITCH_BADGE_SUCCESS_BG, STITCH_BADGE_SUCCESS_BORDER).pack(side="right")
        divider(machine, pady=(8, 6))
        _row(machine, self._t('Khách hàng:'), f"{session.customer_name} — {session.customer_code}", STITCH_TEXT_STRONG)
        _row(machine, self._t('Tài khoản:'), username or "—")
        _row(machine, self._t('Thời lượng:'), format_duration(detail.billed_minutes * 60, language=self._t.language))
        _row(machine, self._t('Đơn giá:'), self._t('{v0}/giờ', v0=f'{format_money(session.hourly_rate, language=self._t.language)}'))

        payment = _panel(left)
        payment.master.pack(fill="both", expand=True, pady=(12, 0))
        ctk.CTkLabel(payment, text=self._t('CHI TIẾT THANH TOÁN'), font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED, anchor="w", height=18).pack(fill="x")
        divider(payment, pady=(6, 6))
        settlement = invoice.settlement_amount
        _row(payment, self._t('Tổng chi phí phiên:'), format_money(invoice.usage_cost, language=self._t.language))
        _row(payment, self._t('Thanh toán từ số dư:'), format_money(invoice.usage_cost - settlement, language=self._t.language))
        if settlement > 0:
            label = self._t('Thanh toán chuyển khoản:') if method == PaymentMethod.TRANSFER else self._t('Thanh toán tiền mặt:')
            _row(payment, label, format_money(settlement, language=self._t.language), STITCH_TEXT_STRONG, strong=True)
            if method == PaymentMethod.CASH and cash_given is not None:
                _row(payment, self._t('Tiền khách đưa:'), format_money(cash_given, language=self._t.language))
                change = ctk.CTkFrame(
                    payment, fg_color=STITCH_BADGE_SUCCESS_BG, border_width=1, border_color=STITCH_BADGE_SUCCESS_BORDER, corner_radius=STITCH_RADIUS
                )
                change.pack(fill="x", pady=(4, 2))
                line = ctk.CTkFrame(change, fg_color="transparent")
                line.pack(fill="x", padx=8, pady=5)
                ctk.CTkLabel(line, text=self._t('Tiền thừa trả khách:'), font=FONT_ST_BODY_STRONG, text_color=STITCH_SUCCESS, height=20).pack(side="left")
                self._change_label = ctk.CTkLabel(
                    line, text=format_money(max(cash_given - settlement, 0), language=self._t.language), font=FONT_TOTAL, text_color=STITCH_SUCCESS, height=20
                )
                self._change_label.pack(side="right")
        divider(payment, pady=(6, 4))
        _row(payment, self._t('Số dư tài khoản còn lại:'), format_money(result.balance_after, language=self._t.language), STITCH_TEXT_STRONG, strong=True)

        self._build_confirmations(columns)
        self.finish(focus=self.confirm_button.focus_set)

    # ------------------------------------------------------------------
    @property
    def invoice_code(self) -> str:
        return self._result.invoice.invoice.invoice_code

    def _build_header_strip(self, invoice_code: str, session_code: str, created: str, cashier: str) -> None:
        strip = _panel(self.body)
        strip.master.pack(fill="x")
        strip.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="strip")
        cells = (
            (self._t('Mã hóa đơn'), invoice_code, STITCH_CYAN),
            (self._t('Mã phiên'), session_code, STITCH_TEXT_STRONG),
            (self._t('Thời gian'), created, STITCH_TEXT),
            (self._t('Thu ngân'), cashier, STITCH_TEXT_STRONG),
        )
        for column, (label, value, color) in enumerate(cells):
            cell = ctk.CTkFrame(strip, fg_color="transparent")
            cell.grid(row=0, column=column, sticky="w")
            ctk.CTkLabel(cell, text=label.upper(), font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED, height=16, anchor="w").pack(anchor="w")
            ctk.CTkLabel(cell, text=value, font=FONT_ST_MONO_SM, text_color=color, height=20, anchor="w").pack(anchor="w")

    def _build_confirmations(self, columns: ctk.CTkFrame) -> None:
        panel = _panel(columns, border=STITCH_BADGE_SUCCESS_BORDER, bg=SUCCESS_PANEL_BG)
        panel.master.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(
            panel, text=self._t('●  HỆ THỐNG XÁC NHẬN HOÀN TẤT'), font=FONT_ST_LABEL_CAPS, text_color=STITCH_SUCCESS, anchor="w", height=18
        ).pack(fill="x")
        divider(panel, pady=(6, 8))
        self._confirm_lines = confirmation_lines(self._result, self._method, language=self._t.language)
        for item in self._confirm_lines:
            line = ctk.CTkFrame(panel, fg_color="transparent")
            line.pack(fill="x", pady=4)
            ctk.CTkLabel(line, text="✓", font=FONT_ST_BODY_STRONG, text_color=STITCH_SUCCESS, width=18, height=20).pack(side="left")
            if item.strong:
                ctk.CTkLabel(line, text=item.strong, font=FONT_TOTAL, text_color=STITCH_TEXT_STRONG, height=20).pack(side="left", padx=(8, 0))
            ctk.CTkLabel(line, text=item.text, font=FONT_ST_BODY, text_color=STITCH_TEXT, height=20).pack(
                side="left", padx=(0 if item.strong else 8, 0)
            )
            if item.code:
                ctk.CTkLabel(line, text=item.code, font=FONT_ST_MONO_SM, text_color=STITCH_CYAN, height=20).pack(side="left")
            if item.tail:
                color = STITCH_SUCCESS if item.tail == self._t('Trống') else STITCH_TEXT
                ctk.CTkLabel(line, text=item.tail, font=FONT_ST_BODY, text_color=color, height=20).pack(side="left")
        spacer = ctk.CTkFrame(panel, fg_color="transparent", height=1)
        spacer.pack(fill="both", expand=True)
        status = ctk.CTkFrame(panel, fg_color=PANEL_BG, border_width=1, border_color=STITCH_BORDER, corner_radius=STITCH_RADIUS)
        status.pack(fill="x", side="bottom", pady=(10, 0))
        ctk.CTkLabel(status, text=self._t('Trạng thái: Giao dịch đã đồng bộ'), font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED, height=22).pack(
            side="left", padx=10, pady=3
        )
        ctk.CTkLabel(status, text=self._t('● THÀNH CÔNG'), font=FONT_ST_LABEL_CAPS, text_color=STITCH_SUCCESS, height=22).pack(side="right", padx=10, pady=3)

    # ------------------------------------------------------------------
    def copy_invoice_code(self) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append(self.invoice_code)
        except tk.TclError:
            return
        ToastManager.show(self, CODE_COPIED, kind="success")

    def submit(self) -> None:
        self.close()

    def cancel(self) -> None:  # Esc / ✕ = đóng (nút "Sao chép mã HĐ" có lệnh riêng)
        self.close()
