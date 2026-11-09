"""Deterministic, heading-aware chunking for approved Markdown knowledge.

No model, network, database or authorization lookup is involved. Each call works
on one document, so content and audiences from different documents never mix.
Word counts are whitespace-delimited words, not an embedding model's tokens.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Iterator

from .errors import ChunkingError
from .models import KnowledgeChunk, KnowledgeDocument

_WORDS = re.compile(r"\S+")
_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*)|[ \t]*)$")
_SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_BLOCK_MARKER = re.compile(r"^ {0,3}(?:[-+*>]|\d+[.)])[ \t]+")
_SENTENCE_END = re.compile(r"[.!?…;:][\"'”’)]*$")


@dataclass(frozen=True)
class _Block:
    text: str
    protected: bool = False

    @property
    def words(self) -> int:
        return len(_WORDS.findall(self.text))


def _opening_fence(line: str) -> str | None:
    match = _FENCE.fullmatch(line)
    if match and not (match[1][0] == "`" and "`" in match[2]):
        return match[1]
    return None


def _closes_fence(line: str, fence: str) -> bool:
    return re.fullmatch(r" {0,3}" + re.escape(fence[0]) +
                        r"{" + str(len(fence)) + r",}[ \t]*", line) is not None


def _heading(lines: list[str], index: int) -> tuple[int, str, int] | None:
    line = lines[index]
    match = _ATX.fullmatch(line)
    if match:
        title = re.sub(r"[ \t]+#+[ \t]*$", "", match[2] or "").strip()
        if title:
            return len(match[1]), title, 1
    if (
        line.strip()
        and not line.startswith(("    ", "\t", "#"))
        and not _BLOCK_MARKER.match(line)
        and index + 1 < len(lines)
        and (underline := _SETEXT.fullmatch(lines[index + 1]))
    ):
        return (1 if underline[1][0] == "=" else 2), line.strip(), 2
    return None


def _sections(document: KnowledgeDocument) -> Iterator[tuple[str, str, str]]:
    """Yield (breadcrumb, repeated heading context, body) for each section.

    ATX and single-line Setext headings are supported. Indented code and fenced
    code are not interpreted as headings. Empty ancestor sections are carried
    into the next section's heading context, not emitted as empty chunks.
    """
    lines = document.content.splitlines()
    headings: list[tuple[int, str]] = []
    body: list[str] = []
    fence: str | None = None

    def section() -> tuple[str, str, str]:
        context = list(headings)
        if not context or context[0][1] != document.title:
            context.insert(0, (1, document.title))
        breadcrumb = " > ".join(title for _, title in context)
        prefix = "\n\n".join("#" * level + " " + title for level, title in context)
        return breadcrumb, prefix, "\n".join(body).strip("\n")

    index = 0
    while index < len(lines):
        line = lines[index]
        if fence is not None:
            body.append(line)
            if _closes_fence(line, fence):
                fence = None
            index += 1
            continue
        fence = _opening_fence(line)
        if fence is not None:
            body.append(line)
            index += 1
            continue
        heading = _heading(lines, index)
        if heading is not None:
            if any(part.strip() for part in body):
                yield section()
            body = []
            level, title, consumed = heading
            headings = [item for item in headings if item[0] < level]
            headings.append((level, title))
            index += consumed
        else:
            body.append(line)
            index += 1
    if fence is not None:
        raise ChunkingError(f"unclosed code fence in {document.source}")
    if any(part.strip() for part in body):
        yield section()


def _blocks(body: str) -> Iterator[_Block]:
    """Keep paragraphs/lists intact when possible; fenced blocks stay atomic."""
    pending: list[str] = []
    fence: str | None = None
    for line in body.splitlines():
        if fence is not None:
            pending.append(line)
            if _closes_fence(line, fence):
                yield _Block("\n".join(pending), protected=True)
                pending = []
                fence = None
        elif (opening := _opening_fence(line)) is not None:
            if pending:
                yield _Block("\n".join(pending))
            pending = [line]
            fence = opening
        elif not line.strip():
            if pending:
                yield _Block("\n".join(pending))
                pending = []
        else:
            pending.append(line)
    if pending:
        yield _Block("\n".join(pending), protected=fence is not None)


def _pieces(block: _Block, budget: int, window: int) -> Iterator[_Block]:
    if block.words <= budget:
        yield block
        return
    if block.protected:
        raise ChunkingError("code block exceeds chunk budget; shorten it or increase max_words")
    words = list(_WORDS.finditer(block.text))
    start = 0
    while start < len(words):
        end = min(start + window, len(words))
        if end < len(words):
            # Prefer a sentence/line boundary in the latter half of the window.
            # A single oversized sentence falls back to words, never truncation.
            for candidate in range(end, start + window // 2, -1):
                gap = block.text[words[candidate - 1].end():words[candidate].start()]
                if "\n" in gap or _SENTENCE_END.search(words[candidate - 1][0]):
                    end = candidate
                    break
        yield _Block(block.text[words[start].start():words[end - 1].end()])
        start = end


def _tail(blocks: list[_Block], limit: int) -> list[_Block]:
    """Overlap only within this section, without producing broken code fences."""
    result = []
    remaining = limit
    for block in reversed(blocks):
        if remaining <= 0:
            break
        if block.words <= remaining:
            result.insert(0, block)
            remaining -= block.words
        else:
            if not block.protected:
                words = list(_WORDS.finditer(block.text))
                result.insert(0, _Block(block.text[words[-remaining].start():]))
            break
    return result


class MarkdownChunker:
    """Split by section, then paragraph, then sentence/word as necessary.

    Defaults target 500 words, maximum 700 (including repeated headings), and
    up to 75 body words of overlap. Short sections remain short. Code fences
    larger than the budget cause an explicit error instead of broken Markdown.
    """

    def __init__(
        self,
        *,
        target_words: int = 500,
        max_words: int = 700,
        overlap_words: int = 75,
    ) -> None:
        for name, value in (("target_words", target_words), ("max_words", max_words)):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if target_words > max_words:
            raise ValueError("target_words must not exceed max_words")
        if type(overlap_words) is not int or not 0 <= overlap_words < target_words:
            raise ValueError("overlap_words must be non-negative and below target_words")
        self._target = target_words
        self._maximum = max_words
        self._overlap = overlap_words

    def split(self, document: KnowledgeDocument) -> list[KnowledgeChunk]:
        if not isinstance(document, KnowledgeDocument):
            raise TypeError("document must be a KnowledgeDocument")
        if document.status != "APPROVED":
            raise ChunkingError("only APPROVED documents may produce chunks")

        chunks = []
        seen: set[str] = set()
        for section, prefix, body in _sections(document):
            heading_words = len(_WORDS.findall(prefix))
            budget = self._maximum - heading_words
            if budget <= 0:
                raise ChunkingError("heading context leaves no space for section content")
            target = max(1, self._target - heading_words)
            pending: list[_Block] = []
            size = 0

            def emit() -> None:
                content = prefix + "\n\n" + "\n\n".join(block.text for block in pending)
                payload = json.dumps(
                    [document.document_id, document.version, section, content],
                    ensure_ascii=False, separators=(",", ":"),
                )
                chunk_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                if chunk_id in seen:
                    return
                seen.add(chunk_id)
                chunks.append(KnowledgeChunk(
                    chunk_id=chunk_id,
                    document_id=document.document_id,
                    title=document.title,
                    section=section,
                    content=content,
                    source=document.source,
                    audience=document.audience,
                    version=document.version,
                    language=document.language,
                ))

            for block in _blocks(body):
                # Leave room for overlap even for one oversized paragraph.
                window = max(1, min(target, budget - min(self._overlap, budget - 1)))
                for piece in _pieces(block, budget, window):
                    if pending and (size >= target or size + piece.words > budget):
                        emit()
                        pending = _tail(pending, min(self._overlap, budget - piece.words))
                        size = sum(item.words for item in pending)
                    pending.append(piece)
                    size += piece.words
            if pending:
                emit()
        return chunks
