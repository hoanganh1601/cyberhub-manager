"""CustomerDialog — Hộp thoại tạo mới hoặc chỉnh sửa thông tin khách hàng.

Tuân thủ thiết kế Stitch:
- Tham chiếu tạo mới: docs/ui-reference/t_o_kh_ch_h_ng_unified/code.html
- Tham chiếu chỉnh sửa: docs/ui-reference/chinh_sua_khach_hang_default/code.html
- Header với icon Cyan và phụ đề hệ thống.
- Lưới Form 2 cột Họ tên / SĐT, Tên đăng nhập với hậu tố @, Mật khẩu & Xác nhận mật khẩu.
- Khối thông tin khởi tạo hệ thống (mã khách, mã tài khoản, trạng thái, số dư).
- Gọi service customer: create_customer() hoặc update_customer().
"""

from __future__ import annotations

import logging
from typing import Any

import customtkinter as ctk

from ...domain.dtos import CustomerSummary
from ...domain.exceptions import ApplicationError
from ..components import ActionButton, ToastManager
from ..formatters import format_money
from ..icons import get_icon
from ..messages import MSG_OPERATION_FAILED, get_field_errors_safe, get_user_friendly_error
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
    STITCH_INPUT_BG,
    STITCH_INPUT_BORDER,
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


class CustomerDialog(ctk.CTkToplevel):
    """Hộp thoại modal tạo mới hoặc chỉnh sửa thông tin khách hàng."""

    def __init__(
        self,
        parent: Any,
        services: Any,
        *,
        customer: CustomerSummary | None = None,
        language: str = "vi",
        on_success: Any = None,
    ) -> None:
        super().__init__(parent)
        self._services = services
        self._customer = customer
        self._is_edit = customer is not None
        self._language = language
        self._on_success = on_success

        self._is_submitting = False
        self._input_boxes: dict[ctk.CTkEntry, ctk.CTkFrame] = {}

        is_vi = language == "vi"
        title_str = (
            ("Chỉnh sửa khách hàng" if self._is_edit else "Tạo khách hàng")
            if is_vi
            else ("Edit Customer" if self._is_edit else "Create Customer")
        )

        self.title(title_str)
        diag_w = 540 if self._is_edit else 560
        diag_h = 490 if self._is_edit else 640
        self.geometry(f"{diag_w}x{diag_h}")
        self.resizable(False, False)
        self.configure(fg_color=STITCH_BG_CANVAS)

        self.transient(parent)
        self.grab_set()

        self._build_ui(title_str)
        self.bind("<Escape>", lambda _e: self._on_escape())
        self.bind("<Return>", lambda _e: self._handle_save())
        self.after(50, lambda: self._name_entry.focus_set() if hasattr(self, "_name_entry") else None)

    def _on_escape(self) -> None:
        if not self._is_submitting:
            self.destroy()

    def _build_ui(self, title_str: str) -> None:
        is_vi = self._language == "vi"

        # Khung viền ngoài (w-[560px] bg-[#111726] border border-[#222f49] rounded-2xl)
        card = ctk.CTkFrame(
            self,
            fg_color="#111726",
            border_width=1,
            border_color="#222F49",
            corner_radius=14,
        )
        card.pack(fill="both", expand=True, padx=10, pady=10)

        # 1. Header (px-6 py-4 border-b border-[#1e293b] bg-[#151c2e])
        header = ctk.CTkFrame(card, fg_color="#151C2E", corner_radius=0, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        h_inner = ctk.CTkFrame(header, fg_color="transparent")
        h_inner.pack(fill="both", expand=True, padx=18, pady=10)

        icon_name = "edit" if self._is_edit else "add"
        try:
            icon_img = get_icon(icon_name, STITCH_CYAN, size=(18, 18))
            icon_box = ctk.CTkLabel(
                h_inner,
                text="",
                image=icon_img,
                width=36,
                height=36,
                corner_radius=8,
                fg_color="#0C2E40",
            )
        except Exception:
            icon_box = ctk.CTkLabel(
                h_inner,
                text="E" if self._is_edit else "+",
                width=36,
                height=36,
                corner_radius=8,
                fg_color="#0C2E40",
            )
        icon_box.pack(side="left")

        title_box = ctk.CTkFrame(h_inner, fg_color="transparent")
        title_box.pack(side="left", padx=(12, 0))

        ctk.CTkLabel(
            title_box,
            text=title_str,
            font=FONT_ST_PAGE_TITLE,
            text_color=STITCH_TEXT_STRONG,
            anchor="w",
        ).pack(anchor="w")

        sub_text = (
            ("Cập nhật họ tên và số điện thoại hồ sơ" if self._is_edit else "Tạo hồ sơ khách hàng và tài khoản đăng nhập")
            if is_vi
            else ("Update full name and phone number" if self._is_edit else "Create customer profile and login account")
        )
        ctk.CTkLabel(
            title_box,
            text=sub_text,
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w")

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

        # 2. Form Body (p-6 space-y-3.5 bg-[#111726])
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=14)

        if not self._is_edit:
            # CREATE MODE: 2 columns for Name & Phone
            row1 = ctk.CTkFrame(body, fg_color="transparent")
            row1.pack(fill="x", pady=(0, 10))
            row1.grid_columnconfigure(0, weight=1)
            row1.grid_columnconfigure(1, weight=1)

            # Field: Họ và tên
            f_name_wrap = ctk.CTkFrame(row1, fg_color="transparent")
            f_name_wrap.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
            self._add_field_label(f_name_wrap, "Họ và tên" if is_vi else "Full Name", required=True)
            self._name_entry = self._create_input(f_name_wrap, "Nhập họ và tên" if is_vi else "Enter full name")
            self._name_err = self._add_error_label(f_name_wrap)

            # Field: Số điện thoại
            f_phone_wrap = ctk.CTkFrame(row1, fg_color="transparent")
            f_phone_wrap.grid(row=0, column=1, padx=(6, 0), sticky="nsew")
            self._add_field_label(f_phone_wrap, "Số điện thoại" if is_vi else "Phone Number", required=True)
            self._phone_entry = self._create_input(f_phone_wrap, "Nhập số điện thoại" if is_vi else "Enter phone number")
            self._phone_err = self._add_error_label(f_phone_wrap)

            # Row 2: Tên đăng nhập
            f_user_wrap = ctk.CTkFrame(body, fg_color="transparent")
            f_user_wrap.pack(fill="x", pady=(0, 10))
            self._add_field_label(f_user_wrap, "Tên đăng nhập" if is_vi else "Username", required=True)

            u_input_wrap = ctk.CTkFrame(f_user_wrap, fg_color="transparent")
            u_input_wrap.pack(fill="x")

            self._user_entry = self._create_input(u_input_wrap, "Nhập tên đăng nhập" if is_vi else "Enter username", suffix="@")
            ctk.CTkLabel(
                f_user_wrap,
                text="4–30 ký tự, gồm chữ, số, dấu gạch dưới và dấu chấm" if is_vi else "4-30 chars, letters, numbers, underscore and dot",
                font=FONT_ST_MONO_XS,
                text_color=STITCH_TEXT_MUTED,
                anchor="w",
            ).pack(anchor="w", pady=(2, 0))
            self._user_err = self._add_error_label(f_user_wrap)

            # Row 3: Mật khẩu & Xác nhận mật khẩu
            row3 = ctk.CTkFrame(body, fg_color="transparent")
            row3.pack(fill="x", pady=(0, 10))
            row3.grid_columnconfigure(0, weight=1)
            row3.grid_columnconfigure(1, weight=1)

            f_pass_wrap = ctk.CTkFrame(row3, fg_color="transparent")
            f_pass_wrap.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
            self._add_field_label(f_pass_wrap, "Mật khẩu" if is_vi else "Password", required=True)
            self._pass_entry = self._create_input(f_pass_wrap, "Nhập mật khẩu" if is_vi else "Enter password", is_password=True)
            self._pass_err = self._add_error_label(f_pass_wrap)

            f_confirm_wrap = ctk.CTkFrame(row3, fg_color="transparent")
            f_confirm_wrap.grid(row=0, column=1, padx=(6, 0), sticky="nsew")
            self._add_field_label(f_confirm_wrap, "Xác nhận mật khẩu" if is_vi else "Confirm Password", required=True)
            self._confirm_entry = self._create_input(f_confirm_wrap, "Nhập lại mật khẩu" if is_vi else "Re-enter password", is_password=True)
            self._confirm_err = self._add_error_label(f_confirm_wrap)

            # Bind typing to clear errors
            self._name_entry.bind("<KeyRelease>", lambda _e: self._clear_field_error(self._name_entry, self._name_err))
            self._phone_entry.bind("<KeyRelease>", lambda _e: self._clear_field_error(self._phone_entry, self._phone_err))
            self._user_entry.bind("<KeyRelease>", lambda _e: self._clear_field_error(self._user_entry, self._user_err))
            self._pass_entry.bind("<KeyRelease>", lambda _e: self._clear_field_error(self._pass_entry, self._pass_err))
            self._confirm_entry.bind("<KeyRelease>", lambda _e: self._clear_field_error(self._confirm_entry, self._confirm_err))

        else:
            # EDIT MODE: Full-width stacked Name and Phone (exact Stitch ch_nh_s_a_kh_ch_h_ng_default)
            f_name_wrap = ctk.CTkFrame(body, fg_color="transparent")
            f_name_wrap.pack(fill="x", pady=(0, 8))
            self._add_field_label(f_name_wrap, "Họ và tên" if is_vi else "Full Name", required=True)
            self._name_entry = self._create_input(f_name_wrap, "Nhập họ và tên" if is_vi else "Enter full name")
            if self._customer:
                self._name_entry.insert(0, self._customer.full_name)
            self._name_err = self._add_error_label(f_name_wrap)

            f_phone_wrap = ctk.CTkFrame(body, fg_color="transparent")
            f_phone_wrap.pack(fill="x", pady=(0, 8))
            self._add_field_label(f_phone_wrap, "Số điện thoại" if is_vi else "Phone Number", required=True)
            self._phone_entry = self._create_input(f_phone_wrap, "Nhập số điện thoại" if is_vi else "Enter phone number")
            if self._customer:
                self._phone_entry.insert(0, self._customer.phone)
            self._phone_err = self._add_error_label(f_phone_wrap)

            self._name_entry.bind("<KeyRelease>", lambda _e: self._clear_field_error(self._name_entry, self._name_err))
            self._phone_entry.bind("<KeyRelease>", lambda _e: self._clear_field_error(self._phone_entry, self._phone_err))

        # 3. System Info Box (bg-[#0B0F19] border border-[#1B253B] rounded-lg p-3)
        sys_box = ctk.CTkFrame(
            body,
            fg_color="#090E19",
            border_width=1,
            border_color="#212B3E",
            corner_radius=8,
        )
        sys_box.pack(fill="x", pady=(2, 0))

        s_inner = ctk.CTkFrame(sys_box, fg_color="transparent")
        s_inner.pack(fill="x", padx=12, pady=8)

        # Header system box
        s_head = ctk.CTkFrame(s_inner, fg_color="transparent")
        s_head.pack(fill="x", pady=(0, 6))

        h_left = ctk.CTkFrame(s_head, fg_color="transparent")
        h_left.pack(side="left")

        h_icon = "wallet" if not self._is_edit else "lock"
        ctk.CTkLabel(
            h_left,
            text="",
            image=get_icon(h_icon, STITCH_CYAN if not self._is_edit else STITCH_TEXT_MUTED, size=(12, 12)),
        ).pack(side="left", padx=(0, 4))

        ctk.CTkLabel(
            h_left,
            text=("THÔNG TIN KHỞI TẠO HỆ THỐNG" if not self._is_edit else "THÔNG TIN HỆ THỐNG (KHÔNG THỂ THAY ĐỔI)"),
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_CYAN if not self._is_edit else STITCH_TEXT_MUTED,
        ).pack(side="left")

        if not self._is_edit:
            ctk.CTkLabel(
                s_head,
                text="Hệ thống tự động gán" if is_vi else "System assigned",
                font=FONT_ST_MONO_XS,
                text_color=STITCH_TEXT_MUTED,
            ).pack(side="right")

        # Grid system details
        s_grid = ctk.CTkFrame(s_inner, fg_color="transparent")
        s_grid.pack(fill="x")
        s_grid.grid_columnconfigure(0, weight=1)
        s_grid.grid_columnconfigure(1, weight=1)

        if not self._is_edit:
            self._add_sys_card(s_grid, 0, 0, "Mã khách hàng:", "Tạo sau khi lưu", is_italic=True)
            self._add_sys_card(s_grid, 0, 1, "Mã tài khoản:", "Tạo sau khi lưu", is_italic=True)
            self._add_sys_card(s_grid, 1, 0, "Trạng thái KH:", "● Hoạt động", is_badge=True)
            self._add_sys_card(s_grid, 1, 1, "Trạng thái TK:", "● Hoạt động", is_badge=True)
            self._add_sys_card(s_grid, 2, 0, "Số dư ví ban đầu:", "0 VND", col_span=2)
        else:
            cust = self._customer
            assert cust is not None
            st_text = "● Hoạt động" if cust.customer_status.value == "ACTIVE" else "Ngừng hoạt động"
            self._add_sys_card(s_grid, 0, 0, "Mã KH:", cust.customer_code, is_cyan=True)
            self._add_sys_card(s_grid, 0, 1, "Mã tài khoản:", f"ACC-{cust.account_id:04d}", is_cyan=True)
            self._add_sys_card(s_grid, 1, 0, "Tên đăng nhập:", cust.username, col_span=2, is_mono=True)
            self._add_sys_card(s_grid, 2, 0, "Trạng thái KH:", st_text, is_badge=True)
            self._add_sys_card(s_grid, 2, 1, "Trạng thái TK:", st_text, is_badge=True)

        # 4. Footer (px-6 py-3.5 border-t border-[#1e293b] bg-[#151c2e])
        footer = ctk.CTkFrame(card, fg_color="#151C2E", corner_radius=0, height=52)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        foot_inner = ctk.CTkFrame(footer, fg_color="transparent")
        foot_inner.pack(fill="both", expand=True, padx=18, pady=8)

        self._hint_lbl = ctk.CTkLabel(
            foot_inner,
            text=("Nhấn Enter để lưu • Esc để hủy" if self._is_edit else "Nhấn Enter để tạo • Esc để hủy")
            if is_vi
            else ("Press Enter to save • Esc to cancel" if self._is_edit else "Press Enter to create • Esc to cancel"),
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

        save_text = (
            ("Lưu thay đổi" if self._is_edit else "+ Tạo khách hàng")
            if is_vi
            else ("Save Changes" if self._is_edit else "+ Create Customer")
        )
        self._save_btn = ActionButton(
            foot_inner,
            text=save_text,
            kind="primary",
            width=140,
            command=self._handle_save,
        )
        self._save_btn.pack(side="right")

    def _add_field_label(self, parent: Any, text: str, required: bool = False) -> None:
        lbl_box = ctk.CTkFrame(parent, fg_color="transparent")
        lbl_box.pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            lbl_box,
            text=text.upper(),
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left")
        if required:
            ctk.CTkLabel(
                lbl_box,
                text=" *",
                font=FONT_ST_MONO_XS_STRONG,
                text_color=STITCH_CYAN,
            ).pack(side="left")

    def _create_input(
        self,
        parent: Any,
        placeholder: str,
        *,
        is_password: bool = False,
        suffix: str | None = None,
    ) -> ctk.CTkEntry:
        box = ctk.CTkFrame(
            parent,
            height=34,
            corner_radius=6,
            fg_color="#0B0F19",
            border_width=1,
            border_color="#222F49",
        )
        box.pack(fill="x")
        box.pack_propagate(False)

        entry = ctk.CTkEntry(
            box,
            placeholder_text=placeholder,
            fg_color="transparent",
            border_width=0,
            text_color=STITCH_TEXT,
            font=FONT_ST_BODY,
            show="•" if is_password else "",
        )
        entry.pack(side="left", fill="both", expand=True, padx=(8, 2))
        self._input_boxes[entry] = box

        if is_password:
            eye_btn = ctk.CTkButton(
                box,
                text="👁",
                width=26,
                height=26,
                corner_radius=4,
                fg_color="transparent",
                hover_color="#1E273A",
                text_color=STITCH_TEXT_MUTED,
                font=FONT_ST_MONO_XS,
                command=lambda: self._toggle_show(entry, eye_btn),
            )
            eye_btn.pack(side="right", padx=(0, 4))
        elif suffix:
            ctk.CTkLabel(
                box,
                text=suffix,
                font=FONT_ST_MONO_XS,
                text_color="#64748B",
            ).pack(side="right", padx=(0, 8))

        return entry

    def _toggle_show(self, entry: ctk.CTkEntry, btn: ctk.CTkButton) -> None:
        current = entry.cget("show")
        if current == "•":
            entry.configure(show="")
            btn.configure(text_color=STITCH_CYAN)
        else:
            entry.configure(show="•")
            btn.configure(text_color=STITCH_TEXT_MUTED)

    def _add_error_label(self, parent: Any) -> ctk.CTkLabel:
        lbl = ctk.CTkLabel(
            parent,
            text="",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_DANGER,
            anchor="w",
        )
        lbl.pack(anchor="w", pady=(2, 0))
        return lbl

    def _add_sys_card(
        self,
        parent: Any,
        row: int,
        col: int,
        label: str,
        val: str,
        *,
        is_italic: bool = False,
        is_badge: bool = False,
        is_cyan: bool = False,
        is_mono: bool = False,
        col_span: int = 1,
    ) -> None:
        card = ctk.CTkFrame(
            parent,
            fg_color="#121824",
            border_width=1,
            border_color="#1E273A",
            corner_radius=6,
            height=30,
        )
        card.grid(row=row, column=col, columnspan=col_span, padx=3, pady=2, sticky="nsew")
        card.pack_propagate(False)

        c_inner = ctk.CTkFrame(card, fg_color="transparent")
        c_inner.pack(fill="both", expand=True, padx=8, pady=2)

        ctk.CTkLabel(
            c_inner,
            text=label,
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left")

        if is_badge:
            ctk.CTkLabel(
                c_inner,
                text=val,
                font=FONT_ST_MONO_XS_STRONG,
                text_color=STITCH_SUCCESS,
                fg_color="#0A2918",
                corner_radius=4,
                padx=6,
                pady=1,
            ).pack(side="right")
        elif is_cyan:
            ctk.CTkLabel(
                c_inner,
                text=val,
                font=FONT_ST_MONO_XS_STRONG,
                text_color=STITCH_CYAN,
            ).pack(side="right")
        elif is_italic:
            ctk.CTkLabel(
                c_inner,
                text=val,
                font=FONT_ST_MONO_XS,
                text_color=STITCH_TEXT_MUTED,
            ).pack(side="right")
        else:
            ctk.CTkLabel(
                c_inner,
                text=val,
                font=FONT_ST_MONO_XS_STRONG if is_mono else FONT_ST_BODY_STRONG,
                text_color=STITCH_TEXT_STRONG,
            ).pack(side="right")

    def _set_inputs_state(self, state: str) -> None:
        for entry in self._input_boxes:
            entry.configure(state=state)

    def _mark_field_error(self, entry: ctk.CTkEntry, err_lbl: ctk.CTkLabel, msg: str) -> None:
        box = self._input_boxes.get(entry)
        if box:
            box.configure(border_color=STITCH_DANGER)
        else:
            entry.configure(border_color=STITCH_DANGER)
        err_lbl.configure(text=f"⚠  {msg}")

    def _clear_field_error(self, entry: ctk.CTkEntry, err_lbl: ctk.CTkLabel) -> None:
        box = self._input_boxes.get(entry)
        if box:
            box.configure(border_color="#222F49")
        else:
            entry.configure(border_color="#222F49")
        err_lbl.configure(text="")

    def _clear_all_errors(self) -> None:
        self._clear_field_error(self._name_entry, self._name_err)
        self._clear_field_error(self._phone_entry, self._phone_err)
        if not self._is_edit:
            self._clear_field_error(self._user_entry, self._user_err)
            self._clear_field_error(self._pass_entry, self._pass_err)
            self._clear_field_error(self._confirm_entry, self._confirm_err)

    def _handle_save(self) -> None:
        if self._is_submitting:
            return

        is_vi = self._language == "vi"
        self._clear_all_errors()
        name = self._name_entry.get().strip()
        phone = self._phone_entry.get().strip()

        # Validation client-side
        has_err = False
        if not name:
            self._mark_field_error(self._name_entry, self._name_err, "Vui lòng nhập họ và tên" if is_vi else "Full name is required")
            has_err = True

        if not phone:
            self._mark_field_error(self._phone_entry, self._phone_err, "Vui lòng nhập số điện thoại" if is_vi else "Phone number is required")
            has_err = True
        elif len(phone) < 9 or len(phone) > 11 or not phone.isdigit():
            self._mark_field_error(self._phone_entry, self._phone_err, "Số điện thoại phải từ 9 đến 11 chữ số" if is_vi else "Phone number must have 9-11 digits")
            has_err = True

        if not self._is_edit:
            user = self._user_entry.get().strip()
            pwd = self._pass_entry.get().strip()
            conf = self._confirm_entry.get().strip()

            if not user:
                self._mark_field_error(self._user_entry, self._user_err, "Vui lòng nhập tên đăng nhập" if is_vi else "Username is required")
                has_err = True
            elif len(user) < 4 or len(user) > 30:
                self._mark_field_error(self._user_entry, self._user_err, "Tên đăng nhập phải từ 4–30 ký tự" if is_vi else "Username must contain 4–30 valid characters")
                has_err = True

            if not pwd:
                self._mark_field_error(self._pass_entry, self._pass_err, "Vui lòng nhập mật khẩu" if is_vi else "Password is required")
                has_err = True
            elif len(pwd) < 6:
                self._mark_field_error(self._pass_entry, self._pass_err, "Mật khẩu tối thiểu 6 ký tự" if is_vi else "Min 6 characters")
                has_err = True

            if pwd != conf:
                self._mark_field_error(self._confirm_entry, self._confirm_err, "Mật khẩu xác nhận không khớp" if is_vi else "Passwords do not match")
                has_err = True

        if has_err:
            return

        self._is_submitting = True
        self._set_inputs_state("disabled")
        self._hint_lbl.configure(text="Đang xử lý dữ liệu..." if is_vi else "Processing data...")
        self._cancel_btn.set_enabled(False)
        self._save_btn.configure(text="Đang lưu…" if self._is_edit else "Đang tạo…")
        self._save_btn.set_busy(True)

        try:
            if self._is_edit:
                assert self._customer is not None
                self._services.customers.update_customer(
                    customer_id=self._customer.customer_id,
                    full_name=name,
                    phone=phone,
                )
            else:
                self._services.customers.create_customer(
                    full_name=name,
                    phone=phone,
                    username=self._user_entry.get().strip(),
                    password=self._pass_entry.get().strip(),
                )

            ToastManager.show(
                self.master,
                ("Cập nhật khách hàng thành công!" if self._is_edit else "Tạo khách hàng mới thành công!")
                if is_vi
                else ("Customer updated successfully!" if self._is_edit else "Customer created successfully!"),
                kind="success",
            )
            if self._on_success:
                self._on_success()
            self.destroy()

        except ApplicationError as err:
            logger.warning("Lỗi lưu khách hàng: %s", err)
            field_errors = get_field_errors_safe(err)
            if "full_name" in field_errors:
                self._mark_field_error(self._name_entry, self._name_err, field_errors["full_name"])
            if "phone" in field_errors:
                self._mark_field_error(self._phone_entry, self._phone_err, field_errors["phone"])
            if not self._is_edit:
                if "username" in field_errors:
                    self._mark_field_error(self._user_entry, self._user_err, field_errors["username"])
                if "password" in field_errors:
                    self._mark_field_error(self._pass_entry, self._pass_err, field_errors["password"])
            if not field_errors:
                ToastManager.show(self, get_user_friendly_error(err), kind="error")
        except Exception:
            logger.exception("Lỗi không mong muốn khi lưu khách hàng")
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")
        finally:
            if self.winfo_exists():
                self._is_submitting = False
                self._set_inputs_state("normal")
                self._cancel_btn.set_enabled(True)
                self._save_btn.set_busy(False)
                save_text = ("Lưu thay đổi" if self._is_edit else "+ Tạo khách hàng") if is_vi else ("Save Changes" if self._is_edit else "+ Create Customer")
                self._save_btn.configure(text=save_text)
                hint_txt = ("Nhấn Enter để lưu • Esc để hủy" if self._is_edit else "Nhấn Enter để tạo • Esc để hủy") if is_vi else ("Press Enter to save • Esc to cancel" if self._is_edit else "Press Enter to create • Esc to cancel")
                self._hint_lbl.configure(text=hint_txt)
