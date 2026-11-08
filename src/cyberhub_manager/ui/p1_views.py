"""Native P1 administration and customer workspace, using shared service contracts."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import filedialog
import tempfile
import webbrowser

import customtkinter as ctk

from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.exceptions import ApplicationError, ValidationError
from cyberhub_manager.domain.p1 import Promotion
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
    "MANAGER": "Quản lý",
    "STAFF": "Nhân viên",
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
        self, parent, context, kind, *, item=None, stores=(), runner=None, on_saved=None
    ):
        self._t = UIStrings(context.language)
        self.context, self.kind, self.item = context, kind, item
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
            specs = [
                ("full_name", "Họ và tên", "text", None),
                ("username", "Tên đăng nhập", "text", None),
                ("store_id", "Cơ sở", "choice", store_choices),
                (
                    "role",
                    "Vai trò",
                    "choice",
                    (
                        ["ADMIN", "MANAGER", "STAFF"]
                        if context.session.role == Role.ADMIN
                        else ["STAFF"]
                    ),
                ),
                ("status", "Trạng thái", "choice", ["ACTIVE", "INACTIVE", "LOCKED"]),
                ("password", "Mật khẩu mới", "password", None),
            ]
        else:
            if context.session.role == Role.ADMIN:
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


class ManagementView(ctk.CTkFrame):
    def __init__(self, master, context, *, kind, runner=None):
        super().__init__(master, fg_color="transparent")
        self._context, self.kind = context, kind
        self._t = UIStrings(context.language)
        self.runner = runner or default_runner()
        self.items, self.stores = [], []
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
        icon_action(
            header.actions,
            self._t("Thêm mới"),
            "plus",
            kind="primary",
            command=lambda: self.open_form(),
        ).pack(side="right")
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
        self.search = ctk.CTkEntry(
            bar,
            placeholder_text=self._t("Tìm kiếm…"),
            font=t.FONT_ST_BODY,
            height=36,
            fg_color=t.STITCH_BG_CANVAS,
            border_color=t.STITCH_BORDER,
        )
        self.search.pack(fill="x", padx=12, pady=10)
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
            return getattr(service, "list_" + self.kind)(actor), service.list_stores(
                actor
            )

        def loaded(result):
            if self._closed or request_id != self._request:
                return
            self.refresh_button.set_busy(False)
            self.items, self.stores = result
            self.render()

        def failed(exc):
            if self._closed or request_id != self._request:
                return
            self.refresh_button.set_busy(False)
            notify_error(self, exc)

        self.runner.submit(self, call, loaded, failed)

    def render(self):
        for child in self.table.winfo_children():
            child.destroy()
        self.tiles[0].value.configure(text=str(len(self.items)))
        active = sum(
            getattr(i, "status", "ACTIVE") == "ACTIVE" and getattr(i, "is_active", True)
            for i in self.items
        )
        self.tiles[1].value.configure(text=str(active))
        self.tiles[2].value.configure(
            text=(
                self._t("Toàn hệ thống")
                if self._context.session.role == Role.ADMIN
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
            button = row_action(
                row,
                "edit",
                self._t("Chỉnh sửa"),
                command=lambda current=item: self.open_form(current),
            )
            editable = (
                self._context.session.role == Role.ADMIN
                or (self.kind == "employees" and item.role == "STAFF")
                or (
                    self.kind == "promotions"
                    and item.store_id == self._context.session.store_id
                )
            )
            button.set_enabled(editable)
            button.grid(row=0, column=4, padx=10, pady=10, sticky="e")
        if not rows:
            ctk.CTkLabel(
                self.table,
                text=self._t("Chưa có dữ liệu. Thêm mới để bắt đầu."),
                font=t.FONT_ST_BODY,
                text_color=t.STITCH_TEXT_MUTED,
            ).pack(pady=60)

    def open_form(self, item=None):
        ManagementForm(
            self.winfo_toplevel(),
            self._context,
            self.kind,
            item=item,
            stores=self.stores,
            runner=self.runner,
            on_saved=lambda _: self.reload(),
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
