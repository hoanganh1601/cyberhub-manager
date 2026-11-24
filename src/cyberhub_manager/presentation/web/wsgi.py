"""Production entrypoint: gunicorn cyberhub_manager.presentation.web.wsgi:app."""

from cyberhub_manager.presentation.web import create_app

app = create_app()
