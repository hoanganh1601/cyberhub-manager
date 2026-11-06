"""Application composition root and entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

import customtkinter as ctk

from .config import load_settings
from .domain.dtos import EmployeeSession
from .services.contracts import ServiceBundle
from .services.mocks.factory import build_mock_services
from .ui.app_shell import DEFAULT_VIEW_FACTORIES, AppShell
from .ui.login_view import LoginView
from .ui.theme import STITCH_BG_CANVAS, load_stitch_fonts, setup_theme

logger = logging.getLogger(__name__)


def create_service_bundle(force_mock: bool = False) -> ServiceBundle:
    """Tạo ServiceBundle cho ứng dụng.

    Thử kết nối MySQL theo cấu hình môi trường; nếu không có cấu hình,
    kết nối thất bại hoặc force_mock=True thì tự động fallback về
    mock services với đầy đủ dữ liệu mẫu.
    """
    if force_mock:
        logger.info("Chế độ dữ liệu mẫu được bật (Mock Services).")
        return build_mock_services()

    use_mock = False
    try:
        settings = load_settings()
        logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
        from .database.connection import get_connection

        with get_connection() as conn:
            if not conn.is_connected():
                use_mock = True
    except Exception as exc:
        logger.info("Chế độ dữ liệu mẫu (Mock): %s", exc)
        use_mock = True

    if use_mock:
        logger.info(
            "Đang sử dụng Mock Services (Dữ liệu demo có sẵn).\n"
            "Tài khoản quản lý: quanly01 / demo123\n"
            "Tài khoản nhân viên: nhanvien01 / demo123"
        )
        return build_mock_services()

    try:
        from .database.transaction import transaction
        from .repositories.account_repository import AccountRepository
        from .repositories.auth_repository import AuthRepository
        from .repositories.customer_repository import CustomerRepository
        from .repositories.invoice_repository import InvoiceRepository
        from .repositories.machine_repository import MachineRepository
        from .repositories.session_repository import SessionRepository
        from .services.auth_service import AuthService
        from .services.customer_service import CustomerService
        from .services.machine_service import MachineService
        from .services.report_service import ReportService
        from .services.session_service import SessionService
        from .services.wallet_service import WalletService

        auth_repo = AuthRepository()
        account_repo = AccountRepository()
        customer_repo = CustomerRepository()
        invoice_repo = InvoiceRepository()
        machine_repo = MachineRepository()
        session_repo = SessionRepository()

        return ServiceBundle(
            auth=AuthService(auth_repo, transaction),
            customers=CustomerService(customer_repo, account_repo, transaction),
            wallet=WalletService(account_repo, transaction),
            machines=MachineService(machine_repo, session_repo, transaction),
            sessions=SessionService(session_repo, machine_repo, account_repo, invoice_repo, transaction),
            reports=ReportService(invoice_repo, session_repo, transaction),
        )
    except Exception as exc:
        logger.warning("Không thể khởi tạo real services: %s. Chuyển sang mock services.", exc)
        return build_mock_services()


class CyberHubApp(ctk.CTk):
    """Cửa sổ chính của ứng dụng CyberHub Manager."""

    def __init__(
        self,
        services: ServiceBundle | None = None,
        *,
        auto_login_username: str | None = None,
        auto_login_password: str = "demo123",
        language: str = "vi",
    ) -> None:
        super().__init__()
        self.title("CyberHub Manager — Cyber Defense Operations")
        self.geometry("1280x720")
        self.minsize(1024, 640)
        self.configure(fg_color=STITCH_BG_CANVAS)

        self._services = services or create_service_bundle()
        self._current_content: ctk.CTkFrame | None = None
        self._session: EmployeeSession | None = None
        self._language = language

        # Tự động đăng nhập nếu có username (phục vụ test nhanh hoặc dev)
        if auto_login_username:
            try:
                session = self._services.auth.login(auto_login_username, auto_login_password)
                self._session = session
                self._show_shell()
                return
            except Exception as exc:
                logger.warning("Auto-login thất bại cho %r: %s", auto_login_username, exc)

        self._show_login()

    def _show_login(self) -> None:
        if self._current_content is not None:
            self._current_content.destroy()
            self._current_content = None

        self._session = None
        self.title("CyberHub Manager — Đăng nhập")

        login_view = LoginView(
            self,
            auth_service=self._services.auth,
            on_login_success=self._on_login_success,
            language=self._language,
        )
        login_view.pack(fill="both", expand=True)
        self._current_content = login_view

    def _on_login_success(self, session: EmployeeSession) -> None:
        self._session = session
        self._show_shell()

    def _show_shell(self) -> None:
        if self._current_content is not None:
            self._current_content.destroy()
            self._current_content = None

        assert self._session is not None
        store_code = self._session.store_code or "STORE"
        full_name = self._session.full_name or self._session.username
        role_str = self._session.role.value.upper()
        self.title(f"CyberHub Manager — [{store_code}] {full_name} ({role_str})")

        shell = AppShell(
            self,
            services=self._services,
            session=self._session,
            on_logout=self._show_login,
            view_factories=DEFAULT_VIEW_FACTORIES,
            language=self._language,
        )
        shell.pack(fill="both", expand=True)
        self._current_content = shell


def main(argv: list[str] | None = None) -> None:
    """Entry point chính khởi chạy ứng dụng CyberHub Manager."""
    parser = argparse.ArgumentParser(description="CyberHub Manager Desktop Application")
    parser.add_argument("--mock", action="store_true", help="Bắt buộc sử dụng mock services")
    parser.add_argument("--user", type=str, default=None, help="Tự động đăng nhập với username chỉ định (ví dụ: quanly01, nhanvien01)")
    parser.add_argument("--password", type=str, default="demo123", help="Mật khẩu cho tự động đăng nhập (mặc định: demo123)")
    parser.add_argument("--lang", type=str, default="vi", choices=["vi", "en"], help="Ngôn ngữ khởi động (vi hoặc en)")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    setup_theme()
    load_stitch_fonts()

    services = create_service_bundle(force_mock=args.mock)
    app = CyberHubApp(
        services=services,
        auto_login_username=args.user,
        auto_login_password=args.password,
        language=args.lang,
    )
    app.mainloop()


if __name__ == "__main__":
    main()
