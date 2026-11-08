"""Production entrypoint: gunicorn cyberhub_manager.web.wsgi:app."""

from . import create_app

app = create_app()
