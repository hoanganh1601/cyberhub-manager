"""Standalone mock UI: python -m cyberhub_manager.ai.preview --port 8058.

No assistant API, authenticated session, corpus loader or real model is wired
here. All chat examples and feedback stay in browser memory, not business data.
"""

import argparse
from importlib.resources import files

from flask import Flask, render_template, send_from_directory


def create_preview_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, root_path=str(files("cyberhub_manager.web")))
    if config:
        app.config.update(config)

    @app.get("/")
    def index():
        return render_template("assistant_preview.html")

    @app.get("/healthz")
    def health():
        return {"mode": "assistant-ui-mock", "real_ai": False}

    @app.get("/assets/<path:name>")
    def assets(name):
        return send_from_directory(str(files("cyberhub_manager.ui.assets")), name)

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self'; font-src 'self'; connect-src 'none'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'none'; object-src 'none'"
        )
        return response

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8058)
    args = parser.parse_args()
    create_preview_app().run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
