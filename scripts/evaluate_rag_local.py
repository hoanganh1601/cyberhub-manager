"""Opt-in real local-model evaluation; no labels are sent to models/providers."""

import argparse
from dataclasses import asdict
import json
import hashlib
from pathlib import Path
import time

from cyberhub_manager.ai.documents import KnowledgeDocumentLoader
from cyberhub_manager.ai.evaluation import load_questions
from cyberhub_manager.ai.fakes import InMemoryAssistantAuditSink
from cyberhub_manager.ai.models import AIAccessContext
from cyberhub_manager.ai.ollama import OllamaEmbeddingProvider, OllamaLLMProvider, OllamaTransport
from cyberhub_manager.ai.runtime import LiveKnowledgeRetriever
from cyberhub_manager.ai.service import RAGAssistantService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default="tests/fixtures/ai/evaluation_questions.json")
    parser.add_argument("--output", default="/tmp/rag-local-evaluation.json")
    parser.add_argument("--threshold", type=float, default=0.53)
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--retrieve-only", action="store_true")
    args = parser.parse_args()
    transport = OllamaTransport(timeout=30)
    embedding = OllamaEmbeddingProvider(transport)
    llm = OllamaLLMProvider(transport, model=args.model)
    documents = KnowledgeDocumentLoader().load()
    retriever = LiveKnowledgeRetriever(embedding, KnowledgeDocumentLoader())
    audit = InMemoryAssistantAuditSink()
    service = RAGAssistantService(retriever, llm, audit=audit, min_similarity=args.threshold, limit=4, context_limit=16, timeout_seconds=40,
                                  max_context_chars=14000, max_prompt_chars=18000)
    sources = {doc.source: doc for doc in documents}
    corpus_hash = hashlib.sha256(json.dumps([asdict(doc) for doc in documents], ensure_ascii=False,
                                           sort_keys=True, default=str).encode()).hexdigest()
    cases = load_questions(args.questions)
    rows = []
    for case in cases:
        access = AIAccessContext(1, case.role, (), case.language)
        hits = retriever.search_scored(question=case.question, access=access, limit=3)
        start = time.monotonic()
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
            "latency_ms": round((time.monotonic() - start) * 1000, 2),
        }
        if answer:
            row["permission_leaks"] += sum(c.source not in sources or case.role not in sources[c.source].audience for c in answer.citations)
        rows.append(row)
        Path(args.output).write_text(json.dumps({"mode": "local-ollama-real-model", "model": args.model, "embedding": embedding.model,
            "min_similarity": args.threshold, "retrieve_only": args.retrieve_only,
            "document_count": len(documents), "corpus_sha256": corpus_hash,
            "expected_case_count": len(cases), "complete": len(rows) == len(cases), "cases": rows}, ensure_ascii=False, indent=2)+"\n")
        print(case.case_id, row["top3_scores"], row["service_result"], flush=True)


if __name__ == "__main__":
    main()
