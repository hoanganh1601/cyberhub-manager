"""NG-05 — Dialog "Mở phiên sử dụng" theo Stitch
(`m_phi_n_s_d_ng_cyberhub_manager_1280x720`, `m_phi_n_s_d_ng_kh_ng_s_d_1280x720`).

Luồng:
1. Thông tin máy (mã, tên, trạng thái, giá hiện tại) lấy từ MachineSummary của dashboard.
2. Tìm khách theo mã / tên / SĐT / tên đăng nhập (CustomerService.search_customers, chạy nền).
3. Chọn khách -> SessionService.preview_open: số dư, số dư tối thiểu, thời gian ước tính.
   UI không tự tính phí hay số dư tối thiểu (07 mục 4.2), chỉ hiển thị số liệu preview.
4. Đủ điều kiện -> "Xác nhận mở phiên" (Enter). Thiếu số dư -> nút xác nhận bị khóa và hiện
   nút "Nạp tiền" (mở TopUpDialog, nạp xong tự kiểm tra lại).
5. Khách ngừng hoạt động / tài khoản khóa / đang có phiên khác / máy hết trống -> hộp đỏ, không mở được.
open_session luôn được service kiểm tra lại; lỗi tranh chấp hiện alert rồi kiểm tra lại.
"""

from __future__ import annotations

import dataclasses
import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ...domain.dtos import CustomerSummary, MachineSummary, OpenSessionPreview, SessionSummary, TopUpResult
from ...domain.enums import AccountStatus, CustomerStatus, MachineStatus
from ...domain.exceptions import ConflictError, InsufficientBalanceError
from ...domain.models import Customer, minimum_balance
from ..app_shell import ViewContext
from ..background import TaskRunner, default_runner
from ..components.stitch_button import stitch_button
from ..feedback import notify_error, notify_success
from ..formatters import format_duration, format_money
from ..messages import get_user_friendly_error
from ..theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_LABEL_CAPS,
    FONT_ST_MONO_11,
    FONT_ST_MONO_BODY,
    FONT_ST_MONO_SM,
    STITCH_BADGE_DANGER_BG,
    STITCH_BADGE_DANGER_BORDER,
    STITCH_BADGE_SUCCESS_BG,
    STITCH_BADGE_SUCCESS_BORDER,
    STITCH_BORDER,
    STITCH_CHIP_BG,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_FONT,
    STITCH_FONT_MONO,
    STITCH_ICON_CYAN_BG,
    STITCH_ICON_CYAN_BORDER,
    STITCH_INPUT_BORDER,
    STITCH_RADIUS,
    STITCH_RADIUS_LG,
    STITCH_SUCCESS,
    STITCH_TAB_HOVER,
    STITCH_TEXT,
    STITCH_TEXT_DIM,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
)
from .stitch_dialog import StitchDialog, chip, divider
from .topup_dialog import TopUpDialog

# Giai đoạn của dialog (OpenSessionDialog.phase)
IDLE = "idle"  # chưa chọn khách
CHECKING = "checking"  # đang gọi preview_open
ELIGIBLE = "eligible"  # đủ điều kiện mở phiên
INSUFFICIENT = "insufficient"  # thiếu số dư -> CTA Nạp tiền
BLOCKED = "blocked"  # khách/tài khoản/máy không cho phép

SEARCH_DELAY_MS = 250
MAX_RESULTS = 5
HINT_READY = "Nhấn Enter để xác nhận • Esc để hủy"
HINT_CANCEL_ONLY = "Nhấn Esc để hủy"
NOT_AVAILABLE = "Không khả dụng"
TOP_UP_DONE = "Top-up successful. New balance: {balance}."

PANEL_BG = "#0D121F"
INPUT_BG = "#090E19"
DISABLED_BG = "#1E293B"  # slate-800
FONT_TITLE_SM = (STITCH_FONT, 14, "bold")
FONT_MACHINE_CODE = (STITCH_FONT_MONO, 15, "bold")
FONT_VALUE = (STITCH_FONT_MONO, 13, "bold")


# ----------------------------------------------------------------------
# Hàm thuần (test được không cần Tk)
# ----------------------------------------------------------------------
def customer_option_text(customer: CustomerSummary) -> str:
    """Dòng hiển thị trong ô tìm kiếm sau khi chọn, như Stitch: "0912345678 - Nguyễn Văn An"."""
    return f"{customer.phone} - {customer.full_name}"


def estimate_text(preview: OpenSessionPreview | None) -> str:
    if preview is None or not preview.can_open:
        return NOT_AVAILABLE
    return format_duration(preview.estimated_minutes * 60)


def required_top_up(preview: OpenSessionPreview) -> int:
    """Số tiền tối thiểu cần nạp thêm để đủ mức mở phiên."""
    return max(preview.minimum_balance - preview.balance, 0)


def customer_block_reason(customer: CustomerSummary) -> str | None:
    """Lý do không mở được phiên biết trước từ CustomerSummary (khỏi gọi service)."""
    if customer.customer_status != CustomerStatus.ACTIVE:
        return "Khách hàng đã ngừng hoạt động"
    if customer.account_status != AccountStatus.ACTIVE:
        return "Tài khoản khách hàng đã bị khóa"
    return None


def conflict_reason(error: Exception) -> str:
    """Câu tiếng Việt cho hộp đỏ khi preview/open_session báo ConflictError.

    Không hiện thông điệp nội bộ của service; chỉ dựa vào trường bị lỗi.
    """
    fields = getattr(error, "field_errors", None) or {}
    if "machine_id" in fields:
        return "Máy không còn trống, vui lòng chọn máy khác"
    if "customer_id" in fields:
        return "Khách hàng đang có phiên khác hoặc không còn hoạt động"
    return get_user_friendly_error(error)


def status_text(customer: CustomerSummary) -> tuple[tuple[str, bool], tuple[str, bool]]:
    """((nhãn KH, ok?), (nhãn TK, ok?)) cho 2 chip trạng thái trong thẻ khách."""
    customer_ok = customer.customer_status == CustomerStatus.ACTIVE
    account_ok = customer.account_status == AccountStatus.ACTIVE
    return (
        (f"Trạng thái KH: {'Hoạt động' if customer_ok else 'Ngừng hoạt động'}", customer_ok),
        (f"Trạng thái TK: {'Hoạt động' if account_ok else 'Đã khóa'}", account_ok),
    )


# ----------------------------------------------------------------------
# Widget nhỏ
# ----------------------------------------------------------------------
def _panel(master: Any, *, border: str = STITCH_BORDER, bg: str = PANEL_BG) -> ctk.CTkFrame:
    box = ctk.CTkFrame(master, fg_color=bg, border_width=1, border_color=border, corner_radius=STITCH_RADIUS_LG + 2)
    box.pack(fill="x", pady=(12, 0))
    inner = ctk.CTkFrame(box, fg_color="transparent")
    inner.pack(fill="x", padx=14, pady=11)
    return inner


def _stat(master: Any, column: int, label: str, value: str, color: str, font: Any = FONT_VALUE) -> ctk.CTkLabel:
    cell = ctk.CTkFrame(master, fg_color="transparent")
    cell.grid(row=0, column=column, sticky="w")
    ctk.CTkLabel(cell, text=label, font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=18, anchor="w").pack(anchor="w")
    value_label = ctk.CTkLabel(cell, text=value, font=font, text_color=color, height=22, anchor="w")
    value_label.pack(anchor="w")
    return value_label


def _status_chip(master: Any, text: str, ok: bool) -> ctk.CTkFrame:
    if ok:
        return chip(master, text, STITCH_SUCCESS, STITCH_BADGE_SUCCESS_BG, STITCH_BADGE_SUCCESS_BORDER, pill=True)
    return chip(master, text, STITCH_DANGER, STITCH_BADGE_DANGER_BG, STITCH_BADGE_DANGER_BORDER, pill=True)


class OpenSessionDialog(StitchDialog):
    """Mở phiên cho một máy AVAILABLE. on_opened(session) được gọi sau khi mở thành công."""

    def __init__(
        self,
        parent: Any,
        context: ViewContext,
        machine: MachineSummary,
        *,
        customer: CustomerSummary | None = None,
        runner: TaskRunner | None = None,
        on_opened: Callable[[SessionSummary], None] | None = None,
    ) -> None:
        super().__init__(
            parent,
            title="Mở phiên sử dụng",
            subtitle="Kiểm tra khách hàng và xác nhận mở phiên",
            icon="",
            width=580,
            hint=HINT_CANCEL_ONLY,
            confirm_text="▶  Xác nhận mở phiên",
            confirm_kind="primary",
            cancel_text="Hủy",
        )
        self._context = context
        self._machine = machine
        self._runner = runner or default_runner()
        self._on_opened = on_opened

        self._phase = IDLE
        self._customer: CustomerSummary | None = None
        self._preview: OpenSessionPreview | None = None
        self._block_reason: str | None = None
        self._results: list[CustomerSummary] = []
        self._search_request = 0
        self._preview_request = 0
        self._search_after: str | None = None
        self._result_buttons: list[ctk.CTkButton] = []

        self.confirm_button.configure(width=190)
        self._top_up_button = stitch_button(self.footer_actions, "⊕  Nạp tiền", kind="primary", command=self.open_top_up, width=120, height=34)

        self._build_machine_panel()
        self._build_customer_picker()
        # height=1: frame CTk rỗng mặc định cao 200px -> để trống thì gần như không chiếm chỗ
        self._customer_card = ctk.CTkFrame(self.body, fg_color="transparent", height=1)
        self._customer_card.pack(fill="x")
        self._eligibility = ctk.CTkFrame(self.body, fg_color="transparent", height=1)
        self._eligibility.pack(fill="x")
        self._build_rate_note()
        self._render()
        self.finish(focus=self._search_entry.focus_set)
        if customer is not None:
            self.select_customer(customer)

    # ------------------------------------------------------------------
    # Thuộc tính công khai (test)
    # ------------------------------------------------------------------
    @property
    def phase(self) -> str:
        """IDLE / CHECKING / ELIGIBLE / INSUFFICIENT / BLOCKED (không đặt tên `state`: trùng Toplevel.state())."""
        return self._phase

    @property
    def machine(self) -> MachineSummary:
        return self._machine

    @property
    def customer(self) -> CustomerSummary | None:
        return self._customer

    @property
    def preview(self) -> OpenSessionPreview | None:
        return self._preview

    @property
    def block_reason(self) -> str | None:
        return self._block_reason

    @property
    def results(self) -> list[CustomerSummary]:
        return list(self._results)

    @property
    def can_confirm(self) -> bool:
        return self._phase == ELIGIBLE and self.confirm_button.is_enabled

    @property
    def top_up_visible(self) -> bool:
        return bool(self._top_up_button.winfo_manager())

    # ------------------------------------------------------------------
    # Dựng giao diện
    # ------------------------------------------------------------------
    def _build_machine_panel(self) -> None:
        machine = self._machine
        inner = _panel(self.body)
        inner.master.pack_configure(pady=(0, 0))
        ctk.CTkLabel(inner, text="THÔNG TIN MÁY", font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED, anchor="w", height=16).pack(fill="x")
        grid = ctk.CTkFrame(inner, fg_color="transparent")
        grid.pack(fill="x", pady=(8, 0))
        grid.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="machine")
        _stat(grid, 0, "Mã máy", machine.machine_code, STITCH_TEXT_STRONG, FONT_MACHINE_CODE)
        _stat(grid, 1, "Tên máy", machine.name, STITCH_TEXT, FONT_ST_BODY_STRONG)
        cell = ctk.CTkFrame(grid, fg_color="transparent")
        cell.grid(row=0, column=2, sticky="w")
        ctk.CTkLabel(cell, text="Trạng thái", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=18, anchor="w").pack(anchor="w")
        available = machine.status == MachineStatus.AVAILABLE
        _status_chip(cell, "Trống" if available else machine.status.value, available).pack(anchor="w", pady=(2, 0))
        self._rate_label = _stat(grid, 3, "Giá hiện tại", f"{format_money(machine.hourly_rate)}/giờ", STITCH_CYAN, FONT_VALUE)

    def _build_customer_picker(self) -> None:
        head = ctk.CTkFrame(self.body, fg_color="transparent")
        head.pack(fill="x", pady=(14, 6))
        ctk.CTkLabel(head, text="Khách hàng", font=FONT_TITLE_SM, text_color=STITCH_TEXT_STRONG, height=20).pack(side="left")
        self._identified_label = ctk.CTkLabel(head, text="● Đã định danh", font=FONT_ST_BODY, text_color=STITCH_SUCCESS, height=20)

        self._search_box = ctk.CTkFrame(
            self.body, fg_color=INPUT_BG, border_width=1, border_color=STITCH_INPUT_BORDER, corner_radius=STITCH_RADIUS_LG
        )
        self._search_box.pack(fill="x")
        ctk.CTkLabel(self._search_box, text="🔍", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, width=20).pack(side="left", padx=(12, 0))
        self._search_entry = ctk.CTkEntry(
            self._search_box,
            height=32,
            border_width=0,
            corner_radius=0,
            fg_color=INPUT_BG,
            text_color=STITCH_TEXT_STRONG,
            placeholder_text="Tìm theo mã, tên, SĐT hoặc tên đăng nhập",
            placeholder_text_color=STITCH_TEXT_DIM,
            font=FONT_ST_BODY,
        )
        self._search_entry.pack(side="left", fill="x", expand=True, padx=(6, 8), pady=3)
        self._check_label = ctk.CTkLabel(self._search_box, text="✔", font=FONT_ST_BODY_STRONG, text_color=STITCH_SUCCESS, width=20)
        self._search_entry.bind("<KeyRelease>", self._on_key_release, add="+")
        self._search_entry.bind("<Return>", self._on_search_return)
        self._search_entry.bind("<FocusIn>", lambda _e: self._search_box.configure(border_color=STITCH_CYAN), add="+")
        self._search_entry.bind("<FocusOut>", lambda _e: self._search_box.configure(border_color=STITCH_INPUT_BORDER), add="+")

        # Danh sách gợi ý khi đang gõ (ẩn khi đã chọn khách)
        self._results_box = ctk.CTkFrame(
            self.body, fg_color=PANEL_BG, border_width=1, border_color=STITCH_INPUT_BORDER, corner_radius=STITCH_RADIUS_LG
        )

    def _build_rate_note(self) -> None:
        note = ctk.CTkFrame(self.body, fg_color="transparent")
        note.pack(fill="x", pady=(12, 0))
        ctk.CTkLabel(note, text="ⓘ", font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT_DIM, width=18, height=18).pack(side="left", anchor="n")
        rate = format_money(self._machine.hourly_rate)
        ctk.CTkLabel(
            note,
            text=f"Đơn giá {rate}/giờ sẽ được ghi nhận vào phiên. Phiên chưa trừ tiền cho đến khi kết thúc hoặc tính cước theo thời gian thực.",
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
            wraplength=500,
            justify="left",
            anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))

    # ------------------------------------------------------------------
    # Tìm khách
    # ------------------------------------------------------------------
    def _on_key_release(self, event: tk.Event) -> None:
        if event.keysym in ("Return", "KP_Enter", "Escape", "Up", "Down", "Tab"):
            return
        text = self._search_entry.get()
        if self._customer is not None and text != customer_option_text(self._customer):
            self._clear_customer()  # sửa lại ô tìm kiếm = bỏ khách đã chọn
        if self._search_after is not None:
            self.after_cancel(self._search_after)
        self._search_after = self.after(SEARCH_DELAY_MS, lambda: self.search(self._search_entry.get()))

    def _on_search_return(self, _event: tk.Event) -> str | None:
        if self._customer is None:
            if self._search_after is not None:  # chưa kịp tìm -> tìm ngay
                self.after_cancel(self._search_after)
                self._search_after = None
                self.search(self._search_entry.get())
            if self._results:
                self.select_customer(self._results[0])
            return "break"  # Enter trong ô tìm kiếm không xác nhận mở phiên
        return None

    def search(self, keyword: str) -> None:
        """Gọi search_customers ở nền; kết quả cũ về muộn bị bỏ qua."""
        self._search_after = None
        keyword = keyword.strip()
        self._search_request += 1
        request = self._search_request
        if not keyword:
            self._show_results([])
            return
        customers = self._context.services.customers
        self._runner.submit(
            self,
            lambda: customers.search_customers(keyword),
            lambda found: self._on_search_done(request, found),
            lambda error: self._on_search_failed(request, error),
        )

    def _on_search_done(self, request: int, found: list[CustomerSummary]) -> None:
        if request != self._search_request or self._customer is not None:
            return
        self._show_results(found[:MAX_RESULTS], searched=True)

    def _on_search_failed(self, request: int, error: Exception) -> None:
        if request != self._search_request:
            return
        self._show_results([])
        notify_error(self, error)

    def _show_results(self, customers: list[CustomerSummary], *, searched: bool = False) -> None:
        self._results = list(customers)
        for child in self._results_box.winfo_children():
            child.destroy()
        self._result_buttons = []
        if not customers and not searched:
            self._results_box.pack_forget()
            return
        if not self._results_box.winfo_manager():
            self._results_box.pack(fill="x", pady=(6, 0), after=self._search_box)
        if not customers:
            ctk.CTkLabel(
                self._results_box, text="Không tìm thấy khách hàng phù hợp", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=30
            ).pack(fill="x", padx=12, pady=4)
            return
        for index, customer in enumerate(customers):
            reason = customer_block_reason(customer)
            text = f"{customer.customer_code}   {customer.full_name}  •  {customer.phone}"
            if reason:
                text += "   (Đã khóa)" if customer.customer_status == CustomerStatus.ACTIVE else "   (Ngừng hoạt động)"
            button = ctk.CTkButton(
                self._results_box,
                text=text,
                anchor="w",
                height=30,
                corner_radius=STITCH_RADIUS,
                fg_color="transparent",
                hover_color=STITCH_TAB_HOVER,
                text_color=STITCH_TEXT_MUTED if reason else STITCH_TEXT,
                font=FONT_ST_BODY,
                command=lambda c=customer: self.select_customer(c),
            )
            button.pack(fill="x", padx=4, pady=(4 if index == 0 else 0, 4 if index == len(customers) - 1 else 0))
            self._result_buttons.append(button)

    # ------------------------------------------------------------------
    # Chọn khách + kiểm tra điều kiện
    # ------------------------------------------------------------------
    def select_customer(self, customer: CustomerSummary) -> None:
        self._customer = customer
        self._search_entry.delete(0, "end")
        self._search_entry.insert(0, customer_option_text(customer))
        self._show_results([])
        self._render_customer_card()
        reason = customer_block_reason(customer)
        if reason is not None:
            self._set_blocked(reason)
            return
        self.check_eligibility()

    def _clear_customer(self) -> None:
        self._customer = None
        self._preview = None
        self._block_reason = None
        self._preview_request += 1  # bỏ kết quả preview đang chạy
        self._phase = IDLE
        self._render_customer_card()
        self._render()

    def check_eligibility(self) -> None:
        """Gọi preview_open cho khách đang chọn (chạy nền)."""
        customer = self._customer
        if customer is None:
            return
        self._phase = CHECKING
        self._preview = None
        self._block_reason = None
        self._render()
        self._preview_request += 1
        request = self._preview_request
        sessions, session = self._context.services.sessions, self._context.session
        customer_id, machine_id = customer.customer_id, self._machine.machine_id
        self._runner.submit(
            self,
            lambda: sessions.preview_open(customer_id, machine_id, session),
            lambda preview: self._on_preview(request, preview),
            lambda error: self._on_preview_failed(request, error),
        )

    def _on_preview(self, request: int, preview: OpenSessionPreview) -> None:
        if request != self._preview_request:
            return
        self._preview = preview
        self._phase = ELIGIBLE if preview.can_open else INSUFFICIENT
        self._render()

    def _on_preview_failed(self, request: int, error: Exception) -> None:
        if request != self._preview_request:
            return
        if isinstance(error, ConflictError):
            self._set_blocked(conflict_reason(error))
            return
        self._phase = IDLE
        self._render()
        notify_error(self, error)

    def _set_blocked(self, reason: str) -> None:
        self._preview = None
        self._block_reason = reason
        self._phase = BLOCKED
        self._render()

    # ------------------------------------------------------------------
    # Vẽ theo trạng thái
    # ------------------------------------------------------------------
    def _render_customer_card(self) -> None:
        for child in self._customer_card.winfo_children():
            child.destroy()
        customer = self._customer
        if customer is None:
            self._identified_label.pack_forget()
            self._check_label.pack_forget()
            return
        if not self._identified_label.winfo_manager():
            self._identified_label.pack(side="right")
        if not self._check_label.winfo_manager():
            self._check_label.pack(side="right", padx=(0, 12))

        inner = _panel(self._customer_card, border=STITCH_INPUT_BORDER)
        inner.master.pack_configure(pady=(10, 0))
        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")
        code = ctk.CTkFrame(top, fg_color=STITCH_ICON_CYAN_BG, border_width=1, border_color=STITCH_ICON_CYAN_BORDER, corner_radius=STITCH_RADIUS)
        code.pack(side="left")
        ctk.CTkLabel(code, text=customer.customer_code, font=FONT_ST_MONO_SM, text_color=STITCH_CYAN, height=22).pack(padx=8)
        ctk.CTkLabel(top, text=customer.full_name, font=FONT_TITLE_SM, text_color=STITCH_TEXT_STRONG, height=22).pack(side="left", padx=(10, 0))
        ctk.CTkLabel(top, text=f"•  {customer.phone}", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, height=22).pack(side="left", padx=(8, 0))
        username = ctk.CTkFrame(top, fg_color=STITCH_CHIP_BG, corner_radius=STITCH_RADIUS)
        username.pack(side="right")
        ctk.CTkLabel(username, text=f"TK: {customer.username}", font=FONT_ST_MONO_BODY, text_color=STITCH_TEXT, height=22).pack(padx=8)
        divider(inner, pady=(10, 8))
        chips = ctk.CTkFrame(inner, fg_color="transparent")
        chips.pack(fill="x")
        for text, ok in status_text(customer):
            _status_chip(chips, text, ok).pack(side="left", padx=(0, 10))

    def _render(self) -> None:
        for child in self._eligibility.winfo_children():
            child.destroy()
        state = self._phase
        ready = state == ELIGIBLE
        self._style_confirm(ready)
        self.set_hint(HINT_READY if ready else HINT_CANCEL_ONLY)
        if state == INSUFFICIENT:
            if not self._top_up_button.winfo_manager():
                self._top_up_button.pack(side="right", padx=(0, 10), before=self.cancel_button)
        else:
            self._top_up_button.pack_forget()
        if state == IDLE:
            return

        preview = self._preview
        inner = _panel(self._eligibility)
        grid = ctk.CTkFrame(inner, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure((0, 1, 2), weight=1, uniform="balance")
        customer = self._customer
        balance = preview.balance if preview else (customer.balance if customer else 0)
        minimum = preview.minimum_balance if preview else minimum_balance(self._machine.hourly_rate)
        if state == CHECKING:
            balance_color = STITCH_TEXT
        else:
            balance_color = STITCH_SUCCESS if ready else STITCH_DANGER
        self._balance_label = _stat(grid, 0, "Số dư hiện tại", format_money(balance), balance_color)
        _stat(grid, 1, "Số dư tối thiểu", format_money(minimum), STITCH_TEXT)
        self._estimate_label = _stat(
            grid, 2, "Thời gian ước tính", "…" if state == CHECKING else estimate_text(preview), STITCH_CYAN if ready else STITCH_TEXT_MUTED
        )

        if state == CHECKING:
            self._banner(inner, "⟳", "Đang kiểm tra điều kiện mở phiên…", "", STITCH_TEXT_MUTED, PANEL_BG, STITCH_BORDER)
        elif ready:
            self._banner(inner, "✔", "Khách hàng đủ điều kiện mở phiên", "", STITCH_SUCCESS, STITCH_BADGE_SUCCESS_BG, STITCH_BADGE_SUCCESS_BORDER)
        elif state == INSUFFICIENT and preview is not None:
            self._banner(
                inner,
                "⚠",
                "Số dư chưa đạt mức tối thiểu để mở phiên",
                f"Vui lòng nạp thêm ít nhất {format_money(required_top_up(preview))}",
                STITCH_DANGER,
                STITCH_BADGE_DANGER_BG,
                STITCH_BADGE_DANGER_BORDER,
            )
        else:
            self._banner(
                inner,
                "⚠",
                self._block_reason or "Không thể mở phiên",
                "Không thể mở phiên cho khách hàng này",
                STITCH_DANGER,
                STITCH_BADGE_DANGER_BG,
                STITCH_BADGE_DANGER_BORDER,
            )

    def _banner(self, master: Any, icon: str, title: str, detail: str, color: str, bg: str, border: str) -> None:
        box = ctk.CTkFrame(master, fg_color=bg, border_width=1, border_color=border, corner_radius=STITCH_RADIUS_LG)
        box.pack(fill="x", pady=(10, 0))
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=7)
        ctk.CTkLabel(row, text=icon, font=FONT_TITLE_SM, text_color=color, width=20).pack(side="left", anchor="n")
        texts = ctk.CTkFrame(row, fg_color="transparent")
        texts.pack(side="left", fill="x", expand=True, padx=(8, 0))
        title_color = color if not detail else STITCH_TEXT_STRONG
        self._banner_label = ctk.CTkLabel(texts, text=title, font=FONT_ST_BODY_STRONG, text_color=title_color, anchor="w", height=20)
        self._banner_label.pack(fill="x")
        if detail:
            ctk.CTkLabel(texts, text=detail, font=FONT_ST_MONO_11, text_color=color, anchor="w", height=16).pack(fill="x")

    def _style_confirm(self, enabled: bool) -> None:
        """Stitch: nút xác nhận bị khóa thì xám mờ, không phải cyan."""
        button = self.confirm_button
        button.set_enabled(enabled)
        if enabled:
            button.configure(fg_color=STITCH_CYAN, border_color=STITCH_CYAN)
        else:
            button.configure(fg_color=DISABLED_BG, border_color=STITCH_INPUT_BORDER, text_color_disabled=STITCH_TEXT_DIM)

    @property
    def banner_text(self) -> str:
        label = getattr(self, "_banner_label", None)
        try:
            return label.cget("text") if label is not None else ""
        except tk.TclError:
            return ""

    # ------------------------------------------------------------------
    # Nạp tiền khi thiếu số dư
    # ------------------------------------------------------------------
    def open_top_up(self) -> None:
        customer = self._customer
        if customer is None or self.is_submitting:
            return
        customers = self._context.services.customers
        self._top_up_button.set_busy(True)

        def show(detail: Customer | None) -> None:
            self._top_up_button.set_busy(False)
            dialog = TopUpDialog(
                self,
                self._context,
                customer,
                account_code=detail.account.code if detail is not None else "",
                runner=self._runner,
                on_success=self._after_top_up,
            )
            dialog.bind("<Destroy>", lambda event: self._regrab() if event.widget is dialog else None, add="+")

        self._runner.submit(self, lambda: customers.get_customer(customer.customer_id), show, lambda _error: show(None))

    def _after_top_up(self, result: TopUpResult) -> None:
        notify_success(self, TOP_UP_DONE.format(balance=format_money(result.balance_after)))
        if self._customer is not None and self._customer.customer_id == result.customer_id:
            self._customer = dataclasses.replace(self._customer, balance=result.balance_after)
            self.check_eligibility()

    def _regrab(self) -> None:
        try:
            if self.winfo_exists():
                self.grab_set()
                self.focus_set()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Xác nhận
    # ------------------------------------------------------------------
    def submit(self) -> None:
        if self.is_submitting or self._phase != ELIGIBLE or self._customer is None:
            return
        self.set_submitting(True)
        self._top_up_button.set_enabled(False)
        sessions, session = self._context.services.sessions, self._context.session
        customer_id, machine_id = self._customer.customer_id, self._machine.machine_id
        self._runner.submit(
            self,
            lambda: sessions.open_session(customer_id, machine_id, session),
            self._on_opened_ok,
            self._on_open_failed,
        )

    def _on_opened_ok(self, summary: SessionSummary) -> None:
        self.set_submitting(False)
        callback = self._on_opened
        self.close()
        if callback is not None:
            callback(summary)

    def _on_open_failed(self, error: Exception) -> None:
        self.set_submitting(False)
        self._top_up_button.set_enabled(True)
        if isinstance(error, InsufficientBalanceError):
            notify_error(self, error)
            self.check_eligibility()  # số dư đã đổi -> hiện CTA Nạp tiền
            return
        if isinstance(error, ConflictError):
            notify_error(self, error, conflict_as_alert=True)
            self._set_blocked(conflict_reason(error))
            return
        notify_error(self, error)

    def close(self) -> None:
        if self._search_after is not None:
            try:
                self.after_cancel(self._search_after)
            except tk.TclError:
                pass
            self._search_after = None
        super().close()
