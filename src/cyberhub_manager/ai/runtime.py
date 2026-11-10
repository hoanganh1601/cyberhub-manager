"""API-key RAG composition; credentials and provider selection are backend-only."""

import os
from threading import RLock

from .documents import KnowledgeDocumentLoader
from .errors import KnowledgeAccessError, KnowledgeIndexUnavailableError, ProviderBusyError, ProviderError
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
            except ProviderError:
                self._index.clear()
                self._documents = None
                raise
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


def gemini_service_factory(audit_sink):
    from .gemini import GeminiEmbeddingProvider, GeminiLLMProvider, GeminiTransport

    transport = GeminiTransport(os.getenv("GEMINI_API_KEY", ""), timeout=30)
    embedding = GeminiEmbeddingProvider(transport, model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"))
    llm = GeminiLLMProvider(transport, model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"))
    knowledge_root = os.getenv("CYBERHUB_KNOWLEDGE_ROOT")
    loader = KnowledgeDocumentLoader(knowledge_root=knowledge_root) if knowledge_root else KnowledgeDocumentLoader()
    retriever = LiveKnowledgeRetriever(embedding, loader)
    # Embedding scores are model-specific; this cloud threshold is configurable
    # and must be evaluated against a real key before claiming semantic accuracy.
    minimum = float(os.getenv("CYBERHUB_GEMINI_MIN_SIMILARITY", "0.6"))
    return RAGAssistantService(retriever, llm, audit=audit_sink, min_similarity=minimum,
                               limit=4, context_limit=16, timeout_seconds=60,
                               max_context_chars=14000, max_prompt_chars=18000)


def configure_assistant(app):
    from dotenv import load_dotenv

    load_dotenv()
    if os.getenv("CYBERHUB_ASSISTANT_ENABLED", "false").lower() == "true":
        provider = os.getenv("CYBERHUB_ASSISTANT_PROVIDER", "gemini").strip().lower()
        if provider != "gemini":
            raise ValueError("only the Gemini API is supported; set CYBERHUB_ASSISTANT_PROVIDER=gemini")
        path = os.getenv("CYBERHUB_ASSISTANT_AUDIT_PATH")
        if not path:
            raise ValueError("set a private persistent CYBERHUB_ASSISTANT_AUDIT_PATH")
        app.config.update(ASSISTANT_ENABLED=True, ASSISTANT_SERVICE_FACTORY=gemini_service_factory,
                          ASSISTANT_AUDIT_PATH=path)
