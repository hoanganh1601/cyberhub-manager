"""API composition and live knowledge revocation, without credentials or network."""

from dataclasses import replace

import pytest

from cyberhub_manager.ai.errors import KnowledgeAccessError, KnowledgeIndexUnavailableError
from cyberhub_manager.ai.fakes import FakeEmbeddingProvider
from cyberhub_manager.ai.models import AIAccessContext, KnowledgeDocument
from cyberhub_manager.ai.runtime import LiveKnowledgeRetriever, configure_assistant


def test_live_retriever_revokes_edited_documents_and_loader_errors():
    doc = KnowledgeDocument("example", "Example", "Số dư tối thiểu đủ 30 phút theo đơn giá máy.",
                            "shared/example.md", ("STAFF",), "APPROVED", 1)
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


def test_unknown_provider_is_rejected_before_network_or_app_configuration(monkeypatch):
    from flask import Flask
    monkeypatch.setenv("CYBERHUB_ASSISTANT_ENABLED", "true")
    monkeypatch.setenv("CYBERHUB_ASSISTANT_PROVIDER", "unsupported")
    app = Flask(__name__)
    with pytest.raises(ValueError, match="only the Gemini API"):
        configure_assistant(app)
    assert "ASSISTANT_SERVICE_FACTORY" not in app.config
