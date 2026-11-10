"""Real offline ranking and honest metric denominators, without an answer oracle."""

from dataclasses import replace
import json
from pathlib import Path
import socket

import pytest

from cyberhub_manager.ai.documents import KnowledgeDocumentLoader
from cyberhub_manager.ai.evaluation import EvaluationQuestion, evaluate, load_questions
from cyberhub_manager.ai.lexical import LexicalEmbeddingProvider
from cyberhub_manager.ai.providers import validate_embedding_batch

QUESTIONS = Path(__file__).resolve().parents[1] / "fixtures/ai/evaluation_questions.json"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("offline evaluation must never connect to a network")
    monkeypatch.setattr(socket.socket, "connect", fail)


def test_lexical_provider_uses_corpus_only_and_handles_unaccented_vietnamese():
    provider = LexicalEmbeddingProvider(["Mở phiên máy", "Nạp tiền vào ví"])
    assert provider.embed_query("Mở phiên máy") == provider.embed_query("mo phien may")
    documents = provider.embed_documents(["Mở phiên máy", "Nạp tiền vào ví"])
    assert documents[0] != documents[1]
    assert provider.embed_query("unseenenglishword")[0] > 0
    assert all(vector[0] == 0 for vector in documents)
    assert validate_embedding_batch(documents, expected_count=2) == documents


def test_lexical_unknown_or_punctuation_inputs_have_valid_nonzero_vectors():
    provider = LexicalEmbeddingProvider([])
    assert provider.embed_query("???") == [1.0]
    assert provider.embed_documents([]) == []


@pytest.mark.parametrize("corpus", [None, "text", [""], [None]])
def test_lexical_invalid_corpus_rejected(corpus):
    with pytest.raises(ValueError):
        LexicalEmbeddingProvider(corpus)


@pytest.mark.parametrize("value", [None, "", " "])
def test_lexical_invalid_query_rejected(value):
    with pytest.raises(ValueError):
        LexicalEmbeddingProvider([]).embed_query(value)


def test_committed_evaluation_has_all_roles_languages_and_refusal_cases():
    cases = load_questions(QUESTIONS)
    assert len(cases) == 29
    assert {case.role for case in cases} == {"STAFF", "MANAGER", "ADMIN", "CUSTOMER"}
    assert {case.language for case in cases} == {"vi", "en"}
    assert any(case.expected_source is None for case in cases)
    assert len({case.case_id for case in cases}) == len(cases)


def test_baseline_exposes_threshold_misses_and_does_not_claim_llm_accuracy():
    report = evaluate(load_questions(QUESTIONS))
    assert report["document_count"] == 12 and report["chunk_count"] == 64
    assert report["semantic_llm_evaluated"] is False
    assert report["permission_leaks"] == 0
    assert report["citation_coverage_of_answered"] == 1.0
    assert report["evidence_hit_at_3"] < report["retrieval_hit_at_3"]
    english = next(case for case in report["cases"] if case["case_id"] == "english-password")
    assert not english["grounded"]
    assert report["correct_refusal_rate"] < 1.0  # Honest unresolved negative case.
    assert any(case["expected_source"] is None and not case["correct_refusal"] for case in report["cases"])


def test_customer_session_suggestion_retrieves_public_minimum_balance_evidence():
    case = next(case for case in load_questions(QUESTIONS) if case.case_id == "customer-minimum-session-balance")
    result, = evaluate([case])["cases"]
    assert result["top3_sources"][0] == "shared/faq.md"
    assert result["evidence_hit_at_3"] is True
    assert result["keyword_hits"] == ["30 phút"]
    assert result["permission_leaks"] == 0


def test_expected_labels_cannot_influence_ranking_or_provider_responses():
    case = load_questions(QUESTIONS)[0]
    changed = replace(case, expected_source=None, expected_keywords=("invented-answer-key",))
    left = evaluate([case])["cases"][0]
    right = evaluate([changed])["cases"][0]
    assert left["top3_sources"] == right["top3_sources"]
    assert left["top3_scores"] == right["top3_scores"]
    assert left["citation_sources"] == right["citation_sources"]


def test_fixture_cannot_declare_private_or_draft_source_as_valid_staff_answer():
    case = load_questions(QUESTIONS)[0]
    with pytest.raises(ValueError, match="unapproved or unauthorized"):
        evaluate([replace(case, expected_source="admin/system-configuration.md")])
    with pytest.raises(ValueError, match="unapproved or unauthorized"):
        evaluate([replace(case, expected_source="manager/revenue-policy.md")])


@pytest.mark.parametrize("change", [
    {"role": "ROOT"}, {"language": "fr"}, {"question": ""},
    {"expected_source": "../../.env"}, {"expected_source": "/secret.md"},
    {"expected_keywords": "not a list"}, {"unexpected": True},
])
def test_invalid_fixture_metadata_is_rejected(tmp_path, change):
    item = json.loads(QUESTIONS.read_text(encoding="utf-8"))[0] | change
    path = tmp_path / "questions.json"
    path.write_text(json.dumps([item]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_questions(path)


def test_duplicate_case_ids_are_rejected(tmp_path):
    item = json.loads(QUESTIONS.read_text(encoding="utf-8"))[0]
    path = tmp_path / "questions.json"
    path.write_text(json.dumps([item, item]), encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_questions(path)


def test_empty_evaluation_is_not_reported_as_perfect():
    with pytest.raises(ValueError):
        evaluate([])
