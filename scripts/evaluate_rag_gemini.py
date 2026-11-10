"""Opt-in Gemini API evaluation. Consumes API quota; labels never reach the provider."""

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from dotenv import load_dotenv

from cyberhub_manager.ai.documents import KnowledgeDocumentLoader
from cyberhub_manager.ai.evaluation import load_questions
from cyberhub_manager.ai.fakes import InMemoryAssistantAuditSink
from cyberhub_manager.ai.gemini import DEFAULT_LLM_MODEL, GeminiEmbeddingProvider, GeminiLLMProvider, GeminiTransport
from cyberhub_manager.ai.models import AIAccessContext
from cyberhub_manager.ai.runtime import LiveKnowledgeRetriever
from cyberhub_manager.ai.service import RAGAssistantService


def main(argv=None):
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default="tests/fixtures/ai/evaluation_questions.json")
    parser.add_argument("--output", type=Path, default=Path(tempfile.gettempdir()) / "rag-gemini-evaluation.json")
    parser.add_argument("--threshold", type=float, default=float(os.getenv("CYBERHUB_GEMINI_MIN_SIMILARITY", "0.6")))
    parser.add_argument("--model", default=os.getenv("GEMINI_MODEL", DEFAULT_LLM_MODEL))
    parser.add_argument("--retrieve-only", action="store_true")
    parser.add_argument("--limit", type=int, help="evaluate only the first N questions to conserve API quota")
    args = parser.parse_args(argv)
    if not os.getenv("GEMINI_API_KEY", "").strip():
        parser.error("set GEMINI_API_KEY in .env before running API evaluation")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    if not 0 < args.threshold <= 1:
        parser.error("--threshold must be greater than zero and at most one")
    cases = load_questions(args.questions)
    if args.limit is not None:
        cases = cases[:args.limit]
    transport = GeminiTransport(os.environ["GEMINI_API_KEY"], timeout=30)
    embedding = GeminiEmbeddingProvider(transport, model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"))
    llm = GeminiLLMProvider(transport, model=args.model)
    knowledge_root = os.getenv("CYBERHUB_KNOWLEDGE_ROOT")
    loader = KnowledgeDocumentLoader(knowledge_root=knowledge_root) if knowledge_root else KnowledgeDocumentLoader()
    retriever = LiveKnowledgeRetriever(embedding, loader)
    documents = tuple(loader.load())
    audit = InMemoryAssistantAuditSink()
    service = RAGAssistantService(retriever, llm, audit=audit, min_similarity=args.threshold,
                                  limit=4, context_limit=16, timeout_seconds=60,
                                  max_context_chars=14000, max_prompt_chars=18000)
    sources = {doc.source: doc for doc in documents}
    corpus_hash = hashlib.sha256(json.dumps([asdict(doc) for doc in documents], ensure_ascii=False,
                                           sort_keys=True, default=str).encode()).hexdigest()
    rows = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        access = AIAccessContext(1, case.role, (), case.language)
        started = time.monotonic()
        hits = retriever.search_scored(question=case.question, access=access, limit=3)
        answer = None if args.retrieve_only else service.ask(question=case.question, access=access)
        row = asdict(case) | {
            "top3_sources": [hit.chunk.source for hit in hits],
            "top3_scores": [round(hit.score, 6) for hit in hits],
            "retrieval_hit_at_3": any(hit.chunk.source == case.expected_source for hit in hits),
            "evidence_hit_at_3": any(hit.chunk.source == case.expected_source and hit.score >= args.threshold for hit in hits),
            "answer": None if answer is None else answer.answer,
            "grounded": None if answer is None else answer.grounded,
            "citation_sources": [] if answer is None else [c.source for c in answer.citations],
            "service_result": None if answer is None else audit.events[-1].result,
            "permission_leaks": sum(case.role not in hit.chunk.audience for hit in hits),
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
        }
        if answer:
            row["permission_leaks"] += sum(c.source not in sources or case.role not in sources[c.source].audience for c in answer.citations)
        rows.append(row)
        args.output.write_text(json.dumps({
            "mode": "gemini-api-real-model", "model": args.model, "embedding": embedding.model,
            "min_similarity": args.threshold, "retrieve_only": args.retrieve_only,
            "document_count": len(documents), "corpus_sha256": corpus_hash,
            "expected_case_count": len(cases), "complete": len(rows) == len(cases), "cases": rows,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(case.case_id, row["top3_scores"], row["service_result"], flush=True)


if __name__ == "__main__":
    main()
