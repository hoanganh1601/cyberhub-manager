"""Explicit composition for local RAG; feature stays off unless configured."""

import os
from threading import RLock

from .documents import KnowledgeDocumentLoader
from .errors import KnowledgeAccessError, KnowledgeIndexUnavailableError, ProviderBusyError
from .ollama import OllamaEmbeddingProvider, OllamaLLMProvider, OllamaTransport
from .retrieval import KnowledgeRetriever
from .service import RAGAssistantService


class LiveKnowledgeRetriever(KnowledgeRetriever):
    """Reload edited/revoked corpus before retrieval and every context check."""

    def __init__(self, embedding, loader):
        super().__init__(embedding)
        self.loader = loader
        self._documents = None
        self._reload_lock = RLock()
        self._reload()

    def _reload(self):
        with self._reload_lock:
            try:
                documents = tuple(self.loader.load())
                if documents != self._documents:
                    self.rebuild(documents)
                    self._documents = documents
            except Exception:
                self._index.clear()
                self._documents = None
                raise KnowledgeIndexUnavailableError("approved corpus cannot be refreshed") from None

    def search_scored(self, **kwargs):
        self._reload()
        return super().search_scored(**kwargs)

    def _check_current(self):
        # Authorization must never start an embedding/rebuild outside the bounded
        # retrieval worker. A corpus change invalidates this answer immediately;
        # the next search may rebuild through its normal deadline/capacity gate.
        if not self._reload_lock.acquire(blocking=False):
            raise ProviderBusyError("knowledge refresh is in progress")
        try:
            try:
                documents = tuple(self.loader.load())
            except Exception:
                self._index.clear()
                self._documents = None
                raise KnowledgeIndexUnavailableError("approved corpus cannot be checked") from None
            if documents != self._documents:
                self._index.clear()
                self._documents = None
                raise KnowledgeAccessError("approved corpus changed during this request")
        finally:
            self._reload_lock.release()

    def authorize_context(self, chunks, access):
        self._check_current()
        return super().authorize_context(chunks, access)

    def expand_context(self, chunks, access):
        self._check_current()
        # Parent-document context supplies conditions/exceptions separated by
        # headings. Only the top two already-authorized document IDs are expanded.
        expanded = self._index.related_context(chunks, access)
        return self.authorize_context(expanded, access)


def local_service_factory(audit_sink):
    transport = OllamaTransport(os.getenv("CYBERHUB_OLLAMA_URL", "http://127.0.0.1:11435"), timeout=30)
    embedding = OllamaEmbeddingProvider(transport, model=os.getenv("CYBERHUB_EMBEDDING_MODEL", "qwen3-embedding:0.6b"))
    llm = OllamaLLMProvider(transport, model=os.getenv("CYBERHUB_LLM_MODEL", "qwen3:8b"))
    # Warmup is bounded startup work, not an unaudited user question/model retry.
    warmup = OllamaTransport(transport.base_url, timeout=120)
    warmup.post("/api/embed", {"model": embedding.model, "input": ["CyberHub startup"], "truncate": False, "keep_alive": "30m"})
    warmup.post("/api/chat", {"model": llm.model, "messages": [], "stream": False, "keep_alive": "30m", "options": {"num_ctx": 32768}})
    knowledge_root = os.getenv("CYBERHUB_KNOWLEDGE_ROOT")
    loader = KnowledgeDocumentLoader(knowledge_root=knowledge_root) if knowledge_root else KnowledgeDocumentLoader()
    retriever = LiveKnowledgeRetriever(embedding, loader)
    # Threshold calibrated on development; supplemental cases are diagnostic regression.
    return RAGAssistantService(retriever, llm, audit=audit_sink, min_similarity=0.53, limit=4, context_limit=16, timeout_seconds=40,
                               max_context_chars=14000, max_prompt_chars=18000)


def configure_local_assistant(app):
    if os.getenv("CYBERHUB_ASSISTANT_ENABLED", "false").lower() == "true":
        path = os.getenv("CYBERHUB_ASSISTANT_AUDIT_PATH")
        if not path:
            raise ValueError("set a private persistent CYBERHUB_ASSISTANT_AUDIT_PATH")
        app.config.update(ASSISTANT_ENABLED=True, ASSISTANT_SERVICE_FACTORY=local_service_factory,
                          ASSISTANT_AUDIT_PATH=path)
