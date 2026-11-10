"""Gemini wire protocol and the real auth/RAG flow, with no cloud calls or key."""

import io
import json
import socket
from dataclasses import replace
from xml.etree import ElementTree as ET
from urllib.error import HTTPError, URLError

import pytest

from cyberhub_manager.ai.errors import (
    InsufficientContextError, InvalidProviderResponseError, ProviderAuthenticationError,
    ProviderRateLimitError, ProviderTimeoutError, ProviderUnavailableError,
)
from cyberhub_manager.ai.gemini import GeminiEmbeddingProvider, GeminiLLMProvider, GeminiTransport
from cyberhub_manager.ai import runtime
from cyberhub_manager.ai.models import AIAccessContext, KnowledgeDocument
from cyberhub_manager.ai.retrieval import KnowledgeRetriever
from cyberhub_manager.ai.service import RAGAssistantService
from cyberhub_manager.web import create_app

QUOTE = "Số dư tối thiểu đủ 30 phút theo đơn giá máy."
PROMPT = f'<request language="vi"><question>Cần số dư bao nhiêu?</question><authorized_context><document ref="S1">{QUOTE}</document></authorized_context></request>'


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Gemini unit tests cannot call a network")
    monkeypatch.setattr(socket.socket, "connect", fail)


def envelope(value, **changes):
    return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(value)}]}}]} | changes


class Transport:
    def __init__(self):
        self.calls = []
        self.failure = None

    def post(self, model, method, data):
        self.calls.append((model, method, data))
        if self.failure:
            raise self.failure
        if method == "batchEmbedContents":
            return {"embeddings": [{"values": [1.0] + [0.0] * 767} for _ in data["requests"]]}
        if method == "embedContent":
            return {"embedding": {"values": [1.0] + [0.0] * 767}}
        if data["systemInstruction"]["parts"][0]["text"].startswith("Verify claims"):
            evidence = json.loads(data["contents"][0]["parts"][0]["text"])["evidence"]
            return envelope({"checks": [{"passage_meaning": "Requires 30 minutes of balance.",
                                         "claim_meaning": "Requires 30 minutes of balance.",
                                         "supported": True} for _ in evidence],
                             "answers_question": True, "safe_scope": True})
        request = ET.fromstring(data["contents"][0]["parts"][0]["text"])
        document = next(node for node in request.findall("authorized_context/*")
                        if any("30" in (part.text or "") for part in node.findall("passage")))
        passage = next(part for part in document.findall("passage") if "30" in (part.text or ""))
        return envelope({"answerable": True, "claims": [
            {"text": "Cần số dư đủ 30 phút.", "ref": document.attrib["ref"], "passage": passage.attrib["id"]},
        ]})


def test_transport_accepts_new_google_api_key_format():
    transport = GeminiTransport("AQ.example_key-with-safe-characters")
    assert transport._api_key == "AQ.example_key-with-safe-characters"


@pytest.mark.parametrize("api_key", ["", "key with spaces", "key:colon", "key/slash", "key\nheader"])
def test_transport_rejects_unsafe_api_key_characters(api_key):
    with pytest.raises(ValueError):
        GeminiTransport(api_key)


def test_generation_and_verification_use_gemini_schema_and_keep_system_separate():
    transport = Transport()
    answer = GeminiLLMProvider(transport).generate(system_prompt="trusted rules", user_prompt=PROMPT)
    assert answer == "Cần số dư đủ 30 phút. [S1]"
    assert len(transport.calls) == 2
    for model, method, data in transport.calls:
        assert model == "gemini-3.1-flash-lite" and method == "generateContent"
        assert data["contents"][0]["role"] == "user"
        assert data["generationConfig"]["responseMimeType"] == "application/json"
        assert data["generationConfig"]["responseJsonSchema"]["type"] == "object"
        assert data["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "MINIMAL"}
        assert "tools" not in data
    assert transport.calls[0][2]["systemInstruction"]["parts"][0]["text"].startswith("trusted rules")


def test_dynamic_snapshots_get_backend_passage_ids_too():
    prompt = PROMPT.replace("<document ", "<snapshot ").replace("</document>", "</snapshot>")
    transport = Transport()
    assert GeminiLLMProvider(transport).generate(system_prompt="trusted", user_prompt=prompt).endswith("[S1]")
    assert '<passage id="S1.P1">' in transport.calls[0][2]["contents"][0]["parts"][0]["text"]


@pytest.mark.parametrize("result", [
    {}, {"candidates": []}, {"candidates": [{"finishReason": "MAX_TOKENS"}]},
    {"candidates": [{"finishReason": "SAFETY"}]},
    {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"functionCall": {}}]}}]},
    {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"thought": True, "text": "private reasoning"}]}}]},
])
def test_blocked_truncated_or_non_text_answers_are_not_published(result):
    class Broken(Transport):
        def post(self, *args):
            return result
    with pytest.raises(InvalidProviderResponseError):
        GeminiLLMProvider(Broken()).generate(system_prompt="rules", user_prompt=PROMPT)


def test_citations_still_reject_invented_numbers():
    class Inventing(Transport):
        def post(self, *args):
            return envelope({"answerable": True, "claims": [
                {"text": "Cần số dư đủ 999 phút.", "ref": "S1", "passage": "S1.P1"},
            ]})
    with pytest.raises(InvalidProviderResponseError):
        GeminiLLMProvider(Inventing()).generate(system_prompt="rules", user_prompt=PROMPT)


def test_semantically_unsupported_answer_is_withheld():
    class Rejecting(Transport):
        def post(self, model, method, data):
            if data["systemInstruction"]["parts"][0]["text"].startswith("Verify claims"):
                return envelope({"checks": [{"passage_meaning": "Requires confirmation.",
                                             "claim_meaning": "Does not require confirmation.",
                                             "supported": False}],
                                 "answers_question": True, "safe_scope": True})
            return super().post(model, method, data)
    with pytest.raises(InsufficientContextError):
        GeminiLLMProvider(Rejecting()).generate(system_prompt="rules", user_prompt=PROMPT)


def test_embedding_document_cache_and_query_use_different_retrieval_tasks():
    transport = Transport()
    provider = GeminiEmbeddingProvider(transport)
    documents = provider.embed_documents(["A", "B", "A"])
    assert len(documents) == 3 and len(documents[0]) == 768
    assert len(transport.calls) == 1
    requests = transport.calls[0][2]["requests"]
    assert len(requests) == 2
    assert all(item["taskType"] == "RETRIEVAL_DOCUMENT" and item["outputDimensionality"] == 768 for item in requests)
    documents[0][0] = 7.0
    assert provider.embed_documents(["B", "A"])[1][0] == 1.0
    assert len(transport.calls) == 1
    provider.embed_documents(["A", "C"])
    assert len(transport.calls[-1][2]["requests"]) == 1
    provider.embed_query("A")
    assert transport.calls[-1][1] == "embedContent"
    assert transport.calls[-1][2]["taskType"] == "RETRIEVAL_QUERY"
    assert provider.embed_documents([]) == []


def test_embedding_batches_preserve_order_and_do_not_commit_partial_failures():
    class Batches(Transport):
        def post(self, model, method, data):
            self.calls.append((model, method, data))
            if len(self.calls) == 2:
                raise ProviderRateLimitError("quota")
            return {"embeddings": [{"values": [float(item["content"]["parts"][0]["text"])] + [0.0] * 767}
                                   for item in data["requests"]]}
    transport = Batches()
    provider = GeminiEmbeddingProvider(transport)
    with pytest.raises(ProviderRateLimitError):
        provider.embed_documents([str(i) for i in range(1, 18)])
    assert not provider._document_cache
    vectors = provider.embed_documents(["3", "1", "3"])
    assert [v[0] for v in vectors] == [3.0, 1.0, 3.0]


@pytest.mark.parametrize("result", [{}, {"embeddings": []}, {"embeddings": [{"values": [0.0] * 768}]},
                                    {"embeddings": [{"values": [1.0]}]}])
def test_invalid_embedding_vectors_are_rejected(result):
    class Broken(Transport):
        def post(self, *args):
            return result
    with pytest.raises(InvalidProviderResponseError):
        GeminiEmbeddingProvider(Broken()).embed_documents(["document"])


def test_transport_puts_key_in_header_only_and_uses_fixed_https_origin(monkeypatch):
    transport = GeminiTransport("test-secret-api-key")
    seen = []
    def open_request(request, timeout):
        seen.append(request)
        return io.BytesIO(b'{"ok":true}')
    monkeypatch.setattr(transport._opener, "open", open_request)
    assert transport.post("gemini-3.1-flash-lite", "generateContent", {}) == {"ok": True}
    request, = seen
    assert request.full_url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"
    assert "test-secret" not in request.full_url
    assert request.get_header("X-goog-api-key") == "test-secret-api-key"
    assert "test-secret" not in repr(transport)


@pytest.mark.parametrize("error,expected", [
    (HTTPError("secret", 429, "private provider detail", None, None), ProviderRateLimitError),
    (HTTPError("secret", 403, "private provider detail", None, None), ProviderAuthenticationError),
    (HTTPError("secret", 400, "private provider detail", None, io.BytesIO(b'{"error":{"details":[{"reason":"API_KEY_INVALID"}]}}')), ProviderAuthenticationError),
    (HTTPError("secret", 500, "private provider detail", None, None), ProviderUnavailableError),
    (URLError("private provider detail"), ProviderUnavailableError),
    (URLError(socket.timeout()), ProviderTimeoutError),
    (socket.timeout(), ProviderTimeoutError),
])
def test_transport_errors_hide_key_and_raw_details(monkeypatch, error, expected):
    transport = GeminiTransport("test-secret-api-key")
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(transport._opener, "open", fail)
    with pytest.raises(expected) as caught:
        transport.post("gemini-3.1-flash-lite", "generateContent", {})
    assert "private" not in str(caught.value) and "secret" not in str(caught.value)


@pytest.mark.parametrize("model", ["https://example.com", "models/gemini", "gemini?key=secret", "../other"])
def test_untrusted_model_cannot_change_endpoint_or_receive_credentials(model):
    with pytest.raises(ValueError):
        GeminiLLMProvider(Transport(), model=model)


def test_runtime_defaults_to_api_provider_without_starting_model_processes(tmp_path, monkeypatch):
    from cyberhub_manager.ai import gemini
    import subprocess
    transport = Transport()
    monkeypatch.setattr(gemini, "GeminiTransport", lambda *args, **kwargs: transport)
    def forbidden(*args, **kwargs):
        raise AssertionError("API mode must not start a model process")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("CYBERHUB_ASSISTANT_ENABLED", "true")
    monkeypatch.delenv("CYBERHUB_ASSISTANT_PROVIDER", raising=False)
    monkeypatch.setenv("CYBERHUB_ASSISTANT_AUDIT_PATH", str(tmp_path / "audit.sqlite3"))
    app = create_app({"TESTING": True, "WEB_MODE": "demo"})
    service, _ = app.extensions["cyberhub_assistant"]
    assert isinstance(service._llm, GeminiLLMProvider)
    assert any(method == "batchEmbedContents" for _, method, _ in transport.calls)
    assert not any(method == "generateContent" for _, method, _ in transport.calls)


def test_reindex_preserves_quota_error_and_can_recover_without_stale_documents():
    class Loader:
        documents = [KnowledgeDocument("public", "Public", QUOTE, "shared/public.md", ("CUSTOMER",), "APPROVED", 1)]
        def load(self):
            return self.documents
    transport, loader = Transport(), Loader()
    retriever = runtime.LiveKnowledgeRetriever(GeminiEmbeddingProvider(transport), loader)
    access = AIAccessContext(1, "CUSTOMER", ())
    retriever.search_scored(question="Balance", access=access)
    loader.documents = [replace(loader.documents[0], content=QUOTE + " Updated policy.", version=2)]
    transport.failure = ProviderRateLimitError("private quota detail")
    with pytest.raises(ProviderRateLimitError):
        retriever.search_scored(question="Balance", access=access)
    assert retriever._documents is None
    transport.failure = None
    matches = retriever.search_scored(question="Balance", access=access)
    assert matches and all(match.chunk.version == 2 for match in matches)


def test_cli_missing_key_fails_before_creating_app(monkeypatch, capsys):
    from scripts import run_rag_gemini
    monkeypatch.setattr(run_rag_gemini, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(SystemExit) as caught:
        run_rag_gemini.main([])
    assert caught.value.code == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().err


@pytest.fixture
def cloud_app(tmp_path):
    transport = Transport()
    def factory(sink):
        retriever = KnowledgeRetriever(GeminiEmbeddingProvider(transport))
        retriever.rebuild([KnowledgeDocument(
            document_id=role.lower(), title=role, content=QUOTE,
            source=f"shared/{role.lower()}.md", audience=(role,), status="APPROVED", version=1,
        ) for role in ("CUSTOMER", "STAFF", "MANAGER", "ADMIN")])
        return RAGAssistantService(retriever, GeminiLLMProvider(transport), audit=sink)
    app = create_app({"TESTING": True, "WEB_MODE": "demo", "ASSISTANT_ENABLED": True,
                      "ASSISTANT_SERVICE_FACTORY": factory,
                      "ASSISTANT_AUDIT_PATH": str(tmp_path / "audit.sqlite3")})
    return app, transport


def cloud_login(app, username="nguyenvanan", kind="customer"):
    client = app.test_client()
    token = client.get("/api/session").json["csrf_token"]
    login = client.post("/api/login", json={"username": username, "kind": kind, "password": "demo123"},
                        headers={"X-CSRF-Token": token})
    assert login.status_code == 200
    return client, {"X-CSRF-Token": login.json["csrf_token"]}


@pytest.mark.parametrize("username,kind,role", [
    ("nguyenvanan", "customer", "CUSTOMER"), ("nhanvien01", "employee", "STAFF"),
    ("quanly01", "employee", "MANAGER"), ("admin01", "employee", "ADMIN"),
])
def test_gemini_http_pipeline_returns_only_role_authorized_citations(cloud_app, username, kind, role):
    app, transport = cloud_app
    client, headers = cloud_login(app, username, kind)
    response = client.post("/api/assistant/messages", json={"question": "Cần số dư bao nhiêu?"}, headers=headers)
    assert response.status_code == 200 and response.json["grounded"] is True
    assert [c["document_id"] for c in response.json["citations"]] == [role.lower()]
    assert len([call for call in transport.calls if call[1] == "generateContent"]) == 2
    assert "GEMINI_API_KEY" not in response.text


@pytest.mark.parametrize("failure,status,code,audit_result", [
    (ProviderRateLimitError("private key and quota detail"), 429, "ASSISTANT_QUOTA_EXCEEDED", "PROVIDER_RATE_LIMITED"),
    (ProviderAuthenticationError("private key and account detail"), 503, "ASSISTANT_CONFIGURATION_ERROR", "PROVIDER_AUTH_ERROR"),
])
def test_gemini_http_quota_and_key_errors_are_safe_and_distinct(cloud_app, failure, status, code, audit_result):
    app, transport = cloud_app
    client, headers = cloud_login(app)
    transport.failure = failure
    response = client.post("/api/assistant/messages", json={"question": "Cần số dư bao nhiêu?"}, headers=headers)
    assert response.status_code == status and response.json["error"]["code"] == code
    assert "private" not in response.text and "key and" not in response.text
    if status == 429:
        assert response.headers["Retry-After"] == "60"
    _, audit = app.extensions["cyberhub_assistant"]
    assert audit.result(response.json["request_id"]) == audit_result


def test_gemini_http_requires_login_and_csrf_before_provider_use(cloud_app):
    app, transport = cloud_app
    before = len(transport.calls)
    response = app.test_client().post("/api/assistant/messages", json={"question": "Cần số dư bao nhiêu?"})
    assert response.status_code in (401, 403)
    client, _ = cloud_login(app)
    response = client.post("/api/assistant/messages", json={"question": "Cần số dư bao nhiêu?"})
    assert response.status_code == 403
    assert len(transport.calls) == before
