"""Cosine relevance, role isolation, revocation and complete-snapshot semantics."""

from dataclasses import replace
import math
import socket
from threading import Event, Thread

import pytest

from cyberhub_manager.ai.chunking import MarkdownChunker
from cyberhub_manager.ai.documents import KnowledgeDocumentLoader
from cyberhub_manager.ai.errors import (
    ChunkingError, DuplicateDocumentError, InvalidMetadataError,
    InvalidProviderResponseError, InvalidQuestionError, KnowledgeAccessError,
    KnowledgeIndexUnavailableError, ProviderTimeoutError,
)
from cyberhub_manager.ai.fakes import FakeEmbeddingProvider
from cyberhub_manager.ai.models import AIAccessContext, KnowledgeDocument
from cyberhub_manager.ai.retrieval import (
    CosineKnowledgeIndex, KnowledgeRetriever, is_allowed, normalize_question,
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("retrieval tests must not use the network")
    monkeypatch.setattr(socket.socket, "connect", fail)


def actor(role="STAFF", **changes):
    return AIAccessContext(**(dict(actor_id=1, role=role, store_ids=(1,)) | changes))


def document(document_id="staff-rule", audience=("STAFF",), **changes):
    return KnowledgeDocument(**(dict(
        document_id=document_id, title="Quy trình", content=f"Nội dung {document_id}.",
        source=f"shared/{document_id}.md", audience=audience,
        status="APPROVED", version=1,
    ) | changes))


def prepared(documents, vectors=None, query=None, *, index=None):
    chunks = [chunk for doc in documents for chunk in MarkdownChunker().split(doc)]
    vectors = vectors if vectors is not None else [[1.0, 0.0] for _ in chunks]
    mapping = {chunk.content: vector for chunk, vector in zip(chunks, vectors, strict=True)}
    mapping["question"] = query if query is not None else [1.0, 0.0]
    provider = FakeEmbeddingProvider(vectors=mapping)
    retriever = KnowledgeRetriever(provider, index=index)
    retriever.rebuild(documents)
    return retriever, provider, chunks


@pytest.mark.parametrize("role", ["CUSTOMER", "STAFF", "MANAGER", "ADMIN"])
@pytest.mark.parametrize("audience", ["CUSTOMER", "STAFF", "MANAGER", "ADMIN"])
def test_explicit_audience_matrix_has_no_implicit_role_inheritance(role, audience):
    doc = document(audience=(audience,))
    retriever, provider, chunks = prepared([doc])
    result = retriever.search(question="question", access=actor(role))
    assert result == (chunks if role == audience else [])
    assert provider.query_calls == (["question"] if role == audience else [])


def test_staff_cannot_retrieve_manager_document_even_when_it_scores_highest(monkeypatch):
    import cyberhub_manager.ai.retrieval as module
    docs = [
        document("staff", ("STAFF",)), document("manager", ("MANAGER", "ADMIN")),
        document("shared", ("STAFF", "MANAGER", "ADMIN", "CUSTOMER")),
    ]
    retriever, _, _ = prepared(docs, [[0.5, 0.5], [1.0, 0.0], [0.1, 1.0]])
    scored = []
    original = module._cosine
    monkeypatch.setattr(module, "_cosine", lambda a, b: scored.append(b) or original(a, b))
    matches = retriever.search_scored(question="question", access=actor(), limit=1)
    assert len(scored) == 2  # The forbidden vector never reaches cosine scoring.
    assert [match.chunk.document_id for match in matches] == ["staff"]
    assert matches[0].score == pytest.approx(math.sqrt(0.5))


def test_admin_can_retrieve_admin_document_and_language_does_not_grant_permissions():
    retriever, _, chunks = prepared([document("admin", ("ADMIN",))])
    assert retriever.search(question="question", access=actor("ADMIN", language="en")) == chunks
    assert retriever.search(question="question", access=actor("CUSTOMER", language="en")) == []


def test_static_knowledge_does_not_require_or_grant_live_store_data_access():
    retriever, _, chunks = prepared([document()])
    assert retriever.search(question="question", access=actor(store_ids=())) == chunks
    assert retriever.search(question="question", access=actor(store_ids=(99,))) == chunks


def test_cosine_scores_and_deterministic_ties_are_not_raw_dot_products():
    docs = [document("a"), document("b"), document("c"), document("d")]
    retriever, _, _ = prepared(docs, [[10.0, 0.0], [1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]])
    result = retriever.search_scored(question="question", access=actor())
    assert [match.score for match in result] == pytest.approx([1.0, 1.0, 0.0, -1.0])
    assert result[0].chunk.chunk_id < result[1].chunk.chunk_id
    assert result == retriever.search_scored(question="question", access=actor())


@pytest.mark.parametrize("size", [1e308, 1e-308])
def test_cosine_is_finite_for_extreme_nonzero_coordinates(size):
    retriever, _, _ = prepared([document()], [[size, size]], [size, -size])
    match, = retriever.search_scored(question="question", access=actor())
    assert math.isfinite(match.score)
    assert match.score == pytest.approx(0.0)


def test_empty_successful_rebuild_returns_no_context_without_querying_provider():
    retriever, provider, _ = prepared([])
    assert provider.document_calls == []
    assert retriever.search(question="question", access=actor()) == []
    assert provider.query_calls == []


def test_uninitialized_index_cannot_serve():
    with pytest.raises(KnowledgeIndexUnavailableError):
        KnowledgeRetriever(FakeEmbeddingProvider()).search(question="question", access=actor())


def test_rebuild_replaces_old_docs_audiences_and_versions():
    original = document()
    index = CosineKnowledgeIndex()
    retriever, _, chunks = prepared([original], index=index)
    old = chunks[0]
    updated = replace(original, audience=("ADMIN",), version=2)
    current, _, new_chunks = prepared([updated], index=index)
    assert current.search(question="question", access=actor()) == []
    assert current.search(question="question", access=actor("ADMIN")) == new_chunks
    with pytest.raises(KnowledgeAccessError):
        current.authorize_context([old], actor("ADMIN"))
    current.rebuild([])
    assert current.search(question="question", access=actor("ADMIN")) == []


@pytest.mark.parametrize("bad_vectors", [[], [[0.0, 0.0]], [[math.nan, 0.0]], [[1.0], [1.0]]])
def test_invalid_rebuild_does_not_leave_old_or_partial_index(monkeypatch, bad_vectors):
    retriever, provider, _ = prepared([document()])
    monkeypatch.setattr(provider, "embed_documents", lambda texts: bad_vectors)
    with pytest.raises(InvalidProviderResponseError):
        retriever.rebuild([document()])
    with pytest.raises(KnowledgeIndexUnavailableError):
        retriever.search(question="question", access=actor())


def test_provider_failure_during_rebuild_invalidates_old_index(monkeypatch):
    retriever, provider, _ = prepared([document()])
    def fail(texts):
        raise ProviderTimeoutError("Test timeout")
    monkeypatch.setattr(provider, "embed_documents", fail)
    with pytest.raises(ProviderTimeoutError):
        retriever.rebuild([document()])
    with pytest.raises(KnowledgeIndexUnavailableError):
        retriever.search(question="question", access=actor())


@pytest.mark.parametrize("status", ["DRAFT", "ARCHIVED"])
def test_direct_rebuild_of_unapproved_document_is_rejected(status):
    retriever, _, _ = prepared([document()])
    with pytest.raises(ChunkingError):
        retriever.rebuild([document(status=status)])
    with pytest.raises(KnowledgeIndexUnavailableError):
        retriever.search(question="question", access=actor())


def test_duplicate_document_ids_fail_before_embedding():
    provider = FakeEmbeddingProvider()
    retriever = KnowledgeRetriever(provider)
    with pytest.raises(DuplicateDocumentError):
        retriever.rebuild([document(), document(version=2)])
    assert provider.document_calls == []


def test_provider_instance_change_requires_rebuilding_index():
    index = CosineKnowledgeIndex()
    prepared([document()], index=index)
    replacement = KnowledgeRetriever(FakeEmbeddingProvider(), index=index)
    with pytest.raises(KnowledgeIndexUnavailableError, match="provider changed"):
        replacement.search(question="question", access=actor())


def test_inflight_search_cannot_return_old_snapshot_after_rebuild(monkeypatch):
    index = CosineKnowledgeIndex()
    retriever, provider, _ = prepared([document()], index=index)
    def query(text):
        index.clear()
        return [1.0, 0.0]
    monkeypatch.setattr(provider, "embed_query", query)
    with pytest.raises(KnowledgeIndexUnavailableError, match="knowledge changed"):
        retriever.search(question="question", access=actor())


@pytest.mark.parametrize("vector", [[1.0], [math.inf, 0.0], [0.0, 0.0]])
def test_invalid_query_vector_never_produces_search_results(monkeypatch, vector):
    retriever, provider, _ = prepared([document()])
    monkeypatch.setattr(provider, "embed_query", lambda text: vector)
    with pytest.raises(InvalidProviderResponseError):
        retriever.search(question="question", access=actor())


@pytest.mark.parametrize("limit", [0, -1, 21, True, "5"])
def test_invalid_limit_is_rejected_before_query(limit):
    retriever, provider, _ = prepared([document()])
    with pytest.raises(ValueError):
        retriever.search(question="question", access=actor(), limit=limit)
    assert provider.query_calls == []


@pytest.mark.parametrize("question", [None, "", " \n ", "x" * 2001])
def test_invalid_question_is_rejected_before_query(question):
    retriever, provider, _ = prepared([document()])
    with pytest.raises(InvalidQuestionError):
        retriever.search(question=question, access=actor())
    assert provider.query_calls == []


def test_question_is_trimmed_before_embedding():
    retriever, provider, _ = prepared([document()])
    retriever.search(question="  question\n", access=actor())
    assert provider.query_calls == ["question"]


def test_client_dictionary_is_not_accepted_as_trusted_access():
    retriever, provider, chunks = prepared([document()])
    with pytest.raises(TypeError):
        retriever.search(question="question", access={"role": "ADMIN"})
    with pytest.raises(TypeError):
        is_allowed(chunks[0], {"role": "ADMIN"})
    assert provider.query_calls == []


def test_refresh_loader_failure_and_revocation_clear_old_snapshot(tmp_path):
    root = tmp_path / "knowledge"
    root.mkdir()
    path = root / "policy.md"
    markdown = """---
id: policy
title: Policy
audience: [STAFF]
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-09
tags: []
---
Approved business rule.
"""
    loader = KnowledgeDocumentLoader(knowledge_root=root)
    retriever = KnowledgeRetriever(FakeEmbeddingProvider())
    path.write_text(markdown, encoding="utf-8")
    retriever.refresh(loader)
    assert retriever.search(question="question", access=actor())
    path.write_text("invalid metadata", encoding="utf-8")
    with pytest.raises(InvalidMetadataError):
        retriever.refresh(loader)
    with pytest.raises(KnowledgeIndexUnavailableError):
        retriever.search(question="question", access=actor())
    path.write_text(markdown.replace("APPROVED", "ARCHIVED"), encoding="utf-8")
    retriever.refresh(loader)
    assert retriever.search(question="question", access=actor()) == []


def test_real_corpus_role_isolation_and_draft_exclusion():
    retriever = KnowledgeRetriever(FakeEmbeddingProvider())
    retriever.refresh(KnowledgeDocumentLoader())
    for role in ("CUSTOMER", "STAFF", "MANAGER", "ADMIN"):
        chunks = retriever.search(question="Cách dùng CyberHub?", access=actor(role), limit=20)
        assert chunks
        assert all(role in chunk.audience for chunk in chunks)
        assert all(chunk.source not in {"shared/role-policy.md", "manager/revenue-policy.md"} for chunk in chunks)
        assert retriever.authorize_context(chunks, actor(role)) == tuple(chunks)


def test_normalization_rejects_invalid_configuration():
    with pytest.raises(ValueError):
        normalize_question("question", max_chars=True)


def test_rebuild_revokes_audience_even_if_editor_forgets_version_bump():
    original = document()
    retriever = KnowledgeRetriever(FakeEmbeddingProvider())
    retriever.rebuild([original])
    old = retriever.search(question="question", access=actor())
    retriever.rebuild([replace(original, audience=("ADMIN",))])
    assert retriever.search(question="question", access=actor()) == []
    with pytest.raises(KnowledgeAccessError):
        retriever.authorize_context(old, actor())


def test_concurrent_rebuilds_are_serialized_and_partial_index_is_unavailable(monkeypatch):
    provider = FakeEmbeddingProvider()
    retriever = KnowledgeRetriever(provider)
    retriever.rebuild([document("initial")])
    entered, release, second_started = Event(), Event(), Event()
    failures = []
    original = provider.embed_documents
    def embed(texts):
        if any("slow" in text for text in texts):
            entered.set()
            if not release.wait(timeout=5):
                raise AssertionError("test did not release rebuild")
        return original(texts)
    monkeypatch.setattr(provider, "embed_documents", embed)
    def rebuild(name):
        if name == "latest":
            second_started.set()
        try:
            retriever.rebuild([document(name)])
        except Exception as exc:
            failures.append(exc)
    first = Thread(target=rebuild, args=("slow",))
    second = Thread(target=rebuild, args=("latest",))
    first.start()
    try:
        assert entered.wait(timeout=5)
        second.start()
        assert second_started.wait(timeout=5)
        with pytest.raises(KnowledgeIndexUnavailableError):
            retriever.search(question="question", access=actor())
    finally:
        release.set()
        first.join(timeout=5)
        if second.ident is not None:
            second.join(timeout=5)
    assert not first.is_alive() and not second.is_alive()
    assert failures == []
    assert [chunk.document_id for chunk in retriever.search(question="question", access=actor())] == ["latest"]


def test_parent_context_preserves_conditions_and_never_expands_other_documents_or_roles():
    docs = [document('procedure', content='# Procedure\n\n## Eligibility\nValid account required.\n\n## Exception\nNever skip identity checks.'),
            document('unrelated'), document('private', ('ADMIN',))]
    index = CosineKnowledgeIndex()
    retriever, _, chunks = prepared(docs, index=index)
    selected = next(chunk for chunk in chunks if chunk.document_id == 'procedure')
    expanded = index.related_context([selected], actor())
    assert all(chunk.document_id == 'procedure' for chunk in expanded)
    assert 'Never skip identity checks.' in '\n'.join(chunk.content for chunk in expanded)
    forbidden = next(chunk for chunk in chunks if chunk.document_id == 'private')
    with pytest.raises(KnowledgeAccessError):
        index.related_context([forbidden], actor())
    retriever.rebuild([replace(docs[0], audience=('ADMIN',), version=2)])
    with pytest.raises(KnowledgeAccessError):
        index.related_context([selected], actor())
