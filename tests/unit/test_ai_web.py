"""HTTP/session to real RAG pipeline using deterministic providers and demo auth.

No model network calls or MySQL dependency; durable policy store uses tmp_path.
"""

from dataclasses import replace
from importlib.resources import files
import json
import sqlite3
from types import SimpleNamespace

import pytest

from cyberhub_manager.ai.errors import ProviderTimeoutError
from cyberhub_manager.ai.fakes import FakeEmbeddingProvider, FakeLLMProvider
from cyberhub_manager.ai.models import KnowledgeDocument
from cyberhub_manager.ai.gemini import GeminiLLMProvider
from cyberhub_manager.ai.policy_store import AssistantLimits
from cyberhub_manager.ai.retrieval import KnowledgeRetriever
from cyberhub_manager.ai.service import RAGAssistantService
from cyberhub_manager.domain.enums import Role
from cyberhub_manager.web import create_app


@pytest.fixture
def ctx(tmp_path):
    holder = SimpleNamespace(path=tmp_path / "assistant.sqlite3")

    def factory(sink):
        holder.embedding = FakeEmbeddingProvider()
        holder.llm = FakeLLMProvider(response="Cần đủ số dư và máy trống. [S1]")
        holder.retriever = KnowledgeRetriever(holder.embedding)
        docs = [KnowledgeDocument(
            document_id=role.lower(), title=role, content=f"Quy định dành riêng cho {role}.",
            source=f"shared/{role.lower()}.md", audience=(role,), status="APPROVED", version=1,
        ) for role in ("CUSTOMER", "STAFF", "MANAGER", "ADMIN")]
        holder.retriever.rebuild(docs)
        holder.service = RAGAssistantService(holder.retriever, holder.llm, audit=sink)
        holder.store = sink
        return holder.service

    holder.app = create_app({
        "TESTING": True, "WEB_MODE": "demo", "SECRET_KEY": "assistant-http-tests",
        "ASSISTANT_ENABLED": True, "ASSISTANT_SERVICE_FACTORY": factory,
        "ASSISTANT_AUDIT_PATH": holder.path,
    })
    holder.client = holder.app.test_client()
    return holder


def login(ctx, username="nhanvien01", kind="employee"):
    token = ctx.client.get("/api/session").json["csrf_token"]
    result = ctx.client.post("/api/login", json={"username": username, "password": "demo123", "kind": kind}, headers={"X-CSRF-Token": token})
    assert result.status_code == 200, result.json
    ctx.headers = {"X-CSRF-Token": result.json["csrf_token"]}
    return result.json


def ask(ctx, data=None, **kwargs):
    return ctx.client.post("/api/assistant/messages", json=data if data is not None else {"question": "Cần gì để mở phiên?"}, headers=ctx.headers, **kwargs)


def audit_rows(ctx):
    with sqlite3.connect(ctx.path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute("SELECT * FROM assistant_requests")]


def workspace(ctx):
    with ctx.client.session_transaction() as state:
        return ctx.app.extensions["cyberhub_demo"].get(state["workspace"])


@pytest.mark.parametrize("username,kind,role", [
    ("nhanvien01", "employee", "STAFF"), ("quanly01", "employee", "MANAGER"),
    ("admin01", "employee", "ADMIN"), ("nguyenvanan", "customer", "CUSTOMER"),
])
def test_authenticated_role_matrix_uses_only_own_backend_sources(ctx, username, kind, role):
    session = login(ctx, username, kind)
    response = ask(ctx, {"question": "Cần gì?", "language": "en"})
    assert response.status_code == 200, response.json
    assert response.json["grounded"] is True
    assert [c["document_id"] for c in response.json["citations"]] == [role.lower()]
    row, = audit_rows(ctx)
    principal = session["customer"] if kind == "customer" else session["actor"]
    assert row["request_id"] == response.json["request_id"]
    assert row["actor_id"] == principal["account_id" if kind == "customer" else "employee_id"]
    assert row["actor_role"] == role and row["language"] == "en"
    assert json.loads(row["store_ids"]) == ([] if kind == "customer" else [1])
    assert row["result"] == "ANSWERED"
    assert role in ctx.llm.calls[0].user_prompt
    for other in {"CUSTOMER", "STAFF", "MANAGER", "ADMIN"} - {role}:
        assert f'Quy định dành riêng cho {other}' not in ctx.llm.calls[0].user_prompt
    assert response.headers["Cache-Control"] == "no-store"


def test_anonymous_csrf_and_replayed_logout_cannot_reach_provider(ctx):
    assert ctx.client.post("/api/assistant/messages", json={"question": "hello"}).status_code == 403
    csrf = ctx.client.get("/api/session").json["csrf_token"]
    assert ctx.client.post("/api/assistant/messages", json={"question": "hello"}, headers={"X-CSRF-Token": csrf}).status_code == 401
    login(ctx)
    assert ctx.client.post("/api/assistant/messages", json={"question": "hello"}).status_code == 403
    cookie = ctx.client.get_cookie("cyberhub_session").value
    assert ctx.client.post("/api/logout", headers=ctx.headers).status_code == 200
    ctx.client.set_cookie("cyberhub_session", cookie)
    assert ask(ctx).status_code == 401
    assert not audit_rows(ctx) and not ctx.llm.calls and not ctx.embedding.query_calls


@pytest.mark.parametrize("payload", [
    {}, {"question": " "}, {"question": True}, {"question": []}, {"question": "x" * 2001},
    {"question": "hi", "role": "ADMIN"}, {"question": "hi", "store_ids": [99]},
    {"question": "hi", "actor_id": 99}, {"question": "hi", "request_id": "a" * 32},
    {"question": "hi", "context": "privileged"}, {"question": "hi", "language": {}},
    {"question": "hi", "language": "fr"}, {"question": "hi", "conversation_id": "someone-else"},
])
def test_invalid_or_forged_inputs_never_call_providers_or_spend_quota(ctx, payload):
    login(ctx)
    response = ask(ctx, payload)
    assert response.status_code == 422
    assert not audit_rows(ctx) and not ctx.llm.calls and not ctx.embedding.query_calls


def test_body_limit_and_wrong_content_type_rejected(ctx):
    login(ctx)
    assert ctx.client.post("/api/assistant/messages", data="x" * 17000, headers=ctx.headers, content_type="application/json").status_code == 413
    assert ctx.client.post("/api/assistant/messages", data="question=hi", headers=ctx.headers).status_code == 422
    assert not audit_rows(ctx)


def test_admin_switch_store_is_backend_scoped_and_cannot_reset_quota(ctx):
    login(ctx, "admin01")
    assert ctx.client.post("/api/store/switch", json={"store_id": 2}, headers=ctx.headers).status_code == 200
    response = ctx.client.post("/api/assistant/messages?store_id=999&role=STAFF", json={"question": "hello"}, headers=ctx.headers)
    assert response.status_code == 200
    row, = audit_rows(ctx)
    assert json.loads(row["store_ids"]) == [2] and row["actor_role"] == "ADMIN"


def test_fallback_and_provider_failure_are_distinct_safe_envelopes(ctx, monkeypatch):
    login(ctx)
    ctx.retriever.rebuild([])
    response = ask(ctx)
    assert response.status_code == 200 and response.json["grounded"] is False
    assert response.json["citations"] == []
    assert audit_rows(ctx)[0]["result"] == "NO_CONTEXT"

    def fail(**kwargs):
        raise RuntimeError("API_KEY_SECRET private prompt")

    monkeypatch.setattr(ctx.retriever, "search_scored", fail)
    response = ask(ctx)
    assert response.status_code == 503
    assert "SECRET" not in response.text and "private prompt" not in response.text
    assert audit_rows(ctx)[1]["result"] == "INTERNAL_ERROR"


def test_local_model_refusal_with_claims_returns_no_context_instead_of_service_failure(ctx):
    class RefusingTransport:
        calls = 0

        def post(self, model, method, payload):
            self.calls += 1
            return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps({
                "answerable": False,
                "claims": [{"text": "private unsupported content", "ref": "S99", "passage": "S99.P1"}],
            })}]}}]}

    login(ctx, "nguyenvanan", "customer")
    transport = RefusingTransport()
    ctx.service._llm = GeminiLLMProvider(transport)
    response = ask(ctx)
    assert response.status_code == 200
    assert response.json["grounded"] is False and response.json["citations"] == []
    assert "private unsupported content" not in response.text
    assert audit_rows(ctx)[0]["result"] == "NO_CONTEXT"
    assert transport.calls == 1


def test_quota_is_applied_before_embedding_and_generation(ctx):
    login(ctx)
    ctx.store.limits = AssistantLimits(per_minute=1)
    assert ask(ctx).status_code == 200
    response = ask(ctx)
    assert response.status_code == 429
    assert 1 <= int(response.headers["Retry-After"]) <= 60
    assert len(ctx.llm.calls) == len(ctx.embedding.query_calls) == 1
    assert len(audit_rows(ctx)) == 1


@pytest.mark.parametrize("failure_stage", ["reserve", "record"])
def test_audit_failure_fails_closed_without_exposing_generated_answer(ctx, monkeypatch, failure_stage):
    login(ctx)

    def fail(*args, **kwargs):
        raise RuntimeError("private-storage-secret")

    monkeypatch.setattr(ctx.store, failure_stage, fail)
    response = ask(ctx)
    assert response.status_code == 503
    assert "private-storage-secret" not in response.text
    assert "Cần đủ số dư" not in response.text
    assert len(ctx.llm.calls) == (0 if failure_stage == "reserve" else 1)


def test_employee_lock_before_request_cannot_reach_model(ctx):
    login(ctx)
    data = workspace(ctx).services.management._repo.data
    # Memory repository uses its authoritative employee records, not cookie roles.
    employee = next(e for e in data.employees.values() if e.username == "nhanvien01")
    employee.lock()
    assert ask(ctx).status_code == 403
    assert not ctx.llm.calls and not audit_rows(ctx)


@pytest.mark.parametrize("target", ["customer", "store"])
def test_inactive_customer_or_operating_store_cannot_reach_model(ctx, target):
    login(ctx, "nguyenvanan" if target == "customer" else "nhanvien01", "customer" if target == "customer" else "employee")
    data = workspace(ctx).services.management._repo.data
    if target == "customer":
        data.customers[1].account.lock()
    else:
        data.stores[1].deactivate()
    assert ask(ctx).status_code == 403
    assert not ctx.llm.calls and not audit_rows(ctx)


def test_employee_locked_during_model_call_withholds_output(ctx, monkeypatch):
    login(ctx)
    data = workspace(ctx).services.management._repo.data
    generate = ctx.llm.generate

    def lock_then_answer(**kwargs):
        next(e for e in data.employees.values() if e.username == "nhanvien01").lock()
        return generate(**kwargs)

    monkeypatch.setattr(ctx.llm, "generate", lock_then_answer)
    response = ask(ctx)
    assert response.status_code == 403
    row, = audit_rows(ctx)
    assert row["result"] == "ACCESS_CHANGED" and row["chunk_ids"] == "[]"


def test_provider_timeout_returns_safe_503_with_audit(ctx, monkeypatch):
    login(ctx)

    def fail(**kwargs):
        raise ProviderTimeoutError("secret provider endpoint")

    monkeypatch.setattr(ctx.llm, "generate", fail)
    response = ask(ctx)
    assert response.status_code == 503 and "secret provider endpoint" not in response.text
    assert audit_rows(ctx)[0]["result"] == "PROVIDER_TIMEOUT"


def test_role_changed_during_generation_withholds_answer_and_sources(ctx, monkeypatch):
    login(ctx, "quanly01")
    management = workspace(ctx).services.management
    original = management.validate_actor
    counter = [0]

    def validate(actor):
        counter[0] += 1
        current = original(actor)
        return replace(current, role=Role.STAFF) if counter[0] > 1 else current

    monkeypatch.setattr(management, "validate_actor", validate)
    response = ask(ctx)
    assert response.status_code == 403
    row, = audit_rows(ctx)
    assert row["result"] == "ACCESS_CHANGED" and row["chunk_ids"] == "[]"
    assert "citations" not in response.json


def test_feature_disabled_by_default_and_misconfiguration_fails_startup(tmp_path):
    app = create_app({"TESTING": True, "WEB_MODE": "demo"})
    ctx = SimpleNamespace(client=app.test_client())
    login(ctx)
    response = ask(ctx)
    assert response.status_code == 503 and response.json["error"]["code"] == "ASSISTANT_DISABLED"
    assert "cyberhub_assistant" not in app.extensions
    assert "assistant_live.js" not in ctx.client.get("/").text
    with pytest.raises(ValueError):
        create_app({"WEB_MODE": "demo", "ASSISTANT_ENABLED": True})
    with pytest.raises(ValueError, match="outside web and asset"):
        create_app({"WEB_MODE": "demo", "ASSISTANT_ENABLED": True,
                    "ASSISTANT_SERVICE_FACTORY": lambda sink: None,
                    "ASSISTANT_AUDIT_PATH": str(files("cyberhub_manager.ui.assets").joinpath("unsafe.sqlite3"))})


def test_live_widget_is_loaded_only_with_configured_backend(ctx):
    for path in ("/", "/customer"):
        page = ctx.client.get(path)
        assert "assistant_live.js" in page.text and 'id="assistant-widget"' in page.text
        assert 'class="assistant-preview assistant-live" hidden' in page.text
        assert "assistant_preview.js" not in page.text
    assert ctx.client.get("/static/assistant_live.js").status_code == 200


def test_read_only_request_does_not_change_wallet_sessions_or_invoices(ctx):
    login(ctx)
    before = {path: ctx.client.get(path).json for path in ("/api/customers/1", "/api/machines", "/api/invoices")}
    assert ask(ctx).status_code == 200
    for path, value in before.items():
        after = ctx.client.get(path).json
        # Live elapsed-time/cost fields on machine cards may advance; IDs/status do not.
        if path == "/api/machines":
            assert [(m["machine_id"], m["status"]) for m in after] == [(m["machine_id"], m["status"]) for m in value]
        else:
            assert after == value


def test_slow_chat_does_not_block_logout_and_withholds_reply_after_revocation(ctx, monkeypatch):
    from threading import Event, Thread
    from time import monotonic
    login(ctx)
    cookie = ctx.client.get_cookie('cyberhub_session').value
    started, release = Event(), Event()
    responses = []

    def slow(**kwargs):
        started.set()
        if not release.wait(5):
            raise ProviderTimeoutError('test deadline')
        return 'Quy định có nguồn. [S1]'

    monkeypatch.setattr(ctx.llm, 'generate', slow)
    thread = Thread(target=lambda: responses.append(ask(ctx)))
    thread.start()
    try:
        assert started.wait(2)
        other = ctx.app.test_client()
        other.set_cookie('cyberhub_session', cookie)
        before = monotonic()
        assert other.post('/api/logout', headers=ctx.headers).status_code == 200
        assert monotonic() - before < 2.5
    finally:
        release.set()
        thread.join(3)
    assert not thread.is_alive()
    assert responses[0].status_code == 403
    assert audit_rows(ctx)[-1]['result'] == 'ACCESS_CHANGED'
