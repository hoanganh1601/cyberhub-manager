"""Real temporary Markdown files exercise ingestion, without DB or network."""

from datetime import date
from pathlib import Path

import pytest

from cyberhub_manager.ai.documents import (
    DEFAULT_KNOWLEDGE_ROOT,
    MAX_METADATA_BYTES,
    KnowledgeDocumentLoader,
)
from cyberhub_manager.ai.errors import (
    DocumentTooLargeError,
    DuplicateDocumentError,
    InvalidMetadataError,
    KnowledgePathError,
    KnowledgeReadError,
)

DOCUMENT = """---
id: staff-payment
title: "Thanh toán: tiền bù"
audience:
  - STAFF
  - MANAGER
  - ADMIN
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-09
tags:
  - payment
---
# Thanh toán

Tiền bù phải bằng đúng số tiền còn thiếu.

[Nguồn đối chiếu](../../outside.md)
"""


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / "knowledge-base"
    root.mkdir()
    return root, KnowledgeDocumentLoader(knowledge_root=root)


def write(root, source="staff/payment.md", text=DOCUMENT):
    path = root / source
    path.parent.mkdir(parents=True, exist_ok=True)
    # Preserve fixture bytes on Windows so size/content assertions are portable.
    path.write_bytes(text.encode("utf-8"))
    return path


def symlink(path, target, *, directory=False):
    try:
        path.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable for this OS/user")


def test_loader_accepts_approved_document(corpus):
    root, loader = corpus
    write(root)
    document, = loader.load(str(root))
    assert document.document_id == "staff-payment"
    assert document.title == "Thanh toán: tiền bù"
    assert document.source == "staff/payment.md"
    assert document.audience == ("STAFF", "MANAGER", "ADMIN")
    assert document.status == "APPROVED"
    assert document.version == 1
    assert document.language == "vi"
    assert document.tags == ("payment",)
    assert document.updated_at == date(2026, 11, 9)
    assert document.content == DOCUMENT.split("---\n", 2)[2]


@pytest.mark.parametrize("status", ["DRAFT", "ARCHIVED"])
def test_loader_skips_unapproved_document(corpus, status):
    root, loader = corpus
    write(root, text=DOCUMENT.replace("status: APPROVED", f"status: {status}"))
    assert loader.load() == []


@pytest.mark.parametrize("status", ["APPROVED", "DRAFT", "ARCHIVED"])
def test_loader_rejects_duplicate_id_across_statuses(corpus, status):
    root, loader = corpus
    write(root)
    write(
        root, "admin/duplicate.md",
        DOCUMENT.replace("status: APPROVED", f"status: {status}"),
    )
    with pytest.raises(DuplicateDocumentError, match="staff-payment"):
        loader.load()


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("  - STAFF", "  - SUPERUSER"),
        ("  - MANAGER", "  - STAFF"),
        ("audience:\n  - STAFF\n  - MANAGER\n  - ADMIN", "audience: STAFF"),
        ("status: APPROVED", "status: PUBLIC"),
        ("version: 1", "version: 0"),
        ("version: 1", "version: true"),
        ("version: 1", 'version: "1"'),
        ("language: vi", "language: fr"),
        ("updated_at: 2026-11-09", "updated_at: 2026-02-30"),
        ("updated_at: 2026-11-09", "updated_at: null"),
        ("updated_at: 2026-11-09", "updated_at: 2026-11-09T12:00:00Z"),
        ("id: staff-payment", "id: ../escape"),
        ('title: "Thanh toán: tiền bù"', "title: null"),
        ("tags:\n  - payment", "tags: payment"),
        ("version: 1", "version: 1\nversion: 2"),
        ("version: 1", "version: [unclosed"),
        ("version: 1", "version: 1\nsource: ../../secrets.md"),
        ("version: 1\n", ""),
        ("tags:\n  - payment", "tags: &roles [payment]\nextra: *roles"),
        ("tags:\n  - payment", "tags: !!python/object/apply:os.system ['echo bad']"),
        ("tags:\n  - payment", "tags: [[[nested]]]"),
    ],
)
def test_loader_rejects_invalid_metadata(corpus, before, after):
    root, loader = corpus
    write(root, text=DOCUMENT.replace(before, after))
    with pytest.raises(InvalidMetadataError, match="staff/payment.md"):
        loader.load()


@pytest.mark.parametrize("text", [
    "# No metadata",
    "---\nid: unterminated",
    "---\n---\nbody",
    DOCUMENT[:DOCUMENT.rfind("---")] + "---\n  \n",
])
def test_loader_rejects_missing_metadata_or_empty_body(corpus, text):
    root, loader = corpus
    write(root, text=text)
    with pytest.raises(InvalidMetadataError):
        loader.load()


def test_loader_rejects_invalid_utf8(corpus):
    root, loader = corpus
    write(root).write_bytes(b"\xff\xfe")
    with pytest.raises(InvalidMetadataError):
        loader.load()


def test_loader_supports_crlf_bom_and_quoted_date(corpus):
    root, loader = corpus
    text = DOCUMENT.replace("updated_at: 2026-11-09", 'updated_at: "2026-11-09"')
    write(root).write_bytes(b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode())
    document, = loader.load()
    assert document.updated_at == date(2026, 11, 9)
    assert "Tiền bù" in document.content


def test_loader_ignores_readme_non_markdown_and_does_not_follow_content_links(corpus):
    root, loader = corpus
    write(root)
    write(root, "README.md", "instructions only")
    write(root, "staff/readme.md", "instructions only")
    write(root, "secrets.txt", "not Markdown")
    write(root.parent, "outside.md", "not approved metadata")
    assert len(loader.load()) == 1


def test_loader_cannot_read_outside_knowledge_root(corpus):
    root, loader = corpus
    outside = root.parent / "outside"
    outside.mkdir()
    write(outside)
    with pytest.raises(KnowledgePathError):
        loader.load(outside)
    with pytest.raises(KnowledgePathError):
        loader.load(root.parent)


@pytest.mark.parametrize("directory", [False, True])
def test_loader_rejects_outside_symlinks(corpus, directory):
    root, loader = corpus
    target = root.parent / "outside"
    if directory:
        target.mkdir()
        write(target)
    else:
        target.write_text(DOCUMENT, encoding="utf-8")
    symlink(root / "link.md", target, directory=directory)
    with pytest.raises(KnowledgePathError):
        loader.load()


def test_loader_rejects_internal_and_broken_symlinks(corpus):
    root, loader = corpus
    target = write(root)
    alias = root / "alias.md"
    symlink(alias, target)
    with pytest.raises(KnowledgePathError):
        loader.load()
    alias.unlink()
    symlink(alias, root / "missing.md")
    with pytest.raises(KnowledgePathError):
        loader.load()


def test_loader_rejects_symlink_root(corpus):
    root, loader = corpus
    alias = root.parent / "alias"
    symlink(alias, root, directory=True)
    with pytest.raises(KnowledgePathError):
        loader.load(alias)


def test_loader_missing_root_reports_read_failure(tmp_path):
    with pytest.raises(KnowledgeReadError):
        KnowledgeDocumentLoader(knowledge_root=tmp_path / "missing").load()


def test_loader_rejects_large_file_before_parsing(corpus):
    root, _ = corpus
    write(root)
    limit = len(DOCUMENT.encode("utf-8"))
    loader = KnowledgeDocumentLoader(knowledge_root=root, max_file_bytes=limit)
    assert len(loader.load()) == 1
    write(root, text=DOCUMENT + "x")
    with pytest.raises(DocumentTooLargeError):
        loader.load()


def test_loader_limits_metadata_before_parsing_yaml(corpus):
    root, loader = corpus
    write(root, text=DOCUMENT.replace("  - payment", "  - " + "x" * MAX_METADATA_BYTES))
    with pytest.raises(InvalidMetadataError, match="metadata exceeds byte limit"):
        loader.load()


def test_loader_validates_revoked_metadata_and_refreshes_audience(corpus):
    root, loader = corpus
    path = write(root)
    assert loader.load()[0].audience == ("STAFF", "MANAGER", "ADMIN")
    changed = DOCUMENT.replace("  - STAFF\n", "").replace("version: 1", "version: 2")
    path.write_text(changed, encoding="utf-8")
    assert loader.load()[0].audience == ("MANAGER", "ADMIN")
    assert loader.load()[0].version == 2
    path.write_text(
        changed.replace("APPROVED", "ARCHIVED").replace("MANAGER", "UNKNOWN"),
        encoding="utf-8",
    )
    with pytest.raises(InvalidMetadataError):
        loader.load()


@pytest.mark.parametrize("limit", [0, -1, True, "100"])
def test_loader_rejects_invalid_size_configuration(corpus, limit):
    root, _ = corpus
    with pytest.raises(ValueError):
        KnowledgeDocumentLoader(knowledge_root=root, max_file_bytes=limit)


def test_loader_deterministic_full_reload_removes_revoked_and_deleted_documents(corpus):
    root, loader = corpus
    first = write(root)
    second = write(root, "admin/second.md", DOCUMENT.replace("staff-payment", "admin-second"))
    initial = loader.load()
    assert loader.load() == initial
    assert [item.source for item in initial] == ["admin/second.md", "staff/payment.md"]
    first.write_text(DOCUMENT.replace("APPROVED", "ARCHIVED"), encoding="utf-8")
    second.unlink()
    assert loader.load() == []


def test_invalid_later_file_does_not_return_partial_corpus(corpus):
    root, loader = corpus
    write(root, "a.md")
    write(root, "z.md", "invalid document")
    with pytest.raises(InvalidMetadataError):
        loader.load()


def test_loader_reads_only_approved_committed_corpus():
    documents = KnowledgeDocumentLoader().load(DEFAULT_KNOWLEDGE_ROOT)
    assert len(documents) == 12
    assert all(document.status == "APPROVED" for document in documents)
    assert {document.source for document in documents}.isdisjoint({
        "shared/role-policy.md", "manager/revenue-policy.md",
    })
    assert all(not Path(document.source).is_absolute() for document in documents)
