"""NG-04 — Dialog Nạp tiền theo Stitch (`n_p_ti_n_default`, `n_p_ti_n_valid_preview`,
`n_p_ti_n_validation_error`, `n_p_ti_n_submitting`).

- Thẻ khách: tên, mã KH, tên đăng nhập, mã TK, số dư hiện tại, trạng thái KH/TK.
- Số tiền nạp (WAL-01: nguyên dương, tối đa 100.000.000 VND/lần), nút chọn nhanh 10k/20k/50k/100k.
- Phương thức Tiền mặt / Chuyển khoản (WAL-03: chỉ ghi nhận, không tích hợp cổng thật).
- Xem trước "Số dư mới" chỉ để hiển thị; số dư thật lấy từ TopUpResult service trả về.
- Tài khoản bị khóa vẫn được nạp để trả nợ (quyết định LI-04), dialog không chặn.
- Gọi wallet.top_up(customer_id, amount, method, employee_id) với nhân viên đang đăng nhập (AUTH-02).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ...domain.dtos import CustomerSummary, TopUpResult
from ...domain.enums import AccountStatus, CustomerStatus, PaymentMethod
from ..app_shell import ViewContext
from ..i18n import UIStrings
from ..background import TaskRunner, default_runner
from ..components import ToastManager
from ..components.stitch_field import StitchField
from ..feedback import notify_error
from ..formatters import format_money
from ..messages import FIELD_ERROR_MESSAGES, get_field_errors_safe, get_user_friendly_error
from ..theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_MONO_11,
    FONT_ST_MONO_BODY,
    FONT_ST_MONO_SM,
    FONT_ST_MONO_VALUE,
    STITCH_BADGE_DANGER_BG,
    STITCH_BADGE_DANGER_BORDER,
    STITCH_BADGE_SUCCESS_BG,
    STITCH_BADGE_SUCCESS_BORDER,
    STITCH_BG_CANVAS,
    STITCH_BORDER,
    STITCH_CHIP_BG,
    STITCH_CHIP_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_NAV_ACTIVE_BG,
    STITCH_NAV_ACTIVE_BORDER,
    STITCH_RADIUS,
    STITCH_RADIUS_LG,
    STITCH_SUCCESS,
    STITCH_TAB_HOVER,
    STITCH_TEXT,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
)
from .stitch_dialog import StitchDialog, chip, divider

MAX_TOP_UP = 100_000_000  # WAL-01
QUICK_AMOUNTS = (10_000, 20_000, 50_000, 100_000)
INVALID_AMOUNT = FIELD_ERROR_MESSAGES["INVALID_AMOUNT"]
MAX_EXCEEDED = FIELD_ERROR_MESSAGES["MAX_TOP_UP_EXCEEDED"]
METHOD_LABELS = {PaymentMethod.CASH: "💵  Tiền mặt", PaymentMethod.TRANSFER: "⇄  Chuyển khoản"}
_SEPARATORS = re.compile(r"[\s.,_]|vnd|đ", re.IGNORECASE)


def parse_amount(text: str) -> int | None:
    """'50.000' / '50,000 VND' / '50000' -> 50000; rỗng, chữ, số âm -> None."""
    cleaned = _SEPARATORS.sub("", text)
    return int(cleaned) if cleaned.isdigit() else None


def validate_amount(text: str) -> tuple[int | None, str | None]:
    """(số tiền, lỗi). Lỗi là None khi hợp lệ theo WAL-01."""
    amount = parse_amount(text)
    if amount is None or amount <= 0:
        return None, INVALID_AMOUNT
    if amount > MAX_TOP_UP:
        return None, MAX_EXCEEDED
    return amount, None


def format_amount_input(amount: int, language: str = "vi") -> str:
    return f"{amount:,}" if language == "en" else f"{amount:,}".replace(",", ".")


class TopUpDialog(StitchDialog):
    def __init__(
        self,
        parent: Any,
        context: ViewContext,
        customer: CustomerSummary,
        *,
        account_code: str = "",
        runner: TaskRunner | None = None,
        on_success: Callable[[TopUpResult], None] | None = None,
    ) -> None:
        self._t = UIStrings(context.language)
        super().__init__(
            parent,
            language=context.language,
            title=self._t('Nạp tiền'),
            subtitle=self._t('Cộng số dư và ghi nhận lịch sử giao dịch'),
            icon="▭",
            width=580,
            hint=self._t('Nhấn Enter để nạp • Esc để hủy'),
            confirm_text=self._t('Xác nhận nạp tiền'),
        )
        self._context = context
        self._customer = customer
        self._runner = runner or default_runner()
        self._on_success_callback = on_success
        self._method = PaymentMethod.CASH
        self._quick_buttons: dict[int, ctk.CTkButton] = {}
        self._method_buttons: dict[PaymentMethod, ctk.CTkButton] = {}

        self._build_customer_card(account_code)
        self.amount_field = StitchField(
            self.body,
            self._t('Số tiền nạp'),
            placeholder="0",
            suffix="VND",
            mono=True,
            justify="right",
            uppercase_label=False,
            hint=self._t('Số tiền phải là số nguyên dương và không vượt quá 100.000.000 VND.'),
        )
        self.amount_field.pack(fill="x", pady=(14, 0))
        self.amount_field.bind_change(self._refresh_preview)
        self._build_quick_amounts()
        self._build_methods()
        self._build_preview()
        self._refresh_preview()
        self.finish(focus=self.amount_field.focus)

    # ------------------------------------------------------------------
    @property
    def method(self) -> PaymentMethod:
        return self._method

    def _build_customer_card(self, account_code: str) -> None:
        customer = self._customer
        card = ctk.CTkFrame(self.body, fg_color=STITCH_BG_CANVAS, border_width=1, border_color=STITCH_BORDER, corner_radius=STITCH_RADIUS_LG)
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=self._t('Khách hàng: '), font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=20).pack(side="left")
        ctk.CTkLabel(top, text=customer.full_name, font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT_STRONG, height=20).pack(side="left")
        code = ctk.CTkFrame(top, fg_color=STITCH_CHIP_BG, border_width=1, border_color=STITCH_CHIP_BORDER, corner_radius=STITCH_RADIUS)
        code.pack(side="right")
        ctk.CTkLabel(code, text=customer.customer_code, font=FONT_ST_MONO_11, text_color=STITCH_CYAN, height=18).pack(padx=8)

        second = ctk.CTkFrame(inner, fg_color="transparent")
        second.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(second, text=self._t('Tài khoản: '), font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=20).pack(side="left")
        ctk.CTkLabel(second, text=customer.username, font=FONT_ST_MONO_BODY, text_color=STITCH_TEXT, height=20).pack(side="left")
        ctk.CTkLabel(second, text=self._t('Mã TK: {v0}', v0=f"{account_code or '—'}"), font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED, height=20).pack(side="right")

        divider(inner, pady=(8, 8))
        third = ctk.CTkFrame(inner, fg_color="transparent")
        third.pack(fill="x")
        ctk.CTkLabel(third, text=self._t('Số dư hiện tại: '), font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=20).pack(side="left")
        ctk.CTkLabel(
            third,
            text=format_money(customer.balance, language=self._t.language),
            font=FONT_ST_MONO_SM,
            text_color=STITCH_DANGER if customer.balance < 0 else STITCH_CYAN,
            height=20,
        ).pack(side="left")
        account_ok = customer.account_status == AccountStatus.ACTIVE
        customer_ok = customer.customer_status == CustomerStatus.ACTIVE
        for text, ok in ((self._t('TK: ') + (self._t('Hoạt động') if account_ok else self._t('Đã khóa')), account_ok), (self._t('KH: ') + (self._t('Hoạt động') if customer_ok else self._t('Ngừng')), customer_ok)):
            colors = (STITCH_SUCCESS, STITCH_BADGE_SUCCESS_BG, STITCH_BADGE_SUCCESS_BORDER) if ok else (STITCH_DANGER, STITCH_BADGE_DANGER_BG, STITCH_BADGE_DANGER_BORDER)
            chip(third, text, *colors).pack(side="right", padx=(6, 0))

    def _build_quick_amounts(self) -> None:
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", pady=(10, 0))
        for index, amount in enumerate(QUICK_AMOUNTS):
            row.grid_columnconfigure(index, weight=1, uniform="quick")
            button = ctk.CTkButton(
                row,
                text=format_amount_input(amount, self._t.language),
                height=30,
                corner_radius=STITCH_RADIUS,
                border_width=1,
                font=FONT_ST_MONO_11,
                command=lambda a=amount: self.set_amount(a),
            )
            button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 4, 0))
            self._quick_buttons[amount] = button

    def _build_methods(self) -> None:
        ctk.CTkLabel(self.body, text=self._t('Phương thức nạp tiền'), font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT, anchor="w", height=18).pack(
            fill="x", pady=(14, 6)
        )
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x")
        for index, method in enumerate((PaymentMethod.CASH, PaymentMethod.TRANSFER)):
            row.grid_columnconfigure(index, weight=1, uniform="method")
            button = ctk.CTkButton(
                row,
                text=self._t(METHOD_LABELS[method]),
                height=34,
                corner_radius=STITCH_RADIUS_LG,
                border_width=1,
                font=FONT_ST_BODY,
                command=lambda m=method: self.set_method(m),
            )
            button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 8, 0))
            self._method_buttons[method] = button
        self._method_note = ctk.CTkLabel(self.body, text="", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED, anchor="w", height=16)
        self._method_note.pack(fill="x", pady=(6, 0))
        self.set_method(PaymentMethod.CASH)

    def _build_preview(self) -> None:
        box = ctk.CTkFrame(self.body, fg_color=STITCH_BG_CANVAS, border_width=1, border_color=STITCH_BORDER, corner_radius=STITCH_RADIUS_LG)
        box.pack(fill="x", pady=(12, 0))
        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)
        self._preview: dict[str, ctk.CTkLabel] = {}
        for key, label in (("current", self._t('Số dư hiện tại')), ("amount", self._t('Số tiền nạp'))):
            line = ctk.CTkFrame(inner, fg_color="transparent")
            line.pack(fill="x", pady=1)
            ctk.CTkLabel(line, text=label, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=20).pack(side="left")
            self._preview[key] = ctk.CTkLabel(line, text="", font=FONT_ST_MONO_BODY, text_color=STITCH_TEXT, height=20)
            self._preview[key].pack(side="right")
        divider(inner, pady=(6, 6))
        line = ctk.CTkFrame(inner, fg_color="transparent")
        line.pack(fill="x")
        ctk.CTkLabel(line, text=self._t('Số dư mới'), font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT_STRONG, height=24).pack(side="left")
        self._preview["new"] = ctk.CTkLabel(line, text="", font=FONT_ST_MONO_VALUE, text_color=STITCH_SUCCESS, height=24)
        self._preview["new"].pack(side="right")

    # ------------------------------------------------------------------
    def set_amount(self, amount: int) -> None:
        self.amount_field.set_value(format_amount_input(amount, self._t.language))
        self.amount_field.set_error(None)
        self._refresh_preview()

    def set_method(self, method: PaymentMethod) -> None:
        self._method = method
        for key, button in self._method_buttons.items():
            active = key == method
            button.configure(
                fg_color=STITCH_NAV_ACTIVE_BG if active else STITCH_CHIP_BG,
                hover_color=STITCH_NAV_ACTIVE_BG if active else STITCH_TAB_HOVER,
                border_color=STITCH_NAV_ACTIVE_BORDER if active else STITCH_CHIP_BORDER,
                text_color=STITCH_CYAN if active else STITCH_TEXT,
                font=FONT_ST_BODY_STRONG if active else FONT_ST_BODY,
            )
        self._method_note.configure(
            text=self._t('ⓘ  Chuyển khoản được ghi nhận thủ công trong P0.') if method == PaymentMethod.TRANSFER else self._t('ⓘ  Nhận tiền mặt tại quầy.')
        )

    def _refresh_preview(self) -> None:
        amount = parse_amount(self.amount_field.get_value())
        valid = amount is not None and 0 < amount <= MAX_TOP_UP
        balance = self._customer.balance
        self._preview["current"].configure(text=format_money(balance, language=self._t.language))
        self._preview["amount"].configure(text=f"+{format_money(amount, language=self._t.language)}" if valid else "—", text_color=STITCH_SUCCESS if valid else STITCH_TEXT_MUTED)
        # Chỉ xem trước; số dư thật lấy từ TopUpResult.balance_after
        new_balance = balance + amount if valid and amount is not None else balance
        self._preview["new"].configure(text=format_money(new_balance, language=self._t.language), text_color=STITCH_DANGER if new_balance < 0 else STITCH_SUCCESS)
        for value, button in self._quick_buttons.items():
            active = valid and value == amount
            button.configure(
                fg_color=STITCH_NAV_ACTIVE_BG if active else STITCH_CHIP_BG,
                hover_color=STITCH_NAV_ACTIVE_BG if active else STITCH_TAB_HOVER,
                border_color=STITCH_NAV_ACTIVE_BORDER if active else STITCH_CHIP_BORDER,
                text_color=STITCH_CYAN if active else STITCH_TEXT_MUTED,
            )

    @property
    def preview_new_balance(self) -> str:
        return str(self._preview["new"].cget("text"))

    # ------------------------------------------------------------------
    def submit(self) -> None:
        if self.is_submitting:
            return
        self.amount_field.set_error(None)
        amount, error = validate_amount(self.amount_field.get_value())
        if error is not None or amount is None:
            self.amount_field.set_error(error)
            self.amount_field.focus()
            return
        self.set_submitting(True)
        wallet, session = self._context.services.wallet, self._context.session
        customer_id, method = self._customer.customer_id, self._method
        self._runner.submit(
            self,
            lambda: wallet.top_up(customer_id, amount, method, session.employee_id),
            self._on_success,
            self._on_error,
        )

    def _on_success(self, result: TopUpResult) -> None:
        self.set_submitting(False)
        callback = self._on_success_callback
        self.close()
        if callback is not None:
            callback(result)

    def _on_error(self, error: Exception) -> None:
        self.set_submitting(False)
        field_errors = get_field_errors_safe(error)
        if "amount" in field_errors:
            self.amount_field.set_error(field_errors["amount"])
            ToastManager.show(self, get_user_friendly_error(error), kind="error")
            return
        notify_error(self, error)
