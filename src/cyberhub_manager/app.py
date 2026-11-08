"""HA-11 — Composition root và entry point của CyberHub Manager.

    cyberhub-manager            # app thật: MySQL theo .env, đăng nhập bằng tài khoản đã seed
    cyberhub-manager --mock     # demo không cần MySQL (quanly01 / nhanvien01, mật khẩu demo123)

- Tạo ServiceBundle một lần. Service thật nhận tham số theo keyword và cùng một `actor_provider`
  đọc SessionHolder (phiên đang đăng nhập) — không tự đoán thứ tự tham số.
- Luồng màn hình: LoginView -> AppShell -> (Đăng xuất) -> LoginView, giữ ngôn ngữ đã chọn.
- Lỗi bất ngờ trong callback Tk: ghi log đầy đủ, người dùng chỉ thấy Toast chung (không traceback).
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from typing import Any

import customtkinter as ctk

from cyberhub_manager.config import load_settings
from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.services.auth_service import AuthService
from cyberhub_manager.services.contracts import ServiceBundle
from cyberhub_manager.services.customer_service import CustomerService
from cyberhub_manager.services.machine_service import MachineService
from cyberhub_manager.services.report_service import ReportService
from cyberhub_manager.services.session_service import SessionService
from cyberhub_manager.services.wallet_service import WalletService
from cyberhub_manager.ui.app_shell import AppShell
from cyberhub_manager.ui.components import ToastManager
from cyberhub_manager.ui.i18n import Language, normalize_language
from cyberhub_manager.ui.login_view import LoginView
from cyberhub_manager.ui.messages import MSG_OPERATION_FAILED
from cyberhub_manager.ui.theme import SHELL_HEIGHT, SHELL_WIDTH, load_stitch_fonts, setup_theme
from cyberhub_manager.ui.views import default_view_factories

logger = logging.getLogger(__name__)

APP_TITLE = "CyberHub Manager"
EXIT_CONFIG_ERROR = 2


class SessionHolder:
    """Phiên nhân viên đang đăng nhập; mọi service thật đọc qua `get` (actor_provider)."""

    def __init__(self) -> None:
        self._session: EmployeeSession | None = None

    def get(self) -> EmployeeSession | None:
        return self._session

    def set(self, session: EmployeeSession) -> None:
        self._session = session

    def clear(self) -> None:
        self._session = None


def build_real_services(holder: SessionHolder) -> ServiceBundle:
    """Sáu service thật dùng chung một actor_provider. Chưa mở kết nối MySQL ở đây (pool tạo khi cần)."""
    actor = holder.get
    return ServiceBundle(
        auth=AuthService(),
        customers=CustomerService(actor_provider=actor),
        wallet=WalletService(actor_provider=actor),
        machines=MachineService(actor_provider=actor),
        sessions=SessionService(actor_provider=actor),
        reports=ReportService(actor_provider=actor),
    )


def build_mock_bundle() -> ServiceBundle:
    from cyberhub_manager.services.mocks.factory import build_mock_services  # chỉ dùng khi --mock

    return build_mock_services()


class CyberHubApp:
    """Đổi qua lại giữa LoginView và AppShell trên cùng một cửa sổ."""

    def __init__(self, root: Any, services: ServiceBundle, holder: SessionHolder, *, language: str | None = None) -> None:
        self._root = root
        self._services = services
        self._holder = holder
        self._language: Language = normalize_language(language)
        self._screen: Any = None
        install_error_hook(root)
        self.show_login()

    @property
    def screen(self) -> Any:
        """LoginView hoặc AppShell đang hiển thị."""
        return self._screen

    @property
    def session(self) -> EmployeeSession | None:
        return self._holder.get()

    def _swap(self, screen: Any) -> None:
        old, self._screen = self._screen, screen
        if old is not None and old.winfo_exists():
            old.destroy()
        screen.pack(fill="both", expand=True)

    def show_login(self) -> None:
        self._holder.clear()
        self._swap(LoginView(self._root, self._services.auth, on_success=self._on_login, language=self._language))

    def _on_login(self, session: EmployeeSession, language: Language) -> None:
        self._holder.set(session)
        self._language = language
        logger.info("Đăng nhập: %s (%s) tại %s", session.username, session.role, session.store_code)
        shell = AppShell(
            self._root,
            self._services,
            session,
            on_logout=self._on_logout,
            view_factories=default_view_factories(),
            language=language,
        )
        self._swap(shell)

    def _on_logout(self) -> None:
        # AppShell.logout() đã tự destroy; giữ ngôn ngữ đang dùng cho màn đăng nhập.
        shell = self._screen
        if isinstance(shell, AppShell):
            self._language = shell.language
        self._screen = None
        logger.info("Đăng xuất")
        self.show_login()


def install_error_hook(root: Any) -> None:
    """Lỗi chưa bắt trong callback Tk: log đầy đủ, chỉ hiện Toast chung (AC-22)."""

    def report(exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
        logger.error("Lỗi không mong đợi trong giao diện", exc_info=(exc_type, exc, tb))
        try:
            ToastManager.show(root, MSG_OPERATION_FAILED, kind="error")
        except Exception:  # noqa: BLE001 — không để chính bộ báo lỗi làm crash app
            logger.exception("Không hiển thị được thông báo lỗi")

    root.report_callback_exception = report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="cyberhub-manager", description=APP_TITLE)
    parser.add_argument("--mock", action="store_true", help="chạy với dữ liệu mock, không cần MySQL")
    parser.add_argument("--lang", choices=("vi", "en"), default="vi", help="ngôn ngữ ban đầu")
    return parser.parse_args(argv)


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    holder = SessionHolder()
    if args.mock:
        configure_logging()
        services = build_mock_bundle()
    else:
        try:
            settings = load_settings()
        except RuntimeError as error:
            # Máy chưa có .env: báo rõ cách sửa thay vì để màn đăng nhập hiện lỗi chung chung.
            print(f"Configuration error: {error}. Copy .env.example to .env and fill in MySQL settings.", file=sys.stderr)
            return EXIT_CONFIG_ERROR
        configure_logging(settings.log_level)
        services = build_real_services(holder)

    setup_theme()
    root = ctk.CTk()
    load_stitch_fonts()  # sau khi có root, trước khi tạo widget
    root.title(APP_TITLE + (" (mock)" if args.mock else ""))
    root.geometry(f"{SHELL_WIDTH}x{SHELL_HEIGHT}")
    root.minsize(SHELL_WIDTH, SHELL_HEIGHT)
    CyberHubApp(root, services, holder, language=args.lang)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
