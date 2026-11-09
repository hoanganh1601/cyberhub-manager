"""Small in-memory cosine index and role-filtered knowledge retrieval.

Static 5A documents have explicit audiences, not live store/account data. An
AIAccessContext must already be authenticated by a backend adapter. This module
does not turn caller-supplied role/store values into a trustworthy identity.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import math
from threading import RLock

from .chunking import MarkdownChunker
from .documents import KnowledgeDocumentLoader
from .errors import (
    DuplicateDocumentError,
    InvalidQuestionError,
    KnowledgeAccessError,
    KnowledgeIndexUnavailableError,
)
from .models import AIAccessContext, KnowledgeChunk, KnowledgeDocument
from .providers import EmbeddingProvider, validate_embedding, validate_embedding_batch


def normalize_question(question: str, *, max_chars: int = 2000) -> str:
    if type(max_chars) is not int or max_chars <= 0:
        raise ValueError("max_chars must be a positive integer")
    if not isinstance(question, str) or not question.strip() or len(question) > max_chars:
        raise InvalidQuestionError("question must be non-blank text within the input limit")
    return question.strip()


def is_allowed(chunk: KnowledgeChunk, access: AIAccessContext) -> bool:
    """No implicit ADMIN/role inheritance, store-data access or language filter."""
    if not isinstance(chunk, KnowledgeChunk) or not isinstance(access, AIAccessContext):
        raise TypeError("chunk and access must use the validated RAG contracts")
    return access.role in chunk.audience


def _unit(vector: list[float]) -> tuple[float, ...]:
    # Scaling before hypot avoids overflow/underflow for finite extreme vectors.
    scale = max(abs(value) for value in vector)
    scaled = [value / scale for value in vector]
    magnitude = math.hypot(*scaled)
    return tuple(value / magnitude for value in scaled)


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    score = math.fsum(a * b for a, b in zip(left, right, strict=True))
    return max(-1.0, min(1.0, score))


@dataclass(frozen=True)
class RetrievalMatch:
    chunk: KnowledgeChunk
    score: float


@dataclass(frozen=True)
class _Entry:
    chunk: KnowledgeChunk
    vector: tuple[float, ...]


@dataclass(frozen=True)
class _Snapshot:
    entries: tuple[_Entry, ...]
    dimensions: int | None
    embedding: EmbeddingProvider


class CosineKnowledgeIndex:
    """An all-or-nothing snapshot; a failed reload leaves the index unavailable.

    Rebuilds are serialized, and old snapshots are invalidated before reading
    sources or calling embeddings. No persistence or incremental append is used.
    """

    def __init__(self) -> None:
        self._snapshot: _Snapshot | None = None
        self._state_lock = RLock()
        self._build_lock = RLock()

    def clear(self) -> None:
        with self._build_lock, self._state_lock:
            self._snapshot = None

    def rebuild(
        self,
        documents: Iterable[KnowledgeDocument],
        *,
        embedding: EmbeddingProvider,
        chunker: MarkdownChunker | None = None,
    ) -> None:
        with self._build_lock:
            self.clear()
            splitter = chunker if chunker is not None else MarkdownChunker()
            chunks = []
            document_ids: set[str] = set()
            chunk_ids: set[str] = set()
            for document in documents:
                if not isinstance(document, KnowledgeDocument):
                    raise TypeError("index inputs must be KnowledgeDocument objects")
                if document.document_id in document_ids:
                    raise DuplicateDocumentError("duplicate document ID during rebuild")
                document_ids.add(document.document_id)
                for chunk in splitter.split(document):
                    if chunk.chunk_id in chunk_ids:
                        raise DuplicateDocumentError("duplicate chunk ID during rebuild")
                    chunk_ids.add(chunk.chunk_id)
                    chunks.append(chunk)
            vectors = validate_embedding_batch(
                embedding.embed_documents([chunk.content for chunk in chunks]) if chunks else [],
                expected_count=len(chunks),
            )
            snapshot = _Snapshot(
                entries=tuple(_Entry(chunk, _unit(vector)) for chunk, vector in zip(chunks, vectors)),
                dimensions=len(vectors[0]) if vectors else None,
                embedding=embedding,
            )
            with self._state_lock:
                self._snapshot = snapshot

    def _read(self) -> _Snapshot:
        with self._state_lock:
            if self._snapshot is None:
                raise KnowledgeIndexUnavailableError("a complete knowledge index is unavailable")
            return self._snapshot

    def _assert_current(self, snapshot: _Snapshot) -> None:
        with self._state_lock:
            if self._snapshot is not snapshot:
                raise KnowledgeIndexUnavailableError("knowledge changed; retrieve context again")

    def search(
        self,
        *,
        question: str,
        access: AIAccessContext,
        embedding: EmbeddingProvider,
        limit: int = 5,
    ) -> list[RetrievalMatch]:
        question = normalize_question(question)
        if not isinstance(access, AIAccessContext):
            raise TypeError("access must be a backend-validated AIAccessContext")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("limit must be an integer from 1 to 20")
        snapshot = self._read()
        if snapshot.embedding is not embedding:
            raise KnowledgeIndexUnavailableError("embedding provider changed; rebuild the index")
        # Filter BEFORE query/scoring/top-k. Never let a high-scoring forbidden
        # chunk displace authorized results or reach the prompt/LLM.
        allowed = [entry for entry in snapshot.entries if is_allowed(entry.chunk, access)]
        if not allowed:
            self._assert_current(snapshot)
            return []
        query = _unit(validate_embedding(
            embedding.embed_query(question), expected_dimensions=snapshot.dimensions,
        ))
        matches = [RetrievalMatch(entry.chunk, _cosine(query, entry.vector)) for entry in allowed]
        matches.sort(key=lambda match: (-match.score, match.chunk.chunk_id))
        self._assert_current(snapshot)
        return matches[:limit]

    def authorize_context(
        self,
        chunks: Iterable[KnowledgeChunk],
        access: AIAccessContext,
    ) -> tuple[KnowledgeChunk, ...]:
        """Recheck role and exact current metadata/content, not just chunk IDs."""
        if not isinstance(access, AIAccessContext):
            raise TypeError("access must be a backend-validated AIAccessContext")
        snapshot = self._read()
        current = {entry.chunk.chunk_id: entry.chunk for entry in snapshot.entries}
        result = []
        seen: set[str] = set()
        for chunk in chunks:
            if (
                not isinstance(chunk, KnowledgeChunk)
                or current.get(chunk.chunk_id) != chunk
                or not is_allowed(chunk, access)
            ):
                raise KnowledgeAccessError("context is unauthorized or no longer current")
            if chunk.chunk_id not in seen:
                result.append(chunk)
                seen.add(chunk.chunk_id)
        self._assert_current(snapshot)
        return tuple(result)


    def related_context(self, chunks, access, *, max_documents=2, max_chunks=16):
        """Expand only selected authorized parent documents in source order."""
        snapshot = self._read()
        selected = self.authorize_context(chunks, access)
        self._assert_current(snapshot)
        ids = list(dict.fromkeys(chunk.document_id for chunk in selected))[:max_documents]
        expanded = [entry.chunk for document_id in ids for entry in snapshot.entries
                    if entry.chunk.document_id == document_id and is_allowed(entry.chunk, access)]
        if len(expanded) > max_chunks:
            from .errors import ContextBudgetError
            raise ContextBudgetError("related document context exceeds the chunk budget")
        self._assert_current(snapshot)
        return self.authorize_context(expanded, access)


class KnowledgeRetriever:
    """One injected embedding provider for both rebuilding and querying."""

    def __init__(
        self,
        embedding: EmbeddingProvider,
        *,
        index: CosineKnowledgeIndex | None = None,
    ) -> None:
        self._embedding = embedding
        self._index = index if index is not None else CosineKnowledgeIndex()

    def rebuild(self, documents: Iterable[KnowledgeDocument]) -> None:
        self._index.rebuild(documents, embedding=self._embedding)

    def refresh(self, loader: KnowledgeDocumentLoader) -> None:
        # Defer loader access until rebuild has invalidated the old snapshot.
        def documents():
            yield from loader.load()

        self.rebuild(documents())

    def search(
        self, *, question: str, access: AIAccessContext, limit: int = 5,
    ) -> list[KnowledgeChunk]:
        return [match.chunk for match in self.search_scored(question=question, access=access, limit=limit)]

    def search_scored(
        self, *, question: str, access: AIAccessContext, limit: int = 5,
    ) -> list[RetrievalMatch]:
        """Expose cosine scores for step 8's evidence threshold, not probabilities."""
        return self._index.search(
            question=question, access=access, embedding=self._embedding, limit=limit,
        )

    def authorize_context(
        self, chunks: Iterable[KnowledgeChunk], access: AIAccessContext,
    ) -> tuple[KnowledgeChunk, ...]:
        return self._index.authorize_context(chunks, access)

    def expand_context(self, chunks, access):
        """Default keeps the selected evidence unchanged; local runtime may expand it."""
        return self.authorize_context(chunks, access)
