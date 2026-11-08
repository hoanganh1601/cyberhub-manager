"""Browser UI backed by the same application services as the desktop."""

from .application import create_app

__all__ = ["create_app"]
