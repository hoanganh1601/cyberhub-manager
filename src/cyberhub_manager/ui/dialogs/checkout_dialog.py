"""NG-06 — Dialog "Xác nhận thanh toán" theo Stitch
(`x_c_nh_n_thanh_to_n_unified_v2`, `x_c_nh_n_thanh_to_n_ti_n_m_t`, `x_c_nh_n_thanh_to_n_chuy_n_kho_n_qr`).

- Mở dialog -> SessionService.preview_checkout(machine_id, current_time) chạy nền; UI không tự tính phí.
- Số dư đủ (settlement_required = 0): 1 cột chi phí + hộp xanh, nút đỏ "Xác nhận thanh toán";
  complete_checkout(settlement_amount=0, method=None).
- Cần bù: hộp đỏ "cần thanh toán thêm X" + cột Phương thức:
  * Tiền mặt: nhập "Khách đưa", tính tiền thừa (chỉ ở UI, không gửi service); đủ tiền mới bấm được.
  * Chuyển khoản QR: mã QR minh họa + nội dung CK; nhân viên tick "Đã xác nhận giao dịch" mới bấm được.
  complete_checkout(settlement_amount = settlement_required của preview mới nhất, method = CASH/TRANSFER).
- SettlementRequiredError (phí tăng vì qua phút mới) -> tính lại preview, giữ phương thức/tiền khách đưa.
- ConflictError (quầy khác đã thanh toán) -> alert, đóng dialog, dashboard làm mới.
- Thành công -> đóng, mở PaymentSuccessDialog (hóa đơn), gọi on_completed(result).
"""

from __future__ import annotations

import hashlib
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import customtkinter as ctk

from ...domain.dtos import CheckoutPreview, CheckoutResult, MachineSummary
from ...domain.enums import PaymentMethod
from ...domain.exceptions import ConflictError, SettlementRequiredError
from ...domain.models import Customer
from ..app_shell import ViewContext
from ..i18n import UIStrings
from ..background import TaskRunner, default_runner
from ..feedback import notify_error
from ..formatters import format_datetime, format_duration, format_money
from ..report_filters import service_now
from ..theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_LABEL_CAPS,
    FONT_ST_MONO_11,
    FONT_ST_MONO_BODY,
    FONT_ST_MONO_SM,
    FONT_ST_MONO_XS_STRONG,
    STITCH_BADGE_DANGER_BG,
    STITCH_BADGE_DANGER_BORDER,
    STITCH_BADGE_SUCCESS_BG,
    STITCH_BADGE_SUCCESS_BORDER,
    STITCH_BADGE_WARNING_BG,
    STITCH_BADGE_WARNING_BORDER,
    STITCH_BORDER,
    STITCH_CHIP_BG,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_FONT_MONO,
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
    STITCH_WARNING,
)
from .payment_success_dialog import PaymentSuccessDialog
from .stitch_dialog import StitchDialog, chip, divider
from .topup_dialog import format_amount_input, parse_amount

LOADING = "loading"
READY = "ready"

METHOD_LABELS = {PaymentMethod.CASH: "Tiền mặt", PaymentMethod.TRANSFER: "Chuyển khoản QR"}
PANEL_BG = "#0D121F"
INPUT_BG = "#090E19"
DISABLED_BG = "#1E293B"
ROSE_SOLID = "#E11D48"
ROSE_SOLID_HOVER = "#BE123C"
FONT_TOTAL = (STITCH_FONT_MONO, 13, "bold")
FONT_BIG = (STITCH_FONT_MONO, 16, "bold")


# ----------------------------------------------------------------------
# Hàm thuần (test được không cần Tk)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class CostBreakdown:
    usage_cost: int
    balance_before: int
    from_account: int  # phần phí trừ vào tài khoản
    settlement: int  # khách phải trả thêm (tiền mặt / chuyển khoản)
    balance_after: int  # số dư sau khi kết thúc


def cost_breakdown(preview: CheckoutPreview) -> CostBreakdown:
    settlement = preview.settlement_required
    return CostBreakdown(
        usage_cost=preview.usage_cost,
        balance_before=preview.balance_before,
        from_account=max(preview.usage_cost - settlement, 0),
        settlement=settlement,
        balance_after=preview.projected_balance + settlement,
    )


def change_due(cash_given: int | None, required: int) -> int | None:
    """Tiền thừa trả khách; None khi chưa nhập hoặc chưa đủ."""
    if cash_given is None or cash_given < required:
        return None
    return cash_given - required


def transfer_content(machine_code: str, customer_code: str) -> str:
    """Nội dung chuyển khoản như Stitch: "PC02-KH001"."""
    return f"{machine_code}-{customer_code}".replace(" ", "")


def qr_matrix(content: str, size: int = 21) -> list[list[bool]]:
    """Ma trận QR *minh họa* (không phải mã QR chuẩn) — POC chưa tích hợp cổng thanh toán.

    Có 3 ô định vị ở góc như QR thật; phần còn lại sinh ổn định từ nội dung.
    """
    bits = "".join(f"{byte:08b}" for byte in hashlib.sha256(content.encode("utf-8")).digest() * 2)
    matrix = [[bits[(r * size + c) % len(bits)] == "1" for c in range(size)] for r in range(size)]

    def finder(top: int, left: int) -> None:
        for r in range(7):
            for c in range(7):
                edge = r in (0, 6) or c in (0, 6)
                core = 2 <= r <= 4 and 2 <= c <= 4
                matrix[top + r][left + c] = edge or core
        for i in range(-1, 8):  # viền trắng quanh ô định vị
            for r, c in ((top - 1, left + i), (top + 7, left + i), (top + i, left - 1), (top + i, left + 7)):
                if 0 <= r < size and 0 <= c < size:
                    matrix[r][c] = False

    finder(0, 0)
    finder(0, size - 7)
    finder(size - 7, 0)
    return matrix


# ----------------------------------------------------------------------
# Widget nhỏ
# ----------------------------------------------------------------------
def _panel(master: Any, *, border: str = STITCH_BORDER, bg: str = PANEL_BG) -> ctk.CTkFrame:
    box = ctk.CTkFrame(master, fg_color=bg, border_width=1, border_color=border, corner_radius=STITCH_RADIUS_LG + 2)
    inner = ctk.CTkFrame(box, fg_color="transparent")
    inner.pack(fill="both", expand=True, padx=14, pady=11)
    return inner


def _caps(master: Any, text: str, color: str = STITCH_TEXT_MUTED) -> None:
    ctk.CTkLabel(master, text=text.upper(), font=FONT_ST_LABEL_CAPS, text_color=color, anchor="w", height=18).pack(fill="x")


def _money_row(master: Any, label: str, value: str, color: str = STITCH_TEXT, *, strong: bool = False) -> ctk.CTkLabel:
    row = ctk.CTkFrame(master, fg_color="transparent")
    row.pack(fill="x", pady=2)
    ctk.CTkLabel(row, text=label, font=FONT_ST_BODY_STRONG if strong else FONT_ST_BODY, text_color=STITCH_TEXT_STRONG if strong else STITCH_TEXT_MUTED, height=20).pack(side="left")
    value_label = ctk.CTkLabel(row, text=value, font=FONT_TOTAL if strong else FONT_ST_MONO_SM, text_color=color, height=20)
    value_label.pack(side="right")
    return value_label


class CheckoutDialog(StitchDialog):
    """Kết thúc phiên trên một máy IN_USE."""

    def __init__(
        self,
        parent: Any,
        context: ViewContext,
        machine: MachineSummary,
        *,
        runner: TaskRunner | None = None,
        now: Callable[[], datetime] | None = None,
        on_completed: Callable[[CheckoutResult], None] | None = None,
        on_conflict: Callable[[], None] | None = None,
    ) -> None:
        self._t = UIStrings(context.language)
        super().__init__(
            parent,
            language=context.language,
            title=self._t('Xác nhận thanh toán'),
            subtitle=self._t('Kiểm tra chi phí trước khi kết thúc phiên sử dụng'),
            icon="🧾",
            icon_tone="cyan",
            width=640,
            hint=self._t('Enter để xác nhận • Esc để hủy'),
            confirm_text=self._t('✓  Xác nhận thanh toán'),
            confirm_kind="primary",
            cancel_text=self._t('Hủy'),
        )
        self._context = context
        self._machine = machine
        self._runner = runner or default_runner()
        self._now = now or (lambda: service_now(context.services))
        self._on_completed = on_completed
        self._on_conflict = on_conflict

        self._phase = LOADING
        self._preview: CheckoutPreview | None = None
        self._username = ""
        self._method = PaymentMethod.CASH
        self._cash_text = ""
        self._transfer_confirmed = tk.BooleanVar(master=self, value=False)
        self._load_request = 0
        self._method_buttons: dict[PaymentMethod, ctk.CTkButton] = {}
        self._cash_entry: ctk.CTkEntry | None = None

        self.confirm_button.configure(width=190)
        self._content = ctk.CTkFrame(self.body, fg_color="transparent", height=1)
        self._content.pack(fill="both", expand=True)
        self.finish(focus=self.cancel_button.focus_set)
        self.reload()

    # ------------------------------------------------------------------
    # Thuộc tính công khai (test)
    # ------------------------------------------------------------------
    @property
    def phase(self) -> str:
        return self._phase

    @property
    def preview(self) -> CheckoutPreview | None:
        return self._preview

    @property
    def needs_settlement(self) -> bool:
        return self._preview is not None and self._preview.settlement_required > 0

    @property
    def method(self) -> PaymentMethod:
        return self._method

    @property
    def username(self) -> str:
        return self._username

    @property
    def cash_given(self) -> int | None:
        return parse_amount(self._cash_text) if self._cash_text.strip() else None

    @property
    def can_confirm(self) -> bool:
        if self._phase != READY or self._preview is None:
            return False
        if not self.needs_settlement:
            return True
        if self._method == PaymentMethod.CASH:
            return change_due(self.cash_given, self._preview.settlement_required) is not None
        return bool(self._transfer_confirmed.get())

    # ------------------------------------------------------------------
    # Tải preview
    # ------------------------------------------------------------------
    def reload(self) -> None:
        """Tính lại phí (preview_checkout) và tên đăng nhập của khách, chạy nền."""
        self._phase = LOADING
        self._render_loading()
        self._load_request += 1
        request = self._load_request
        services = self._context.services
        machine_id = self._machine.machine_id
        at = self._now()

        def load() -> tuple[CheckoutPreview, Customer | None]:
            preview = services.sessions.preview_checkout(machine_id, at)
            try:
                customer = services.customers.get_customer(preview.session.customer_id)
            except Exception:  # noqa: BLE001 - tên đăng nhập chỉ để hiển thị
                customer = None
            return preview, customer

        self._runner.submit(self, load, lambda data: self._on_loaded(request, data), lambda error: self._on_load_failed(request, error))

    def _on_loaded(self, request: int, data: tuple[CheckoutPreview, Customer | None]) -> None:
        if request != self._load_request:
            return
        preview, customer = data
        self._preview = preview
        if customer is not None:
            self._username = customer.account.username
        self._phase = READY
        self._render_ready()

    def _on_load_failed(self, request: int, error: Exception) -> None:
        if request != self._load_request:
            return
        notify_error(self.master, error, conflict_as_alert=True)
        callback = self._on_conflict if isinstance(error, ConflictError) else None
        self.close()
        if callback is not None:
            callback()

    # ------------------------------------------------------------------
    # Vẽ
    # ------------------------------------------------------------------
    def _clear(self) -> None:
        for child in self._content.winfo_children():
            child.destroy()
        self._method_buttons = {}
        self._cash_entry = None

    def _render_loading(self) -> None:
        self._clear()
        ctk.CTkLabel(self._content, text=self._t('⟳  Đang tính phí phiên sử dụng…'), font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=60).pack(fill="x")
        self._update_confirm()

    def _render_ready(self) -> None:
        preview = self._preview
        assert preview is not None
        self._clear()
        breakdown = cost_breakdown(preview)
        self._build_session_panel(preview)
        if breakdown.settlement > 0:
            self.minsize(860, 1)
            banner = ctk.CTkFrame(
                self._content, fg_color=STITCH_BADGE_DANGER_BG, border_width=1, border_color=STITCH_BADGE_DANGER_BORDER, corner_radius=STITCH_RADIUS_LG
            )
            banner.pack(fill="x", pady=(12, 0))
            row = ctk.CTkFrame(banner, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=9)
            ctk.CTkLabel(row, text=self._t('⚠  Khách hàng cần thanh toán thêm '), font=FONT_ST_BODY_STRONG, text_color=STITCH_DANGER, height=20).pack(side="left")
            ctk.CTkLabel(row, text=format_money(breakdown.settlement, language=self._t.language), font=FONT_TOTAL, text_color=STITCH_TEXT_STRONG, height=20).pack(side="left")
            ctk.CTkLabel(row, text=self._t(' trước khi kết thúc phiên.'), font=FONT_ST_BODY_STRONG, text_color=STITCH_DANGER, height=20).pack(side="left")

            columns = ctk.CTkFrame(self._content, fg_color="transparent")
            columns.pack(fill="both", expand=True, pady=(12, 0))
            columns.grid_columnconfigure((0, 1), weight=1, uniform="checkout")
            left = _panel(columns)
            left.master.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
            self._build_cost_rows(left, breakdown, titled=True)
            right = _panel(columns)
            right.master.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
            self._build_method_panel(right, breakdown.settlement)
        else:
            self.minsize(640, 1)
            panel = _panel(self._content)
            panel.master.pack(fill="x", pady=(12, 0))
            self._build_cost_rows(panel, breakdown, titled=False)
            note = ctk.CTkFrame(
                self._content, fg_color=STITCH_BADGE_SUCCESS_BG, border_width=1, border_color=STITCH_BADGE_SUCCESS_BORDER, corner_radius=STITCH_RADIUS_LG
            )
            note.pack(fill="x", pady=(12, 0))
            ctk.CTkLabel(
                note,
                text=self._t('✓  Số dư tài khoản đủ thanh toán. Phiên sẽ kết thúc, máy chuyển về Trống và hóa đơn được tạo sau khi xác nhận.'),
                font=FONT_ST_BODY,
                text_color=STITCH_SUCCESS,
                wraplength=560,
                justify="left",
                anchor="w",
            ).pack(fill="x", padx=14, pady=10)
        self._update_confirm()

    def _build_session_panel(self, preview: CheckoutPreview) -> None:
        session = preview.session
        inner = _panel(self._content)
        inner.master.pack(fill="x")
        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=session.machine_code, font=FONT_TOTAL, text_color=STITCH_TEXT_STRONG, height=22).pack(side="left")
        ctk.CTkLabel(top, text=f"  —  {session.machine_name}", font=FONT_ST_BODY, text_color=STITCH_TEXT, height=22).pack(side="left")
        chip(top, self._t('ĐANG DÙNG'), STITCH_DANGER, STITCH_BADGE_DANGER_BG, STITCH_BADGE_DANGER_BORDER).pack(side="right")
        divider(inner, pady=(8, 6))
        grid = ctk.CTkFrame(inner, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure((1, 3), weight=1)
        cells = (
            (self._t('Khách hàng:'), f"{session.customer_name} — {session.customer_code}", STITCH_TEXT_STRONG),
            (self._t('Tài khoản:'), self._username or "—", STITCH_TEXT),
            (self._t('Bắt đầu:'), format_datetime(session.started_at), STITCH_TEXT),
            (self._t('Kết thúc:'), format_datetime(preview.calculated_at), STITCH_TEXT),
            (self._t('Thời lượng:'), format_duration(preview.billed_minutes * 60, language=self._t.language), STITCH_SUCCESS),
            (self._t('Đơn giá:'), self._t('{v0}/giờ', v0=f'{format_money(session.hourly_rate, language=self._t.language)}'), STITCH_TEXT),
        )
        for index, (label, value, color) in enumerate(cells):
            row, column = divmod(index, 2)
            ctk.CTkLabel(grid, text=label, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=20, anchor="w").grid(
                row=row, column=column * 2, sticky="w", padx=(0 if column == 0 else 18, 8)
            )
            ctk.CTkLabel(grid, text=value, font=FONT_ST_MONO_BODY, text_color=color, height=20, anchor="e").grid(row=row, column=column * 2 + 1, sticky="e")

    def _build_cost_rows(self, master: Any, breakdown: CostBreakdown, *, titled: bool) -> None:
        if titled:
            _caps(master, self._t('Chi tiết chi phí'))
            divider(master, pady=(6, 6))
        _money_row(master, self._t('Chi phí sử dụng:'), format_money(breakdown.usage_cost, language=self._t.language))
        _money_row(master,self._t("Khuyến mãi đã sử dụng:"),format_money(self._preview.bonus_used,language=self._t.language),STITCH_CYAN)
        _money_row(master, self._t("Số dư hiện tại:"), format_money(breakdown.balance_before, language=self._t.language), STITCH_DANGER if breakdown.balance_before < 0 else STITCH_TEXT)
        _money_row(master, self._t('Trừ tài khoản:'), f"-{format_money(breakdown.from_account, language=self._t.language)}" if breakdown.from_account else "0 VND", STITCH_DANGER)
        if breakdown.settlement > 0:
            box = ctk.CTkFrame(master, fg_color=STITCH_BADGE_DANGER_BG, border_width=1, border_color=STITCH_BADGE_DANGER_BORDER, corner_radius=STITCH_RADIUS)
            box.pack(fill="x", pady=(6, 2))
            row = ctk.CTkFrame(box, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=6)
            ctk.CTkLabel(row, text=self._t('Cần thanh toán thêm:'), font=FONT_ST_BODY_STRONG, text_color=STITCH_DANGER, height=20).pack(side="left")
            ctk.CTkLabel(row, text=format_money(breakdown.settlement, language=self._t.language), font=FONT_TOTAL, text_color=STITCH_DANGER, height=20).pack(side="right")
        else:
            _money_row(master, self._t('Cần thanh toán thêm:'), "0 VND")
        divider(master, pady=(8, 6))
        _money_row(
            master,
            self._t('Số dư sau khi kết thúc:'),
            format_money(breakdown.balance_after, language=self._t.language),
            STITCH_SUCCESS if breakdown.balance_after > 0 else STITCH_TEXT,
            strong=True,
        )

    def _build_method_panel(self, master: Any, required: int) -> None:
        head = ctk.CTkFrame(master, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text=self._t('PHƯƠNG THỨC THANH TOÁN'), font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED, height=18).pack(side="left")
        for method in (PaymentMethod.TRANSFER, PaymentMethod.CASH):  # pack từ phải: Tiền mặt | Chuyển khoản QR
            button = ctk.CTkButton(
                head,
                text=self._t(METHOD_LABELS[method]),
                width=70 if method == PaymentMethod.CASH else 120,
                height=28,
                corner_radius=STITCH_RADIUS,
                border_width=1,
                font=FONT_ST_BODY_STRONG,
                command=lambda m=method: self.set_method(m),
            )
            button.pack(side="right", padx=(6, 0))
            self._method_buttons[method] = button
        divider(master, pady=(8, 8))
        self._method_body = ctk.CTkFrame(master, fg_color="transparent")
        self._method_body.pack(fill="both", expand=True)
        self._render_method(required)

    def _render_method(self, required: int) -> None:
        for method, button in self._method_buttons.items():
            active = method == self._method
            button.configure(
                fg_color=STITCH_NAV_ACTIVE_BG if active else "transparent",
                border_color=STITCH_NAV_ACTIVE_BORDER if active else STITCH_INPUT_BORDER,
                text_color=STITCH_CYAN if active else STITCH_TEXT_MUTED,
                hover_color=STITCH_TAB_HOVER,
            )
        for child in self._method_body.winfo_children():
            child.destroy()
        self._cash_entry = None
        if self._method == PaymentMethod.CASH:
            self._build_cash(required)
        else:
            self._build_transfer(required)

    def _build_cash(self, required: int) -> None:
        body = self._method_body
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text=self._t('Khách đưa:'), font=FONT_ST_BODY, text_color=STITCH_TEXT, height=34).pack(side="left")
        box = ctk.CTkFrame(row, fg_color=INPUT_BG, border_width=1, border_color=STITCH_NAV_ACTIVE_BORDER, corner_radius=STITCH_RADIUS_LG)
        box.pack(side="right")
        ctk.CTkLabel(box, text="VND", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED).pack(side="right", padx=(0, 10))
        entry = ctk.CTkEntry(
            box,
            width=130,
            height=30,
            border_width=0,
            corner_radius=0,
            fg_color=INPUT_BG,
            text_color=STITCH_TEXT_STRONG,
            font=FONT_TOTAL,
            justify="right",
            placeholder_text=format_amount_input(required),
            placeholder_text_color=STITCH_TEXT_DIM,
        )
        entry.pack(side="right", padx=(8, 6), pady=3)
        if self._cash_text:
            entry.insert(0, self._cash_text)
        entry.bind("<KeyRelease>", lambda _e: self.set_cash_given(entry.get(), from_entry=True), add="+")
        self._cash_entry = entry

        summary = ctk.CTkFrame(body, fg_color=PANEL_BG, border_width=1, border_color=STITCH_BORDER, corner_radius=STITCH_RADIUS_LG)
        summary.pack(fill="x", pady=(10, 0))
        inner = ctk.CTkFrame(summary, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=8)
        _money_row(inner, self._t('Cần thu:'), format_money(required, language=self._t.language), STITCH_TEXT_STRONG)
        self._given_label = _money_row(inner, self._t('Tiền khách đưa:'), "—")
        divider(inner, pady=(4, 2))
        change_row = ctk.CTkFrame(inner, fg_color="transparent")
        change_row.pack(fill="x", pady=2)
        ctk.CTkLabel(change_row, text=self._t('Tiền thừa trả khách:'), font=FONT_ST_BODY_STRONG, text_color=STITCH_SUCCESS, height=22).pack(side="left")
        self._change_label = ctk.CTkLabel(change_row, text="—", font=FONT_BIG, text_color=STITCH_SUCCESS, height=22)
        self._change_label.pack(side="right")

        status = ctk.CTkFrame(body, fg_color="transparent")
        status.pack(fill="x", pady=(8, 0))
        self._cash_status = ctk.CTkLabel(status, text="", font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT_MUTED, height=18)
        self._cash_status.pack(side="left")
        ctk.CTkLabel(status, text=self._t('Xác nhận tiền mặt tại quầy'), font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED, height=18).pack(side="right")
        ctk.CTkLabel(
            body,
            text=self._t('* Nhân viên chịu trách nhiệm xác nhận số tiền mặt đã nhận và hoàn lại tiền thừa.'),
            font=(FONT_ST_MONO_11[0], 10, "italic"),
            text_color=STITCH_TEXT_DIM,
            wraplength=360,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(4, 0))
        self._refresh_cash()

    def _build_transfer(self, required: int) -> None:
        body = self._method_body
        preview = self._preview
        assert preview is not None
        content = transfer_content(preview.session.machine_code, preview.session.customer_code)
        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x")
        size, cell = 21, 5
        canvas = tk.Canvas(top, width=size * cell + 12, height=size * cell + 12, bg="#FFFFFF", highlightthickness=0)
        canvas.pack(side="left")
        for r, line in enumerate(qr_matrix(content, size)):
            for c, dark in enumerate(line):
                if dark:
                    x, y = 6 + c * cell, 6 + r * cell
                    canvas.create_rectangle(x, y, x + cell, y + cell, fill="#000000", outline="")
        info = ctk.CTkFrame(top, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=(14, 0))
        ctk.CTkLabel(info, text=self._t('Số tiền cần quét:'), font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, anchor="w", height=18).pack(fill="x")
        ctk.CTkLabel(info, text=format_money(required, language=self._t.language), font=FONT_BIG, text_color=STITCH_CYAN, anchor="w", height=26).pack(fill="x")
        line = ctk.CTkFrame(info, fg_color="transparent")
        line.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(line, text=self._t('Nội dung: '), font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=18).pack(side="left")
        ctk.CTkLabel(line, text=content, font=FONT_ST_MONO_SM, text_color=STITCH_TEXT_STRONG, height=18).pack(side="left")
        state_line = ctk.CTkFrame(info, fg_color="transparent")
        state_line.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(state_line, text=self._t('Trạng thái: '), font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=18).pack(side="left")
        self._transfer_chip_box = ctk.CTkFrame(state_line, fg_color="transparent")
        self._transfer_chip_box.pack(side="left")
        divider(body, pady=(10, 8))
        ctk.CTkCheckBox(
            body,
            text=self._t('Đã xác nhận giao dịch thành công'),
            variable=self._transfer_confirmed,
            command=self._refresh_transfer,
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT,
            fg_color=STITCH_CYAN,
            border_color=STITCH_INPUT_BORDER,
            hover_color=STITCH_TAB_HOVER,
            checkbox_width=18,
            checkbox_height=18,
        ).pack(anchor="w")
        ctk.CTkLabel(
            body,
            text=self._t('* POC: xác nhận chuyển khoản thủ công; mã QR minh họa, không tích hợp cổng thanh toán thực.'),
            font=(FONT_ST_MONO_11[0], 10, "italic"),
            text_color=STITCH_TEXT_DIM,
            wraplength=360,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(6, 0))
        self._refresh_transfer()

    # ------------------------------------------------------------------
    # Tương tác
    # ------------------------------------------------------------------
    def set_method(self, method: PaymentMethod) -> None:
        if method not in METHOD_LABELS or method == self._method or self.is_submitting:
            return
        self._method = method
        if self._phase == READY and self.needs_settlement:
            assert self._preview is not None
            self._render_method(self._preview.settlement_required)
        self._update_confirm()

    def set_cash_given(self, text: str, *, from_entry: bool = False) -> None:
        self._cash_text = text
        if not from_entry and self._cash_entry is not None:
            self._cash_entry.delete(0, "end")
            self._cash_entry.insert(0, text)
        self._refresh_cash()

    def set_transfer_confirmed(self, confirmed: bool) -> None:
        self._transfer_confirmed.set(confirmed)
        self._refresh_transfer()

    def _refresh_cash(self) -> None:
        preview = self._preview
        if preview is None or self._cash_entry is None:
            self._update_confirm()
            return
        required = preview.settlement_required
        given = self.cash_given
        change = change_due(given, required)
        self._given_label.configure(text=format_money(given, language=self._t.language) if given is not None else "—")
        self._change_label.configure(text=format_money(change, language=self._t.language) if change is not None else "—")
        if given is None:
            self._cash_status.configure(text=self._t('●  Chưa nhập tiền khách đưa'), text_color=STITCH_TEXT_MUTED)
        elif change is None:
            self._cash_status.configure(text=self._t('●  Còn thiếu {v0}', v0=f'{format_money(required - given, language=self._t.language)}'), text_color=STITCH_DANGER)
        else:
            self._cash_status.configure(text=self._t('●  Đã nhận đủ tiền'), text_color=STITCH_SUCCESS)
        self._update_confirm()

    def _refresh_transfer(self) -> None:
        box = getattr(self, "_transfer_chip_box", None)
        if box is not None and box.winfo_exists():
            for child in box.winfo_children():
                child.destroy()
            if self._transfer_confirmed.get():
                chip(box, self._t('Đã xác nhận'), STITCH_SUCCESS, STITCH_BADGE_SUCCESS_BG, STITCH_BADGE_SUCCESS_BORDER).pack()
            else:
                chip(box, self._t('Chưa xác nhận'), STITCH_WARNING, STITCH_BADGE_WARNING_BG, STITCH_BADGE_WARNING_BORDER).pack()
        self._update_confirm()

    def _update_confirm(self) -> None:
        button = self.confirm_button
        enabled = self.can_confirm
        button.set_enabled(enabled)
        if not enabled:
            button.configure(fg_color=DISABLED_BG, border_color=STITCH_INPUT_BORDER, text_color_disabled=STITCH_TEXT_DIM)
        elif self.needs_settlement:
            button.configure(fg_color=STITCH_CYAN, hover_color="#33D1FF", border_color=STITCH_CYAN, text_color="#020617")
        else:  # Stitch unified_v2: nút đỏ đặc khi trừ thẳng vào số dư
            button.configure(fg_color=ROSE_SOLID, hover_color=ROSE_SOLID_HOVER, border_color=ROSE_SOLID, text_color=STITCH_TEXT_STRONG)

    # ------------------------------------------------------------------
    # Xác nhận
    # ------------------------------------------------------------------
    def submit(self) -> None:
        if self.is_submitting or not self.can_confirm or self._preview is None:
            return
        settlement = self._preview.settlement_required
        method = self._method if settlement > 0 else None
        self.set_submitting(True)
        sessions, session = self._context.services.sessions, self._context.session
        machine_id = self._machine.machine_id
        self._runner.submit(
            self,
            lambda: sessions.complete_checkout(machine_id, session, settlement, method),
            self._on_success,
            self._on_failed,
        )

    def _on_success(self, result: CheckoutResult) -> None:
        self.set_submitting(False)
        preview = self._preview
        settlement = preview.settlement_required if preview else 0
        cash = self.cash_given if settlement > 0 and self._method == PaymentMethod.CASH else None
        method = self._method if settlement > 0 else None
        parent, callback, username = self.master, self._on_completed, self._username
        self.close()
        PaymentSuccessDialog(parent, result, username=username, method=method, cash_given=cash, language=self._t.language)
        if callback is not None:
            callback(result)

    def _on_failed(self, error: Exception) -> None:
        self.set_submitting(False)
        if isinstance(error, SettlementRequiredError):
            notify_error(self, error)  # phí vừa tăng (qua phút mới): tính lại, giữ phương thức đã chọn
            self.reload()
            return
        if isinstance(error, ConflictError):
            notify_error(self.master, error, conflict_as_alert=True)
            callback = self._on_conflict
            self.close()
            if callback is not None:
                callback()
            return
        notify_error(self, error)
        self._update_confirm()
