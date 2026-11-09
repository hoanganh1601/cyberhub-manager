"""Deterministic providers for tests/demos, without AI SDKs or network calls.

These fakes are not real embeddings or an answering model. Configure vectors
explicitly for retrieval tests; the default constant vector cannot measure
semantic relevance. Prompt/input call history is held in memory for tests only,
not suitable for production audit logs containing private data.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .audit import AssistantAuditEvent
from .errors import ProviderError, ProviderUnavailableError
from .providers import validate_embedding, validate_generation


def _input_text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("provider input must be non-blank text")


def _error(value: ProviderError | None) -> None:
    if value is not None and not isinstance(value, ProviderError):
        raise ValueError("error must be a ProviderError or None")


class FakeEmbeddingProvider:
    """Return explicit per-text vectors, or a constant unit vector by default.

    If a mapping is supplied, unknown inputs fail rather than silently matching
    everything. Both document and query calls share that same vector space.
    Returned vectors and recorded batches cannot mutate configured fixtures.
    """

    def __init__(
        self,
        *,
        dimensions: int = 2,
        vectors: Mapping[str, list[float]] | None = None,
        error: ProviderError | None = None,
    ) -> None:
        if type(dimensions) is not int or dimensions <= 0:
            raise ValueError("dimensions must be a positive integer")
        if vectors is not None and not isinstance(vectors, Mapping):
            raise ValueError("vectors must be a mapping or None")
        _error(error)
        self._dimensions = dimensions
        self._error = error
        self._vectors = None
        if vectors is not None:
            self._vectors = {}
            for text, vector in vectors.items():
                _input_text(text)
                self._vectors[text] = tuple(validate_embedding(
                    vector, expected_dimensions=dimensions,
                ))
        self.document_calls: list[tuple[str, ...]] = []
        self.query_calls: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list):
            raise ValueError("texts must be a list of non-blank strings")
        for text in texts:
            _input_text(text)
        self.document_calls.append(tuple(texts))
        if not texts:
            return []
        if self._error is not None:
            raise self._error
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        _input_text(text)
        self.query_calls.append(text)
        if self._error is not None:
            raise self._error
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        if self._vectors is None:
            return [1.0] + [0.0] * (self._dimensions - 1)
        try:
            return list(self._vectors[text])
        except KeyError:
            raise ProviderUnavailableError("no fake embedding configured for this input") from None


@dataclass(frozen=True)
class GenerationCall:
    system_prompt: str
    user_prompt: str


class FakeLLMProvider:
    """Return fixed text or simulate a typed provider failure, without retries."""

    def __init__(
        self,
        *,
        response: str = "Câu trả lời thử nghiệm.",
        error: ProviderError | None = None,
    ) -> None:
        self._response = validate_generation(response)
        _error(error)
        self._error = error
        self.calls: list[GenerationCall] = []

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        _input_text(system_prompt)
        _input_text(user_prompt)
        self.calls.append(GenerationCall(system_prompt, user_prompt))
        if self._error is not None:
            raise self._error
        return self._response


class InMemoryAssistantAuditSink:
    """Test-only audit sink, deliberately without persistence or prompt storage."""

    def __init__(self) -> None:
        self.events: list[AssistantAuditEvent] = []

    def record(self, event: AssistantAuditEvent) -> None:
        self.events.append(event)
