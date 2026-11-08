"""HA-11 — Màn đăng nhập theo Stitch `ng_nh_p_cyberhub_manager_1280x720`.

- Trái: logo, tên sản phẩm, tagline và các điểm nổi bật. Phải: VI/EN, form đăng nhập, trạng thái hệ thống.
- Form: tên đăng nhập + mật khẩu (nút 👁 hiện/ẩn), Enter để đăng nhập.
- Đang gửi: khóa nút và hai ô nhập, chống bấm hai lần.
- Sai thông tin: giữ tên đăng nhập, xóa mật khẩu, báo một câu chung (không lộ tài khoản có tồn tại hay không).
- Lỗi khác (mất kết nối DB...): câu tiếng Anh an toàn qua ui.messages; không bao giờ hiện traceback.
- Gọi AuthService.login ở nền (TaskRunner) để cửa sổ không bị treo khi MySQL chậm.
"""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from importlib.resources import files
from typing import Any

import customtkinter as ctk
from PIL import Image

from ..domain.dtos import EmployeeSession
from ..domain.exceptions import ApplicationError
from ..services.contracts import AuthServiceProtocol
from .background import TaskRunner, default_runner
from .components.stitch_button import stitch_button
from .components.stitch_field import StitchField
from .i18n import Language, normalize_language, translate
from .messages import FIELD_ERROR_MESSAGES, MSG_OPERATION_FAILED, get_user_friendly_error
from .theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_LABEL_CAPS,
    FONT_ST_MONO_11,
    FONT_ST_MONO_SM,
    STITCH_BADGE_DANGER_BG,
    STITCH_BADGE_DANGER_BORDER,
    STITCH_BG_CANVAS,
    STITCH_BG_CHROME,
    STITCH_BORDER,
    STITCH_CHIP_BG,
    STITCH_CHIP_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_FONT,
    STITCH_NAV_ACTIVE_BG,
    STITCH_NAV_ACTIVE_BORDER,
    STITCH_RADIUS,
    STITCH_RADIUS_LG,
    STITCH_SUCCESS,
    STITCH_TAB_HOVER,
    STITCH_TEXT,
    STITCH_TEXT_DIM,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_ON_CYAN,
    STITCH_TEXT_STRONG,
)

logger = logging.getLogger(__name__)

REQUIRED = FIELD_ERROR_MESSAGES["REQUIRED"]
FONT_HERO = (STITCH_FONT, 30, "bold")
FONT_TITLE = (STITCH_FONT, 24, "bold")
LOGO_HEIGHT = 64
FEATURE_KEYS = ("login.feature_sessions", "login.feature_billing", "login.feature_roles", "login.feature_reports")
FEATURE_ICONS = ("✓", "₫", "⚿", "▤")

OnSuccess = Callable[[EmployeeSession, Language], None]


def _load_logo() -> ctk.CTkImage | None:
    """Logo đầy đủ cho cột trái; lỗi thì trả None (chỉ hiện chữ)."""
    try:
        resource = files("cyberhub_manager.ui.assets").joinpath("cyberhub_logo_dark.png")
        with resource.open("rb") as stream:
            image = Image.open(stream).convert("RGBA")
        width = round(image.width * LOGO_HEIGHT / image.height)
        return ctk.CTkImage(light_image=image, dark_image=image, size=(width, LOGO_HEIGHT))
    except Exception:  # noqa: BLE001 — thiếu logo không được làm hỏng màn đăng nhập
        logger.exception("Không tải được logo")
        return None


def validate_login(username: str, password: str) -> dict[str, str]:
    """Lỗi từng ô trước khi gọi service; tên đăng nhập được trim, mật khẩu giữ nguyên."""
    errors: dict[str, str] = {}
    if not username.strip():
        errors["username"] = REQUIRED
    if not password:
        errors["password"] = REQUIRED
    return errors


def login_error_message(error: Exception) -> str:
    """Câu báo lỗi an toàn cho người dùng; lỗi không mong đợi chỉ ghi log."""
    if isinstance(error, ApplicationError):
        return get_user_friendly_error(error)
    logger.error("Lỗi không mong đợi khi đăng nhập", exc_info=error)
    return MSG_OPERATION_FAILED


class LoginView(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        auth: AuthServiceProtocol,
        *,
        on_success: OnSuccess,
        runner: TaskRunner | None = None,
        language: str | None = None,
    ) -> None:
        super().__init__(master, fg_color=STITCH_BG_CANVAS, corner_radius=0)
        self._auth = auth
        self._on_success = on_success
        self._runner = runner or default_runner()
        self._language: Language = normalize_language(language)
        self._submitting = False
        self._logo = _load_logo()

        self.grid_columnconfigure(0, weight=11, uniform="login")
        self.grid_columnconfigure(1, weight=9, uniform="login")
        self.grid_rowconfigure(0, weight=1)
        self._brand = ctk.CTkFrame(self, fg_color=STITCH_BG_CHROME, corner_radius=0)
        self._brand.grid(row=0, column=0, sticky="nsew")
        # Đường kẻ 1px dùng tk.Frame: CTkFrame 1px không được vẽ ổn định (giống app_shell).
        tk.Frame(self, width=1, bg=STITCH_BORDER, bd=0, highlightthickness=0).grid(row=0, column=0, sticky="nse")
        self._panel = ctk.CTkFrame(self, fg_color=STITCH_BG_CANVAS, corner_radius=0)
        self._panel.grid(row=0, column=1, sticky="nsew")
        self._render()

    # ------------------------------------------------------------------
    # Thuộc tính công khai (test)
    # ------------------------------------------------------------------
    @property
    def language(self) -> Language:
        return self._language

    @property
    def is_submitting(self) -> bool:
        return self._submitting

    @property
    def username_field(self) -> StitchField:
        return self._username

    @property
    def password_field(self) -> StitchField:
        return self._password

    @property
    def error_text(self) -> str:
        return self._error_label.cget("text") if self._error_box.winfo_manager() else ""

    def _t(self, key: str) -> str:
        return translate(key, self._language)

    # ------------------------------------------------------------------
    # Dựng giao diện (dựng lại toàn bộ khi đổi ngôn ngữ, giữ tên đăng nhập đã gõ)
    # ------------------------------------------------------------------
    def _render(self, username: str = "") -> None:
        for frame in (self._brand, self._panel):
            for child in frame.winfo_children():
                child.destroy()
        self._build_brand()
        self._build_panel()
        if username:
            self._username.set_value(username)
        self.after(0, self._focus_first)

    def _build_brand(self) -> None:
        box = ctk.CTkFrame(self._brand, fg_color="transparent")
        box.place(relx=0.08, rely=0.5, anchor="w")
        logo = ctk.CTkFrame(box, fg_color=STITCH_BG_CANVAS, border_width=1, border_color=STITCH_BORDER, corner_radius=14)
        logo.pack(anchor="w")
        if self._logo is not None:
            ctk.CTkLabel(logo, text="", image=self._logo).pack(padx=22, pady=14)
        else:
            ctk.CTkLabel(logo, text="CyberHub", font=FONT_TITLE, text_color=STITCH_CYAN).pack(padx=22, pady=14)
        tag = ctk.CTkFrame(box, fg_color=STITCH_NAV_ACTIVE_BG, border_width=1, border_color=STITCH_NAV_ACTIVE_BORDER, corner_radius=STITCH_RADIUS)
        tag.pack(anchor="w", pady=(26, 0))
        ctk.CTkLabel(tag, text=self._t("login.brand_tag"), font=FONT_ST_MONO_11, text_color=STITCH_CYAN, height=22).pack(padx=10)
        title = ctk.CTkFrame(box, fg_color="transparent")
        title.pack(anchor="w", pady=(14, 0))
        ctk.CTkLabel(title, text="CyberHub ", font=FONT_HERO, text_color=STITCH_TEXT_STRONG).pack(side="left")
        ctk.CTkLabel(title, text="Manager", font=FONT_HERO, text_color=STITCH_CYAN).pack(side="left")
        ctk.CTkLabel(box, text=self._t("login.brand_tagline"), font=(STITCH_FONT, 15, "normal"), text_color=STITCH_TEXT_MUTED).pack(
            anchor="w", pady=(6, 0)
        )
        tk.Frame(box, height=1, width=520, bg=STITCH_BORDER, bd=0, highlightthickness=0).pack(anchor="w", pady=(26, 18))
        features = ctk.CTkFrame(box, fg_color="transparent")
        features.pack(anchor="w")
        for index, (key, icon) in enumerate(zip(FEATURE_KEYS, FEATURE_ICONS)):
            cell = ctk.CTkFrame(features, fg_color="transparent")
            cell.grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 40), pady=4)
            ctk.CTkLabel(cell, text=icon, font=FONT_ST_BODY_STRONG, text_color=STITCH_CYAN, width=18).pack(side="left")
            ctk.CTkLabel(cell, text=self._t(key), font=FONT_ST_BODY, text_color=STITCH_TEXT).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(self._brand, text=self._t("login.copyright"), font=FONT_ST_MONO_11, text_color=STITCH_TEXT_DIM).place(
            relx=0.08, rely=0.93, anchor="w"
        )

    def _build_panel(self) -> None:
        top = ctk.CTkFrame(self._panel, fg_color="transparent")
        top.pack(fill="x", padx=40, pady=(36, 0))
        ctk.CTkLabel(top, text=self._t("login.portal"), font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_MUTED).pack(side="left")
        switch = ctk.CTkFrame(top, fg_color=STITCH_CHIP_BG, border_width=1, border_color=STITCH_CHIP_BORDER, corner_radius=STITCH_RADIUS)
        switch.pack(side="right")
        self._lang_buttons: dict[Language, ctk.CTkButton] = {}
        for code in ("vi", "en"):
            active = code == self._language
            button = ctk.CTkButton(
                switch,
                text=code.upper(),
                width=40,
                height=26,
                corner_radius=STITCH_RADIUS,
                fg_color=STITCH_CYAN if active else "transparent",
                hover_color=STITCH_CYAN if active else STITCH_TAB_HOVER,
                text_color=STITCH_TEXT_ON_CYAN if active else STITCH_TEXT_MUTED,
                font=FONT_ST_MONO_SM,
                command=lambda c=code: self.set_language(c),
            )
            button.pack(side="left", padx=2, pady=2)
            self._lang_buttons[code] = button

        form = ctk.CTkFrame(self._panel, fg_color="transparent", width=400)
        form.place(relx=0.5, rely=0.47, anchor="center")
        ctk.CTkLabel(form, text=self._t("login.title"), font=FONT_TITLE, text_color=STITCH_TEXT_STRONG, anchor="w").pack(fill="x")
        ctk.CTkLabel(form, text=self._t("login.subtitle"), font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, anchor="w").pack(
            fill="x", pady=(2, 22)
        )
        self._username = StitchField(form, self._t("login.username"), placeholder=self._t("login.username_placeholder"), required=False)
        self._username.pack(fill="x")
        self._username.entry.configure(width=380)
        self._password = StitchField(
            form, self._t("login.password"), placeholder=self._t("login.password_placeholder"), required=False, password=True
        )
        self._password.pack(fill="x", pady=(16, 0))
        for field in (self._username, self._password):
            field.bind_return(self.submit)

        self._error_box = ctk.CTkFrame(
            form, fg_color=STITCH_BADGE_DANGER_BG, border_width=1, border_color=STITCH_BADGE_DANGER_BORDER, corner_radius=STITCH_RADIUS_LG
        )
        self._error_label = ctk.CTkLabel(
            self._error_box, text="", font=FONT_ST_BODY_STRONG, text_color=STITCH_DANGER, anchor="w", justify="left", wraplength=360
        )
        self._error_label.pack(fill="x", padx=12, pady=8)

        self._submit_button = stitch_button(form, self._t("login.submit"), kind="primary", command=self.submit, width=380, height=44)
        self._submit_button.configure(font=(STITCH_FONT, 14, "bold"))
        self._submit_button.pack(fill="x", pady=(22, 0))
        ctk.CTkLabel(form, text=self._t("login.enter_hint"), font=FONT_ST_MONO_11, text_color=STITCH_TEXT_DIM).pack(pady=(10, 0))

        footer = ctk.CTkFrame(self._panel, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=40, pady=(0, 30))
        tk.Frame(footer, height=1, bg=STITCH_BORDER, bd=0, highlightthickness=0).pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(footer, text=f"●  {self._t('status.ready')}", font=FONT_ST_BODY_STRONG, text_color=STITCH_SUCCESS).pack(side="left")

    def _focus_first(self) -> None:
        try:
            target = self._password if self._username.get_value().strip() else self._username
            target.focus()
        except Exception:  # noqa: BLE001 — màn đã bị hủy trước khi kịp focus
            pass

    # ------------------------------------------------------------------
    # Hành động
    # ------------------------------------------------------------------
    def set_language(self, language: str) -> None:
        code = normalize_language(language)
        if code == self._language or self._submitting:
            return
        self._language = code
        self._render(username=self._username.get_value())

    def show_error(self, message: str | None) -> None:
        self._error_label.configure(text=message or "")
        if message and not self._error_box.winfo_manager():
            self._error_box.pack(fill="x", pady=(16, 0), before=self._submit_button)
        elif not message and self._error_box.winfo_manager():
            self._error_box.pack_forget()

    def _set_submitting(self, submitting: bool) -> None:
        self._submitting = submitting
        self._submit_button.set_busy(submitting)
        state = "disabled" if submitting else "normal"
        for field in (self._username, self._password):
            field.entry.configure(state=state)
        for button in self._lang_buttons.values():
            button.configure(state=state)

    def submit(self) -> None:
        if self._submitting:
            return  # chống double-submit (Enter + click)
        username = self._username.get_value()
        password = self._password.get_value()
        errors = validate_login(username, password)
        self._username.set_error(errors.get("username"))
        self._password.set_error(errors.get("password"))
        self.show_error(None)
        if errors:
            (self._username if "username" in errors else self._password).focus()
            return
        self._set_submitting(True)
        auth = self._auth
        self._runner.submit(self, lambda: auth.login(username.strip(), password), self._on_logged_in, self._on_failed)

    def _on_logged_in(self, session: EmployeeSession) -> None:
        self._set_submitting(False)
        self._on_success(session, self._language)

    def _on_failed(self, error: Exception) -> None:
        self._set_submitting(False)
        self._password.set_value("")  # sai thì xóa mật khẩu, giữ tên đăng nhập
        self.show_error(login_error_message(error))
        self._password.focus()


def _run_demo() -> None:
    """Xem thử màn đăng nhập với mock (không cần MySQL): python -m cyberhub_manager.ui.login_view

    Tài khoản demo: quanly01 / nhanvien01, mật khẩu demo123.
    """
    from ..services.mocks.factory import build_mock_services
    from .theme import SHELL_HEIGHT, SHELL_WIDTH, load_stitch_fonts, setup_theme

    setup_theme()
    root = ctk.CTk()
    load_stitch_fonts()
    root.title("CyberHub Manager")
    root.geometry(f"{SHELL_WIDTH}x{SHELL_HEIGHT}")

    def done(session: EmployeeSession, language: Language) -> None:
        print(f"Login OK: {session.username} ({session.role}), language={language}")  # ASCII: console Windows cp1252
        root.after(300, root.destroy)

    LoginView(root, build_mock_services().auth, on_success=done).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    _run_demo()
