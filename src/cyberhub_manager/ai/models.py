"""Immutable RAG contracts; no Flask, database, provider or authorization hooks.

Construct access contexts only from an authenticated backend identity. Validation
here checks structure, not whether the actor actually holds the supplied role.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import PurePosixPath
from typing import Literal, TypeAlias, get_args

Role: TypeAlias = Literal["CUSTOMER", "STAFF", "MANAGER", "ADMIN"]
DocumentStatus: TypeAlias = Literal["DRAFT", "APPROVED", "ARCHIVED"]
Language: TypeAlias = Literal["vi", "en"]

_ROLES = frozenset(get_args(Role))
_STATUSES = frozenset(get_args(DocumentStatus))
_LANGUAGES = frozenset(get_args(Language))
_DOCUMENT_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-blank string")


def _positive_int(value: int, field: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field} must be a positive integer")


def _source(value: str) -> None:
    """Require a portable Markdown path relative to the knowledge root."""
    _text(value, "source")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in value
        or ":" in value
        or path.suffix != ".md"
        or path.as_posix() != value
    ):
        raise ValueError("source must be a canonical relative Markdown path")


def _document_id(value: str) -> None:
    if not isinstance(value, str) or not _DOCUMENT_ID.fullmatch(value):
        raise ValueError("document_id must use lowercase letters, digits and hyphens")


def _audience(value: tuple[Role, ...]) -> None:
    if (
        type(value) is not tuple
        or not value
        or any(not isinstance(role, str) or role not in _ROLES for role in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError("audience must be a non-empty tuple of unique supported roles")


@dataclass(frozen=True)
class AIAccessContext:
    """Trusted identity: actor_id is employees.id, or accounts.id for CUSTOMER.

    An empty store_ids tuple grants no store-data access, including for ADMIN.
    Static knowledge audiences are explicit; role inheritance is not implied.
    The future backend adapter must revalidate identity, role and store scope.
    """

    actor_id: int
    role: Role
    store_ids: tuple[int, ...]
    language: Language = "vi"

    def __post_init__(self) -> None:
        _positive_int(self.actor_id, "actor_id")
        if not isinstance(self.role, str) or self.role not in _ROLES:
            raise ValueError("role is not supported")
        if type(self.store_ids) is not tuple:
            raise ValueError("store_ids must be a tuple")
        for store_id in self.store_ids:
            _positive_int(store_id, "store_id")
        if len(set(self.store_ids)) != len(self.store_ids):
            raise ValueError("store_ids must be unique")
        if not isinstance(self.language, str) or self.language not in _LANGUAGES:
            raise ValueError("language must be vi or en")


@dataclass(frozen=True)
class KnowledgeDocument:
    """One document; DRAFT and ARCHIVED exist for editorial use only.

    A future loader maps frontmatter id to document_id and sets source from
    the actual file path. Only APPROVED documents may enter the serving index.
    """

    document_id: str
    title: str
    content: str
    source: str
    audience: tuple[Role, ...]
    status: DocumentStatus
    version: int
    language: Language = "vi"
    tags: tuple[str, ...] = ()
    updated_at: date | None = None

    def __post_init__(self) -> None:
        _document_id(self.document_id)
        _text(self.title, "title")
        _text(self.content, "content")
        _source(self.source)
        _audience(self.audience)
        _positive_int(self.version, "version")
        if not isinstance(self.status, str) or self.status not in _STATUSES:
            raise ValueError("status is not supported")
        if not isinstance(self.language, str) or self.language not in _LANGUAGES:
            raise ValueError("language must be vi or en")
        if type(self.tags) is not tuple:
            raise ValueError("tags must be a tuple")
        for tag in self.tags:
            _text(tag, "tag")
        if self.updated_at is not None and type(self.updated_at) is not date:
            raise ValueError("updated_at must be a date")


@dataclass(frozen=True)
class KnowledgeChunk:
    """Text segment carrying the original document's audience and version.

    Only approved documents may produce retrievable chunks. Enforcing that
    precondition belongs to the future loader/indexing pipeline.
    """

    chunk_id: str
    document_id: str
    title: str
    section: str
    content: str
    source: str
    audience: tuple[Role, ...]
    version: int
    language: Language = "vi"

    def __post_init__(self) -> None:
        _text(self.chunk_id, "chunk_id")
        _document_id(self.document_id)
        _text(self.title, "title")
        _text(self.section, "section")
        _text(self.content, "content")
        _source(self.source)
        _audience(self.audience)
        _positive_int(self.version, "version")
        if not isinstance(self.language, str) or self.language not in _LANGUAGES:
            raise ValueError("language must be vi or en")


@dataclass(frozen=True)
class Citation:
    """Source identity is copied from an authorized chunk by the backend."""

    title: str
    section: str
    source: str
    chunk_id: str
    document_id: str
    version: int

    def __post_init__(self) -> None:
        _text(self.title, "title")
        _text(self.section, "section")
        _source(self.source)
        _text(self.chunk_id, "chunk_id")
        _document_id(self.document_id)
        _positive_int(self.version, "version")


@dataclass(frozen=True)
class AssistantAnswer:
    """Result envelope; citation presence alone does not prove factual accuracy."""

    answer: str
    citations: tuple[Citation, ...]
    grounded: bool

    def __post_init__(self) -> None:
        _text(self.answer, "answer")
        if type(self.citations) is not tuple or any(
            not isinstance(citation, Citation) for citation in self.citations
        ):
            raise ValueError("citations must be a tuple of Citation objects")
        if type(self.grounded) is not bool:
            raise ValueError("grounded must be a boolean")
        if self.grounded != bool(self.citations):
            raise ValueError("grounded answers need citations; fallback answers have none")
