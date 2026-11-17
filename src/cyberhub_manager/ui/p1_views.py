"""Native P1 administration and customer workspace, using shared service contracts."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import filedialog
import secrets
import string
import tempfile
import webbrowser

import customtkinter as ctk

from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.exceptions import ApplicationError, ValidationError
from cyberhub_manager.domain.p1 import Permission, Promotion, can, separated_rbac, chain_director
from cyberhub_manager.services.invoice_export import invoice_html, invoice_csv
from . import theme as t
from .background import default_runner
from .components.stitch_field import StitchField
from .components.stitch_button import stitch_button
from .components.workspace import (
    PageHeader,
    MetricTile,
    surface,
    icon_action,
    row_action,
)
from .dialogs.stitch_dialog import StitchDialog
from .formatters import format_money, format_datetime
from .i18n import UIStrings
from .feedback import notify_error, notify_success

VN = timezone(timedelta(hours=7))
STATUS = {
    "ACTIVE": "Hoạt động",
    "INACTIVE": "Ngừng hoạt động",
    "LOCKED": "Đã khóa",
    "ADMIN": "Quản trị viên",
    "DIRECTOR": "Giám đốc",
    "MANAGER": "Quản lý",
    "STAFF": "Nhân viên",
    "KITCHEN": "Nhân viên bếp",
    "INVENTORY": "Thủ kho",
}


def export_detail(parent, detail, language="vi", print_view=False):
    copy = UIStrings(language)
    if print_view:
        with tempfile.NamedTemporaryFile(
            prefix="cyberhub-receipt-",
            suffix=".html",
            delete=False,
            mode="w",
            encoding="utf-8",
        ) as stream:
            stream.write(invoice_html(detail, language))
            filename = stream.name
        webbrowser.open(Path(filename).as_uri())
        return
    filename = filedialog.asksaveasfilename(
        parent=parent.winfo_toplevel(),
        title=copy("Xuất hóa đơn"),
        initialfile=detail.invoice.invoice_code + ".html",
        defaultextension=".html",
        filetypes=[("HTML", "*.html"), ("CSV", "*.csv")],
    )
    if filename:
        try:
            Path(filename).write_text(
                (
                    invoice_csv(detail)
                    if filename.lower().endswith(".csv")
                    else invoice_html(detail, language)
                ),
                encoding="utf-8",
            )
            notify_success(parent, copy("Đã xuất hóa đơn"))
        except OSError as exc:
            notify_error(parent, exc)


class StorePicker(StitchDialog):
    def __init__(self, parent, services, actor, stores, on_change, language):
        self.services, self.actor, self.on_change = services, actor, on_change
        self.stores = {
            f"{s.code} · {s.name}": s.id for s in stores if s.status == "ACTIVE"
        }
        copy = UIStrings(language)
        super().__init__(
            parent,
            title=copy("Chuyển cơ sở"),
            subtitle=copy("Chọn cơ sở để vận hành"),
            icon="",
            width=560,
            language=language,
            confirm_text=copy("Áp dụng"),
        )
        self.option = ctk.CTkOptionMenu(
            self.body, values=list(self.stores), height=40, font=t.FONT_ST_BODY
        )
        self.option.pack(fill="x")
        self.finish()

    def submit(self):
        if self.is_submitting:
            return
        self.set_submitting(True)

        def saved(actor):
            callback = self.on_change
            self.close()
            callback(actor)

        def failed(error):
            self.set_submitting(False)
            notify_error(self, error)

        default_runner().submit(
            self,
            lambda: self.services.management.switch_store(
                self.actor, self.stores[self.option.get()]
            ),
            saved,
            failed,
        )


class ManagementForm(StitchDialog):
    def __init__(
        self,
        parent,
        context,
        kind,
        *,
        item=None,
        stores=(),
        profiles=(),
        runner=None,
        on_saved=None,
    ):
        self._t = UIStrings(context.language)
        self.context, self.kind, self.item = context, kind, item
        self.profiles = list(profiles)
        self.runner = runner or default_runner()
        self.on_saved = on_saved
        self.fields, self.choices = {}, {}
        title = {
            "stores": "Cơ sở",
            "employees": "Nhân viên",
            "promotions": "Khuyến mãi",
        }[kind]
        super().__init__(
            parent,
            title=(
                self._t("Chỉnh sửa") + " · " + self._t(title)
                if item
                else self._t("Thêm mới") + " · " + self._t(title)
            ),
            subtitle=self._t("Thông tin được kiểm tra và lưu theo quyền của bạn"),
            icon="",
            width=700,
            language=context.language,
            confirm_text=self._t("Lưu thay đổi"),
            hint=self._t("Nhấn Enter để lưu • Esc để hủy"),
        )
        self.grid = ctk.CTkFrame(self.body, fg_color="transparent")
        self.grid.pack(fill="x")
        self.grid.grid_columnconfigure((0, 1), weight=1, uniform="fields")
        store_choices = {
            s.id: f"{s.code} · {s.name}" for s in stores if s.status == "ACTIVE"
        }
        if kind == "stores":
            specs = [
                ("code", "Mã cơ sở", "text", None),
                ("name", "Tên cơ sở", "text", None),
                ("address", "Địa chỉ", "text", None),
                ("status", "Trạng thái", "choice", ["ACTIVE", "INACTIVE"]),
            ]
        elif kind == "employees":
            credentials = can(context.session.role, Permission.MANAGE_EMPLOYEE_CREDENTIALS)
            pending_profiles = {
                profile["id"]: (
                    f'{profile["full_name"]} · '
                    f'{next((s.code for s in stores if s.id == profile["home_store_id"]), profile["home_store_id"])}'
                )
                for profile in self.profiles
                if not profile.get("employee_id")
                and profile.get("employment_status") == "ACTIVE"
            }
            if separated_rbac() and not item and credentials and pending_profiles:
                specs = [
                    ("profile_id", "Hồ sơ nhân sự", "choice", pending_profiles),
                    ("username", "Tên đăng nhập", "text", None),
                    ("role", "Vai trò", "choice", ["ADMIN", "DIRECTOR", "MANAGER", "STAFF", "KITCHEN", "INVENTORY"]),
                    ("status", "Trạng thái", "choice", ["ACTIVE", "INACTIVE", "LOCKED"]),
                    ("password", "Mật khẩu tạm thời", "password", None),
                ]
            else:
                specs = [("full_name", "Họ và tên", "text", None),
                         ("username", "Tên đăng nhập", "text", None),
                         ("store_id", "Cơ sở", "choice", store_choices),
                         ("role", "Vai trò", "choice",
                          ["ADMIN", "DIRECTOR", "MANAGER", "STAFF", "KITCHEN", "INVENTORY"] if credentials else ["STAFF"]),
                         ("status", "Trạng thái", "choice", ["ACTIVE", "INACTIVE", "LOCKED"]),
                         ("password", "Mật khẩu mới", "password", None)]
            if separated_rbac() and item:
                allowed = {"username", "role", "status"} if credentials else {"full_name", "store_id"} if context.session.role == Role.DIRECTOR else {"full_name"}
                specs = [spec for spec in specs if spec[0] in allowed]
        else:
            if can(context.session.role, Permission.SWITCH_STORE):
                store_choices = {None: self._t("Toàn hệ thống"), **store_choices}
            specs = [
                ("code", "Mã khuyến mãi", "text", None),
                ("name", "Tên khuyến mãi", "text", None),
                ("store_id", "Phạm vi áp dụng", "choice", store_choices),
                ("minimum_amount", "Mốc nạp tối thiểu", "number", None),
                ("bonus_percent", "Tỷ lệ thưởng (%)", "number", None),
                (
                    "is_active",
                    "Trạng thái",
                    "choice",
                    {True: self._t("Bật"), False: self._t("Tắt")},
                ),
                ("starts_at", "Bắt đầu (dd/mm/yyyy HH:MM)", "date", None),
                ("ends_at", "Kết thúc (dd/mm/yyyy HH:MM)", "date", None),
            ]
        now = datetime.now(VN).replace(second=0, microsecond=0)
        defaults = dict(
            store_id=context.session.store_id,
            profile_id=(next(iter(pending_profiles)) if kind == "employees" and 'pending_profiles' in locals() and pending_profiles else None),
            role="STAFF",
            status="ACTIVE",
            bonus_percent=5,
            minimum_amount=100000,
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=30),
            is_active=True,
        )
        for index, (key, label, field_type, options) in enumerate(specs):
            value = (
                getattr(item, key, defaults.get(key, ""))
                if item
                else defaults.get(key, "")
            )
            if field_type == "choice":
                choices = (
                    options
                    if isinstance(options, dict)
                    else {v: self._t(STATUS.get(v, v)) for v in options}
                )
                box = ctk.CTkFrame(self.grid, fg_color="transparent")
                ctk.CTkLabel(
                    box,
                    text=self._t(label),
                    font=t.FONT_ST_LABEL_CAPS,
                    text_color=t.STITCH_TEXT_MUTED,
                    anchor="w",
                ).pack(fill="x")
                menu = ctk.CTkOptionMenu(
                    box,
                    values=list(choices.values()),
                    height=36,
                    font=t.FONT_ST_BODY,
                    fg_color=t.STITCH_BG_CANVAS,
                    button_color=t.STITCH_CHIP_BG,
                    button_hover_color=t.STITCH_TAB_HOVER,
                )
                menu.pack(fill="x", pady=(5, 0))
                menu.set(choices.get(value, next(iter(choices.values()), "")))
                self.fields[key], self.choices[key] = menu, choices
                box.grid(
                    row=index // 2,
                    column=index % 2,
                    sticky="new",
                    padx=(0, 10) if index % 2 == 0 else (10, 0),
                    pady=(0, 14),
                )
            else:
                if field_type == "date":
                    value = value.astimezone(VN).strftime("%d/%m/%Y %H:%M")
                field = StitchField(
                    self.grid,
                    self._t(label),
                    password=field_type == "password",
                    required=field_type != "password" or item is None,
                    hint=(
                        self._t("Để trống để giữ mật khẩu hiện tại")
                        if field_type == "password" and item
                        else ""
                    ),
                )
                field.set_value(str(value) if field_type != "password" else "")
                field.grid(
                    row=index // 2,
                    column=index % 2,
                    sticky="new",
                    padx=(0, 10) if index % 2 == 0 else (10, 0),
                    pady=(0, 14),
                )
                self.fields[key] = field
        self.error_label = ctk.CTkLabel(
            self.body,
            text="",
            text_color=t.STITCH_DANGER,
            font=t.FONT_ST_BODY,
            wraplength=620,
            justify="left",
        )
        self.error_label.pack(fill="x")
        self.finish()

    def submit(self):
        if self.is_submitting:
            return
        try:
            values = {
                key: (
                    next(k for k, v in self.choices[key].items() if v == field.get())
                    if key in self.choices
                    else field.get_value()
                )
                for key, field in self.fields.items()
            }
            for key in ("minimum_amount", "bonus_percent"):
                if key in values:
                    try:
                        values[key] = int(values[key])
                    except ValueError:
                        raise ValidationError(
                            field_errors={key: self._t("Vui lòng nhập số nguyên")}
                        ) from None
            for key in ("starts_at", "ends_at"):
                if key in values:
                    try:
                        values[key] = datetime.strptime(
                            values[key], "%d/%m/%Y %H:%M"
                        ).replace(tzinfo=VN)
                    except ValueError:
                        raise ValidationError(
                            field_errors={key: self._t("Ngày giờ không hợp lệ")}
                        ) from None
        except (ValidationError, StopIteration) as exc:
            self._error(exc)
            return
        self.set_submitting(True)
        service, actor = self.context.services.management, self.context.session
        entity_id = self.item.id if self.item else None

        def call():
            if self.kind == "stores":
                return service.save_store(actor, entity_id, **values)
            if self.kind == "employees":
                if values.get("profile_id") is not None:
                    selected = next(
                        profile
                        for profile in self.profiles
                        if profile["id"] == values["profile_id"]
                    )
                    values["full_name"] = selected["full_name"]
                    values["store_id"] = selected["home_store_id"]
                if self.item:
                    for key in ("full_name", "username", "store_id", "role", "status"):
                        values.setdefault(key, getattr(self.item, key))
                return service.save_employee(actor, entity_id, **values)
            if self.item:
                values.update(minimum_tier=self.item.minimum_tier,minimum_points=self.item.minimum_points,target_customer_id=self.item.target_customer_id)
            return service.save_promotion(actor, Promotion(id=entity_id or 0, **values))

        self.runner.submit(self, call, self._saved, self._error)

    def _saved(self, result):
        callback = self.on_saved
        self.close()
        if callback:
            callback(result)

    def _error(self, exc):
        self.set_submitting(False)
        if isinstance(exc, ApplicationError):
            self.error_label.configure(
                text=(
                    exc.message
                    if self._t.language == "vi"
                    else self._t(
                        "Không thể lưu. Kiểm tra thông tin hoặc quyền truy cập."
                    )
                )
            )
            for key, message in exc.field_errors.items():
                field = self.fields.get(key)
                if isinstance(field, StitchField):
                    field.set_error(
                        message
                        if self._t.language == "vi"
                        else self._t("Vui lòng kiểm tra giá trị này")
                    )
        else:
            self.error_label.configure(
                text=self._t("Không thể lưu. Kiểm tra thông tin hoặc quyền truy cập.")
            )


class EmployeeProfileForm(StitchDialog):
    """Business-owned personnel profile, deliberately separate from credentials."""

    def __init__(self, parent, context, stores, *, profile=None, runner=None, on_saved=None):
        self.context, self.profile = context, profile
        self.runner = runner or default_runner()
        self.on_saved = on_saved
        self._t = UIStrings(context.language)
        super().__init__(
            parent,
            title=self._t("Hồ sơ nhân sự"),
            subtitle=self._t("Thông tin công việc; không thay đổi tài khoản đăng nhập"),
            icon="",
            width=620,
            language=context.language,
            confirm_text=self._t("Lưu hồ sơ"),
        )
        self.name = StitchField(self.body, self._t("Họ và tên"))
        self.name.pack(fill="x", pady=(0, 12))
        if profile:
            self.name.set_value(profile["full_name"])
        active_stores = [store for store in stores if store.status == "ACTIVE"]
        self.store_values = {
            f"{store.code} · {store.name}": store.id for store in active_stores
        }
        ctk.CTkLabel(
            self.body,
            text=self._t("CƠ SỞ CHÍNH"),
            font=t.FONT_ST_LABEL_CAPS,
            text_color=t.STITCH_TEXT,
            anchor="w",
        ).pack(fill="x")
        self.store = ctk.CTkOptionMenu(
            self.body,
            values=list(self.store_values),
            height=38,
            font=t.FONT_ST_BODY,
            fg_color=t.STITCH_BG_CANVAS,
            button_color=t.STITCH_CHIP_BG,
            button_hover_color=t.STITCH_TAB_HOVER,
        )
        self.store.pack(fill="x", pady=(6, 12))
        selected_store = profile["home_store_id"] if profile else context.session.store_id
        for label, store_id in self.store_values.items():
            if store_id == selected_store:
                self.store.set(label)
                break
        self.status_values = {
            self._t("Hoạt động"): "ACTIVE",
            self._t("Ngừng hoạt động"): "INACTIVE",
        }
        ctk.CTkLabel(
            self.body,
            text=self._t("TRẠNG THÁI LÀM VIỆC"),
            font=t.FONT_ST_LABEL_CAPS,
            text_color=t.STITCH_TEXT,
            anchor="w",
        ).pack(fill="x")
        self.status = ctk.CTkOptionMenu(
            self.body,
            values=list(self.status_values),
            height=38,
            font=t.FONT_ST_BODY,
            fg_color=t.STITCH_BG_CANVAS,
            button_color=t.STITCH_CHIP_BG,
            button_hover_color=t.STITCH_TAB_HOVER,
        )
        self.status.pack(fill="x", pady=(6, 0))
        if profile and profile["employment_status"] == "INACTIVE":
            self.status.set(self._t("Ngừng hoạt động"))
        self.error_label = ctk.CTkLabel(
            self.body, text="", font=t.FONT_ST_BODY, text_color=t.STITCH_DANGER
        )
        self.error_label.pack(fill="x", pady=(8, 0))
        self.finish(self.name.focus)

    def submit(self):
        if self.is_submitting:
            return
        self.set_submitting(True)
        profile_id = self.profile["id"] if self.profile else None
        self.runner.submit(
            self,
            lambda: self.context.services.management.save_employee_profile(
                self.context.session,
                profile_id,
                self.store_values[self.store.get()],
                self.name.get_value(),
                self.status_values[self.status.get()],
            ),
            self._saved,
            self._failed,
        )

    def _saved(self, result):
        callback = self.on_saved
        self.close()
        if callback:
            callback(result)

    def _failed(self, exc):
        self.set_submitting(False)
        self.error_label.configure(text=getattr(exc, "message", str(exc)))


class EmployeePasswordResetForm(StitchDialog):
    """ADMIN-only temporary-password reset; the service enforces revocation and audit."""

    def __init__(self, parent, context, employee, *, runner=None, on_saved=None):
        self.context, self.employee = context, employee
        self.runner = runner or default_runner()
        self.on_saved = on_saved
        self._t = UIStrings(context.language)
        super().__init__(
            parent,
            title=self._t("Đặt lại mật khẩu"),
            subtitle=f"{employee.full_name} · {employee.username}",
            icon="",
            width=620,
            language=context.language,
            confirm_text=self._t("Đặt mật khẩu tạm"),
        )
        self.password = StitchField(
            self.body,
            self._t("Mật khẩu tạm thời"),
            password=True,
            hint=self._t("Người dùng phải đổi mật khẩu ở lần đăng nhập tiếp theo"),
        )
        self.password.pack(fill="x")
        generate = stitch_button(
            self.body,
            self._t("Tạo mật khẩu an toàn"),
            command=self._generate,
            width=180,
        )
        generate.pack(anchor="e", pady=(10, 0))
        self.error_label = ctk.CTkLabel(
            self.body, text="", font=t.FONT_ST_BODY, text_color=t.STITCH_DANGER
        )
        self.error_label.pack(fill="x", pady=(8, 0))
        self.finish(self.password.focus)

    def _generate(self):
        alphabet = string.ascii_letters + string.digits + "!@#$%"
        value = "".join(secrets.choice(alphabet) for _ in range(16))
        self.password.set_value(value)
        if not self.password.is_revealed:
            self.password.toggle_password()

    def submit(self):
        if self.is_submitting:
            return
        self.set_submitting(True)
        self.runner.submit(
            self,
            lambda: self.context.services.management.reset_employee_password(
                self.context.session, self.employee.id, self.password.get_value()
            ),
            self._saved,
            self._failed,
        )

    def _saved(self, result):
        callback = self.on_saved
        self.close()
        if callback:
            callback(result)

    def _failed(self, exc):
        self.set_submitting(False)
        self.error_label.configure(text=getattr(exc, "message", str(exc)))


class ManagerStoreAssignmentForm(StitchDialog):
    """ADMIN-owned grant/revoke dialog for a manager's additional stores."""

    def __init__(self, parent, context, employee, stores, assigned, *, runner=None, on_saved=None):
        self.context, self.employee = context, employee
        self.runner = runner or default_runner()
        self.on_saved = on_saved
        self._t = UIStrings(context.language)
        super().__init__(
            parent,
            title=self._t("Phân công cơ sở"),
            subtitle=f"{employee.full_name} · {employee.username}",
            icon="",
            width=640,
            language=context.language,
            confirm_text=self._t("Áp dụng"),
        )
        available = [
            store for store in stores
            if store.status == "ACTIVE" and store.id != employee.store_id
        ]
        self.store_values = {
            f"{store.code} · {store.name}": store.id for store in available
        }
        assigned_names = [store.name for store in available if store.id in set(assigned)]
        ctk.CTkLabel(
            self.body,
            text=self._t("Cơ sở phụ hiện tại") + ": " + (", ".join(assigned_names) or "—"),
            font=t.FONT_ST_BODY,
            text_color=t.STITCH_TEXT_MUTED,
            anchor="w",
            wraplength=570,
        ).pack(fill="x", pady=(0, 12))
        self.store = ctk.CTkOptionMenu(
            self.body,
            values=list(self.store_values) or [self._t("Không có cơ sở phụ")],
            height=38,
            font=t.FONT_ST_BODY,
            fg_color=t.STITCH_BG_CANVAS,
            button_color=t.STITCH_CHIP_BG,
            button_hover_color=t.STITCH_TAB_HOVER,
        )
        self.store.pack(fill="x", pady=(0, 12))
        self.action_values = {
            self._t("Giao quyền vận hành"): True,
            self._t("Thu hồi quyền vận hành"): False,
        }
        self.action = ctk.CTkOptionMenu(
            self.body,
            values=list(self.action_values),
            height=38,
            font=t.FONT_ST_BODY,
            fg_color=t.STITCH_BG_CANVAS,
            button_color=t.STITCH_CHIP_BG,
            button_hover_color=t.STITCH_TAB_HOVER,
        )
        self.action.pack(fill="x")
        self.error_label = ctk.CTkLabel(
            self.body, text="", font=t.FONT_ST_BODY, text_color=t.STITCH_DANGER
        )
        self.error_label.pack(fill="x", pady=(8, 0))
        if not self.store_values:
            self.confirm_button.set_enabled(False)
        self.finish()

    def submit(self):
        if self.is_submitting or not self.store_values:
            return
        self.set_submitting(True)
        self.runner.submit(
            self,
            lambda: self.context.services.management.set_manager_store_assignment(
                self.context.session,
                self.employee.id,
                self.store_values[self.store.get()],
                self.action_values[self.action.get()],
            ),
            self._saved,
            self._failed,
        )

    def _saved(self, result):
        callback = self.on_saved
        self.close()
        if callback:
            callback(result)

    def _failed(self, exc):
        self.set_submitting(False)
        self.error_label.configure(text=getattr(exc, "message", str(exc)))


class ManagementView(ctk.CTkFrame):
    def __init__(self, master, context, *, kind, runner=None):
        super().__init__(master, fg_color="transparent")
        self._context, self.kind = context, kind
        self._t = UIStrings(context.language)
        self.runner = runner or default_runner()
        self.items, self.stores, self.profiles = [], [], []
        self.employee_mode = "accounts"
        self._closed = False
        self._request = 0
        title, subtitle = {
            "stores": ("Cơ sở", "Quản lý địa điểm, trạng thái và phạm vi vận hành"),
            "employees": (
                "Nhân viên",
                "Tài khoản, vai trò và quyền truy cập theo cơ sở",
            ),
            "promotions": (
                "Khuyến mãi",
                "Chính sách theo mốc nạp · không cộng dồn nhiều chính sách",
            ),
        }[kind]
        header = PageHeader(
            self,
            self._t(title),
            self._t(subtitle),
            eyebrow=self._t("QUẢN TRỊ VẬN HÀNH"),
        )
        header.pack(fill="x")
        self.add_button = icon_action(
            header.actions,
            self._t("Thêm mới"),
            "plus",
            kind="primary",
            command=lambda: self.open_form(),
        )
        if kind != "employees" or not separated_rbac() or can(context.session.role, Permission.MANAGE_EMPLOYEE_CREDENTIALS):
            self.add_button.pack(side="right")
        if (
            kind == "employees"
            and separated_rbac()
            and can(context.session.role, Permission.MANAGE_EMPLOYEES)
            and context.session.role != Role.ADMIN
        ):
            self.profile_button = icon_action(
                header.actions,
                self._t("Tạo hồ sơ nhân sự"),
                "plus",
                kind="primary",
                command=lambda: self.open_profile_form(),
            )
            self.profile_button.pack(side="right")
        self.refresh_button = icon_action(
            header.actions, self._t("Làm mới"), "refresh", command=self.reload
        )
        self.refresh_button.pack(side="right", padx=(0, 10))
        self.metrics = ctk.CTkFrame(self, fg_color="transparent")
        self.metrics.pack(fill="x", pady=12)
        self.tiles = []
        for index, (label, icon) in enumerate(
            (
                ("Tổng số", "reports"),
                ("Hoạt động", "check"),
                ("Phạm vi cơ sở", "customers"),
            )
        ):
            self.metrics.grid_columnconfigure(index, weight=1, uniform="metrics")
            tile = MetricTile(
                self.metrics,
                self._t(label),
                icon=icon,
                color=t.STITCH_CYAN if index == 0 else t.STITCH_SUCCESS,
            )
            tile.grid(
                row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 10, 0)
            )
            self.tiles.append(tile)
        bar = surface(self)
        bar.pack(fill="x", pady=(0, 12))
        if kind == "employees" and separated_rbac():
            self.employee_tabs = ctk.CTkSegmentedButton(
                bar,
                values=[self._t("Tài khoản đăng nhập"), self._t("Hồ sơ nhân sự")],
                command=self._set_employee_mode,
                font=t.FONT_ST_BODY,
            )
            self.employee_tabs.set(self._t("Tài khoản đăng nhập"))
            self.employee_tabs.pack(side="left", padx=(12, 0), pady=10)
        self.search = ctk.CTkEntry(
            bar,
            placeholder_text=self._t("Tìm kiếm…"),
            font=t.FONT_ST_BODY,
            height=36,
            fg_color=t.STITCH_BG_CANVAS,
            border_color=t.STITCH_BORDER,
        )
        self.search.pack(side="left", fill="x", expand=True, padx=12, pady=10)
        self.search.bind("<KeyRelease>", lambda _: self.render())
        self.table = ctk.CTkScrollableFrame(
            self, fg_color=t.STITCH_CARD_BG, corner_radius=12
        )
        self.table.pack(fill="both", expand=True)
        note = (
            "Quản lý chỉ được quản trị nhân viên STAFF tại cơ sở được giao"
            if kind == "employees"
            else (
                "Tiền khuyến mãi dùng trước, không quy đổi tiền mặt"
                if kind == "promotions"
                else "Ngừng cơ sở yêu cầu không còn phiên đang hoạt động"
            )
        )
        ctk.CTkLabel(
            self,
            text=self._t(note),
            font=t.FONT_ST_MONO_11,
            text_color=t.STITCH_TEXT_DIM,
        ).pack(anchor="w", pady=(10, 0))
        self.reload()

    def reload(self):
        self._request += 1
        request_id = self._request
        self.refresh_button.set_busy(True)

        def call():
            service, actor = self._context.services.management, self._context.session
            profiles = (
                service.list_employee_profiles(actor)
                if self.kind == "employees" and separated_rbac()
                else []
            )
            return (
                getattr(service, "list_" + self.kind)(actor),
                service.list_stores(actor),
                profiles,
            )

        def loaded(result):
            if self._closed or request_id != self._request:
                return
            self.refresh_button.set_busy(False)
            self.items, self.stores, self.profiles = result
            self.render()

        def failed(exc):
            if self._closed or request_id != self._request:
                return
            self.refresh_button.set_busy(False)
            notify_error(self, exc)

        self.runner.submit(self, call, loaded, failed)

    def _set_employee_mode(self, label):
        self.employee_mode = (
            "profiles" if label == self._t("Hồ sơ nhân sự") else "accounts"
        )
        self.render()

    def render(self):
        for child in self.table.winfo_children():
            child.destroy()
        if self.kind == "employees" and self.employee_mode == "profiles":
            self._render_employee_profiles()
            return
        self.tiles[0].value.configure(text=str(len(self.items)))
        active = sum(
            getattr(i, "status", "ACTIVE") == "ACTIVE" and getattr(i, "is_active", True)
            for i in self.items
        )
        self.tiles[1].value.configure(text=str(active))
        self.tiles[2].value.configure(
            text=(
                self._t("Toàn hệ thống")
                if chain_director(self._context.session.role)
                else self._context.session.store_code
            )
        )
        search = self.search.get().strip().casefold()
        rows = [
            item
            for item in self.items
            if not search
            or search in " ".join(str(v) for v in vars(item).values()).casefold()
        ]
        headers = {
            "stores": ["Mã cơ sở", "Tên cơ sở", "Địa chỉ", "Trạng thái"],
            "employees": [
                "Họ và tên",
                "Tên đăng nhập",
                "Vai trò / Cơ sở",
                "Trạng thái",
            ],
            "promotions": [
                "Tên khuyến mãi",
                "Mốc nạp / Thưởng",
                "Thời gian áp dụng",
                "Phạm vi áp dụng",
            ],
        }[self.kind]
        header = ctk.CTkFrame(self.table, fg_color=t.STITCH_BG_CHROME, corner_radius=6)
        header.pack(fill="x", pady=(4, 8), padx=4)
        for column, label in enumerate(headers + ["Thao tác"]):
            header.grid_columnconfigure(
                column, weight=1 if column == 4 else 3, uniform="cols"
            )
            ctk.CTkLabel(
                header,
                text=self._t(label),
                font=t.FONT_ST_LABEL_CAPS,
                text_color=t.STITCH_TEXT_MUTED,
                anchor="w",
                wraplength=180,
            ).grid(row=0, column=column, sticky="ew", padx=10, pady=10)
        store_names = {s.id: s.code for s in self.stores}
        for index, item in enumerate(rows):
            row = ctk.CTkFrame(
                self.table,
                fg_color=t.WORKSPACE_ROW_ALT if index % 2 else "transparent",
                corner_radius=7,
            )
            row.pack(fill="x", padx=4, pady=2)
            if self.kind == "stores":
                values = [
                    item.code,
                    item.name,
                    item.address,
                    self._t(STATUS[item.status]),
                ]
            elif self.kind == "employees":
                values = [
                    item.full_name,
                    item.username,
                    self._t(STATUS[item.role])
                    + " · "
                    + store_names.get(item.store_id, str(item.store_id)),
                    self._t(STATUS[item.status]),
                ]
            else:
                values = [
                    item.name + "\n" + item.code,
                    format_money(item.minimum_amount, self._t.language)
                    + f" · {item.bonus_percent}%",
                    format_datetime(item.starts_at)
                    + "\n"
                    + format_datetime(item.ends_at),
                    store_names.get(item.store_id, self._t("Toàn hệ thống"))
                    + "\n"
                    + self._t("Bật" if item.is_active else "Tắt"),
                ]
            for column, value in enumerate(values):
                row.grid_columnconfigure(column, weight=3, uniform="cols")
                ctk.CTkLabel(
                    row,
                    text=value,
                    font=t.FONT_ST_BODY,
                    text_color=t.STITCH_TEXT,
                    anchor="w",
                    justify="left",
                    wraplength=180,
                ).grid(row=0, column=column, sticky="ew", padx=10, pady=12)
            row.grid_columnconfigure(4, weight=1, uniform="cols")
            actions = ctk.CTkFrame(row, fg_color="transparent")
            role = self._context.session.role
            editable = (
                can(role, Permission.MANAGE_STORES) if self.kind == "stores" else
                (can(role, Permission.MANAGE_EMPLOYEE_CREDENTIALS)
                 if separated_rbac()
                 else can(role, Permission.MANAGE_EMPLOYEE_CREDENTIALS) or
                 can(role, Permission.MANAGE_EMPLOYEES) and
                 (role == Role.DIRECTOR or item.role == "STAFF")) if self.kind == "employees" else
                can(role, Permission.MANAGE_PROMOTIONS) and
                (can(role, Permission.SWITCH_STORE) or item.store_id == self._context.session.store_id)
            )
            if editable:
                button = row_action(
                    actions,
                    "edit",
                    self._t("Chỉnh sửa"),
                    command=lambda current=item: self.open_form(current),
                )
                button.pack(side="left")
            if (
                self.kind == "employees"
                and separated_rbac()
                and can(role, Permission.MANAGE_EMPLOYEE_CREDENTIALS)
                and item.id != self._context.session.employee_id
            ):
                reset = row_action(
                    actions,
                    "lock",
                    self._t("Đặt lại mật khẩu"),
                    command=lambda current=item: self.open_password_reset(current),
                )
                reset.pack(side="left", padx=(6, 0))
                if item.role == "MANAGER":
                    assignment = row_action(
                        actions,
                        "stores",
                        self._t("Phân công cơ sở"),
                        command=lambda current=item: self.open_store_assignment(current),
                    )
                    assignment.pack(side="left", padx=(6, 0))
            if not actions.winfo_children():
                ctk.CTkLabel(
                    actions,
                    text="—",
                    font=t.FONT_ST_BODY,
                    text_color=t.STITCH_TEXT_DIM,
                ).pack()
            actions.grid(row=0, column=4, padx=10, pady=10, sticky="e")
        if not rows:
            ctk.CTkLabel(
                self.table,
                text=self._t("Chưa có dữ liệu. Thêm mới để bắt đầu."),
                font=t.FONT_ST_BODY,
                text_color=t.STITCH_TEXT_MUTED,
            ).pack(pady=60)

    def _render_employee_profiles(self):
        self.tiles[0].value.configure(text=str(len(self.profiles)))
        self.tiles[1].value.configure(
            text=str(sum(p["employment_status"] == "ACTIVE" for p in self.profiles))
        )
        self.tiles[2].value.configure(
            text=(
                self._t("Toàn hệ thống")
                if chain_director(self._context.session.role)
                else self._context.session.store_code
            )
        )
        search = self.search.get().strip().casefold()
        profiles = [
            profile for profile in self.profiles
            if not search
            or search in " ".join(str(value) for value in profile.values()).casefold()
        ]
        header = ctk.CTkFrame(self.table, fg_color=t.STITCH_BG_CHROME, corner_radius=6)
        header.pack(fill="x", pady=(4, 8), padx=4)
        labels = ["Mã hồ sơ", "Họ và tên", "Cơ sở chính", "Tài khoản", "Trạng thái", "Thao tác"]
        for column, label in enumerate(labels):
            header.grid_columnconfigure(column, weight=2 if column != 5 else 1, uniform="profiles")
            ctk.CTkLabel(
                header,
                text=self._t(label),
                font=t.FONT_ST_LABEL_CAPS,
                text_color=t.STITCH_TEXT_MUTED,
                anchor="w",
            ).grid(row=0, column=column, sticky="ew", padx=10, pady=10)
        store_names = {store.id: store.code for store in self.stores}
        account_names = {employee.id: employee.username for employee in self.items}
        can_edit = (
            can(self._context.session.role, Permission.MANAGE_EMPLOYEES)
            and self._context.session.role != Role.ADMIN
        )
        for index, profile in enumerate(profiles):
            row = ctk.CTkFrame(
                self.table,
                fg_color=t.WORKSPACE_ROW_ALT if index % 2 else "transparent",
                corner_radius=7,
            )
            row.pack(fill="x", padx=4, pady=2)
            values = [
                profile["code"],
                profile["full_name"],
                store_names.get(profile["home_store_id"], str(profile["home_store_id"])),
                account_names.get(profile.get("employee_id"), self._t("Chưa cấp")),
                self._t(STATUS[profile["employment_status"]]),
            ]
            for column, value in enumerate(values):
                row.grid_columnconfigure(column, weight=2, uniform="profiles")
                ctk.CTkLabel(
                    row,
                    text=value,
                    font=t.FONT_ST_BODY,
                    text_color=t.STITCH_TEXT,
                    anchor="w",
                ).grid(row=0, column=column, sticky="ew", padx=10, pady=12)
            row.grid_columnconfigure(5, weight=1, uniform="profiles")
            if can_edit:
                button = row_action(
                    row,
                    "edit",
                    self._t("Chỉnh sửa"),
                    command=lambda current=profile: self.open_profile_form(current),
                )
                button.grid(row=0, column=5, padx=10, pady=10, sticky="e")
            else:
                ctk.CTkLabel(row, text="—", text_color=t.STITCH_TEXT_DIM).grid(
                    row=0, column=5, padx=10, pady=10, sticky="e"
                )
        if not profiles:
            ctk.CTkLabel(
                self.table,
                text=self._t("Chưa có hồ sơ nhân sự phù hợp."),
                font=t.FONT_ST_BODY,
                text_color=t.STITCH_TEXT_MUTED,
            ).pack(pady=60)

    def open_form(self, item=None):
        if self.kind == "employees" and separated_rbac() and item is None:
            pending = [
                profile for profile in self.profiles
                if not profile.get("employee_id")
                and profile.get("employment_status") == "ACTIVE"
            ]
            if not pending:
                notify_error(
                    self,
                    ValidationError(
                        "Cần có hồ sơ nhân sự đang hoạt động và chưa được cấp tài khoản"
                    ),
                )
                return
        ManagementForm(
            self.winfo_toplevel(),
            self._context,
            self.kind,
            item=item,
            stores=self.stores,
            profiles=self.profiles,
            runner=self.runner,
            on_saved=lambda _: self.reload(),
        )

    def open_profile_form(self, profile=None):
        EmployeeProfileForm(
            self.winfo_toplevel(),
            self._context,
            self.stores,
            profile=profile,
            runner=self.runner,
            on_saved=lambda _: self.reload(),
        )

    def open_password_reset(self, employee):
        EmployeePasswordResetForm(
            self.winfo_toplevel(),
            self._context,
            employee,
            runner=self.runner,
            on_saved=lambda _: self.reload(),
        )

    def open_store_assignment(self, employee):
        def loaded(assigned):
            ManagerStoreAssignmentForm(
                self.winfo_toplevel(),
                self._context,
                employee,
                self.stores,
                assigned,
                runner=self.runner,
                on_saved=lambda _: self.reload(),
            )

        self.runner.submit(
            self,
            lambda: self._context.services.management.list_manager_store_assignments(
                self._context.session, employee.id
            ),
            loaded,
            lambda exc: notify_error(self, exc),
        )

    def shutdown(self):
        self._closed = True

    def destroy(self):
        self.shutdown()
        super().destroy()


class CustomerPortalView(ctk.CTkFrame):
    def __init__(
        self, master, services, principal, *, language="vi", on_logout=None, runner=None
    ):
        super().__init__(master, fg_color=t.STITCH_BG_CANVAS)
        self.services, self.principal, self.language = services, principal, language
        self._t = UIStrings(language)
        self.runner = runner or default_runner()
        self.closed = False
        self.after_id = None
        self.snapshot = None
        self._on_logout = on_logout
        head = PageHeader(
            self,
            self._t("Không gian khách hàng"),
            principal.full_name + " · " + principal.username,
            eyebrow="CYBERHUB",
        )
        head.pack(fill="x", padx=28, pady=22)
        self.header = head
        self.logout_button = icon_action(
            head.actions, self._t("Đăng xuất"), "logout", command=on_logout
        )
        self.logout_button.pack(side="right")
        self.refresh_button = icon_action(
            head.actions, self._t("Làm mới"), "refresh", command=self.reload
        )
        self.refresh_button.pack(side="right", padx=8)
        self.language_control = ctk.CTkSegmentedButton(
            head.actions,
            values=["VI", "EN"],
            command=lambda value: self.set_language(value.lower()),
            width=90,
            font=t.FONT_ST_BODY,
        )
        self.language_control.set(language.upper())
        self.language_control.pack(side="right", padx=8)
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=22, pady=(0, 20))
        self.reload()

    def set_language(self, language):
        self.language = "en" if language == "en" else "vi"
        self._t = UIStrings(self.language)
        self.header.title_label.configure(text=self._t("Không gian khách hàng"))
        self.logout_button.configure(text=self._t("Đăng xuất"))
        self.refresh_button.configure(text=self._t("Làm mới"))
        if self.snapshot:
            self.render(self.snapshot)

    def reload(self):
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.runner.submit(
            self,
            lambda: self.services.portal.snapshot(self.principal),
            self.render,
            lambda exc: notify_error(self, exc),
        )

    def render(self, snapshot):
        if self.closed:
            return
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.snapshot = snapshot
        for child in self.body.winfo_children():
            child.destroy()
        metrics = ctk.CTkFrame(self.body, fg_color="transparent")
        metrics.pack(fill="x")
        for index, (key, label, color) in enumerate(
            (
                ("cash_balance", "Số dư chính", t.STITCH_TEXT_STRONG),
                ("bonus_balance", "Số dư khuyến mãi", t.STITCH_SUCCESS),
                ("balance", "Tổng số dư sử dụng", t.STITCH_CYAN),
            )
        ):
            metrics.grid_columnconfigure(index, weight=1, uniform="wallet")
            tile = MetricTile(
                metrics,
                self._t(label),
                icon="money",
                color=color,
                note=(
                    self._t("Khuyến mãi không quy đổi tiền mặt")
                    if key == "bonus_balance"
                    else ""
                ),
            )
            tile.value.configure(
                text=format_money(snapshot["wallet"][key], self.language)
            )
            tile.note.configure(wraplength=250,justify="left")
            tile.grid(
                row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 12, 0)
            )
        for key, title in (
            ("sessions", "Phiên sử dụng"),
            ("transactions", "Lịch sử giao dịch"),
            ("invoices", "Hóa đơn của tôi"),
        ):
            panel = surface(self.body)
            panel.pack(fill="x", pady=(18, 0))
            ctk.CTkLabel(
                panel,
                text=self._t(title),
                font=t.FONT_WORKSPACE_SECTION,
                text_color=t.STITCH_TEXT_STRONG,
            ).pack(anchor="w", padx=18, pady=12)
            if not snapshot[key]:
                ctk.CTkLabel(
                    panel, text=self._t("Chưa có dữ liệu"), text_color=t.STITCH_TEXT_DIM
                ).pack(pady=20)
            for item in snapshot[key]:
                row = ctk.CTkFrame(panel, fg_color="transparent")
                row.pack(fill="x", padx=18, pady=6)
                if key == "transactions":
                    stamp = format_datetime(item["created_at"])
                    value = ("+" if item["amount"] > 0 else "") + format_money(
                        item["amount"], self.language
                    )
                    description = self._t(
                        {
                            "TOP_UP": "Nạp tiền",
                            "PROMOTION": "Khuyến mãi",
                            "USAGE_PAYMENT": "Thanh toán phiên",
                            "DEBT_SETTLEMENT": "Bù nợ",
                        }.get(item["type"], item["type"])
                    )
                    caption = item["code"] + " · " + description + " · " + stamp
                elif key == "sessions":
                    value = (
                        self._t("Đang dùng")
                        if item["status"] == "ACTIVE"
                        else self._t("Đã hoàn tất")
                    )
                    caption = (
                        item["code"]
                        + " · "
                        + item["machine_code"]
                        + " · "
                        + item["store_name"]
                        + " · "
                        + format_datetime(item["started_at"])
                    )
                else:
                    caption = (
                        item["code"]
                        + " · "
                        + item["store_name"]
                        + " · "
                        + format_datetime(item["created_at"])
                    )
                    value = (
                        format_money(item["usage_cost"], self.language)
                        + " · "
                        + self._t(
                            "Đã thanh toán" if item["status"] == "PAID" else "Đã hủy"
                        )
                    )
                    icon_action(
                        row,
                        self._t("Xuất / In"),
                        "invoices",
                        width=110,
                        command=lambda invoice_id=item["id"]: self.export(invoice_id),
                    ).pack(side="right", padx=(10, 0))
                ctk.CTkLabel(
                    row,
                    text=value,
                    font=t.FONT_ST_BODY_STRONG,
                    text_color=t.STITCH_CYAN,
                ).pack(side="right")
                ctk.CTkLabel(
                    row,
                    text=caption,
                    font=t.FONT_ST_BODY,
                    text_color=t.STITCH_TEXT_MUTED,
                    wraplength=600,
                    justify="left",
                ).pack(side="left", fill="x", expand=True)
        self.after_id = self.after(15000, self.reload)

    def export(self, invoice_id):
        self.runner.submit(
            self,
            lambda: self.services.portal.invoice(self.principal, invoice_id),
            lambda detail: export_detail(self, detail, self.language, True),
            lambda exc: notify_error(self, exc),
        )

    def destroy(self):
        self.closed = True
        if self.after_id:
            self.after_cancel(self.after_id)
        super().destroy()
