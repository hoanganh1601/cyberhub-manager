"""HA-11 safe login errors on the current Stitch view (VI and EN)."""

from unittest.mock import Mock

import pytest

from cyberhub_manager.domain.exceptions import AuthenticationError, ServiceUnavailableError
from cyberhub_manager.ui.background import ImmediateTaskRunner
from cyberhub_manager.ui.login_view import LoginView


@pytest.mark.parametrize("language", ["vi", "en"])
@pytest.mark.parametrize("failure", [AuthenticationError, ServiceUnavailableError, RuntimeError])
def test_login_error_is_localized_recoverable_and_keeps_technical_details_in_logs(
    tk_root, caplog, language, failure
):
    auth = Mock()
    auth.login.side_effect = failure("secret_sql_column")
    callback = Mock()
    view = LoginView(tk_root, auth, on_login_success=callback,
                     language=language, runner=ImmediateTaskRunner())
    try:
        view.username.entry.insert(0, "unknown.user")
        view.password.entry.insert(0, "wrong-password")
        view.submit()
        callback.assert_not_called()
        assert view.username.entry.get() == "unknown.user"
        # Authentication failure clears the password; a service outage permits retry.
        assert view.password.entry.get() == ("" if failure is AuthenticationError else "wrong-password")
        assert not view._busy
        assert view.submit_button.cget("state") == "normal"
        assert "secret_sql_column" not in view.feedback_text.cget("text")
        assert view._feedback_key == ("invalid" if failure is AuthenticationError else "unavailable")
        if failure is RuntimeError:
            assert "Unexpected sign-in failure" in caplog.text
        else:
            assert "Unexpected sign-in failure" not in caplog.text
        before = view.feedback_text.cget("text")
        view.set_language("en" if language == "vi" else "vi")
        assert view.feedback_text.cget("text") != before
    finally:
        view.destroy()
