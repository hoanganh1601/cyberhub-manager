"""Read-only RAG orchestration with evidence gates, citations and safe audit.

grounded=True means authorized evidence passed the similarity threshold and
each answer line has a valid reference. It does NOT prove semantic entailment;
evaluate the chosen model against approved business policies before deployment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import math
import re
import time
from uuid import uuid4

from .audit import AssistantAuditEvent, AssistantAuditSink, LoggingAssistantAuditSink
from .errors import (
    ContextBudgetError, InsufficientContextError, InvalidContextError,
    InvalidProviderResponseError, InvalidQuestionError, KnowledgeAccessError,
    KnowledgeIndexUnavailableError, ProviderBusyError, ProviderError,
    ProviderTimeoutError, ProviderUnavailableError,
)
from .models import AIAccessContext, AssistantAnswer, Citation
from .prompts import RAGPromptBuilder
from .providers import FormattedLLMProvider, LLMProvider, validate_generation
from .retrieval import KnowledgeRetriever, normalize_question
from .runner import BoundedProviderRunner

_LOG = logging.getLogger(__name__)
_REF = re.compile(r"\[S([1-9][0-9]*)\]")
_REFLIKE = re.compile(r"\[S[^\]\r\n]*(?:\]|$)", re.MULTILINE)
_LINE_END = re.compile(r"(?:\[S[1-9][0-9]*\][ \t]*)+[.!?…]?$")
_UNSUPPORTED_LINK = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://|www\.|\]\s*\(|</?[a-zA-Z][^>]*>")
_FORMAT = {
    "vi": "\nĐịnh dạng: mỗi đoạn hoặc ý trả lời trên một dòng, kết thúc bằng [S1] hoặc các ref hợp lệ. "
          "Không thêm tiêu đề/dòng không có nguồn, URL, liên kết Markdown hoặc HTML.",
    "en": "\nFormat: one paragraph or claim per line, ending with [S1] or other valid refs. "
          "Do not add uncited headings/lines, URLs, Markdown links or HTML.",
}
_FALLBACK = {
    "vi": "Tôi chưa tìm thấy thông tin đã được phê duyệt để trả lời câu hỏi này. "
          "Vui lòng liên hệ quản lý hoặc quản trị viên.",
    "en": "I could not find approved information to answer this question. "
          "Please contact a manager or administrator.",
}
_UNAVAILABLE = {
    "vi": "Trợ lý hiện chưa thể trả lời. Vui lòng thử lại sau hoặc liên hệ quản lý.",
    "en": "The assistant cannot answer right now. Please try again later or contact a manager.",
}
_FAILURES = (
    (ProviderTimeoutError, "PROVIDER_TIMEOUT"),
    (TimeoutError, "PROVIDER_TIMEOUT"),
    (ProviderBusyError, "PROVIDER_BUSY"),
    (InvalidProviderResponseError, "INVALID_RESPONSE"),
    (ProviderUnavailableError, "PROVIDER_UNAVAILABLE"),
    (KnowledgeIndexUnavailableError, "INDEX_UNAVAILABLE"),
    (ContextBudgetError, "CONTEXT_BUDGET"),
    (InsufficientContextError, "NO_CONTEXT"),
    (KnowledgeAccessError, "CONTEXT_REJECTED"),
    (InvalidContextError, "CONTEXT_REJECTED"),
    (ProviderError, "PROVIDER_ERROR"),
)


@dataclass
class _Attempt:
    result: str = "INTERNAL_ERROR"
    chunk_ids: tuple[str, ...] = ()


def _fallback(access: AIAccessContext, *, unavailable: bool = False) -> AssistantAnswer:
    messages = _UNAVAILABLE if unavailable else _FALLBACK
    return AssistantAnswer(answer=messages[access.language], citations=(), grounded=False)


def _cited_answer(text: str, candidates: tuple[Citation, ...]) -> AssistantAnswer:
    """Validate ref syntax and return only cited sources, with compact labels."""
    tokens = _REFLIKE.findall(text)
    if not tokens or any(_REF.fullmatch(token) is None for token in tokens):
        raise InvalidProviderResponseError("answer must contain valid source references")
    refs = [int(match[1]) for match in _REF.finditer(text)]
    if any(ref > len(candidates) for ref in refs):
        raise InvalidProviderResponseError("answer refers to an unavailable source")
    if _UNSUPPORTED_LINK.search(text):
        raise InvalidProviderResponseError("answer contains unsupported links or markup")
    for line in text.splitlines():
        if not line.strip():
            continue
        if not _LINE_END.search(line.strip()) or not _REF.sub("", line).strip(" \t-*.•():"):
            raise InvalidProviderResponseError("every answer line must have text and a source")
    ordered = list(dict.fromkeys(refs))
    labels = {old: new for new, old in enumerate(ordered, start=1)}
    answer = _REF.sub(lambda match: f"[S{labels[int(match[1])]}]", text)
    return AssistantAnswer(
        answer=answer,
        citations=tuple(candidates[ref - 1] for ref in ordered),
        grounded=True,
    )


class RAGAssistantService:
    """One query embedding and at most one generation per authenticated ask.

    Reuse this service/runner in the backend so timed-out calls share the bounded
    worker capacity. No SDK, transaction service, SQL or business-action hooks.
    """

    def __init__(
        self,
        retriever: KnowledgeRetriever,
        llm: LLMProvider,
        *,
        audit: AssistantAuditSink | None = None,
        runner: BoundedProviderRunner | None = None,
        min_similarity: float = 0.7,
        limit: int = 5,
        timeout_seconds: float = 15.0,
        max_question_chars: int = 2000,
        max_context_chars: int = 20_000,
        max_prompt_chars: int = 24_000,
        max_answer_chars: int = 4000,
        context_limit: int | None = None,
    ) -> None:
        if type(min_similarity) not in (int, float) or not 0 < min_similarity <= 1:
            raise ValueError("min_similarity must be greater than zero and at most one")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("limit must be an integer from 1 to 20")
        if (
            type(timeout_seconds) not in (int, float)
            or not math.isfinite(timeout_seconds) or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be positive and finite")
        if type(max_question_chars) is not int or not 1 <= max_question_chars <= 2000:
            raise ValueError("max_question_chars must be an integer from 1 to 2000")
        for name, value in (("max_prompt_chars", max_prompt_chars), ("max_answer_chars", max_answer_chars)):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        self._retriever = retriever
        self._llm = llm
        self._audit = audit if audit is not None else LoggingAssistantAuditSink()
        self._runner = runner if runner is not None else BoundedProviderRunner()
        self._minimum = min_similarity
        self._limit = limit
        self._timeout = float(timeout_seconds)
        self._question_chars = max_question_chars
        self._prompt_chars = max_prompt_chars
        self._answer_chars = max_answer_chars
        self._prompts = RAGPromptBuilder(
            retriever, max_question_chars=max_question_chars,
            max_context_chars=max_context_chars, max_chunks=limit if context_limit is None else context_limit,
        )

    def ask(
        self, *, question: str, access: AIAccessContext, request_id: str | None = None,
    ) -> AssistantAnswer:
        if not isinstance(access, AIAccessContext):
            raise TypeError("access must be a backend-validated AIAccessContext")
        if request_id is not None and (
            not isinstance(request_id, str) or re.fullmatch(r"[0-9a-f]{32}", request_id) is None
        ):
            raise ValueError("request_id must be a backend-generated UUID hex string")
        started = time.monotonic()
        deadline = started + self._timeout
        request_id = uuid4().hex if request_id is None else request_id
        attempt = _Attempt()
        try:
            question = normalize_question(question, max_chars=self._question_chars)
            answer = self._answer(question, access, deadline, attempt)
        except InvalidQuestionError:
            attempt.result = "INVALID_QUESTION"
            raise
        except tuple(kind for kind, _ in _FAILURES) as exc:
            attempt.result = next(result for kind, result in _FAILURES if isinstance(exc, kind))
            answer = _fallback(access, unavailable=attempt.result != "NO_CONTEXT")
        except Exception:
            # A vendor adapter may fail with an unclassified SDK exception.
            # Keep that message/trace out of the user response and audit payload.
            _LOG.error("assistant request failed; request_id=%s", request_id)
            answer = _fallback(access, unavailable=True)
        finally:
            audited = self._record(request_id, access, attempt, started)
        return answer if audited else _fallback(access, unavailable=True)

    def _answer(
        self, question: str, access: AIAccessContext, deadline: float, attempt: _Attempt,
    ) -> AssistantAnswer:
        matches = self._runner.run(
            lambda: self._retriever.search_scored(question=question, access=access, limit=self._limit),
            timeout_seconds=self._remaining(deadline),
        )
        current = self._retriever.authorize_context([match.chunk for match in matches], access)
        attempt.chunk_ids = tuple(chunk.chunk_id for chunk in current)
        if not matches:
            attempt.result = "NO_CONTEXT"
            return _fallback(access)
        chunks = [match.chunk for match in matches if match.score >= self._minimum]
        if not chunks:
            attempt.result = "LOW_RELEVANCE"
            return _fallback(access)
        chunks = list(self._retriever.expand_context(chunks, access))
        attempt.chunk_ids = tuple(chunk.chunk_id for chunk in chunks)
        prompt = self._prompts.build(question=question, access=access, chunks=chunks)
        format_instructions = (self._llm.format_instructions(access.language)
                               if isinstance(self._llm, FormattedLLMProvider) else _FORMAT[access.language])
        if not isinstance(format_instructions, str):
            raise InvalidProviderResponseError("provider format instructions must be text")
        system_prompt = prompt.system_prompt + format_instructions
        if len(system_prompt) + len(prompt.user_prompt) > self._prompt_chars:
            raise ContextBudgetError("complete prompt exceeds the request budget")
        self._retriever.authorize_context(chunks, access)
        response = self._runner.run(
            lambda: self._llm.generate(system_prompt=system_prompt, user_prompt=prompt.user_prompt),
            timeout_seconds=self._remaining(deadline),
        )
        self._remaining(deadline)
        text = validate_generation(response).strip()
        if len(text) > self._answer_chars:
            raise InvalidProviderResponseError("answer exceeds the output budget")
        # Never return an answer based on documents revoked while LLM was running.
        self._retriever.authorize_context(chunks, access)
        answer = _cited_answer(text, prompt.citations)
        attempt.result = "ANSWERED"
        return answer

    @staticmethod
    def _remaining(deadline: float) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProviderTimeoutError("request deadline exceeded")
        return remaining

    def _record(
        self, request_id: str, access: AIAccessContext, attempt: _Attempt, started: float,
    ) -> bool:
        event = AssistantAuditEvent(
            request_id=request_id, actor_id=access.actor_id, actor_role=access.role,
            store_ids=access.store_ids, language=access.language,
            retrieved_chunk_ids=attempt.chunk_ids, result=attempt.result,
            latency_ms=max(0, int((time.monotonic() - started) * 1000)),
            created_at=datetime.now(timezone.utc),
        )
        try:
            self._audit.record(event)
        except Exception:
            # Do not log exceptions: external sink messages may contain secrets.
            _LOG.error("assistant audit write failed; request_id=%s", request_id)
            return False
        return True
