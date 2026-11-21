"""Compatibility entry point for existing gunicorn configurations."""
from cyberhub_manager.presentation.web.wsgi import app

__all__ = ["app"]
