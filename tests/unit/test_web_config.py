import pytest
from flask import Flask

from cyberhub_manager.presentation.web.config import configure_web_app


@pytest.mark.parametrize("value,expected", [("true", True), (" TRUE ", True), ("false", False)])
def test_boolean_environment_values_are_parsed_strictly(monkeypatch, value, expected):
    monkeypatch.setenv("CYBERHUB_COOKIE_SECURE", value)
    app = Flask(__name__)
    configure_web_app(app, {"WEB_MODE": "demo", "SECRET_KEY": "test"})
    assert app.config["SESSION_COOKIE_SECURE"] is expected


def test_invalid_boolean_environment_value_fails_fast(monkeypatch):
    monkeypatch.setenv("CYBERHUB_TRUST_PROXY", "tru")
    with pytest.raises(RuntimeError, match="CYBERHUB_TRUST_PROXY must be true or false"):
        configure_web_app(Flask(__name__), {"WEB_MODE": "demo", "SECRET_KEY": "test"})


def test_allowed_hosts_are_trimmed_and_empty_entries_removed(monkeypatch):
    monkeypatch.setenv("CYBERHUB_ALLOWED_HOSTS", " app.example.com, ,localhost ")
    app = Flask(__name__)
    configure_web_app(app, {"WEB_MODE": "demo", "SECRET_KEY": "test"})
    assert app.config["TRUSTED_HOSTS"] == ["app.example.com", "localhost"]


def test_mysql_mode_requires_a_stable_secret(monkeypatch):
    monkeypatch.setattr("cyberhub_manager.presentation.web.config.load_dotenv", lambda: None)
    monkeypatch.delenv("CYBERHUB_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="stable CYBERHUB_SECRET_KEY"):
        configure_web_app(Flask(__name__), {"WEB_MODE": "mysql"})
