"""NG-04 — Dialog xác nhận Khóa / Mở khóa khách hàng theo Stitch
(`kh_a_kh_ch_h_ng_t_i_kho_n_confirm`, `m_kh_a_kh_ch_h_ng_t_i_kho_n_confirm`).

- Khóa: khách -> INACTIVE, tài khoản -> LOCKED; Mở khóa: cả hai -> ACTIVE (CUS-05, LI-03).
- Chỉ MANAGER/ADMIN thấy nút mở dialog; service vẫn kiểm tra quyền.
- Nội dung xác nhận bằng tiếng Anh như Stitch và quy định chung trong messages.py.
- Khác Stitch có chủ đích: Stitch ghi "wallet top-ups will be unavailable" khi khóa, nhưng
  tài khoản bị khóa vẫn được nạp tiền để trả nợ (quyết định LI-04), nên câu này được sửa lại.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ...domain.dtos import CustomerSummary
from ...domain.enums import CustomerStatus
from ...domain.models import Customer
from ..app_shell import ViewContext
from ..i18n import UIStrings
from ..background import TaskRunner, default_runner
from ..feedback import notify_error
from ..formatters import format_money
from ..theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_LABEL_CAPS,
    FONT_ST_MONO_BODY,
    FONT_ST_MONO_SM,
    STITCH_BADGE_DANGER_BORDER,
    STITCH_BADGE_SUCCESS_BORDER,
    STITCH_BG_CANVAS,
    STITCH_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_KPI_SUCCESS_CARD_BG,
    STITCH_RADIUS_LG,
    STITCH_SUCCESS,
    STITCH_TEXT,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
)
from .stitch_dialog import StitchDialog

LOCK_EFFECTS = (
    ("The customer status will become ", "INACTIVE", "."),
    ("The account status will become ", "LOCKED", "."),
    ("New sessions will be blocked. Top-ups stay available to settle debt.", "", ""),
    ("The balance and transaction history will be preserved.", "", ""),
)
UNLOCK_EFFECTS = (
    ("Customer status will become ", "ACTIVE", "."),
    ("Account status will become ", "ACTIVE", "."),
    ("New sessions will be available again.", "", ""),
    ("Existing balance and transaction history will remain unchanged.", "", ""),
)
NEGATIVE_BOX_BG = "#1C1520"  # rose-950/20


class CustomerLockDialog(StitchDialog):
    """Khách ACTIVE -> dialog Khóa; khách INACTIVE -> dialog Mở khóa."""

    def __init__(
        self,
        parent: Any,
        context: ViewContext,
        customer: CustomerSummary,
        *,
        account_code: str = "",
        runner: TaskRunner | None = None,
        on_done: Callable[[Customer], None] | None = None,
    ) -> None:
        self._locking = customer.customer_status == CustomerStatus.ACTIVE
        self._t = UIStrings(context.language)
        super().__init__(
            parent,
            language=context.language,
            title="Lock customer account" if self._locking else "Unlock customer account",
            subtitle="Restrict access and disable new sessions" if self._locking else "Restore operational access and permit transactions",
            icon="🔒" if self._locking else "🔓",
            icon_tone="danger" if self._locking else "success",
            width=560,
            hint="Esc to cancel",
            confirm_text="🔒  Lock customer" if self._locking else "🔓  Unlock customer",
            confirm_kind="danger" if self._locking else "primary",
            cancel_text="Cancel",
        )
        self._context = context
        self._customer = customer
        self._runner = runner or default_runner()
        self._on_done = on_done
        if self._locking:  # nút nguy hiểm đặc như Stitch
            self.confirm_button.configure(fg_color="#E11D48", hover_color="#BE123C", text_color=STITCH_TEXT_STRONG, border_color="#E11D48")

        question = ctk.CTkFrame(self.body, fg_color="transparent")
        question.pack(fill="x")
        prefix = "Are you sure you want to lock customer " if self._locking else "Reactivate "
        suffix = "?" if self._locking else " and restore full access to sessions and billing?"
        ctk.CTkLabel(question, text=prefix, font=FONT_ST_BODY, text_color=STITCH_TEXT, height=20).pack(side="left")
        ctk.CTkLabel(question, text=customer.full_name, font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT_STRONG, height=20).pack(side="left")
        ctk.CTkLabel(question, text=suffix, font=FONT_ST_BODY, text_color=STITCH_TEXT, height=20).pack(side="left")

        self._build_details(account_code)
        self._build_effects()
        if self._locking:
            note = ctk.CTkFrame(self.body, fg_color=STITCH_BG_CANVAS, border_width=1, border_color=STITCH_BORDER, corner_radius=STITCH_RADIUS_LG)
            note.pack(fill="x", pady=(12, 0))
            ctk.CTkLabel(
                note,
                text="ⓘ  This is a soft lock. You can unlock and restore full access anytime from the detail panel.",
                font=FONT_ST_BODY,
                text_color=STITCH_TEXT_MUTED,
                wraplength=470,
                justify="left",
                anchor="w",
            ).pack(fill="x", padx=12, pady=10)
        self.finish(focus=self.cancel_button.focus_set)

    @property
    def locking(self) -> bool:
        return self._locking

    def _build_details(self, account_code: str) -> None:
        customer = self._customer
        box = ctk.CTkFrame(self.body, fg_color=STITCH_BG_CANVAS, border_width=1, border_color=STITCH_BORDER, corner_radius=STITCH_RADIUS_LG)
        box.pack(fill="x", pady=(12, 0))
        grid = ctk.CTkFrame(box, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=10)
        grid.grid_columnconfigure((0, 1), weight=1, uniform="details")
        cells = (
            ("Customer code", customer.customer_code, STITCH_CYAN),
            ("Account code", account_code or "—", STITCH_CYAN),
            ("Username", customer.username, STITCH_TEXT),
            ("Current balance", format_money(customer.balance, language=self._t.language), STITCH_DANGER if customer.balance < 0 else STITCH_SUCCESS),
        )
        for index, (label, value, color) in enumerate(cells):
            cell = ctk.CTkFrame(grid, fg_color="transparent")
            cell.grid(row=index // 2, column=index % 2, sticky="w", pady=4)
            ctk.CTkLabel(cell, text=label, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=18, anchor="w").pack(anchor="w")
            ctk.CTkLabel(
                cell, text=value, font=FONT_ST_MONO_SM if color != STITCH_TEXT else FONT_ST_MONO_BODY, text_color=color, height=18, anchor="w"
            ).pack(anchor="w")

    def _build_effects(self) -> None:
        locking = self._locking
        box = ctk.CTkFrame(
            self.body,
            fg_color=NEGATIVE_BOX_BG if locking else STITCH_KPI_SUCCESS_CARD_BG,
            border_width=1,
            border_color=STITCH_BADGE_DANGER_BORDER if locking else STITCH_BADGE_SUCCESS_BORDER,
            corner_radius=STITCH_RADIUS_LG,
        )
        box.pack(fill="x", pady=(12, 0))
        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)
        color = STITCH_DANGER if locking else STITCH_SUCCESS
        ctk.CTkLabel(
            inner,
            text="⚠  Consequences of this action:" if locking else "✓  Restoration effects",
            font=FONT_ST_BODY_STRONG,
            text_color=color,
            anchor="w",
            height=20,
        ).pack(fill="x")
        for before, highlight, after in LOCK_EFFECTS if locking else UNLOCK_EFFECTS:
            line = ctk.CTkFrame(inner, fg_color="transparent")
            line.pack(fill="x", pady=(4, 0))
            ctk.CTkLabel(line, text="•  ", font=FONT_ST_LABEL_CAPS, text_color=color, height=18).pack(side="left")
            ctk.CTkLabel(line, text=before, font=FONT_ST_BODY, text_color=STITCH_TEXT, height=18).pack(side="left")
            if highlight:
                ctk.CTkLabel(line, text=highlight, font=FONT_ST_BODY_STRONG, text_color=color, height=18).pack(side="left")
                ctk.CTkLabel(line, text=after, font=FONT_ST_BODY, text_color=STITCH_TEXT, height=18).pack(side="left")

    # ------------------------------------------------------------------
    def submit(self) -> None:
        if self.is_submitting:
            return
        self.set_submitting(True)
        customers, session = self._context.services.customers, self._context.session
        customer_id = self._customer.customer_id
        status = CustomerStatus.INACTIVE if self._locking else CustomerStatus.ACTIVE
        self._runner.submit(
            self,
            lambda: customers.set_customer_status(customer_id, status, session),
            self._on_success,
            self._on_error,
        )

    def _on_success(self, customer: Customer) -> None:
        self.set_submitting(False)
        callback = self._on_done
        self.close()
        if callback is not None:
            callback(customer)

    def _on_error(self, error: Exception) -> None:
        self.set_submitting(False)
        notify_error(self, error, conflict_as_alert=True)
