"""Metadata-only audit contracts; no raw questions, prompts or model answers."""

from dataclasses import asdict, dataclass
from datetime import datetime
import json
import logging
from typing import Protocol

from .models import Language, Role


@dataclass(frozen=True)
class AssistantAuditEvent:
    request_id: str
    actor_id: int
    actor_role: Role
    store_ids: tuple[int, ...]
    language: Language
    retrieved_chunk_ids: tuple[str, ...]
    result: str
    latency_ms: int
    created_at: datetime


class AssistantAuditSink(Protocol):
    def record(self, event: AssistantAuditEvent) -> None:
        ...


class LoggingAssistantAuditSink:
    """Use the host application's configured INFO audit handler.

    This is not a durable database audit store. Deployment must configure the
    handler/retention, or inject a durable sink after the history schema exists.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger if logger is not None else logging.getLogger("cyberhub.ai.audit")

    def record(self, event: AssistantAuditEvent) -> None:
        fields = asdict(event)
        fields["created_at"] = event.created_at.isoformat()
        self._logger.info("ai_assistant_audit %s", json.dumps(fields, sort_keys=True))
