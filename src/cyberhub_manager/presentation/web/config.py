"""Environment-backed configuration for the Flask adapter."""

from datetime import timedelta
import os
import secrets
from typing import Any

from dotenv import load_dotenv
from flask import Flask


def configure_web_app(app: Flask, overrides: dict[str, Any] | None = None) -> bool:
    """Apply and validate web settings; return whether demo mode is active."""

    load_dotenv()
    configured_secret = os.getenv("CYBERHUB_SECRET_KEY")
    allowed_hosts = tuple(
        host.strip()
        for host in os.getenv("CYBERHUB_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    )
    app.config.update(
        SECRET_KEY=configured_secret or secrets.token_hex(32),
        WEB_MODE=os.getenv("CYBERHUB_WEB_MODE", "demo"),
        SESSION_COOKIE_NAME="cyberhub_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=_boolean("CYBERHUB_COOKIE_SECURE", False),
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=16 * 1024,
        TRUSTED_HOSTS=list(allowed_hosts) if allowed_hosts else None,
        TRUST_PROXY=_boolean("CYBERHUB_TRUST_PROXY", False),
        RBAC_POLICY=os.getenv("CYBERHUB_RBAC_POLICY", "legacy").lower(),
        LOGIN_RATE_LIMIT_ENABLED=_boolean(
            "CYBERHUB_LOGIN_RATE_LIMIT_ENABLED", True
        ),
        LOGIN_RATE_LIMIT_ATTEMPTS=_integer(
            "CYBERHUB_LOGIN_RATE_LIMIT_ATTEMPTS", 10
        ),
        LOGIN_RATE_LIMIT_WINDOW_SECONDS=_integer(
            "CYBERHUB_LOGIN_RATE_LIMIT_WINDOW_SECONDS", 600
        ),
        EMAIL_VERIFICATION_ENABLED=_boolean(
            "CYBERHUB_EMAIL_VERIFICATION",
            bool(os.getenv("CYBERHUB_SMTP_HOST") and os.getenv("CYBERHUB_EMAIL_TOKEN_SECRET")),
        ),
    )
    app.config.update(overrides or {})
    _validate(app, stable_secret=bool(configured_secret or (overrides or {}).get("SECRET_KEY")))
    return app.config["WEB_MODE"] == "demo"


def _boolean(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise RuntimeError(f"{name} must be true or false")


def _integer(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer") from error


def _validate(app: Flask, *, stable_secret: bool) -> None:
    if (
        app.config["LOGIN_RATE_LIMIT_ATTEMPTS"] < 1
        or app.config["LOGIN_RATE_LIMIT_WINDOW_SECONDS"] < 1
    ):
        raise RuntimeError("Login rate-limit values must be positive integers")
    if app.config["WEB_MODE"] not in ("demo", "mysql"):
        raise RuntimeError("CYBERHUB_WEB_MODE must be demo or mysql")
    if app.config["RBAC_POLICY"] not in ("legacy", "separated"):
        raise RuntimeError("CYBERHUB_RBAC_POLICY must be legacy or separated")
    if app.config["RBAC_POLICY"] != os.getenv("CYBERHUB_RBAC_POLICY", "legacy").lower():
        raise RuntimeError("RBAC_POLICY override must match CYBERHUB_RBAC_POLICY used by services")
    if app.config["WEB_MODE"] == "mysql" and (
        len(str(app.config["SECRET_KEY"])) < 32 or not stable_secret
    ):
        raise RuntimeError(
            "MySQL web mode requires a stable CYBERHUB_SECRET_KEY of at least 32 characters"
        )
