"""Desktop composition root: Login → role-based AppShell → Login."""

from __future__ import annotations

import argparse
from collections.abc import Callable

import customtkinter as ctk

from .domain.dtos import EmployeeSession
from .services.contracts import ServiceBundle
from .ui.background import TaskRunner
from .ui.login_view import LoginView
from .ui.theme import LOGIN_BG, LOGIN_HEIGHT, LOGIN_WIDTH, load_stitch_fonts, setup_theme


def create_service_bundle(*, mock: bool = False,
                          actor_provider: Callable[[], EmployeeSession | None] | None = None) -> ServiceBundle:
    """Wire real services to the signed-in actor; demo is an explicit CLI choice."""
    if mock:
        from .services.mocks.factory import build_mock_services

        return build_mock_services()

    from .services.auth_service import AuthService
    from .services.customer_service import CustomerService
    from .services.machine_service import MachineService
    from .services.report_service import ReportService
    from .services.session_service import SessionService
    from .services.wallet_service import WalletService

    return ServiceBundle(
        auth=AuthService(),
        customers=CustomerService(actor_provider=actor_provider),
        wallet=WalletService(actor_provider=actor_provider),
        machines=MachineService(actor_provider=actor_provider),
        sessions=SessionService(actor_provider=actor_provider),
        reports=ReportService(actor_provider=actor_provider),
    )


class CyberHubApp(ctk.CTk):
    def __init__(self, services: ServiceBundle | None = None, *, mock: bool = False,
                 language: str = "vi", runner: TaskRunner | None = None) -> None:
        setup_theme()
        super().__init__()
        load_stitch_fonts()
        self.title("CyberHub Manager — Đăng nhập")
        self.configure(fg_color=LOGIN_BG)
        self.geometry(f"{LOGIN_WIDTH}x{LOGIN_HEIGHT}")
        self.minsize(1100, 650)
        self._session: EmployeeSession | None = None
        self._services = services if services is not None else create_service_bundle(
            mock=mock, actor_provider=lambda: self._session)
        self._language = language
        self._runner = runner
        self._mock = mock
        self._content: ctk.CTkFrame | None = None
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
        self.title("CyberHub Manager — Đăng nhập" if self._language == "vi" else "CyberHub Manager — Sign in")
        self._content = LoginView(self, self._services.auth, on_login_success=self._on_login_success,
                                  language=self._language, runner=self._runner, demo=self._mock)
        self._content.pack(fill="both", expand=True)

    def _on_login_success(self, session: EmployeeSession) -> None:
        from .ui.app_shell import AppShell
        from .ui.views import default_view_factories

        self._dispose_view()
        self._session = session
        self.title(f"CyberHub Manager — {session.store_name} · {session.full_name}")
        self._content = AppShell(self, self._services, session, on_logout=self._show_login,
                                 language=self._language, view_factories=default_view_factories())
        self._content.pack(fill="both", expand=True)

    def destroy(self) -> None:
        self._session = None
        self._dispose_view()
        super().destroy()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="CyberHub Manager desktop")
    parser.add_argument("--mock", action="store_true", help="Use demo data without MySQL")
    parser.add_argument("--lang", choices=("vi", "en"), default="vi")
    args = parser.parse_args(argv)
    if not args.mock:
        from .config import load_settings

        try:
            load_settings()
        except RuntimeError as error:
            parser.error(f"{error}. Configure .env or use --mock for a preview.")
    app = CyberHubApp(mock=args.mock, language=args.lang)
    app.mainloop()


if __name__ == "__main__":
    main()
