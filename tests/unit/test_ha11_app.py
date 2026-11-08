"""HA-11 integration with the current desktop root and shared web bootstrap."""

import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from cyberhub_manager import app as app_module
from cyberhub_manager.app import install_error_hook, parse_args
from cyberhub_manager.services.bootstrap import create_service_bundle
from cyberhub_manager.services.mocks.factory import build_mock_services


def test_real_services_follow_one_session_provider_without_opening_mysql():
    state = {"actor": None}
    with patch("cyberhub_manager.database.connection.init_pool") as init_pool:
        bundle = create_service_bundle(actor_provider=lambda: state["actor"])
    init_pool.assert_not_called()
    services = [getattr(bundle, name) for name in
                ("customers", "wallet", "machines", "sessions", "reports")]
    assert all(service._actor_provider() is None for service in services)
    state["actor"] = build_mock_services().auth.login("quanly01", "demo123")
    assert all(service._actor_provider() is state["actor"] for service in services)
    state["actor"] = None
    assert all(service._actor_provider() is None for service in services)


@pytest.mark.parametrize("language", ["vi", "en"])
def test_callback_error_logs_details_and_shows_localized_safe_text(language, caplog):
    root = SimpleNamespace()
    install_error_hook(root, lambda: language)
    error = KeyError("secret_column")
    with patch("cyberhub_manager.ui.components.ToastManager.show") as toast:
        root.report_callback_exception(type(error), error, error.__traceback__)
    message = toast.call_args.args[1]
    assert "secret_column" not in message
    assert ("Có lỗi" if language == "vi" else "unexpected error") in message
    assert "secret_column" in caplog.text


def test_notification_failure_does_not_recursively_raise(caplog):
    root = SimpleNamespace()
    install_error_hook(root)
    with patch("cyberhub_manager.ui.components.ToastManager.show", side_effect=RuntimeError("closed")):
        root.report_callback_exception(ValueError, ValueError("bad callback"), None)
    assert "Unable to display" in caplog.text


def test_cli_options():
    assert not parse_args([]).mock
    args = parse_args(["--mock", "--lang", "en"])
    assert args.mock and args.lang == "en"
    with pytest.raises(SystemExit):
        parse_args(["--lang", "fr"])


def test_missing_configuration_fails_before_creating_a_window(capsys):
    with patch("cyberhub_manager.config.load_settings", side_effect=RuntimeError("MYSQL_DATABASE missing")):
        with patch.object(app_module, "CyberHubApp") as app:
            with pytest.raises(SystemExit) as stopped:
                app_module.main([])
    assert stopped.value.code == 2
    assert "Configure .env or use --mock" in capsys.readouterr().err
    app.assert_not_called()


def test_mock_cli_does_not_require_database_settings():
    with patch("cyberhub_manager.config.load_settings", side_effect=AssertionError("DB access")):
        with patch.object(app_module, "CyberHubApp") as app:
            app_module.main(["--mock", "--lang", "en"])
    app.assert_called_once_with(mock=True, language="en")
    app.return_value.mainloop.assert_called_once()


def test_shared_bootstrap_imports_without_tk():
    result = subprocess.run([sys.executable, "-c", """
import sys
from cyberhub_manager.services.bootstrap import create_service_bundle
create_service_bundle(mock=True)
assert 'tkinter' not in sys.modules
"""], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
