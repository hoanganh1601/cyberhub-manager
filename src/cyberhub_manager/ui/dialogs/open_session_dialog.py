"""OpenSessionDialog — Hộp thoại modal Mở phiên sử dụng cho máy trạm.

Tuân thủ thiết kế Stitch:
- Tham chiếu: docs/ui-reference/m_phi_n_s_d_ng_cyberhub_manager_1280x720/code.html
- Tham chiếu trạng thái không đủ điều kiện: docs/ui-reference/m_phi_n_s_d_ng_kh_ng_s_d_1280x720/code.html
- Kích thước: 580x640, nền STITCH_BG_CHROME (#111726), viền #273147.
- Khối 1: Thông tin máy (Mã, Tên, Trạng thái Trống, Giá hiện tại).
- Khối 2: Tìm kiếm và thẻ hồ sơ khách hàng (Mã KH, Tên, SĐT, Username, Dual badges Trạng thái).
- Khối 3: Chỉ số tài chính (Số dư hiện tại, Số dư tối thiểu, Thời gian ước tính).
- Khối 4: Banner trạng thái đủ điều kiện hoặc cảnh báo không đủ số dư / tài khoản bị khóa.
- Khối 5: Ghi chú vận hành và quy tắc cước.
- Chân trang: Phím tắt Enter/Esc, Nút Hủy, Nút Nạp tiền (khi thiếu số dư), Nút Xác nhận mở phiên.
"""

from __future__ import annotations

import logging
from typing import Any

import customtkinter as ctk

from ...domain.dtos import CustomerSummary, EmployeeSession, MachineSummary
from ...domain.enums import AccountStatus, CustomerStatus, MachineStatus
from ...domain.exceptions import ApplicationError
from ...domain.models import estimate_play_minutes, minimum_balance
from ..components import ActionButton, ToastManager
from ..formatters import format_money
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
    STITCH_NAV_ACTIVE_BORDER,
    STITCH_SUNKEN_BG,
    STITCH_TEXT,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_ON_CYAN,
    STITCH_TEXT_STRONG,
)
from .topup_dialog import TopUpDialog

logger = logging.getLogger(__name__)


class OpenSessionDialog(ctk.CTkToplevel):
    """Hộp thoại modal mở phiên sử dụng cho máy trạm."""

    def __init__(
        self,
        parent: Any,
        services: Any,
        machine: MachineSummary,
        *,
        actor: EmployeeSession,
        initial_customer: CustomerSummary | None = None,
        language: str = "vi",
        on_success: Any = None,
    ) -> None:
        super().__init__(parent)
        self._services = services
        self._machine = machine
        self._actor = actor
        self._language = language
        self._on_success = on_success

        self._selected_customer: CustomerSummary | None = initial_customer
        self._is_submitting = False
        self._search_results: list[CustomerSummary] = []

        is_vi = language == "vi"
        self.title("Mở phiên sử dụng" if is_vi else "Open Session")
        self.geometry("580x640")
        self.resizable(False, False)
        self.configure(fg_color=STITCH_BG_CANVAS)

        self.transient(parent)
        self.grab_set()

        self._build_ui()

        if self._selected_customer:
            self._apply_customer_selection(self._selected_customer)
        else:
            self._update_metrics_and_eligibility()

        self.bind("<Escape>", lambda _e: self._handle_close())
        self.bind("<Return>", lambda _e: self._handle_confirm_pressed())
        self.after(50, lambda: self._search_entry.focus_set() if hasattr(self, "_search_entry") else None)

    def _handle_close(self) -> None:
        if not self._is_submitting and self.winfo_exists():
            self.destroy()

    def _handle_confirm_pressed(self) -> None:
        if self._can_open_session():
            self._handle_confirm()

    def _build_ui(self) -> None:
        is_vi = self._language == "vi"

        container = ctk.CTkFrame(
            self,
            fg_color=STITCH_BG_CHROME,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=RADIUS_DIALOG,
        )
        container.pack(fill="both", expand=True, padx=12, pady=12)

        # ------------------------------------------------------------------
        # Header
        # ------------------------------------------------------------------
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 10))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            title_box,
            text="Mở phiên sử dụng" if is_vi else "Open Workstation Session",
            font=FONT_ST_PAGE_TITLE,
            text_color=STITCH_TEXT_STRONG,
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Kiểm tra khách hàng và xác nhận mở phiên" if is_vi else "Verify customer details and confirm session opening",
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

        ctk.CTkFrame(container, fg_color=STITCH_BORDER, height=1).pack(fill="x", padx=16, pady=(0, 10))

        # ------------------------------------------------------------------
        # SECTION 1: THÔNG TIN MÁY
        # ------------------------------------------------------------------
        mach_card = ctk.CTkFrame(
            container,
            fg_color=STITCH_SUNKEN_BG,
            border_width=1,
            border_color=STITCH_BORDER,
            corner_radius=8,
            height=68,
        )
        mach_card.pack(fill="x", padx=16, pady=(0, 10))
        mach_card.pack_propagate(False)

        mach_inner = ctk.CTkFrame(mach_card, fg_color="transparent")
        mach_inner.pack(fill="both", expand=True, padx=12, pady=8)

        ctk.CTkLabel(
            mach_inner,
            text="THÔNG TIN MÁY" if is_vi else "MACHINE INFO",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_TEXT_MUTED,
        ).pack(anchor="w")

        cols_grid = ctk.CTkFrame(mach_inner, fg_color="transparent")
        cols_grid.pack(fill="x", pady=(2, 0))
        for c in range(4):
            cols_grid.grid_columnconfigure(c, weight=1)

        # Col 0: Mã máy
        c0 = ctk.CTkFrame(cols_grid, fg_color="transparent")
        c0.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(c0, text="Mã máy" if is_vi else "Code", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED).pack(anchor="w")
        ctk.CTkLabel(c0, text=self._machine.machine_code, font=FONT_ST_METRIC_LG, text_color=STITCH_TEXT_STRONG).pack(anchor="w")

        # Col 1: Tên máy
        c1 = ctk.CTkFrame(cols_grid, fg_color="transparent")
        c1.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(c1, text="Tên máy" if is_vi else "Name", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED).pack(anchor="w")
        ctk.CTkLabel(c1, text=self._machine.name, font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT).pack(anchor="w")

        # Col 2: Trạng thái
        c2 = ctk.CTkFrame(cols_grid, fg_color="transparent")
        c2.grid(row=0, column=2, sticky="w")
        ctk.CTkLabel(c2, text="Trạng thái" if is_vi else "Status", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED).pack(anchor="w")
        st_pill = ctk.CTkFrame(c2, fg_color="#132E27", corner_radius=10, height=20)
        st_pill.pack(anchor="w", pady=(2, 0))
        st_name = "Trống" if self._machine.status == MachineStatus.AVAILABLE else self._machine.status.value
        ctk.CTkLabel(st_pill, text=f"● {st_name}", font=FONT_ST_MONO_XS_STRONG, text_color=STITCH_EMERALD).pack(padx=6, pady=1)

        # Col 3: Giá hiện tại
        c3 = ctk.CTkFrame(cols_grid, fg_color="transparent")
        c3.grid(row=0, column=3, sticky="w")
        ctk.CTkLabel(c3, text="Giá hiện tại" if is_vi else "Rate", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED).pack(anchor="w")
        ctk.CTkLabel(
            c3,
            text=f"{format_money(self._machine.hourly_rate)} VND/h",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_CYAN,
        ).pack(anchor="w")

        # ------------------------------------------------------------------
        # SECTION 2: KHÁCH HÀNG (Search & Profile Card)
        # ------------------------------------------------------------------
        cus_section = ctk.CTkFrame(container, fg_color="transparent")
        cus_section.pack(fill="x", padx=16, pady=(0, 10))

        cus_hdr = ctk.CTkFrame(cus_section, fg_color="transparent")
        cus_hdr.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(
            cus_hdr,
            text="Khách hàng" if is_vi else "Customer",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT_STRONG,
        ).pack(side="left")

        self._cus_status_lbl = ctk.CTkLabel(
            cus_hdr,
            text="○ Chưa chọn khách hàng" if is_vi else "○ No customer selected",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_TEXT_MUTED,
        )
        self._cus_status_lbl.pack(side="right")

        # Search Bar
        search_wrap = ctk.CTkFrame(
            cus_section,
            fg_color=STITCH_INPUT_BG,
            border_width=1,
            border_color=STITCH_INPUT_BORDER,
            corner_radius=6,
            height=34,
        )
        search_wrap.pack(fill="x")
        search_wrap.pack_propagate(False)

        ctk.CTkLabel(search_wrap, text=" 🔍 ", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED).pack(side="left", padx=(4, 0))

        self._search_entry = ctk.CTkEntry(
            search_wrap,
            placeholder_text="Tìm theo mã, tên, SĐT hoặc tên đăng nhập..." if is_vi else "Search by code, name, phone or username...",
            font=FONT_ST_BODY,
            fg_color="transparent",
            border_width=0,
            text_color=STITCH_TEXT_STRONG,
        )
        self._search_entry.pack(side="left", fill="both", expand=True, padx=4)
        self._search_entry.bind("<KeyRelease>", lambda _e: self._on_search_key())

        self._search_icon_right = ctk.CTkLabel(search_wrap, text="", font=FONT_ST_MONO_SM, text_color=STITCH_EMERALD)
        self._search_icon_right.pack(side="right", padx=(0, 8))

        # Search dropdown container (visible when typing search results)
        self._dropdown_frame = ctk.CTkFrame(
            cus_section,
            fg_color="#0A0E17",
            border_width=1,
            border_color=STITCH_BORDER,
            corner_radius=6,
        )

        # Customer Profile Card
        self._profile_card = ctk.CTkFrame(
            cus_section,
            fg_color=STITCH_SUNKEN_BG,
            border_width=1,
            border_color=STITCH_BORDER,
            corner_radius=8,
        )
        self._profile_card.pack(fill="x", pady=(6, 0))

        p_inner = ctk.CTkFrame(self._profile_card, fg_color="transparent")
        p_inner.pack(fill="both", expand=True, padx=12, pady=10)

        row_top = ctk.CTkFrame(p_inner, fg_color="transparent")
        row_top.pack(fill="x", pady=(0, 4))

        self._cus_code_badge = ctk.CTkLabel(
            row_top,
            text="CUS-0000",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_CYAN,
            fg_color=STITCH_NAV_ACTIVE_BG,
            corner_radius=4,
            padx=6,
            pady=1,
        )
        self._cus_code_badge.pack(side="left", padx=(0, 8))

        self._cus_name_lbl = ctk.CTkLabel(
            row_top,
            text="Chưa chọn khách hàng",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT_STRONG,
        )
        self._cus_name_lbl.pack(side="left", padx=(0, 8))

        self._cus_phone_lbl = ctk.CTkLabel(
            row_top,
            text="",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        )
        self._cus_phone_lbl.pack(side="left")

        self._cus_username_badge = ctk.CTkLabel(
            row_top,
            text="",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT,
            fg_color="#1E273A",
            corner_radius=4,
            padx=6,
            pady=1,
        )
        self._cus_username_badge.pack(side="right")

        # Divider inside profile
        ctk.CTkFrame(p_inner, fg_color=STITCH_BORDER, height=1).pack(fill="x", pady=(2, 6))

        # Bottom row inside profile: dual status pills
        row_bottom = ctk.CTkFrame(p_inner, fg_color="transparent")
        row_bottom.pack(fill="x")

        self._status_kh_pill = ctk.CTkLabel(
            row_bottom,
            text="Trạng thái KH: —",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_TEXT_MUTED,
            fg_color="#171F30",
            corner_radius=10,
            padx=8,
            pady=2,
        )
        self._status_kh_pill.pack(side="left", padx=(0, 8))

        self._status_tk_pill = ctk.CTkLabel(
            row_bottom,
            text="Trạng thái TK: —",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_TEXT_MUTED,
            fg_color="#171F30",
            corner_radius=10,
            padx=8,
            pady=2,
        )
        self._status_tk_pill.pack(side="left")

        # ------------------------------------------------------------------
        # SECTION 3: FINANCIAL METRICS & ELIGIBILITY BANNER
        # ------------------------------------------------------------------
        finance_card = ctk.CTkFrame(
            container,
            fg_color=STITCH_SUNKEN_BG,
            border_width=1,
            border_color=STITCH_BORDER,
            corner_radius=8,
        )
        finance_card.pack(fill="x", padx=16, pady=(0, 10))

        f_inner = ctk.CTkFrame(finance_card, fg_color="transparent")
        f_inner.pack(fill="both", expand=True, padx=12, pady=10)

        f_grid = ctk.CTkFrame(f_inner, fg_color="transparent")
        f_grid.pack(fill="x")
        for c in range(3):
            f_grid.grid_columnconfigure(c, weight=1)

        # Col 0: Số dư hiện tại
        fc0 = ctk.CTkFrame(f_grid, fg_color="transparent")
        fc0.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(fc0, text="Số dư hiện tại" if is_vi else "Current Balance", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED).pack(anchor="w")
        self._metric_balance = ctk.CTkLabel(fc0, text="—", font=FONT_ST_METRIC_LG, text_color=STITCH_TEXT_MUTED)
        self._metric_balance.pack(anchor="w")

        # Col 1: Số dư tối thiểu
        fc1 = ctk.CTkFrame(f_grid, fg_color="transparent")
        fc1.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(fc1, text="Số dư tối thiểu" if is_vi else "Min Required", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED).pack(anchor="w")
        min_req = minimum_balance(self._machine.hourly_rate)
        self._metric_min_balance = ctk.CTkLabel(fc1, text=f"{format_money(min_req)} VND", font=FONT_ST_METRIC_LG, text_color=STITCH_TEXT)
        self._metric_min_balance.pack(anchor="w")

        # Col 2: Thời gian ước tính
        fc2 = ctk.CTkFrame(f_grid, fg_color="transparent")
        fc2.grid(row=0, column=2, sticky="w")
        ctk.CTkLabel(fc2, text="Thời gian ước tính" if is_vi else "Est. Play Time", font=FONT_ST_MONO_XS, text_color=STITCH_TEXT_MUTED).pack(anchor="w")
        self._metric_est_time = ctk.CTkLabel(fc2, text="—", font=FONT_ST_METRIC_LG, text_color=STITCH_CYAN)
        self._metric_est_time.pack(anchor="w")

        # Eligibility Banner
        self._banner_frame = ctk.CTkFrame(
            f_inner,
            fg_color="#121824",
            border_width=1,
            border_color=STITCH_BORDER,
            corner_radius=6,
            height=38,
        )
        self._banner_frame.pack(fill="x", pady=(10, 0))

        self._banner_label = ctk.CTkLabel(
            self._banner_frame,
            text="Vui lòng tìm và chọn khách hàng để mở phiên",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT_MUTED,
        )
        self._banner_label.pack(fill="both", expand=True, padx=10, pady=6)

        # ------------------------------------------------------------------
        # SECTION 4: OPERATIONAL NOTE
        # ------------------------------------------------------------------
        note_row = ctk.CTkFrame(container, fg_color="transparent")
        note_row.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(
            note_row,
            text="ℹ",
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left", anchor="n", padx=(0, 6))

        rate_fmt = format_money(self._machine.hourly_rate)
        note_text = (
            f"Đơn giá {rate_fmt} VND/giờ sẽ được ghi nhận vào phiên. Phiên chưa trừ tiền cho đến khi kết thúc hoặc tính cước theo thời gian thực."
            if is_vi
            else f"Rate of {rate_fmt} VND/h will be logged. Balance is settled when session concludes or billed in real-time."
        )
        ctk.CTkLabel(
            note_row,
            text=note_text,
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            justify="left",
            wraplength=520,
        ).pack(side="left", fill="x", expand=True)

        # ------------------------------------------------------------------
        # SECTION 5: FOOTER ACTIONS
        # ------------------------------------------------------------------
        ctk.CTkFrame(container, fg_color=STITCH_BORDER, height=1).pack(fill="x", padx=16, pady=(0, 10))

        footer = ctk.CTkFrame(container, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(0, 14))

        self._shortcut_hint = ctk.CTkLabel(
            footer,
            text="Nhấn Esc để hủy" if is_vi else "Press Esc to cancel",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        )
        self._shortcut_hint.pack(side="left")

        actions_right = ctk.CTkFrame(footer, fg_color="transparent")
        actions_right.pack(side="right")

        self._btn_cancel = ActionButton(
            actions_right,
            text="Hủy" if is_vi else "Cancel",
            kind="ghost",
            width=70,
            height=34,
            command=self._handle_close,
        )
        self._btn_cancel.pack(side="left", padx=(0, 6))

        self._btn_topup = ActionButton(
            actions_right,
            text="+ Nạp tiền" if is_vi else "+ Top Up",
            kind="primary",
            width=100,
            height=34,
            command=self._handle_topup,
        )
        # Sẽ pack nút Nạp tiền khi số dư thiếu

        self._btn_confirm = ActionButton(
            actions_right,
            text="Xác nhận mở phiên" if is_vi else "Confirm Session",
            kind="primary",
            width=140,
            height=34,
            command=self._handle_confirm,
        )
        self._btn_confirm.pack(side="left")

    # ------------------------------------------------------------------
    # Customer Search & Selection
    # ------------------------------------------------------------------
    def _on_search_key(self) -> None:
        kw = self._search_entry.get().strip()
        if not kw:
            self._hide_dropdown()
            self._search_icon_right.configure(text="")
            return

        try:
            results = self._services.customers.search_customers(kw)
            self._search_results = results

            # Nếu từ khóa khớp chính xác mã hoặc SĐT của duy nhất 1 khách: tự chọn
            exact_match = next(
                (c for c in results if c.customer_code.upper() == kw.upper() or c.phone == kw or c.username.lower() == kw.lower()),
                None,
            )
            if exact_match and len(results) == 1:
                self._apply_customer_selection(exact_match)
                self._hide_dropdown()
                return

            if results:
                self._show_dropdown(results[:4])
            else:
                self._hide_dropdown()
        except Exception as e:
            logger.warning("Lỗi tìm kiếm khách hàng: %s", e)
            self._hide_dropdown()

    def _show_dropdown(self, customers: list[CustomerSummary]) -> None:
        for c in self._dropdown_frame.winfo_children():
            c.destroy()

        self._dropdown_frame.pack(fill="x", pady=(4, 0))

        for cus in customers:
            row_btn = ctk.CTkButton(
                self._dropdown_frame,
                text=f"{cus.customer_code} • {cus.full_name} ({cus.phone}) - TK: {cus.username} [Số dư: {format_money(cus.balance)}đ]",
                anchor="w",
                font=FONT_ST_MONO_XS,
                fg_color="transparent",
                hover_color=STITCH_NAV_ACTIVE_BG,
                text_color=STITCH_TEXT_STRONG,
                height=26,
                command=lambda c=cus: self._apply_customer_selection(c),
            )
            row_btn.pack(fill="x", padx=4, pady=2)

    def _hide_dropdown(self) -> None:
        self._dropdown_frame.pack_forget()

    def _apply_customer_selection(self, cus: CustomerSummary) -> None:
        self._selected_customer = cus
        self._hide_dropdown()

        # Update search bar
        self._search_entry.delete(0, "end")
        self._search_entry.insert(0, f"{cus.phone} - {cus.full_name}")
        self._search_icon_right.configure(text="✓")

        is_vi = self._language == "vi"
        self._cus_status_lbl.configure(
            text="● Đã định danh" if is_vi else "● Identified",
            text_color=STITCH_EMERALD,
        )

        # Profile card updates
        self._cus_code_badge.configure(text=cus.customer_code)
        self._cus_name_lbl.configure(text=cus.full_name)
        self._cus_phone_lbl.configure(text=f"• {cus.phone}")
        self._cus_username_badge.configure(text=f"TK: {cus.username}")

        kh_active = cus.customer_status == CustomerStatus.ACTIVE
        self._status_kh_pill.configure(
            text=f"Trạng thái KH: {'Hoạt động' if kh_active else 'Bị khóa'}" if is_vi else f"Customer: {'Active' if kh_active else 'Locked'}",
            text_color=STITCH_EMERALD if kh_active else STITCH_DANGER,
            fg_color="#132E27" if kh_active else "#2D151F",
        )

        tk_active = cus.account_status == AccountStatus.ACTIVE
        self._status_tk_pill.configure(
            text=f"Trạng thái TK: {'Hoạt động' if tk_active else 'Bị khóa'}" if is_vi else f"Account: {'Active' if tk_active else 'Locked'}",
            text_color=STITCH_EMERALD if tk_active else STITCH_DANGER,
            fg_color="#132E27" if tk_active else "#2D151F",
        )

        self._update_metrics_and_eligibility()

    # ------------------------------------------------------------------
    # Metrics & Eligibility Assessment
    # ------------------------------------------------------------------
    def _can_open_session(self) -> bool:
        if not self._selected_customer:
            return False
        cus = self._selected_customer
        if cus.customer_status != CustomerStatus.ACTIVE or cus.account_status != AccountStatus.ACTIVE:
            return False
        min_req = minimum_balance(self._machine.hourly_rate)
        return cus.balance >= min_req

    def _update_metrics_and_eligibility(self) -> None:
        is_vi = self._language == "vi"
        min_req = minimum_balance(self._machine.hourly_rate)

        if not self._selected_customer:
            self._metric_balance.configure(text="—", text_color=STITCH_TEXT_MUTED)
            self._metric_est_time.configure(text="—", text_color=STITCH_CYAN)
            self._banner_frame.configure(fg_color="#121824", border_color=STITCH_BORDER)
            self._banner_label.configure(
                text="Vui lòng tìm và chọn khách hàng để mở phiên" if is_vi else "Please search and select customer",
                text_color=STITCH_TEXT_MUTED,
            )
            self._shortcut_hint.configure(text="Nhấn Esc để hủy" if is_vi else "Press Esc to cancel")
            self._btn_topup.pack_forget()
            self._btn_confirm.set_enabled(False)
            return

        cus = self._selected_customer
        balance = cus.balance
        self._metric_balance.configure(
            text=f"{format_money(balance)} VND",
            text_color=STITCH_EMERALD if balance >= min_req else STITCH_DANGER,
        )

        # Kiểm tra trạng thái tài khoản
        if cus.customer_status != CustomerStatus.ACTIVE or cus.account_status != AccountStatus.ACTIVE:
            self._metric_est_time.configure(text="Không khả dụng" if is_vi else "Unavailable", text_color=STITCH_TEXT_MUTED)
            self._banner_frame.configure(fg_color="#2D151F", border_color=STITCH_DANGER)
            self._banner_label.configure(
                text="⚠ Tài khoản hoặc hồ sơ khách hàng đang bị khóa, không thể mở phiên!" if is_vi else "⚠ Account or customer is locked, cannot start session!",
                text_color=STITCH_DANGER,
            )
            self._shortcut_hint.configure(text="Nhấn Esc để hủy" if is_vi else "Press Esc to cancel")
            self._btn_topup.pack_forget()
            self._btn_confirm.set_enabled(False)
            return

        # Kiểm tra số dư
        if balance < min_req:
            deficit = min_req - balance
            self._metric_est_time.configure(text="Không khả dụng" if is_vi else "Unavailable", text_color=STITCH_TEXT_MUTED)
            self._banner_frame.configure(fg_color="#2D151F", border_color=STITCH_DANGER)
            self._banner_label.configure(
                text=f"⚠ Số dư chưa đạt mức tối thiểu. Vui lòng nạp thêm ít nhất {format_money(deficit)} VND"
                if is_vi
                else f"⚠ Insufficient balance. Please top up at least {format_money(deficit)} VND",
                text_color=STITCH_DANGER,
            )
            self._shortcut_hint.configure(text="Nhấn Esc để hủy" if is_vi else "Press Esc to cancel")

            # Hiển thị nút nạp tiền
            self._btn_topup.pack(side="left", padx=(0, 6))
            self._btn_confirm.set_enabled(False)
            return

        # Đủ điều kiện!
        play_mins = estimate_play_minutes(balance, self._machine.hourly_rate)
        hours = play_mins // 60
        mins = play_mins % 60
        time_str = f"{hours} giờ {mins} phút" if is_vi else f"{hours}h {mins}m"

        self._metric_est_time.configure(text=time_str, text_color=STITCH_CYAN)
        self._banner_frame.configure(fg_color="#132E27", border_color="#1B4D3E")
        self._banner_label.configure(
            text="✓ Khách hàng đủ điều kiện mở phiên" if is_vi else "✓ Customer is eligible to start session",
            text_color=STITCH_EMERALD,
        )
        self._shortcut_hint.configure(
            text="Nhấn Enter để xác nhận • Esc để hủy" if is_vi else "Press Enter to confirm • Esc to cancel"
        )
        self._btn_topup.pack_forget()
        self._btn_confirm.set_enabled(True)

    # ------------------------------------------------------------------
    # Actions: TopUp & Confirm
    # ------------------------------------------------------------------
    def _handle_topup(self) -> None:
        if not self._selected_customer:
            return

        def on_topup_success() -> None:
            if not self.winfo_exists():
                return
            try:
                updated_cus = self._services.customers.get_customer(self._selected_customer.customer_id)
                self._apply_customer_selection(updated_cus)
            except Exception as err:
                logger.warning("Không nạp lại được khách hàng sau topup: %s", err)

        TopUpDialog(
            self,
            self._services,
            self._selected_customer,
            employee_id=self._actor.employee_id,
            language=self._language,
            on_success=on_topup_success,
        )

    def _handle_confirm(self) -> None:
        if self._is_submitting or not self._can_open_session():
            return

        assert self._selected_customer is not None
        is_vi = self._language == "vi"
        self._set_submitting(True)

        try:
            res = self._services.sessions.open_session(
                customer_id=self._selected_customer.customer_id,
                machine_id=self._machine.machine_id,
                actor=self._actor,
            )
            ToastManager.show(
                self.master,
                f"Đã mở phiên {res.session_code} trên máy {self._machine.machine_code}!"
                if is_vi
                else f"Opened session {res.session_code} on {self._machine.machine_code}!",
                kind="success",
            )
            if self._on_success:
                self._on_success()
            if self.winfo_exists():
                self.destroy()

        except ApplicationError as err:
            logger.warning("Lỗi mở phiên: %s", err)
            ToastManager.show(self, get_user_friendly_error(err), kind="error")
        except Exception:
            logger.exception("Lỗi không mong muốn khi mở phiên")
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")
        finally:
            if self.winfo_exists():
                self._set_submitting(False)

    def _set_submitting(self, busy: bool) -> None:
        self._is_submitting = busy
        self._btn_confirm.set_busy(busy)
        self._btn_cancel.set_enabled(not busy)
        self._btn_topup.set_enabled(not busy)
        self._search_entry.configure(state="disabled" if busy else "normal")
