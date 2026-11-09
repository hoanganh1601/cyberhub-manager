"""Chunk semantics, source/role preservation and deterministic identifiers."""

from dataclasses import replace
import hashlib
import json
import re

import pytest

from cyberhub_manager.ai.chunking import MarkdownChunker
from cyberhub_manager.ai.documents import KnowledgeDocumentLoader
from cyberhub_manager.ai.errors import ChunkingError
from cyberhub_manager.ai.models import KnowledgeDocument


def document(content="# Thanh toán\n\nChỉ xác nhận khi đã nhận đủ tiền.", **changes):
    values = dict(
        document_id="staff-payment",
        title="Thanh toán",
        content=content,
        source="staff/payment.md",
        audience=("STAFF", "MANAGER", "ADMIN"),
        status="APPROVED",
        version=1,
        language="vi",
    )
    return KnowledgeDocument(**(values | changes))


def numbered_words(count, prefix="word"):
    return " ".join(f"{prefix}{index:04d}" for index in range(count))


def body_words(chunk):
    return re.findall(r"\bword\d{4}\b", chunk.content)


def test_chunk_preserves_source_metadata_and_nested_heading_context():
    source = document(
        "# Thanh toán\n\n## Tiền bù\n\n### Ngoại lệ\n\n"
        "Không cộng tiền khách đưa dư vào ví."
    )
    chunk, = MarkdownChunker().split(source)
    assert chunk.section == "Thanh toán > Tiền bù > Ngoại lệ"
    assert chunk.content == (
        "# Thanh toán\n\n## Tiền bù\n\n### Ngoại lệ\n\n"
        "Không cộng tiền khách đưa dư vào ví."
    )
    for field in ("document_id", "title", "source", "audience", "version", "language"):
        assert getattr(chunk, field) == getattr(source, field)


def test_sibling_headings_do_not_inherit_previous_sibling():
    chunks = MarkdownChunker().split(document(
        "# Thanh toán\n\n## Tiền mặt\n\nNội dung A.\n\n"
        "### Xác nhận\n\nNội dung B.\n\n## Chuyển khoản\n\nNội dung C."
    ))
    assert [chunk.section for chunk in chunks] == [
        "Thanh toán > Tiền mặt",
        "Thanh toán > Tiền mặt > Xác nhận",
        "Thanh toán > Chuyển khoản",
    ]
    assert "Tiền mặt" not in chunks[2].content


def test_preamble_and_headingless_text_keep_document_title():
    chunks = MarkdownChunker().split(document("Giới thiệu.\n\n## Chi tiết\n\nĐiều kiện."))
    assert [chunk.section for chunk in chunks] == ["Thanh toán", "Thanh toán > Chi tiết"]
    assert chunks[0].content == "# Thanh toán\n\nGiới thiệu."


def test_setext_and_closing_hashes_are_headings():
    chunks = MarkdownChunker().split(document(
        "Thanh toán\n=========\n\nTiền bù\n-------\n\nNội dung A.\n\n"
        "## Tiền mặt ###\n\nNội dung B."
    ))
    assert [chunk.section for chunk in chunks] == [
        "Thanh toán > Tiền bù", "Thanh toán > Tiền mặt",
    ]


def test_hash_without_space_and_indented_code_are_not_headings():
    chunk, = MarkdownChunker().split(document(
        "# Thanh toán\n\n#khongphaitieude\n\n    ## code\n    giữ nguyên"
    ))
    assert chunk.section == "Thanh toán"
    assert "#khongphaitieude" in chunk.content
    assert "    ## code\n    giữ nguyên" in chunk.content


@pytest.mark.parametrize("fence", ["```", "~~~~", "````"])
def test_code_block_headings_and_shorter_fences_are_literal(fence):
    content = f"{fence}markdown\n# Không phải mục\n\n## Cũng là code\n```\n{fence}"
    # With a three-backtick fence, the embedded triple closes it; use another literal.
    if fence == "```":
        content = content.replace("\n```\n", "\n~~\n")
    chunk, = MarkdownChunker().split(document("# Thanh toán\n\n" + content))
    assert chunk.section == "Thanh toán"
    assert content in chunk.content


def test_short_sections_are_not_padded_or_joined():
    chunks = MarkdownChunker().split(document(
        "# Thanh toán\n\n## A\n\nMột điều kiện.\n\n## B\n\nMột ngoại lệ."
    ))
    assert len(chunks) == 2
    assert "Một ngoại lệ." not in chunks[0].content
    assert "Một điều kiện." not in chunks[1].content


def test_heading_only_document_does_not_emit_empty_body():
    assert MarkdownChunker().split(document("# Thanh toán\n\n## Trống")) == []


def test_chunk_ids_are_stable_sha256_of_unambiguous_identity():
    source = document()
    chunker = MarkdownChunker()
    chunk, = chunker.split(source)
    assert chunker.split(source) == chunker.split(source)
    payload = json.dumps(
        [source.document_id, source.version, chunk.section, chunk.content],
        ensure_ascii=False, separators=(",", ":"),
    )
    assert chunk.chunk_id == hashlib.sha256(payload.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("changes", [
    {"version": 2},
    {"document_id": "other-document"},
    {"content": "# Thanh toán\n\nChính sách mới."},
    {"title": "Tiêu đề mới"},
])
def test_changing_identity_content_or_version_changes_chunk_id(changes):
    source = document()
    chunker = MarkdownChunker()
    assert chunker.split(source)[0].chunk_id != chunker.split(replace(source, **changes))[0].chunk_id


def test_editing_one_section_does_not_renumber_other_sections():
    source = document("# Thanh toán\n\n## A\n\nNội dung A.\n\n## B\n\nNội dung B.")
    chunker = MarkdownChunker()
    before = chunker.split(source)
    after = chunker.split(replace(source, content=source.content.replace("Nội dung A.", "A mới.")))
    assert before[0].chunk_id != after[0].chunk_id
    assert before[1] == after[1]


def test_repeated_identical_sections_are_deduplicated():
    chunks = MarkdownChunker().split(document(
        "# Thanh toán\n\n## Lưu ý\n\nKhông trả tiền mặt.\n\n"
        "## Lưu ý\n\nKhông trả tiền mặt."
    ))
    assert len(chunks) == 1


@pytest.mark.parametrize("word_count", [701, 1401, 4000])
def test_long_paragraph_is_bounded_overlaps_and_loses_no_words(word_count):
    source = document("# Thanh toán\n\n" + numbered_words(word_count))
    chunks = MarkdownChunker().split(source)
    assert len(chunks) > 1
    assert all(len(chunk.content.split()) <= 700 for chunk in chunks)
    assert all(chunk.content.startswith("# Thanh toán\n\n") for chunk in chunks)
    observed = set()
    for previous, current in zip(chunks, chunks[1:]):
        left, right = body_words(previous), body_words(current)
        assert left[-75:] == right[:75]
        assert int(right[-1][4:]) > int(left[-1][4:])
    for chunk in chunks:
        observed.update(body_words(chunk))
    assert observed == set(numbered_words(word_count).split())


def test_configurable_limits_include_headings_and_do_not_cross_sections():
    source = document(
        "# Thanh toán\n\n## A\n\n" + numbered_words(80) +
        "\n\n## B\n\n" + numbered_words(80, "other")
    )
    chunks = MarkdownChunker(target_words=18, max_words=25, overlap_words=4).split(source)
    assert all(len(chunk.content.split()) <= 25 for chunk in chunks)
    assert all(not ("word0000" in chunk.content and "other0000" in chunk.content) for chunk in chunks)
    assert all("word" not in chunk.content for chunk in chunks if chunk.section.endswith(" > B"))


def test_zero_overlap_does_not_duplicate_body_words():
    chunks = MarkdownChunker(target_words=30, max_words=40, overlap_words=0).split(
        document(numbered_words(100))
    )
    assert [word for chunk in chunks for word in body_words(chunk)] == numbered_words(100).split()


def test_paragraph_with_condition_and_exception_remains_intact():
    rule = "Chỉ nhận đúng tiền thiếu. Ngoại lệ: tiền khách đưa dư phải trả lại khách."
    chunks = MarkdownChunker(target_words=30, max_words=45, overlap_words=5).split(document(
        numbered_words(30) + "\n\n" + rule + "\n\n" + numbered_words(30, "later")
    ))
    assert any(rule in chunk.content for chunk in chunks)


def test_oversized_paragraph_prefers_sentence_boundary():
    first = numbered_words(17) + "."
    chunks = MarkdownChunker(target_words=24, max_words=30, overlap_words=2).split(
        document(first + " " + numbered_words(50, "later"))
    )
    assert chunks[0].content.endswith(first)


def test_fenced_code_is_never_cut_or_overlapped_as_a_fragment():
    code = "```text\n" + numbered_words(20, "code") + "\n```"
    chunks = MarkdownChunker(target_words=25, max_words=35, overlap_words=5).split(
        document(numbered_words(20) + "\n\n" + code + "\n\n" + numbered_words(20, "after"))
    )
    assert sum(code in chunk.content for chunk in chunks) == 1
    assert all(chunk.content.count("```") % 2 == 0 for chunk in chunks)


def test_oversized_code_and_heading_report_explicit_error():
    chunker = MarkdownChunker(target_words=15, max_words=20, overlap_words=3)
    with pytest.raises(ChunkingError, match="code block exceeds"):
        chunker.split(document("```text\n" + numbered_words(50) + "\n```"))
    with pytest.raises(ChunkingError, match="heading context"):
        chunker.split(document("Text", title=numbered_words(20)))


def test_unclosed_fence_does_not_return_partial_result():
    with pytest.raises(ChunkingError, match="unclosed code fence"):
        MarkdownChunker().split(document("# Thanh toán\n\n## A\n\nHợp lệ.\n\n## B\n\n```\ncode"))


@pytest.mark.parametrize("status", ["DRAFT", "ARCHIVED"])
def test_unapproved_document_cannot_produce_chunks(status):
    with pytest.raises(ChunkingError, match="APPROVED"):
        MarkdownChunker().split(document(status=status))


def test_audience_does_not_leak_between_calls_and_language_is_preserved():
    chunker = MarkdownChunker()
    staff, = chunker.split(document())
    admin, = chunker.split(document(document_id="admin-policy", audience=("ADMIN",), language="en"))
    assert staff.audience == ("STAFF", "MANAGER", "ADMIN")
    assert admin.audience == ("ADMIN",)
    assert admin.language == "en"
    assert admin.document_id != staff.document_id


@pytest.mark.parametrize("config", [
    {"target_words": 0}, {"target_words": True}, {"max_words": -1},
    {"max_words": 0.5}, {"target_words": 701}, {"overlap_words": -1},
    {"overlap_words": True}, {"overlap_words": 500},
])
def test_invalid_configuration_is_rejected(config):
    with pytest.raises(ValueError):
        MarkdownChunker(**config)


def test_invalid_document_type_is_rejected():
    with pytest.raises(TypeError):
        MarkdownChunker().split("raw Markdown")


def test_complete_approved_corpus_has_unique_traceable_bounded_chunks():
    documents = KnowledgeDocumentLoader().load()
    chunker = MarkdownChunker()
    all_chunks = []
    for source in documents:
        chunks = chunker.split(source)
        assert chunks
        assert chunks == chunker.split(source)
        assert all(chunk.source == source.source for chunk in chunks)
        assert all(chunk.audience == source.audience for chunk in chunks)
        assert all(chunk.version == source.version for chunk in chunks)
        assert all(len(chunk.content.split()) <= 700 for chunk in chunks)
        all_chunks.extend(chunks)
    assert len({chunk.chunk_id for chunk in all_chunks}) == len(all_chunks)
    assert {chunk.document_id for chunk in all_chunks} == {doc.document_id for doc in documents}
