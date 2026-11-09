"""Standalone UI preview serves assets, without an assistant API/session/DB."""

import subprocess
import sys

import pytest

pytest.importorskip("flask")

from cyberhub_manager.ai.preview import create_preview_app


@pytest.fixture
def client():
    return create_preview_app({"TESTING": True}).test_client()


def test_preview_is_explicitly_mock_and_does_not_create_session(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Mô phỏng giao diện" in response.text
    assert "assistant-chat" in response.text
    assert "chat-form" in response.text
    assert "Set-Cookie" not in response.headers
    assert client.get("/healthz").json == {"mode": "assistant-ui-mock", "real_ai": False}


@pytest.mark.parametrize("path", [
    "/api/assistant/messages", "/api/login", "/api/session", "/api/revenue",
    "/docs/knowledge-base/admin/employee-management.md", "/.env",
])
def test_preview_does_not_expose_auth_business_or_knowledge_routes(client, path):
    assert client.get(path).status_code == 404
    assert client.post(path, json={"role": "ADMIN", "question": "private"}).status_code == 404


def test_preview_has_csp_to_block_network_calls_and_external_content(client):
    response = client.get("/")
    assert "connect-src 'none'" in response.headers["Content-Security-Policy"]
    assert "form-action 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"


def test_preview_reuses_packaged_theme_fonts_logo_and_static_ui(client):
    for path in (
        "/static/app.css", "/static/assistant_preview.css", "/static/assistant_preview.js",
        "/assets/cyberhub_logo_dark.png", "/assets/fonts/Inter-400.ttf",
    ):
        assert client.get(path).status_code == 200, path
    assert client.get("/assets/../../.env").status_code == 404


def test_preview_imports_headless_without_initializing_tk_or_ai_models():
    code = """
import sys
from cyberhub_manager.ai.preview import create_preview_app
app = create_preview_app({'TESTING': True})
assert app.test_client().get('/').status_code == 200
assert 'tkinter' not in sys.modules
assert 'cyberhub_manager.ai.service' not in sys.modules
assert 'cyberhub_manager.ai.documents' not in sys.modules
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
