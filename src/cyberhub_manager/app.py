"""Desktop composition root: Login → role-based AppShell → Login."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable

import customtkinter as ctk

from .domain.dtos import EmployeeSession
from .services.contracts import ServiceBundle
from .services.bootstrap import create_service_bundle
from .ui.background import TaskRunner
from .ui.login_view import LoginView
from .ui.theme import (
    LOGIN_BG,
    LOGIN_HEIGHT,
    LOGIN_WIDTH,
    load_stitch_fonts,
    setup_theme,
)

logger = logging.getLogger(__name__)


def install_error_hook(root, language_provider: Callable[[], str] | None = None) -> None:
    """Log unexpected Tk callback failures and display only localized safe text."""
    def report(exc_type, exc, traceback):
        from .ui.components import ToastManager

        logger.error("Unexpected desktop callback failure", exc_info=(exc_type, exc, traceback))
        language = language_provider() if language_provider else "vi"
        message = (
            "An unexpected error occurred. Please try again."
            if language == "en"
            else "Có lỗi xảy ra. Vui lòng thử lại."
        )
        try:
            ToastManager.show(root, message, kind="error")
        except Exception:
            logger.exception("Unable to display the desktop error notification")

    root.report_callback_exception = report


class CyberHubApp(ctk.CTk):
    def __init__(
        self,
        services: ServiceBundle | None = None,
        *,
        mock: bool = False,
        language: str = "vi",
        runner: TaskRunner | None = None,
    ) -> None:
        setup_theme()
        super().__init__()
        load_stitch_fonts()
        self.title("CyberHub Manager — Đăng nhập")
        self.configure(fg_color=LOGIN_BG)
        self.geometry(f"{LOGIN_WIDTH}x{LOGIN_HEIGHT}")
        self.minsize(1100, 650)
        self._session: EmployeeSession | None = None
        self._services = (
            services
            if services is not None
            else create_service_bundle(mock=mock, actor_provider=lambda: self._session)
        )
        self._language = language
        self._runner = runner
        self._mock = mock
        self._content: ctk.CTkFrame | None = None
        install_error_hook(self, lambda: getattr(self._content, "language", self._language))
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._show_login()

    @property
    def session(self) -> EmployeeSession | None:
        return self._session

    @property
    def current_view(self) -> ctk.CTkFrame | None:
        return self._content

    def _dispose_view(self) -> None:
        if self._content is not None:
            self._language = getattr(self._content, "language", self._language)
            if self._content.winfo_exists():
                self._content.destroy()
            self._content = None

    def _show_login(self) -> None:
        self._dispose_view()
        self._session = None
        self.title(
            "CyberHub Manager — Đăng nhập"
            if self._language == "vi"
            else "CyberHub Manager — Sign in"
        )
        self._content = LoginView(
            self,
            self._services.auth,
            on_login_success=self._on_login_success,
            language=self._language,
            runner=self._runner,
            demo=self._mock,
            portal_service=self._services.portal,
        )
        self._content.pack(fill="both", expand=True)

    def _on_login_success(self, session: EmployeeSession) -> None:
        from .ui.app_shell import AppShell
        from .ui.views import default_view_factories

        self._dispose_view()
        from .domain.p1 import CustomerSession
        if isinstance(session, CustomerSession):
            from .ui.p1_views import CustomerPortalView
            self._session = None
            self.title(f"CyberHub — {session.full_name}")
            self._content = CustomerPortalView(self,self._services,session,language=self._language,on_logout=self._show_login,runner=self._runner)
            self._content.pack(fill="both",expand=True)
            return
        self._session = session
        self.title(f"CyberHub Manager — {session.store_name} · {session.full_name}")
        self._content = AppShell(
            self,
            self._services,
            session,
            on_logout=self._show_login,
            on_store_change=self._on_login_success,
            language=self._language,
            view_factories=default_view_factories(),
        )
        self._content.pack(fill="both", expand=True)

    def destroy(self) -> None:
        self._session = None
        self._dispose_view()
        super().destroy()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CyberHub Manager desktop")
    parser.add_argument(
        "--mock", action="store_true", help="Use demo data without MySQL"
    )
    parser.add_argument("--lang", choices=("vi", "en"), default="vi")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    log_level = "INFO"
    if not args.mock:
        from .config import load_settings

        try:
            log_level = load_settings().log_level
        except RuntimeError as error:
            argparse.ArgumentParser(prog="cyberhub-manager").error(
                f"{error}. Configure .env or use --mock for a preview."
            )
    logging.basicConfig(level=log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = CyberHubApp(mock=args.mock, language=args.lang)
    app.mainloop()


if __name__ == "__main__":
    main()
