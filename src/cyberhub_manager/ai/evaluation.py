"""Offline retrieval and citation-envelope evaluation, never LLM certification."""

from dataclasses import asdict, dataclass
import json
from pathlib import Path, PurePosixPath
import time
from xml.etree import ElementTree as ET

from .chunking import MarkdownChunker
from .documents import KnowledgeDocumentLoader
from .fakes import InMemoryAssistantAuditSink
from .lexical import LexicalEmbeddingProvider
from .models import AIAccessContext, Language, Role
from .retrieval import KnowledgeRetriever
from .service import RAGAssistantService


@dataclass(frozen=True)
class EvaluationQuestion:
    case_id: str
    question: str
    role: Role
    language: Language
    expected_source: str | None
    expected_keywords: tuple[str, ...]


def load_questions(path: str | Path) -> list[EvaluationQuestion]:
    items = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        raise ValueError("evaluation must contain a non-empty list")
    result, seen = [], set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {
            "case_id", "question", "role", "language", "expected_source", "expected_keywords",
        }:
            raise ValueError("invalid evaluation case fields")
        if not isinstance(item["case_id"], str) or not item["case_id"].strip() or item["case_id"] in seen:
            raise ValueError("case IDs must be unique non-blank strings")
        seen.add(item["case_id"])
        AIAccessContext(actor_id=1, role=item["role"], store_ids=(), language=item["language"])
        if not isinstance(item["question"], str) or not 0 < len(item["question"].strip()) <= 2000:
            raise ValueError("invalid evaluation question")
        source = item["expected_source"]
        if source is not None:
            if not isinstance(source, str):
                raise ValueError("expected_source must be a relative Markdown path or null")
            relative = PurePosixPath(source)
            if (relative.is_absolute() or ".." in relative.parts or relative.suffix != ".md"
                    or relative.as_posix() != source or "\\" in source or ":" in source):
                raise ValueError("expected_source must be a relative Markdown path")
        keywords = item["expected_keywords"]
        if not isinstance(keywords, list) or any(not isinstance(word, str) or not word.strip() for word in keywords):
            raise ValueError("expected_keywords must be a string list")
        result.append(EvaluationQuestion(**(item | {"expected_keywords": tuple(keywords)})))
    return result


class ExtractiveEvaluationLLM:
    """Quote the first retrieved paragraph; no labels, answers or AI model used.

    Used solely to exercise service citations/fallback. It does not synthesize,
    translate or demonstrate the correctness of a real model's answer.
    """

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        node = ET.fromstring(user_prompt).find("authorized_context/document")
        if node is None or not node.text:
            raise ValueError("evaluation requires authorized context")
        paragraphs = node.text.split("\n\n")
        body = next(part for part in paragraphs if part.strip() and not part.lstrip().startswith("#"))
        return " ".join(body.split()) + " [S1]"


def evaluate(
    cases: list[EvaluationQuestion],
    *,
    loader: KnowledgeDocumentLoader | None = None,
    min_similarity: float = 0.2,
) -> dict:
    if not cases:
        raise ValueError("at least one evaluation case is required")
    documents = (loader if loader is not None else KnowledgeDocumentLoader()).load()
    chunks = [chunk for document in documents for chunk in MarkdownChunker().split(document)]
    # Expected sources/keywords are used ONLY for scoring, never fitting/ranking.
    provider = LexicalEmbeddingProvider([chunk.content for chunk in chunks])
    retriever = KnowledgeRetriever(provider)
    retriever.rebuild(documents)
    by_source = {document.source: document for document in documents}
    audit = InMemoryAssistantAuditSink()
    service = RAGAssistantService(
        retriever, ExtractiveEvaluationLLM(), audit=audit, min_similarity=min_similarity, limit=3,
    )
    rows = []
    for case in cases:
        if case.expected_source is not None and (
            case.expected_source not in by_source or case.role not in by_source[case.expected_source].audience
        ):
            raise ValueError(f"expected source is unapproved or unauthorized: {case.case_id}")
        access = AIAccessContext(actor_id=1, role=case.role, store_ids=(), language=case.language)
        hits = retriever.search_scored(question=case.question, access=access, limit=3)
        started = time.perf_counter()
        answer = service.ask(question=case.question, access=access)
        latency = (time.perf_counter() - started) * 1000
        leaks = sum(case.role not in hit.chunk.audience for hit in hits)
        leaks += sum(
            citation.source not in by_source or case.role not in by_source[citation.source].audience
            for citation in answer.citations
        )
        rows.append({
            **asdict(case),
            "top3_sources": [hit.chunk.source for hit in hits],
            "top3_scores": [round(hit.score, 6) for hit in hits],
            "retrieval_hit_at_3": case.expected_source is not None and any(
                hit.chunk.source == case.expected_source for hit in hits
            ),
            "evidence_hit_at_3": case.expected_source is not None and any(
                hit.chunk.source == case.expected_source and hit.score >= min_similarity for hit in hits
            ),
            "grounded": answer.grounded,
            "citation_sources": [citation.source for citation in answer.citations],
            "keyword_hits": [word for word in case.expected_keywords if word.casefold() in answer.answer.casefold()],
            "correct_refusal": case.expected_source is None and not answer.grounded,
            "permission_leaks": leaks,
            "latency_ms": round(latency, 3),
        })
    retrieve = [row for row in rows if row["expected_source"] is not None]
    refuse = [row for row in rows if row["expected_source"] is None]
    answered = [row for row in rows if row["grounded"]]
    def ratio(numerator, denominator):
        return round(numerator / denominator, 4) if denominator else None
    return {
        "mode": "offline-tfidf-extractive-baseline",
        "semantic_llm_evaluated": False,
        "min_similarity": min_similarity,
        "document_count": len(documents), "chunk_count": len(chunks),
        "case_count": len(rows),
        "retrieval_hit_at_3": ratio(sum(row["retrieval_hit_at_3"] for row in retrieve), len(retrieve)),
        "evidence_hit_at_3": ratio(sum(row["evidence_hit_at_3"] for row in retrieve), len(retrieve)),
        "answer_rate_on_retrievable": ratio(sum(row["grounded"] for row in retrieve), len(retrieve)),
        "expected_source_in_answer_rate": ratio(sum(
            row["expected_source"] in row["citation_sources"] for row in retrieve
        ), len(retrieve)),
        "citation_coverage_of_answered": ratio(sum(bool(row["citation_sources"]) for row in answered), len(answered)),
        "correct_refusal_rate": ratio(sum(row["correct_refusal"] for row in refuse), len(refuse)),
        "permission_leaks": sum(row["permission_leaks"] for row in rows),
        "mean_latency_ms": round(sum(row["latency_ms"] for row in rows) / len(rows), 3),
        "limitations": [
            "Lexical ranking is not multilingual semantic retrieval.",
            "Extractive responses measure citation plumbing, not LLM answer accuracy or translation.",
            "No live model, network, financial data or authenticated web session was evaluated.",
        ],
        "cases": rows,
    }
