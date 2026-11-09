"""Lint the committed Markdown corpus, without adding a runtime YAML loader.

The helper below accepts only the flat scalar/list frontmatter used by these
fixtures. A complete, safe YAML loader belongs to phase 5A step 3.
"""

from datetime import date
from pathlib import Path
import re

import pytest

from cyberhub_manager.ai import KnowledgeDocument


PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_ROOT = PROJECT_ROOT / "docs" / "knowledge-base"
DOCUMENT_PATHS = sorted(
    path for path in KNOWLEDGE_ROOT.rglob("*.md") if path.name != "README.md"
)


def _read_committed_document(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    _, frontmatter, content = text.split("---\n", 2)
    fields = {}
    list_key = None
    for line in frontmatter.splitlines():
        if line.startswith("  - "):
            assert list_key is not None, path
            fields[list_key].append(line[4:])
        else:
            key, separator, value = line.partition(":")
            assert separator and key not in fields, path
            value = value.strip()
            fields[key] = value if value else []
            list_key = key if not value else None
    assert set(fields) == {
        "id", "title", "audience", "status", "version", "language", "updated_at", "tags"
    }, path
    return KnowledgeDocument(
        document_id=fields["id"],
        title=fields["title"],
        content=content,
        source=path.relative_to(KNOWLEDGE_ROOT).as_posix(),
        audience=tuple(fields["audience"]),
        status=fields["status"],
        version=int(fields["version"]),
        language=fields["language"],
        tags=tuple(fields["tags"]),
        updated_at=date.fromisoformat(fields["updated_at"]),
    )


@pytest.mark.parametrize(
    "path", DOCUMENT_PATHS, ids=lambda path: path.relative_to(KNOWLEDGE_ROOT).as_posix()
)
def test_document_metadata_and_review_sources_are_valid(path):
    document = _read_committed_document(path)
    assert document.content.lstrip().startswith("# " + document.title)
    assert "## Nguồn đối chiếu" in document.content
    source_section = document.content.partition("## Nguồn đối chiếu")[2]
    source_paths = re.findall(r"^- `([^`]+)`", source_section, flags=re.MULTILINE)
    assert source_paths
    for source_path in source_paths:
        assert (PROJECT_ROOT / source_path).is_file(), source_path
    folder = path.parent.name
    if folder == "customer":
        assert document.audience == ("CUSTOMER",)
    elif folder == "staff":
        assert document.audience == ("STAFF", "MANAGER", "ADMIN")
    elif folder == "manager":
        assert document.audience == ("MANAGER", "ADMIN")
    elif folder == "admin":
        assert document.audience == ("ADMIN",)


def test_document_ids_are_unique_and_every_audience_has_approved_knowledge():
    documents = [_read_committed_document(path) for path in DOCUMENT_PATHS]
    assert documents
    ids = [document.document_id for document in documents]
    assert len(ids) == len(set(ids))
    approved_audiences = {
        role for document in documents if document.status == "APPROVED"
        for role in document.audience
    }
    assert approved_audiences == {"CUSTOMER", "STAFF", "MANAGER", "ADMIN"}
