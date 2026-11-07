"""CustomerLockDialog — Hộp thoại xác nhận khóa hoặc mở khóa tài khoản khách hàng.

Tuân thủ thiết kế Stitch:
- Tham chiếu: docs/ui-reference/kh_a_kh_ch_h_ng_t_i_kho_n_confirm/code.html
- Tham chiếu mở khóa: docs/ui-reference/m_kh_a_kh_ch_h_ng_t_i_kho_n_confirm/code.html
- Hiển thị metadata khách hàng, bảng liệt kê hệ quả, lưu ý khóa mềm, nút xác nhận màu theo trạng thái.
"""

from __future__ import annotations

import logging
from typing import Any

import customtkinter as ctk

from ...domain.dtos import CustomerSummary
from ...domain.enums import CustomerStatus
from ...domain.exceptions import ApplicationError
from ..components import ActionButton, ToastManager
from ..formatters import format_money
from ..icons import get_icon
from ..messages import MSG_OPERATION_FAILED, get_user_friendly_error
from ..theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
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
    STITCH_DANGER_HOVER_BG,
    STITCH_NAV_ACTIVE_BG,
    STITCH_RADIUS,
    STITCH_SUCCESS,
    STITCH_SUNKEN_BG,
    STITCH_SUNKEN_BORDER,
    STITCH_TEXT,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
)

logger = logging.getLogger(__name__)


class CustomerLockDialog(ctk.CTkToplevel):
    """Hộp thoại xác nhận Khóa / Mở khóa tài khoản khách hàng."""

    def __init__(
        self,
        parent: Any,
        services: Any,
        customer: CustomerSummary,
        actor: Any,
        *,
        language: str = "vi",
        on_success: Any = None,
    ) -> None:
        super().__init__(parent)
        self._services = services
        self._customer = customer
        self._actor = actor
        self._language = language
        self._on_success = on_success

        is_vi = language == "vi"
        self._is_active = customer.customer_status == CustomerStatus.ACTIVE
        self._target_status = CustomerStatus.INACTIVE if self._is_active else CustomerStatus.ACTIVE

        title_str = (
            ("Khóa tài khoản khách hàng" if self._is_active else "Mở khóa tài khoản khách hàng")
            if is_vi
            else ("Lock Customer Account" if self._is_active else "Unlock Customer Account")
        )

        self._is_submitting = False

        self.title(title_str)
        diag_w = 490 if self._is_active else 520
        self.geometry(f"{diag_w}x570")
        self.resizable(False, False)
        self.configure(fg_color=STITCH_BG_CANVAS)

        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self.bind("<Escape>", lambda _e: self._on_escape())
        self.bind("<Return>", lambda _e: self._handle_confirm())
        self.after(
            50,
            lambda: (
                self._reason_entry.focus_set()
                if hasattr(self, "_reason_entry") and self._reason_entry
                else (self._btn_confirm.focus_set() if hasattr(self, "_btn_confirm") else None)
            ),
        )

    def _on_escape(self) -> None:
        if not self._is_submitting:
            self.destroy()

    def _build_ui(self) -> None:
        is_vi = self._language == "vi"
        is_lock = self._is_active
        accent_color = STITCH_DANGER if is_lock else STITCH_SUCCESS
        accent_bg = STITCH_DANGER_HOVER_BG if is_lock else STITCH_NAV_ACTIVE_BG

        # Outer card container
        card = ctk.CTkFrame(
            self,
            fg_color="#121824",
            border_width=1,
            border_color="#27344E",
            corner_radius=12,
        )
        card.pack(fill="both", expand=True, padx=12, pady=12)

        # 1. Header (px-5 py-3.5 bg-[#0E131E] border-b border-[#212B3E])
        header = ctk.CTkFrame(card, fg_color="#0E131E", corner_radius=0, height=54)
        header.pack(fill="x")
        header.pack_propagate(False)

        h_inner = ctk.CTkFrame(header, fg_color="transparent")
        h_inner.pack(fill="both", expand=True, padx=16, pady=8)

        # Icon pill
        icon_name = "lock" if is_lock else "unlock"
        icon_box = ctk.CTkLabel(
            h_inner,
            text="",
            image=get_icon(icon_name, accent_color, size=(16, 16)),
            width=32,
            height=32,
            corner_radius=8,
            fg_color=accent_bg,
        )
        icon_box.pack(side="left")

        # Title + Subtitle
        text_box = ctk.CTkFrame(h_inner, fg_color="transparent")
        text_box.pack(side="left", padx=(10, 0))

        title_text = (
            ("Khóa tài khoản khách hàng" if is_lock else "Mở khóa tài khoản khách hàng")
            if is_vi
            else ("Lock customer account" if is_lock else "Unlock customer account")
        )
        t_wrap = ctk.CTkFrame(text_box, fg_color="transparent")
        t_wrap.pack(anchor="w")
        ctk.CTkLabel(
            t_wrap,
            text=title_text,
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT_STRONG,
            anchor="w",
        ).pack(side="left")

        if not is_lock:
            ctk.CTkLabel(
                t_wrap,
                text="Kích hoạt lại" if is_vi else "Reactivation",
                font=FONT_ST_MONO_XS_STRONG,
                text_color=STITCH_CYAN,
                fg_color="#0C2E40",
                corner_radius=4,
                padx=6,
                pady=1,
            ).pack(side="left", padx=(6, 0))

        sub_text = (
            ("Hạn chế quyền truy cập và vô hiệu hóa các hoạt động" if is_lock else "Khôi phục toàn bộ quyền truy cập và sử dụng dịch vụ")
            if is_vi
            else ("Restrict access and disable active operations" if is_lock else "Restore full access and operational services")
        )
        ctk.CTkLabel(
            text_box,
            text=sub_text,
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w")

        # Close X button
        close_btn = ctk.CTkButton(
            h_inner,
            text="",
            image=get_icon("close", STITCH_TEXT_MUTED, size=(12, 12)),
            width=28,
            height=28,
            corner_radius=6,
            fg_color="transparent",
            hover_color="#1E273A",
            command=self.destroy,
        )
        close_btn.pack(side="right")

        # 2. Body (p-5 space-y-3.5)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # Confirm question
        q_text = (
            f"Bạn có chắc chắn muốn {'khóa' if is_lock else 'mở khóa'} khách hàng {self._customer.full_name}?"
            if is_vi
            else f"Are you sure you want to {'lock' if is_lock else 'unlock'} customer {self._customer.full_name}?"
        )
        ctk.CTkLabel(
            body,
            text=q_text,
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT,
            anchor="w",
            wraplength=430,
        ).pack(anchor="w", pady=(0, 8))

        # Metadata grid box (bg-[#0B101B] border border-[#212B3E] rounded-lg p-3)
        meta_box = ctk.CTkFrame(
            body,
            fg_color="#0B101B",
            border_width=1,
            border_color="#212B3E",
            corner_radius=8,
        )
        meta_box.pack(fill="x", pady=(0, 10))

        m_inner = ctk.CTkFrame(meta_box, fg_color="transparent")
        m_inner.pack(fill="x", padx=10, pady=8)
        m_inner.grid_columnconfigure(0, weight=1)
        m_inner.grid_columnconfigure(1, weight=1)

        # Row 1: Mã KH & Mã TK
        self._add_meta_cell(m_inner, 0, 0, "MÃ KHÁCH HÀNG" if is_vi else "CUSTOMER CODE", self._customer.customer_code, STITCH_CYAN)
        self._add_meta_cell(m_inner, 0, 1, "MÃ TÀI KHOẢN" if is_vi else "ACCOUNT CODE", f"ACC-{self._customer.account_id:04d}", STITCH_CYAN)

        # Row 2: Tên đăng nhập & Số dư hiện tại
        self._add_meta_cell(m_inner, 1, 0, "TÊN ĐĂNG NHẬP" if is_vi else "USERNAME", self._customer.username, STITCH_TEXT)
        bal_color = STITCH_DANGER if self._customer.balance < 0 else STITCH_SUCCESS
        self._add_meta_cell(m_inner, 1, 1, "SỐ DƯ HIỆN TẠI" if is_vi else "CURRENT BALANCE", format_money(self._customer.balance), bal_color)

        # Consequences box (bg-rose-950/20 border border-rose-500/30)
        c_box = ctk.CTkFrame(
            body,
            fg_color=accent_bg,
            border_width=1,
            border_color=accent_color,
            corner_radius=8,
        )
        c_box.pack(fill="x", pady=(0, 10))

        c_inner = ctk.CTkFrame(c_box, fg_color="transparent")
        c_inner.pack(fill="x", padx=10, pady=8)

        c_title = (
            ("Hệ quả của thao tác này:" if is_lock else "Quyền lợi sau khi mở khóa:")
            if is_vi
            else ("Consequences of this action:" if is_lock else "Benefits upon unlocking:")
        )
        ctk.CTkLabel(
            c_inner,
            text=c_title,
            font=FONT_ST_BODY_STRONG,
            text_color=accent_color,
            anchor="w",
        ).pack(anchor="w", pady=(0, 4))

        if is_lock:
            bullets = [
                "• Trạng thái khách hàng sẽ chuyển sang NGỪNG HOẠT ĐỘNG." if is_vi else "• Customer status will become INACTIVE.",
                "• Trạng thái tài khoản sẽ chuyển sang BỊ KHÓA." if is_vi else "• Account status will become LOCKED.",
                "• Không thể mở phiên chơi mới hoặc nạp thêm tiền." if is_vi else "• New sessions and wallet top-ups will be unavailable.",
                "• Số dư và lịch sử giao dịch vẫn được bảo lưu toàn vẹn." if is_vi else "• Balance and transaction history will be preserved.",
            ]
        else:
            bullets = [
                "• Trạng thái khách hàng sẽ chuyển sang HOẠT ĐỘNG." if is_vi else "• Customer status will become ACTIVE.",
                "• Trạng thái tài khoản sẽ chuyển sang HOẠT ĐỘNG." if is_vi else "• Account status will become ACTIVE.",
                "• Khách hàng có thể đăng nhập mở máy và nạp tiền bình thường." if is_vi else "• Customer can start gaming sessions and top up wallet.",
            ]

        for b in bullets:
            ctk.CTkLabel(
                c_inner,
                text=b,
                font=FONT_ST_MONO_XS,
                text_color=STITCH_TEXT,
                anchor="w",
            ).pack(anchor="w", pady=1)

        # Soft lock note (bg-[#0E131E] border border-[#212B3E])
        note_box = ctk.CTkFrame(
            body,
            fg_color="#0E131E",
            border_width=1,
            border_color="#212B3E",
            corner_radius=6,
        )
        note_box.pack(fill="x")

        note_text = (
            ("ℹ Đây là thao tác khóa mềm. Bạn có thể mở khóa và khôi phục toàn bộ quyền truy cập bất cứ lúc nào từ panel chi tiết." if is_lock else "ℹ Thao tác mở khóa có hiệu lực ngay lập tức trên toàn hệ thống phòng máy.")
            if is_vi
            else ("ℹ This is a soft lock. You can unlock and restore full access anytime from the detail panel." if is_lock else "ℹ Unlocking takes effect immediately across all client workstations.")
        )
        ctk.CTkLabel(
            note_box,
            text=note_text,
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=410,
        ).pack(fill="x", padx=10, pady=8)

        # 3. Footer (px-5 py-3 border-t border-[#212B3E] bg-[#0E131E])
        footer = ctk.CTkFrame(card, fg_color="#0E131E", corner_radius=0, height=48)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        foot_inner = ctk.CTkFrame(footer, fg_color="transparent")
        foot_inner.pack(fill="both", expand=True, padx=16, pady=6)

        self._cancel_btn = ActionButton(
            foot_inner,
            text="Hủy" if is_vi else "Cancel",
            kind="ghost",
            width=80,
            command=self.destroy,
        )
        self._cancel_btn.pack(side="right", padx=(8, 0))

        confirm_text = (
            ("Khóa khách hàng" if is_lock else "Mở khóa khách hàng")
            if is_vi
            else ("Lock customer" if is_lock else "Unlock customer")
        )
        self._confirm_btn = ActionButton(
            foot_inner,
            text=confirm_text,
            kind="danger" if is_lock else "stitch_primary",
            width=150,
            command=self._handle_confirm,
        )
        self._confirm_btn.pack(side="right")

    def _add_meta_cell(self, parent: Any, row: int, col: int, label: str, val: str, val_color: str) -> None:
        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(row=row, column=col, padx=4, pady=3, sticky="w")
        ctk.CTkLabel(
            cell,
            text=label,
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            cell,
            text=val,
            font=FONT_ST_BODY_STRONG,
            text_color=val_color,
            anchor="w",
        ).pack(anchor="w")

    def _handle_confirm(self) -> None:
        if self._is_submitting:
            return

        is_vi = self._language == "vi"
        action_word = ("Khóa" if self._is_active else "Mở khóa") if is_vi else ("Lock" if self._is_active else "Unlock")
        self._is_submitting = True
        self._cancel_btn.set_enabled(False)
        self._confirm_btn.set_busy(True)
        try:
            self._services.customers.set_customer_status(
                customer_id=self._customer.customer_id,
                status=self._target_status,
                actor=self._actor,
            )
            ToastManager.show(
                self.master,
                f"Đã {action_word.lower()} thành công khách hàng {self._customer.full_name}!"
                if is_vi
                else f"Successfully {action_word.lower()}ed customer {self._customer.full_name}!",
                kind="success" if not self._is_active else "info",
            )
            if self._on_success:
                self._on_success()
            self.destroy()
        except ApplicationError as err:
            logger.warning("Lỗi khóa/mở khách hàng: %s", err)
            ToastManager.show(self, get_user_friendly_error(err), kind="error")
        except Exception:
            logger.exception("Lỗi không mong muốn khi khóa/mở khách hàng")
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")
        finally:
            if self.winfo_exists():
                self._is_submitting = False
                self._cancel_btn.set_enabled(True)
                self._confirm_btn.set_busy(False)


# Alias tương thích tên gọi quy định
LockAccountDialog = CustomerLockDialog
