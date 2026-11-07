"""NG-04 — Dialog Tạo / Chỉnh sửa khách hàng theo Stitch
(`t_o_kh_ch_h_ng_unified`, `t_o_kh_ch_h_ng_validation_error`, `ch_nh_s_a_kh_ch_h_ng_default`).

- Tạo: họ tên, SĐT, tên đăng nhập, mật khẩu + xác nhận -> customers.create_customer(...) (CUS-01).
- Sửa: chỉ họ tên và SĐT (CUS-03); mã KH, mã TK, tên đăng nhập, trạng thái chỉ hiển thị;
  không cho sửa số dư.
- Kiểm tra sơ bộ ở UI theo mục validation của 01_REQUIREMENTS (CUS): họ tên 2–100 ký tự,
  SĐT 10 số bắt đầu bằng 0, tên đăng nhập 4–30 ký tự [chữ, số, _ .], mật khẩu ≥ 6 ký tự.
  Service vẫn kiểm tra lại; lỗi trùng SĐT/tên đăng nhập gắn vào đúng ô, giữ dữ liệu đã nhập.
- Thông báo lỗi giữ tiếng Anh theo quy định chung trong messages.py.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ...domain.dtos import CustomerSummary
from ...domain.enums import AccountStatus, CustomerStatus
from ...domain.models import Customer
from ..app_shell import ViewContext
from ..background import TaskRunner, default_runner
from ..components import ToastManager
from ..components.stitch_field import StitchField
from ..feedback import notify_error
from ..messages import FIELD_ERROR_MESSAGES, get_field_errors_safe, get_user_friendly_error
from ..theme import (
    STITCH_BADGE_DANGER_BG,
    STITCH_BADGE_DANGER_BORDER,
    STITCH_BADGE_SUCCESS_BG,
    STITCH_BADGE_SUCCESS_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_SUCCESS,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
)
from .stitch_dialog import StitchDialog, chip, info_panel, info_row

REQUIRED = FIELD_ERROR_MESSAGES["REQUIRED"]
INVALID_FULL_NAME = FIELD_ERROR_MESSAGES["INVALID_FULL_NAME"]
INVALID_PHONE = FIELD_ERROR_MESSAGES["INVALID_PHONE"]
INVALID_USERNAME = FIELD_ERROR_MESSAGES["INVALID_USERNAME"]
INVALID_PASSWORD = FIELD_ERROR_MESSAGES["INVALID_PASSWORD"]
PASSWORD_MISMATCH = "Passwords do not match."

_PHONE = re.compile(r"0\d{9}")
_USERNAME = re.compile(r"[A-Za-z0-9_.]{4,30}")


def validate_customer_form(values: dict[str, str], *, creating: bool) -> dict[str, str]:
    """Trả lỗi theo field (rỗng nếu hợp lệ). `values` đã được strip (trừ mật khẩu)."""
    errors: dict[str, str] = {}
    name = values.get("full_name", "")
    if not name:
        errors["full_name"] = REQUIRED
    elif not 2 <= len(name) <= 100:
        errors["full_name"] = INVALID_FULL_NAME
    phone = values.get("phone", "")
    if not phone:
        errors["phone"] = REQUIRED
    elif not _PHONE.fullmatch(phone):
        errors["phone"] = INVALID_PHONE
    if not creating:
        return errors
    username = values.get("username", "")
    if not username:
        errors["username"] = REQUIRED
    elif not _USERNAME.fullmatch(username):
        errors["username"] = INVALID_USERNAME
    password = values.get("password", "")
    if len(password) < 6:
        errors["password"] = INVALID_PASSWORD if password else REQUIRED
    if values.get("confirm_password", "") != password:
        errors["confirm_password"] = PASSWORD_MISMATCH
    return errors


def _status_chip(active: bool, active_text: str, inactive_text: str) -> Callable[[Any], ctk.CTkFrame]:
    if active:
        return lambda master: chip(master, active_text, STITCH_SUCCESS, STITCH_BADGE_SUCCESS_BG, STITCH_BADGE_SUCCESS_BORDER)
    return lambda master: chip(master, inactive_text, STITCH_DANGER, STITCH_BADGE_DANGER_BG, STITCH_BADGE_DANGER_BORDER)


class CustomerDialog(StitchDialog):
    """Truyền `customer` (+ `account_code`) để sửa, bỏ trống để tạo mới."""

    def __init__(
        self,
        parent: Any,
        context: ViewContext,
        *,
        customer: CustomerSummary | None = None,
        account_code: str = "",
        runner: TaskRunner | None = None,
        on_saved: Callable[[Customer], None] | None = None,
    ) -> None:
        self._creating = customer is None
        super().__init__(
            parent,
            title="Tạo khách hàng" if self._creating else "Chỉnh sửa khách hàng",
            subtitle="Tạo hồ sơ khách hàng và tài khoản đăng nhập" if self._creating else "Cập nhật thông tin hồ sơ khách hàng",
            icon="👤" if self._creating else "✎",
            width=640 if self._creating else 560,
            hint="Nhấn Enter để tạo • Esc để hủy" if self._creating else "Nhấn Enter để lưu • Esc để hủy",
            confirm_text="＋  Tạo khách hàng" if self._creating else "✓  Lưu thay đổi",
        )
        self._context = context
        self._customer = customer
        self._runner = runner or default_runner()
        self._on_saved = on_saved
        self._fields: dict[str, StitchField] = {}

        if self._creating:
            self._build_create_form()
        else:
            assert customer is not None
            self._build_edit_form(customer, account_code)
        self.finish(focus=self._fields["full_name"].focus)

    # ------------------------------------------------------------------
    @property
    def fields(self) -> dict[str, StitchField]:
        return self._fields

    def _field(self, master: Any, key: str, label: str, **options: Any) -> StitchField:
        field = StitchField(master, label, **options)
        self._fields[key] = field
        return field

    def _build_create_form(self) -> None:
        grid = ctk.CTkFrame(self.body, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure((0, 1), weight=1, uniform="form")
        self._field(grid, "full_name", "Họ và tên", placeholder="Nhập họ và tên").grid(row=0, column=0, sticky="new", padx=(0, 8))
        self._field(grid, "phone", "Số điện thoại", placeholder="0xxxxxxxxx", mono=True).grid(row=0, column=1, sticky="new", padx=(8, 0))
        self._field(
            grid,
            "username",
            "Tên đăng nhập",
            placeholder="vd: an.nv",
            suffix="@",
            mono=True,
            hint="4–30 ký tự, gồm chữ, số, dấu gạch dưới và dấu chấm",
        ).grid(row=1, column=0, columnspan=2, sticky="new", pady=(14, 0))
        self._field(grid, "password", "Mật khẩu", placeholder="Nhập mật khẩu", password=True).grid(
            row=2, column=0, sticky="new", padx=(0, 8), pady=(14, 0)
        )
        self._field(grid, "confirm_password", "Xác nhận mật khẩu", placeholder="Nhập lại mật khẩu", password=True).grid(
            row=2, column=1, sticky="new", padx=(8, 0), pady=(14, 0)
        )

        ctk.CTkFrame(self.body, fg_color="transparent", height=16).pack(fill="x")
        info = info_panel(self.body, "Thông tin khởi tạo hệ thống", right_note="Hệ thống tự động gán")
        cols = ctk.CTkFrame(info, fg_color="transparent")
        cols.pack(fill="x")
        cols.grid_columnconfigure((0, 1), weight=1, uniform="info")
        left = ctk.CTkFrame(cols, fg_color="transparent")
        left.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        right = ctk.CTkFrame(cols, fg_color="transparent")
        right.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        info_row(left, "Mã khách hàng:", "Tạo sau khi lưu", value_color=STITCH_TEXT_MUTED, italic=True)
        info_row(left, "Trạng thái KH:", _status_chip(True, "Hoạt động", ""))
        info_row(right, "Mã tài khoản:", "Tạo sau khi lưu", value_color=STITCH_TEXT_MUTED, italic=True)
        info_row(right, "Trạng thái TK:", _status_chip(True, "Hoạt động", ""))
        info_row(info, "Số dư ví ban đầu:", "0 VND", value_color=STITCH_TEXT_STRONG)

    def _build_edit_form(self, customer: CustomerSummary, account_code: str) -> None:
        self._field(self.body, "full_name", "Họ và tên", uppercase_label=False).pack(fill="x")
        self._field(self.body, "phone", "Số điện thoại", mono=True, uppercase_label=False).pack(fill="x", pady=(14, 0))
        self._fields["full_name"].set_value(customer.full_name)
        self._fields["phone"].set_value(customer.phone)

        ctk.CTkFrame(self.body, fg_color="transparent", height=16).pack(fill="x")
        info = info_panel(self.body, "Thông tin hệ thống (không thể thay đổi)", locked=True)
        cols = ctk.CTkFrame(info, fg_color="transparent")
        cols.pack(fill="x")
        cols.grid_columnconfigure((0, 1), weight=1, uniform="info")
        left = ctk.CTkFrame(cols, fg_color="transparent")
        left.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        right = ctk.CTkFrame(cols, fg_color="transparent")
        right.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        info_row(left, "Mã KH:", customer.customer_code, value_color=STITCH_CYAN)
        info_row(left, "Trạng thái KH:", _status_chip(customer.customer_status == CustomerStatus.ACTIVE, "Hoạt động", "Ngừng hoạt động"))
        info_row(right, "Mã tài khoản:", account_code or "—", value_color=STITCH_CYAN)
        info_row(right, "Trạng thái TK:", _status_chip(customer.account_status == AccountStatus.ACTIVE, "Hoạt động", "Đã khóa"))
        info_row(info, "Tên đăng nhập:", customer.username, value_color=STITCH_TEXT_STRONG)

    # ------------------------------------------------------------------
    def values(self) -> dict[str, str]:
        result = {key: field.get_value() for key, field in self._fields.items()}
        for key in ("full_name", "phone", "username"):
            if key in result:
                result[key] = result[key].strip()
        return result

    def submit(self) -> None:
        if self.is_submitting:
            return
        for field in self._fields.values():
            field.set_error(None)
        values = self.values()
        errors = validate_customer_form(values, creating=self._creating)
        if errors:
            self._show_field_errors(errors)
            return

        self.set_submitting(True)
        customers = self._context.services.customers
        editing = self._customer

        def call() -> Customer:  # chạy ở luồng nền: chỉ gọi service, không chạm widget
            if editing is None:
                return customers.create_customer(values["full_name"], values["phone"], values["username"], values["password"])
            return customers.update_customer(editing.customer_id, values["full_name"], values["phone"])

        self._runner.submit(self, call, self._on_success, self._on_error)

    def _on_success(self, customer: Customer) -> None:
        self.set_submitting(False)
        callback = self._on_saved
        self.close()
        if callback is not None:
            callback(customer)

    def _on_error(self, error: Exception) -> None:
        self.set_submitting(False)
        field_errors = {k: v for k, v in get_field_errors_safe(error).items() if k in self._fields}
        if field_errors:
            # Lỗi gắn được vào field (vd. trùng SĐT/tên đăng nhập): viền đỏ + Toast, giữ dữ liệu.
            self._show_field_errors(field_errors)
            ToastManager.show(self, get_user_friendly_error(error), kind="error")
            return
        notify_error(self, error)

    def _show_field_errors(self, errors: dict[str, str]) -> None:
        for key, message in errors.items():
            self._fields[key].set_error(message)
        self._fields[next(iter(errors))].focus()
