"""Unit tests cho HA-11 — composition root (app.py): nối service, Login <-> AppShell, error hook, CLI."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import patch

import pytest

from cyberhub_manager import app as app_module
from cyberhub_manager.app import CyberHubApp, SessionHolder, build_real_services, install_error_hook, main, parse_args
from cyberhub_manager.services.contracts import ServiceBundle
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.ui.app_shell import AppShell
from cyberhub_manager.ui.background import ImmediateTaskRunner
from cyberhub_manager.ui.login_view import LoginView
from cyberhub_manager.ui.messages import MSG_OPERATION_FAILED
from cyberhub_manager.ui.navigation import NavKey

RUNNER = ImmediateTaskRunner()
UI_MODULES = ("login_view", "dashboard_view", "customers_view", "invoices_view", "reports_view", "machine_management_view")


@pytest.fixture(autouse=True)
def _restore_error_hook(tk_root):
    """install_error_hook gắn vào root dùng chung cả phiên test: gỡ ra sau mỗi test."""
    yield
    tk_root.__dict__.pop("report_callback_exception", None)


@pytest.fixture
def sync_ui():
    """Mọi view chạy service đồng bộ; Toast/Confirm chỉ được ghi lại."""
    with ExitStack() as stack:
        for module in UI_MODULES:
            stack.enter_context(patch(f"cyberhub_manager.ui.{module}.default_runner", return_value=RUNNER))
        toast = stack.enter_context(patch("cyberhub_manager.ui.components.toast.ToastManager.show"))
        stack.enter_context(patch("cyberhub_manager.ui.app_shell.ConfirmDialog.ask", return_value=True))
        yield toast


def _login(app: CyberHubApp, username: str = "quanly01", password: str = DEMO_PASSWORD) -> None:
    login = app.screen
    assert isinstance(login, LoginView)
    login.username_field.set_value(username)
    login.password_field.set_value(password)
    login.submit()


# ----------------------------------------------------------------------
# Nối service thật
# ----------------------------------------------------------------------
def test_session_holder() -> None:
    holder = SessionHolder()
    assert holder.get() is None
    session = build_mock_services().auth.login("quanly01", DEMO_PASSWORD)
    holder.set(session)
    assert holder.get() is session
    holder.clear()
    assert holder.get() is None


def test_real_services_share_one_actor_provider_without_touching_mysql() -> None:
    holder = SessionHolder()
    with patch("cyberhub_manager.database.connection.init_pool") as init_pool:
        bundle = build_real_services(holder)
    init_pool.assert_not_called()  # pool chỉ tạo khi có thao tác DB đầu tiên
    assert isinstance(bundle, ServiceBundle)
    for name in ("customers", "wallet", "machines", "sessions", "reports"):
        provider = getattr(bundle, name)._actor_provider
        assert provider == holder.get, name  # cùng một nguồn phiên đăng nhập
    session = build_mock_services().auth.login("nhanvien01", DEMO_PASSWORD)
    holder.set(session)
    assert bundle.sessions._actor_provider() is session


# ----------------------------------------------------------------------
# Luồng màn hình
# ----------------------------------------------------------------------
def test_login_then_logout_flow(tk_root, sync_ui) -> None:
    holder = SessionHolder()
    app = CyberHubApp(tk_root, build_mock_services(), holder, language="en")
    assert isinstance(app.screen, LoginView) and app.session is None
    _login(app)
    shell = app.screen
    assert isinstance(shell, AppShell)
    assert holder.get().username == "quanly01"
    assert shell.language == "en"  # ngôn ngữ chọn ở màn đăng nhập được giữ
    shell.set_language("vi")
    shell.logout()
    assert isinstance(app.screen, LoginView)
    assert holder.get() is None  # đăng xuất xóa phiên => service thật từ chối mọi thao tác
    assert app.screen.language == "vi"
    assert not shell.winfo_exists()
    app.screen.destroy()


def test_failed_login_stays_on_login(tk_root, sync_ui) -> None:
    holder = SessionHolder()
    app = CyberHubApp(tk_root, build_mock_services(), holder)
    _login(app, password="sai")
    assert isinstance(app.screen, LoginView)
    assert holder.get() is None
    assert app.screen.error_text == "Invalid username or password."
    app.screen.destroy()


def test_staff_login_opens_shell_without_machine_menu(tk_root, sync_ui) -> None:
    app = CyberHubApp(tk_root, build_mock_services(), SessionHolder())
    _login(app, "nhanvien01")
    assert NavKey.MACHINES not in app.screen.nav_keys
    app.screen.destroy()


# ----------------------------------------------------------------------
# Error hook + CLI
# ----------------------------------------------------------------------
def test_error_hook_logs_and_shows_generic_toast(tk_root, sync_ui, caplog: pytest.LogCaptureFixture) -> None:
    install_error_hook(tk_root)
    try:
        raise KeyError("secret_column")
    except KeyError as error:
        tk_root.report_callback_exception(type(error), error, error.__traceback__)
    assert sync_ui.call_args.args[1] == MSG_OPERATION_FAILED
    assert "secret_column" in caplog.text  # chi tiết chỉ nằm trong log


def test_parse_args() -> None:
    assert parse_args([]).mock is False
    assert parse_args(["--mock", "--lang", "en"]).lang == "en"


def test_main_reports_missing_configuration(monkeypatch, capsys) -> None:
    def missing() -> None:
        raise RuntimeError("Missing required environment variable: MYSQL_DATABASE")

    monkeypatch.setattr(app_module, "load_settings", missing)
    with patch.object(app_module.ctk, "CTk") as ctk_root:
        assert main([]) == app_module.EXIT_CONFIG_ERROR
    ctk_root.assert_not_called()  # không mở cửa sổ khi chưa cấu hình
    assert "Copy .env.example to .env" in capsys.readouterr().err
