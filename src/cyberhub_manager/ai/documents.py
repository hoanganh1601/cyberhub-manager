"""Load a complete, approved Markdown corpus without following document links.

The root is trusted deployment configuration, never a request parameter. Corpus
files must be managed by administrators, not modified by untrusted users during
ingestion. Callers must replace an index from a successful full load rather than
append documents to an existing index; failures must not publish partial results.
"""

from __future__ import annotations

import os
import stat
from datetime import date
from pathlib import Path
from typing import Iterator

import yaml
from yaml.events import AliasEvent, CollectionEndEvent, CollectionStartEvent

from .errors import (
    DocumentTooLargeError,
    DuplicateDocumentError,
    InvalidMetadataError,
    KnowledgePathError,
    KnowledgeReadError,
)
from .models import KnowledgeDocument

DEFAULT_KNOWLEDGE_ROOT = Path(__file__).resolve().parents[3] / "docs/knowledge-base"
DEFAULT_MAX_FILE_BYTES = 256 * 1024
MAX_METADATA_BYTES = 16 * 1024
_FIELDS = frozenset({
    "id", "title", "audience", "status", "version", "language", "updated_at", "tags",
})


class _MetadataLoader(yaml.SafeLoader):
    """Safe YAML with duplicate mapping keys rejected instead of overwritten."""


def _unique_mapping(loader: _MetadataLoader, node: yaml.MappingNode) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if type(key) is not str or key in result:
            raise ValueError("metadata keys must be unique strings")
        result[key] = loader.construct_object(value_node)
    return result


_MetadataLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping,
)


def _metadata(text: str) -> dict:
    # Frontmatter only needs a flat mapping of scalars and lists. Aliases,
    # explicit tags and nested collections add no business value to this format.
    depth = 0
    for event in yaml.parse(text, Loader=_MetadataLoader):
        if isinstance(event, AliasEvent) or getattr(event, "anchor", None):
            raise ValueError("YAML anchors and aliases are not supported")
        if getattr(event, "tag", None) is not None:
            raise ValueError("explicit YAML tags are not supported")
        if isinstance(event, CollectionStartEvent):
            depth += 1
            if depth > 2:
                raise ValueError("nested metadata collections are not supported")
        elif isinstance(event, CollectionEndEvent):
            depth -= 1
    fields = yaml.load(text, Loader=_MetadataLoader)
    if type(fields) is not dict or set(fields) != _FIELDS:
        raise ValueError("metadata must contain exactly the eight documented fields")
    for field in ("audience", "tags"):
        if type(fields[field]) is not list:
            raise ValueError(f"{field} must be a list")
    if type(fields["updated_at"]) is str:
        fields["updated_at"] = date.fromisoformat(fields["updated_at"])
    if type(fields["updated_at"]) is not date:
        raise ValueError("updated_at must be an ISO date")
    return fields


class KnowledgeDocumentLoader:
    """Return approved documents from one explicitly configured knowledge root.

    A custom root is allowed for trusted deployments/tests. Passing an arbitrary
    path to load() does not change that configured root. All symlinks, including
    directory symlinks inside the root, are rejected. README.md is never indexed.
    """

    def __init__(
        self,
        *,
        knowledge_root: str | Path = DEFAULT_KNOWLEDGE_ROOT,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    ) -> None:
        if type(max_file_bytes) is not int or max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be a positive integer")
        self._root = Path(knowledge_root).absolute()
        self._max_file_bytes = max_file_bytes

    def load(self, root_path: str | Path | None = None) -> list[KnowledgeDocument]:
        """Validate every document, then return only APPROVED ones, in path order.

        Draft/archived files are still validated and reserve their document IDs.
        This detects accidental duplicate approvals and malformed revocations.
        """
        try:
            root = self._root.resolve(strict=True)
            requested = Path(root_path) if root_path is not None else self._root
            if self._root.is_symlink() or requested.is_symlink():
                raise KnowledgePathError("knowledge root must not be a symlink")
            if requested.resolve(strict=True) != root or not root.is_dir():
                raise KnowledgePathError("load path must equal the configured knowledge root")

            documents = []
            sources: dict[str, str] = {}
            for path in self._paths(root):
                if not path.resolve(strict=True).is_relative_to(root):
                    raise KnowledgePathError("document resolves outside knowledge root")
                source = path.relative_to(root).as_posix()
                document = self._document(path, source)
                previous = sources.get(document.document_id)
                if previous is not None:
                    raise DuplicateDocumentError(
                        f"duplicate id {document.document_id!r}: {previous}, {source}"
                    )
                sources[document.document_id] = source
                if document.status == "APPROVED":
                    documents.append(document)
            return documents
        except OSError as exc:
            raise KnowledgeReadError("cannot read the configured knowledge corpus") from exc

    def _paths(self, folder: Path) -> Iterator[Path]:
        for path in sorted(folder.iterdir()):
            if path.is_symlink():
                raise KnowledgePathError(f"symlinks are not allowed: {path.name}")
            if path.is_dir():
                yield from self._paths(path)
            elif path.suffix == ".md" and path.name.lower() != "readme.md":
                yield path

    def _document(self, path: Path, source: str) -> KnowledgeDocument:
        # The bounded read protects even when a regular file grows after stat().
        # O_NOFOLLOW also blocks swapping the final component for a symlink on
        # platforms that support it. Directory ownership remains a prerequisite.
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise KnowledgePathError(f"not a regular Markdown file: {source}")
            if info.st_size > self._max_file_bytes:
                raise DocumentTooLargeError(f"document exceeds byte limit: {source}")
            raw = stream.read(self._max_file_bytes + 1)
        if len(raw) > self._max_file_bytes:
            raise DocumentTooLargeError(f"document exceeds byte limit: {source}")

        try:
            lines = raw.decode("utf-8-sig").splitlines(keepends=True)
            if not lines or lines[0].strip() != "---":
                raise ValueError("YAML frontmatter is required at the start")
            end = next(
                index for index in range(1, len(lines))
                if lines[index].strip() == "---"
            )
            header = "".join(lines[1:end])
            if len(header.encode("utf-8")) > MAX_METADATA_BYTES:
                raise ValueError("metadata exceeds byte limit")
            fields = _metadata(header)
            return KnowledgeDocument(
                document_id=fields["id"],
                title=fields["title"],
                content="".join(lines[end + 1:]),
                source=source,
                audience=tuple(fields["audience"]),
                status=fields["status"],
                version=fields["version"],
                language=fields["language"],
                tags=tuple(fields["tags"]),
                updated_at=fields["updated_at"],
            )
        except (ValueError, TypeError, StopIteration, RecursionError, yaml.YAMLError) as exc:
            raise InvalidMetadataError(f"invalid knowledge document {source}: {exc}") from exc
