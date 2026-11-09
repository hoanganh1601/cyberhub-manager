"""Framework-independent contracts for the phase 5A knowledge assistant."""

from .models import (
    AIAccessContext,
    AssistantAnswer,
    Citation,
    KnowledgeChunk,
    KnowledgeDocument,
)

__all__ = [
    "AIAccessContext",
    "AssistantAnswer",
    "Citation",
    "KnowledgeChunk",
    "KnowledgeDocument",
]
