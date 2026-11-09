"""Ollama protocol, bounded transport and supporting quote validation, offline."""

from dataclasses import replace
import io
import json
import socket
from urllib.error import HTTPError, URLError

import pytest

from cyberhub_manager.ai.errors import (
    InsufficientContextError, InvalidProviderResponseError, KnowledgeAccessError,
    KnowledgeIndexUnavailableError, ProviderTimeoutError, ProviderUnavailableError,
)
from cyberhub_manager.ai.fakes import FakeEmbeddingProvider
from cyberhub_manager.ai.models import AIAccessContext, KnowledgeDocument
from cyberhub_manager.ai.ollama import OllamaTransport, OllamaEmbeddingProvider, OllamaLLMProvider
from cyberhub_manager.ai.runtime import LiveKnowledgeRetriever


class Transport:
    def __init__(self, result):
        self.result, self.calls = result, []

    def post(self, endpoint, payload):
        self.calls.append((endpoint, payload))
        if payload.get("messages", [{}])[0].get("content", "").startswith("Verify claims"):
            count = len(json.loads(payload["messages"][1]["content"])["evidence"])
            return answer({"checks": [{"passage_meaning": "Supported policy", "claim_meaning": "Supported policy", "supported": True}] * count, "answers_question": True, "safe_scope": True})
        return self.result


QUOTE = "Số dư tối thiểu đủ 30 phút theo đơn giá máy."
PROMPT = f'<request><authorized_context><document ref="S1">{QUOTE}</document></authorized_context></request>'


def answer(value, **changes):
    return {"done": True, "done_reason": "stop", "message": {"content": json.dumps(value)}} | changes


def claim(**changes):
    return {"text": "Cần đủ số dư cho 30 phút.", "ref": "S1", "passage": "S1.P1"} | changes


def generate(value):
    return OllamaLLMProvider(Transport(answer(value))).generate(system_prompt="rules", user_prompt=PROMPT)


def test_generation_uses_schema_native_limits_and_backend_resolved_source_passages():
    transport = Transport(answer({"answerable": True, "claims": [claim()]}))
    result = OllamaLLMProvider(transport).generate(system_prompt="rules", user_prompt=PROMPT)
    assert result == "Cần đủ số dư cho 30 phút. [S1]"
    endpoint, payload = transport.calls[0]
    assert endpoint == "/api/chat"
    assert payload["stream"] is False and payload["think"] is False
    assert payload["options"]["num_predict"] == 768 and payload["options"]["num_ctx"] == 32768
    assert payload["format"]["required"] == ["answerable", "claims"]
    assert "tools" not in payload
    assert payload["messages"][0]["role"] == "system"
    from xml.etree import ElementTree as ET
    assert ET.fromstring(payload["messages"][1]["content"]).findtext("authorized_context/document/passage") == QUOTE


def test_model_can_refuse_without_fabricating_citations():
    with pytest.raises(InsufficientContextError):
        generate({"answerable": False, "claims": []})


def test_semantic_verifier_can_withhold_a_claim_even_with_a_real_quote():
    class Rejecting(Transport):
        def post(self, endpoint, payload):
            if payload.get("messages", [{}])[0].get("content", "").startswith("Verify claims"):
                return answer({"checks": [{"passage_meaning": "Required", "claim_meaning": "Not required", "supported": False}], "answers_question": True, "safe_scope": True})
            return super().post(endpoint, payload)
    provider = OllamaLLMProvider(Rejecting(answer({"answerable": True, "claims": [claim()]})))
    with pytest.raises(InsufficientContextError):
        provider.generate(system_prompt="rules", user_prompt=PROMPT)


@pytest.mark.parametrize("value", [
    {}, {"answerable": "true", "claims": []}, {"answerable": True, "claims": []},
    {"answerable": False, "claims": [claim()]}, {"answerable": True, "claims": [claim()] * 5},
    {"answerable": True, "claims": [claim(ref="S99")]},
    {"answerable": True, "claims": [claim(passage="S1.P999")]},
    {"answerable": True, "claims": [claim(text="abc\nmore")]},
    {"answerable": True, "claims": [claim(text="hello [S1]")]},
    {"answerable": True, "claims": [claim(text=True)]},
    {"answerable": True, "claims": [claim(text="Cần số dư cho 60 phút.")]},
])
def test_malformed_claim_or_invented_source_passage_is_rejected(value):
    with pytest.raises(InvalidProviderResponseError):
        generate(value)


@pytest.mark.parametrize("response", [
    {}, {"done": False}, answer({}, done_reason="length"), {"done": True, "message": {"content": "not json"}},
])
def test_truncated_or_non_json_model_output_is_rejected(response):
    with pytest.raises(InvalidProviderResponseError):
        OllamaLLMProvider(Transport(response)).generate(system_prompt="rules", user_prompt=PROMPT)


def test_embeddings_preserve_order_use_instruction_only_for_query_and_disable_truncation():
    transport = Transport({"embeddings": [[1.0, 0.0]]})
    provider = OllamaEmbeddingProvider(transport)
    assert provider.embed_documents([]) == [] and not transport.calls
    assert provider.embed_documents(["tài liệu"]) == [[1.0, 0.0]]
    assert transport.calls[0][1]["input"] == ["tài liệu"]
    assert provider.embed_query("câu hỏi") == [1.0, 0.0]
    assert transport.calls[-1][1]["input"][0].endswith("Query: câu hỏi")
    assert all(payload["truncate"] is False for _, payload in transport.calls)


@pytest.mark.parametrize("url", ["https://example.com", "http://192.168.0.1", "http://127.0.0.1@evil.test", "http://localhost/foo", "http://localhost?x=1"])
def test_transport_rejects_remote_or_ambiguous_endpoints(url):
    with pytest.raises(ValueError):
        OllamaTransport(url)


@pytest.mark.parametrize("exc, expected", [
    (socket.timeout(), ProviderTimeoutError), (URLError(socket.timeout()), ProviderTimeoutError),
    (URLError("secret"), ProviderUnavailableError), (OSError("secret"), ProviderUnavailableError),
    (HTTPError("url", 500, "secret", None, None), ProviderUnavailableError),
])
def test_native_transport_errors_are_typed_and_do_not_expose_payload(monkeypatch, exc, expected):
    transport = OllamaTransport()
    def fail(*args, **kwargs):
        raise exc
    monkeypatch.setattr(transport._opener, "open", fail)
    with pytest.raises(expected) as error:
        transport.post("/api/chat", {"question": "private"})
    assert "secret" not in str(error.value) and "private" not in str(error.value)


def test_live_retriever_revokes_edited_documents_and_loader_errors():
    doc = KnowledgeDocument("example", "Example", QUOTE, "shared/example.md", ("STAFF",), "APPROVED", 1)
    class Loader:
        documents = [doc]
        fail = False
        def load(self):
            if self.fail:
                raise ValueError("broken metadata")
            return self.documents
    loader = Loader()
    embedding = FakeEmbeddingProvider()
    retriever = LiveKnowledgeRetriever(embedding, loader)
    access = AIAccessContext(1, "STAFF", (1,))
    chunks = retriever.search(question="test", access=access)
    assert chunks
    builds_before = len(embedding.document_calls)
    loader.documents = [replace(doc, audience=("ADMIN",), version=2)]
    with pytest.raises(KnowledgeAccessError):
        retriever.authorize_context(chunks, access)
    assert len(embedding.document_calls) == builds_before
    assert retriever.search(question="test", access=access) == []
    loader.fail = True
    with pytest.raises(KnowledgeIndexUnavailableError):
        retriever.authorize_context(chunks, access)


@pytest.mark.parametrize("name", ["qwen3:cloud", "../model", "remote/model", "model?token=secret"])
def test_cloud_or_path_model_names_rejected(name):
    with pytest.raises(ValueError):
        OllamaLLMProvider(model=name)


def test_vietnamese_claim_is_not_silently_returned_as_an_english_answer():
    provider = OllamaLLMProvider(Transport(answer({'answerable': True, 'claims': [{'english_text': 'Cần đủ số dư cho 30 phút.', 'ref': 'S1', 'passage': 'S1.P1'}]})))
    english_prompt = PROMPT.replace('<request>', '<request language="en">')
    with pytest.raises(InvalidProviderResponseError, match='English'):
        provider.generate(system_prompt='Answer in English', user_prompt=english_prompt)
