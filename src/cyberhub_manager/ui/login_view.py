"""Native desktop login adapted from the supplied 1280×720 Stitch export."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk
from typing import Any

import customtkinter as ctk

from ..domain.dtos import EmployeeSession
from ..domain.exceptions import AuthenticationError
from ..services.contracts import AuthServiceProtocol
from . import theme as t
from .background import TaskRunner, default_runner
from .i18n import Language, normalize_language
from .login_art import BrandPanel, icon_image


_COPY = {
    "portal": ("CỔNG VẬN HÀNH NHÂN VIÊN", "STAFF OPERATIONS PORTAL"),
    "title": ("Đăng nhập", "Sign in"),
    "subtitle": ("Đăng nhập để tiếp tục quản lý cửa hàng", "Sign in to manage your cybercafe"),
    "username": ("TÊN ĐĂNG NHẬP", "USERNAME"),
    "password": ("MẬT KHẨU", "PASSWORD"),
    "username_placeholder": ("Nhập tên đăng nhập", "Enter your username"),
    "password_placeholder": ("Nhập mật khẩu", "Enter your password"),
    "username_required": ("Vui lòng nhập tên đăng nhập.", "Please enter your username."),
    "password_required": ("Vui lòng nhập mật khẩu.", "Please enter your password."),
    "invalid": ("Tên đăng nhập hoặc mật khẩu không đúng.", "Incorrect username or password."),
    "retry_credentials": ("Vui lòng kiểm tra lại thông tin đăng nhập.", "Please check your sign-in details."),
    "unavailable": ("Không thể kết nối. Vui lòng thử lại.", "Unable to connect. Please try again."),
    "busy": ("Đang đăng nhập…", "Signing in…"),
    "hint_before": ("Nhấn", "Press"),
    "hint_after": ("để đăng nhập", "to sign in"),
    "ready": ("Hệ thống sẵn sàng", "System ready"),
    "demo": ("Dữ liệu mẫu", "Demo mode"),
}


class LoginField(ctk.CTkFrame):
    """Icon + native input, with focus border and a reserved inline-error line."""

    def __init__(self, master: Any, *, password: bool = False) -> None:
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self._error = False
        self._focused = False
        self.revealed = False
        self.label = ctk.CTkLabel(self, text="", font=t.LOGIN_FONT_LABEL,
                                  text_color=t.LOGIN_TEXT, anchor="w", height=16)
        self.label.pack(fill="x", pady=(0, 8))
        self.box = ctk.CTkFrame(self, height=44, corner_radius=8, border_width=1,
                               border_color=t.LOGIN_BORDER, fg_color=t.LOGIN_SURFACE)
        self.box.pack(fill="x")
        self.box.pack_propagate(False)
        ctk.CTkLabel(self.box, text="", width=18, height=18,
                     image=icon_image("lock" if password else "user", t.LOGIN_MUTED)).pack(
                         side="left", padx=(14, 10))
        self.toggle: ctk.CTkButton | None = None
        if password:
            self.toggle = ctk.CTkButton(self.box, text="", width=32, height=30,
                                        corner_radius=5, fg_color=t.LOGIN_SURFACE,
                                        hover_color=t.LOGIN_BORDER,
                                        image=icon_image("eye", t.LOGIN_MUTED), command=self.toggle_password)
            self.toggle.pack(side="right", padx=(0, 7))
            self.toggle._canvas.configure(takefocus=1)
            self.toggle._canvas.bind("<space>", lambda _e: self.toggle_password())
            self.toggle._canvas.bind("<Return>", lambda _e: self.toggle_password())
        self.entry = ctk.CTkEntry(self.box, height=40, corner_radius=0, border_width=0,
                                 fg_color=t.LOGIN_SURFACE, text_color=t.LOGIN_TEXT,
                                 placeholder_text="", placeholder_text_color=t.LOGIN_DIM,
                                 font=t.LOGIN_FONT_BODY, show="•" if password else "")
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=2)
        self.entry.bind("<FocusIn>", lambda _e: self._focus_border(True), add="+")
        self.entry.bind("<FocusOut>", lambda _e: self._focus_border(False), add="+")
        self.error_label = ctk.CTkLabel(self, text="", height=20, anchor="w",
                                        font=t.LOGIN_FONT_SMALL, text_color=t.LOGIN_ERROR)
        self.error_label.pack(fill="x", pady=(3, 0))

    def _focus_border(self, focused: bool) -> None:
        self._focused = focused
        self._paint_border()

    def _paint_border(self) -> None:
        color = t.LOGIN_ERROR if self._error else t.LOGIN_PRIMARY if self._focused else t.LOGIN_BORDER
        self.box.configure(border_color=color)

    def set_error(self, message: str = "") -> None:
        self._error = bool(message)
        self.error_label.configure(text=message)
        self._paint_border()

    def toggle_password(self) -> None:
        if self.toggle is None or self.entry.cget("state") == "disabled":
            return
        self.revealed = not self.revealed
        self.entry.configure(show="" if self.revealed else "•")
        self.toggle.configure(image=icon_image("eye-off" if self.revealed else "eye", t.LOGIN_MUTED))

    def set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.entry.configure(state=state)
        if self.toggle:
            self.toggle.configure(state=state)

    def set_placeholder(self, text: str) -> None:
        self.entry.configure(placeholder_text=text)
        # CTk 6 activates placeholders on configure even when the entry has focus.
        if self._focused:
            self.entry._deactivate_placeholder()


class LoginView(ctk.CTkFrame):
    """Service-injected login. All authentication runs outside the Tk event loop."""

    def __init__(self, master: Any, auth_service: AuthServiceProtocol, *,
                 on_login_success: Callable[[EmployeeSession], None], language: str = "vi",
                 runner: TaskRunner | None = None, demo: bool = False) -> None:
        super().__init__(master, fg_color=t.LOGIN_BG, corner_radius=0)
        self._auth_service = auth_service
        self._on_login_success = on_login_success
        self._runner = runner or default_runner()
        self._language: Language = normalize_language(language)
        self._busy = False
        self._closed = False
        self._demo = demo
        self._spinner_id: str | None = None
        self._focus_id: str | None = None
        self._spinner_angle = 0
        self._feedback_key = ""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=55, uniform="login")
        self.grid_columnconfigure(1, weight=45, uniform="login")
        self.brand = BrandPanel(self, self._language)
        self.brand.grid(row=0, column=0, sticky="nsew")
        self.panel = ctk.CTkFrame(self, fg_color=t.LOGIN_PANEL, corner_radius=0, border_width=0)
        self.panel.grid(row=0, column=1, sticky="nsew")
        tk.Frame(self.panel, bg=t.LOGIN_BORDER, bd=0).place(x=0, y=0, width=1, relheight=1)
        self._build_topbar()
        self._build_form()
        self._build_footer()
        self._bind_focus_order()
        self.set_language(self._language)
        self._focus_id = self.after(120, self._focus_username)

    @property
    def language(self) -> Language:
        return self._language

    def _tr(self, key: str) -> str:
        return _COPY[key][0 if self.language == "vi" else 1]

    def _build_topbar(self) -> None:
        top = ctk.CTkFrame(self.panel, fg_color="transparent", height=32)
        top.pack(fill="x", padx=48, pady=(46, 0))
        self.portal = ctk.CTkLabel(top, text="", font=t.LOGIN_FONT_PORTAL, text_color=t.LOGIN_MUTED)
        self.portal.pack(side="left")
        switch = ctk.CTkFrame(top, fg_color=t.LOGIN_SURFACE, corner_radius=5,
                              border_width=1, border_color=t.LOGIN_BORDER)
        switch.pack(side="right")
        self.lang_buttons: dict[str, ctk.CTkButton] = {}
        for lang in ("vi", "en"):
            button = ctk.CTkButton(switch, text=lang.upper(), width=32, height=24,
                                   corner_radius=3, font=t.LOGIN_FONT_LABEL,
                                   command=lambda code=lang: self.set_language(code))
            button.pack(side="left", padx=3, pady=3)
            self.lang_buttons[lang] = button

    def _build_form(self) -> None:
        self.form = ctk.CTkFrame(self.panel, width=384, height=418, fg_color="transparent")
        self.form.place(relx=.5, rely=.54, anchor="center")
        self.form.pack_propagate(False)
        self.title_label = ctk.CTkLabel(self.form, text="", font=t.LOGIN_FONT_TITLE,
                                        text_color=t.LOGIN_WHITE, anchor="w", height=40)
        self.title_label.pack(fill="x")
        self.subtitle = ctk.CTkLabel(self.form, text="", font=t.LOGIN_FONT_BODY,
                                     text_color=t.LOGIN_MUTED, height=22, anchor="w")
        self.subtitle.pack(fill="x", pady=(4, 28))
        self.username = LoginField(self.form)
        self.username.pack(fill="x", pady=(0, 4))
        self.password = LoginField(self.form, password=True)
        self.password.pack(fill="x", pady=(0, 6))
        glow = ctk.CTkFrame(self.form, fg_color=t.LOGIN_GLOW, corner_radius=11)
        glow.pack(fill="x")
        self.submit_button = ctk.CTkButton(glow, text="", height=44, corner_radius=8,
                                           font=t.LOGIN_FONT_BUTTON, fg_color=t.LOGIN_PRIMARY,
                                           hover_color=t.LOGIN_PRIMARY_HOVER,
                                           text_color=t.LOGIN_BG, text_color_disabled=t.LOGIN_BG,
                                           image=icon_image("arrow", t.LOGIN_BG, 16), compound="right",
                                           command=self.submit)
        self.submit_button.pack(fill="x", padx=2, pady=2)
        self.submit_button._canvas.configure(takefocus=1)
        self.submit_button._canvas.bind("<Return>", self.submit)
        self.submit_button._canvas.bind("<space>", self.submit)
        hint = ctk.CTkFrame(self.form, fg_color="transparent")
        hint.pack(pady=(14, 0))
        self.hint_before = ctk.CTkLabel(hint, text="", height=20,
                                        font=t.LOGIN_FONT_HINT, text_color=t.LOGIN_DIM)
        self.hint_before.pack(side="left", padx=(0, 6))
        ctk.CTkLabel(hint, text="Enter ↵", height=20, corner_radius=4,
                     fg_color=t.LOGIN_SURFACE, text_color=t.LOGIN_TEXT,
                     font=t.LOGIN_FONT_KICKER, padx=7).pack(side="left")
        self.hint_after = ctk.CTkLabel(hint, text="", height=20,
                                       font=t.LOGIN_FONT_HINT, text_color=t.LOGIN_DIM)
        self.hint_after.pack(side="left", padx=(6, 0))
        self.feedback = ctk.CTkFrame(self.form, fg_color=t.LOGIN_ERROR_BG, border_width=1,
                                     border_color=t.LOGIN_ERROR_BORDER, corner_radius=6)
        ctk.CTkLabel(self.feedback, text="", image=icon_image("alert", t.LOGIN_ERROR, 16),
                     width=18).pack(side="left", padx=(10, 8), pady=8)
        self.feedback_text = ctk.CTkLabel(self.feedback, text="", text_color=t.LOGIN_ERROR,
                                          font=t.LOGIN_FONT_SMALL, anchor="w", justify="left", wraplength=330)
        self.feedback_text.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=8)
        for field in (self.username, self.password):
            field.entry.bind("<Return>", self.submit, add="+")
            field.entry.bind("<KeyRelease>", lambda event, f=field: self._on_typing(event, f), add="+")

    def _build_footer(self) -> None:
        foot = ctk.CTkFrame(self.panel, fg_color="transparent", height=36)
        foot.pack(side="bottom", fill="x", padx=48, pady=(0, 40))
        tk.Frame(foot, height=1, bg=t.LOGIN_BORDER, bd=0).pack(fill="x", pady=(0, 14))
        status = ctk.CTkFrame(foot, fg_color="transparent")
        status.pack(fill="x")
        ctk.CTkLabel(status, text="●", text_color=t.LOGIN_SUCCESS, width=12,
                     height=20, font=("Arial", 12)).pack(side="left", padx=(0, 6))
        self.status_label = ctk.CTkLabel(status, text="", height=20,
                                         text_color=t.LOGIN_TEXT, font=t.LOGIN_FONT_HINT)
        self.status_label.pack(side="left")
        self.demo_label = ctk.CTkLabel(status, text="", height=20,
                                       text_color=t.LOGIN_DIM, font=t.LOGIN_FONT_KICKER)
        self.demo_label.pack(side="right")

    def _focus_username(self) -> None:
        self._focus_id = None
        if not self._closed:
            self.username.entry.focus_set()

    def _bind_focus_order(self) -> None:
        """Explicit order: username → password → eye → submit → VI → EN."""
        assert self.password.toggle is not None
        targets = [self.username.entry, self.password.entry, self.password.toggle._canvas,
                   self.submit_button._canvas, self.lang_buttons["vi"]._canvas,
                   self.lang_buttons["en"]._canvas]
        for index, widget in enumerate(targets):
            def move(_event: Any, target: Any = targets[(index + 1) % len(targets)]) -> str:
                target.focus_set()
                return "break"

            def back(_event: Any, target: Any = targets[(index - 1) % len(targets)]) -> str:
                target.focus_set()
                return "break"

            widget.bind("<Tab>", move, add="+")
            widget.bind("<Shift-Tab>", back, add="+")
        for button in (self.password.toggle, self.submit_button, *self.lang_buttons.values()):
            button._canvas.configure(takefocus=1)
            button._canvas.bind("<FocusIn>", lambda _e, b=button: b.configure(
                border_width=1, border_color=t.LOGIN_PRIMARY), add="+")
            button._canvas.bind("<FocusOut>", lambda _e, b=button: b.configure(border_width=0), add="+")
        for lang, button in self.lang_buttons.items():
            button._canvas.bind("<Return>", lambda _e, code=lang: self.set_language(code))
            button._canvas.bind("<space>", lambda _e, code=lang: self.set_language(code))

    def set_language(self, language: str) -> None:
        if self._busy:
            return
        self._language = normalize_language(language)
        self.portal.configure(text=self._tr("portal"))
        self.title_label.configure(text=self._tr("title"))
        self.subtitle.configure(text=self._tr("subtitle"))
        for name, field in (("username", self.username), ("password", self.password)):
            field.label.configure(text=self._tr(name))
            field.set_placeholder(self._tr(f"{name}_placeholder"))
            if field._error:
                field.set_error(self._tr("retry_credentials") if self._feedback_key == "invalid" else self._tr(f"{name}_required"))
        self.submit_button.configure(text=self._tr("title"))
        self.hint_before.configure(text=self._tr("hint_before"))
        self.hint_after.configure(text=self._tr("hint_after"))
        self.status_label.configure(text=self._tr("ready"))
        self.demo_label.configure(text=self._tr("demo") if self._demo else "")
        for lang, button in self.lang_buttons.items():
            active = lang == self.language
            button.configure(fg_color=t.LOGIN_PRIMARY if active else t.LOGIN_SURFACE,
                             hover_color=t.LOGIN_PRIMARY_HOVER if active else t.LOGIN_BORDER,
                             text_color=t.LOGIN_BG if active else t.LOGIN_MUTED)
        if self._feedback_key:
            self.feedback_text.configure(text=self._tr(self._feedback_key))
        self.brand.set_language(self.language)

    def _on_typing(self, event: Any, field: LoginField) -> None:
        if self._busy or event.keysym in ("Return", "Tab", "Shift_L", "Shift_R"):
            return
        field.set_error()
        self.feedback.pack_forget()
        self._feedback_key = ""

    def submit(self, _event: Any = None) -> str:
        if self._busy or self._closed:
            return "break"
        username, password = self.username.entry.get().strip(), self.password.entry.get()
        self.feedback.pack_forget()
        self._feedback_key = ""
        self.username.set_error("" if username else self._tr("username_required"))
        self.password.set_error("" if password else self._tr("password_required"))
        if not username or not password:
            (self.username if not username else self.password).entry.focus_set()
            return "break"
        self._set_busy(True)
        self._runner.submit(self, lambda: self._auth_service.login(username, password),
                            self._login_succeeded, self._login_failed)
        return "break"

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.username.set_enabled(not busy)
        self.password.set_enabled(not busy)
        self.submit_button.configure(state="disabled" if busy else "normal",
                                     text=self._tr("busy" if busy else "title"))
        for button in self.lang_buttons.values():
            button.configure(state="disabled" if busy else "normal")
        if self._spinner_id:
            self.after_cancel(self._spinner_id)
            self._spinner_id = None
        if busy:
            self._spin()
        else:
            self.submit_button.configure(image=icon_image("arrow", t.LOGIN_BG, 16))

    def _spin(self) -> None:
        self._spinner_angle = (self._spinner_angle + 35) % 360
        self.submit_button.configure(image=icon_image("spinner", t.LOGIN_BG, 16, angle=self._spinner_angle))
        self._spinner_id = self.after(70, self._spin)

    def _login_succeeded(self, session: EmployeeSession) -> None:
        if self._closed:
            return
        self.password.entry.configure(state="normal")
        self.password.entry.delete(0, "end")
        # Keep the double-submit guard active until the app replaces this view.
        self._on_login_success(session)

    def _login_failed(self, error: Exception) -> None:
        if self._closed:
            return
        self._set_busy(False)
        self._feedback_key = "invalid" if isinstance(error, AuthenticationError) else "unavailable"
        if isinstance(error, AuthenticationError):
            self.password.entry.delete(0, "end")
            if self.password.revealed:
                self.password.toggle_password()
            self.password.set_error(self._tr("retry_credentials"))
        self.feedback_text.configure(text=self._tr(self._feedback_key))
        self.feedback.pack(fill="x", pady=(14, 0))
        self.password.entry.focus_set()

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        for callback_id in (self._spinner_id, self._focus_id):
            if callback_id:
                self.after_cancel(callback_id)
        self._spinner_id = self._focus_id = None

    def destroy(self) -> None:
        self.shutdown()
        super().destroy()


if __name__ == "__main__":
    from ..app import main

    main(["--mock"])

