"""Unit tests cho HA-11 — màn đăng nhập (validation, sai mật khẩu, chống double-submit, lỗi dịch vụ, VI/EN)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cyberhub_manager.domain.enums import Role
from cyberhub_manager.domain.exceptions import AuthenticationError, ServiceUnavailableError
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.ui.background import ImmediateTaskRunner
from cyberhub_manager.ui.login_view import REQUIRED, LoginView, login_error_message, validate_login
from cyberhub_manager.ui.messages import MSG_OPERATION_FAILED

RUNNER = ImmediateTaskRunner()
INVALID = "Invalid username or password."


class DeferredRunner:
    """Giữ lại công việc để test trạng thái "đang đăng nhập" trước khi service trả lời."""

    def __init__(self) -> None:
        self.jobs: list[tuple] = []

    def submit(self, widget, func, on_success, on_error) -> None:
        self.jobs.append((func, on_success, on_error))

    def finish(self) -> None:
        func, on_success, on_error = self.jobs.pop(0)
        try:
            result = func()
        except Exception as error:  # noqa: BLE001
            on_error(error)
        else:
            on_success(result)


def _view(tk_root, auth=None, runner=RUNNER, language: str = "vi"):
    logged_in: list = []
    view = LoginView(
        tk_root,
        auth or build_mock_services().auth,
        on_success=lambda session, lang: logged_in.append((session, lang)),
        runner=runner,
        language=language,
    )
    return view, logged_in


def _fill(view: LoginView, username: str, password: str) -> None:
    view.username_field.set_value(username)
    view.password_field.set_value(password)


# ----------------------------------------------------------------------
# Hàm thuần
# ----------------------------------------------------------------------
def test_validate_login() -> None:
    assert validate_login("quanly01", "x") == {}
    assert validate_login("   ", "") == {"username": REQUIRED, "password": REQUIRED}
    assert validate_login("quanly01", " ") == {}  # mật khẩu giữ nguyên, không trim


def test_login_error_message_never_leaks_details() -> None:
    assert login_error_message(AuthenticationError()) == INVALID
    assert "temporarily unavailable" in login_error_message(ServiceUnavailableError())
    assert login_error_message(RuntimeError("SELECT password_hash FROM employees")) == MSG_OPERATION_FAILED


# ----------------------------------------------------------------------
# View
# ----------------------------------------------------------------------
def test_successful_login_trims_username_and_reports_language(tk_root) -> None:
    view, logged_in = _view(tk_root, language="en")
    _fill(view, "  quanly01 ", DEMO_PASSWORD)
    view.submit()
    session, language = logged_in[0]
    assert (session.username, session.role, language) == ("quanly01", Role.MANAGER, "en")
    assert view.error_text == ""
    view.destroy()


def test_wrong_password_keeps_username_and_clears_password(tk_root) -> None:
    view, logged_in = _view(tk_root)
    _fill(view, "quanly01", "sai-mat-khau")
    view.submit()
    assert logged_in == []
    assert view.error_text == INVALID
    assert view.username_field.get_value() == "quanly01"
    assert view.password_field.get_value() == ""
    assert not view.is_submitting
    view.destroy()


def test_unknown_user_gets_same_message(tk_root) -> None:
    view, _ = _view(tk_root)
    _fill(view, "khong-ton-tai", "abc123")
    view.submit()
    assert view.error_text == INVALID  # không tiết lộ tài khoản có tồn tại hay không
    view.destroy()


def test_blank_fields_do_not_call_service(tk_root) -> None:
    auth = MagicMock()
    view, _ = _view(tk_root, auth=auth)
    view.submit()
    auth.login.assert_not_called()
    assert view.username_field._error_label.cget("text") == REQUIRED
    assert view.password_field._error_label.cget("text") == REQUIRED
    view.username_field.set_value("quanly01")
    view.submit()
    assert view.username_field._error_label.cget("text") == ""
    auth.login.assert_not_called()
    view.destroy()


def test_double_submit_is_blocked_while_waiting(tk_root) -> None:
    runner = DeferredRunner()
    view, logged_in = _view(tk_root, runner=runner)
    _fill(view, "quanly01", DEMO_PASSWORD)
    view.submit()
    view.submit()  # Enter + click liên tiếp
    assert len(runner.jobs) == 1
    assert view.is_submitting
    assert view._submit_button.cget("text") == "Processing…"
    assert view.username_field.entry.cget("state") == "disabled"
    runner.finish()
    assert len(logged_in) == 1
    assert not view.is_submitting
    view.destroy()


def test_service_unavailable_shows_safe_message(tk_root) -> None:
    auth = MagicMock()
    auth.login.side_effect = ServiceUnavailableError()
    view, logged_in = _view(tk_root, auth=auth)
    _fill(view, "quanly01", DEMO_PASSWORD)
    view.submit()
    assert logged_in == []
    assert view.error_text == "Service is temporarily unavailable. Please try again later."
    assert view._submit_button.is_enabled
    view.destroy()


def test_unexpected_error_is_logged_not_shown(tk_root, caplog: pytest.LogCaptureFixture) -> None:
    auth = MagicMock()
    auth.login.side_effect = RuntimeError("mysql: Access denied for user 'root'")
    view, _ = _view(tk_root, auth=auth)
    _fill(view, "quanly01", DEMO_PASSWORD)
    view.submit()
    assert view.error_text == MSG_OPERATION_FAILED
    assert "Access denied" in caplog.text  # chi tiết chỉ nằm trong log
    view.destroy()


def test_language_switch_keeps_username(tk_root) -> None:
    view, _ = _view(tk_root)
    view.username_field.set_value("nhanvien01")
    view.set_language("en")
    assert view.language == "en"
    assert view.username_field.get_value() == "nhanvien01"
    assert view._submit_button.cget("text") == "Sign in  →"
    view.destroy()


def test_password_toggle(tk_root) -> None:
    view, _ = _view(tk_root)
    view.password_field.set_value("secret")
    assert view.password_field.entry.cget("show") == "•"
    view.password_field.toggle_password()
    assert view.password_field.entry.cget("show") == ""
    view.destroy()
