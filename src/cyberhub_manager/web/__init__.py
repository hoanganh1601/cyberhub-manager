"""Compatibility entry point; HTTP implementation lives in presentation.web."""
from cyberhub_manager.presentation.web import create_app

__all__ = ["create_app"]
