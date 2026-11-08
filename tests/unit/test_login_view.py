"""Login validation, async state, safe errors, and the real app lifecycle."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cyberhub_manager.app import create_service_bundle
from cyberhub_manager.domain.exceptions import AuthenticationError, ServiceUnavailableError
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.ui.background import ImmediateTaskRunner
from cyberhub_manager.ui.login_view import LoginView
from cyberhub_manager.ui.theme import load_stitch_fonts


@pytest.fixture
def login(tk_root):
    load_stitch_fonts()
    services = build_mock_services()
    callback = Mock()
    view = LoginView(tk_root, services.auth, on_login_success=callback,
                     runner=ImmediateTaskRunner(), demo=True)
    view.pack(fill="both", expand=True)
    tk_root.update()
    return view, callback


def fill(view, username="quanly01", password="demo123"):
    view.username.entry.delete(0, "end")
    view.username.entry.insert(0, username)
    view.password.entry.delete(0, "end")
    view.password.entry.insert(0, password)


def test_blank_fields_never_call_auth(login):
    view, callback = login
    view._auth_service = Mock()
    view.submit()
    view._auth_service.login.assert_not_called()
    callback.assert_not_called()
    assert view.username._error and view.password._error


@pytest.mark.parametrize("username", ["quanly01", "nhanvien01"])
def test_valid_login_emits_session_and_erases_password(login, username):
    view, callback = login
    fill(view, username)
    view.submit()
    assert callback.call_count == 1
    assert callback.call_args.args[0].username == username
    assert view.password.entry.get() == ""
    view.submit()
    assert callback.call_count == 1


def test_bad_password_keeps_username_clears_and_masks_password(login):
    view, callback = login
    fill(view, password="wrong")
    view.password.toggle_password()
    view.submit()
    callback.assert_not_called()
    assert view.username.entry.get() == "quanly01"
    assert view.password.entry.get() == ""
    assert not view.password.revealed
    assert view.password.entry.cget("show") == "•"
    assert view.password._error
    assert view._feedback_key == "invalid"
    assert not view._busy
    assert view.submit_button.cget("state") == "normal"


def test_password_is_never_trimmed(login):
    view, callback = login
    fill(view, username="  quanly01  ", password=" demo123")
    view.submit()
    callback.assert_not_called()
    fill(view, username="  quanly01  ")
    view.submit()
    assert callback.call_args.args[0].username == "quanly01"


def test_language_switch_preserves_input_and_error_translation(login):
    view, callback = login
    fill(view, password="wrong")
    view.submit()
    view.set_language("en")
    assert view.username.entry.get() == "quanly01"
    assert view.title_label.cget("text") == "Sign in"
    assert view.feedback_text.cget("text") == "Incorrect username or password."
    assert view.password.error_label.cget("text") == "Please check your sign-in details."
    fill(view)
    view.set_language("vi")
    assert view.password.entry.get() == "demo123"
    callback.assert_not_called()


@pytest.mark.parametrize("error", [ServiceUnavailableError(), RuntimeError("mysql password=secret traceback")])
def test_service_failure_is_safe_and_can_retry(login, error):
    view, callback = login
    view._auth_service = Mock()
    view._auth_service.login.side_effect = error
    fill(view)
    view.submit()
    assert view._feedback_key == "unavailable"
    assert "secret" not in view.feedback_text.cget("text")
    assert not view._busy
    view._auth_service = build_mock_services().auth
    view.submit()
    callback.assert_called_once()


class DeferredRunner:
    def __init__(self):
        self.calls = []

    def submit(self, widget, func, on_success, on_error):
        self.calls.append((func, on_success, on_error))


def test_busy_blocks_double_submit_language_and_password_toggle(login):
    view, _ = login
    runner = DeferredRunner()
    view._runner = runner
    fill(view)
    view.submit()
    view.submit()
    view.set_language("en")
    view.password.toggle_password()
    assert len(runner.calls) == 1
    assert view._busy and view.language == "vi" and not view.password.revealed
    assert view.submit_button.cget("state") == "disabled"
    assert view.username.entry.cget("state") == "disabled"
    runner.calls[0][2](AuthenticationError())
    assert not view._busy
    assert view.username.entry.cget("state") == "normal"


def test_typing_clears_inline_error(login):
    view, _ = login
    fill(view, password="wrong")
    view.submit()
    view._on_typing(SimpleNamespace(keysym="a"), view.password)
    assert not view.password._error
    assert view._feedback_key == ""


def test_closed_login_ignores_delayed_auth_result(login):
    view, callback = login
    runner = DeferredRunner()
    view._runner = runner
    fill(view)
    view.submit()
    view.destroy()
    func, on_success, on_error = runner.calls[0]
    on_success(func())
    on_error(AuthenticationError())
    callback.assert_not_called()
    assert view._spinner_id is None


def test_real_services_follow_current_session_without_database_access():
    state = {"actor": None}
    bundle = create_service_bundle(actor_provider=lambda: state["actor"])
    services = (bundle.customers, bundle.wallet, bundle.machines, bundle.sessions, bundle.reports)
    assert all(service._actor_provider() is None for service in services)
    actor = build_mock_services().auth.login("quanly01", "demo123")
    state["actor"] = actor
    assert all(service._actor_provider() is actor for service in services)
    state["actor"] = None
    assert all(service._actor_provider() is None for service in services)


def test_login_shell_logout_lifecycle_in_separate_process():
    # A dedicated process exercises the CTk root without creating multiple Tcl roots
    # in the shared UI test process on Windows.
    source = """
from cyberhub_manager.app import CyberHubApp
from cyberhub_manager.ui.app_shell import AppShell
from cyberhub_manager.ui.background import ImmediateTaskRunner
from cyberhub_manager.ui.login_view import LoginView
from cyberhub_manager.ui.navigation import NavKey
app = CyberHubApp(mock=True, runner=ImmediateTaskRunner())
app.update()
login = app.current_view
login.set_language('en')
login.username.entry.insert(0, 'nhanvien01')
login.password.entry.insert(0, 'demo123')
login.submit()
app.update()
shell = app.current_view
assert isinstance(shell, AppShell)
assert NavKey.MACHINES not in shell.nav_keys
assert app.session.username == 'nhanvien01'
shell.logout()
app.update()
assert isinstance(app.current_view, LoginView)
assert app.session is None
assert app.current_view.language == 'en'
assert app.current_view.password.entry.get() == ''
app.destroy()
print('login-shell-logout OK')
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src")}
    result = subprocess.run([sys.executable, "-c", source], capture_output=True,
                            text=True, env=env, timeout=45)
    assert result.returncode == 0, result.stderr
    assert "login-shell-logout OK" in result.stdout
