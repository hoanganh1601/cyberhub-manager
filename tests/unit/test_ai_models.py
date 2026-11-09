"""Identity, metadata and citation invariants for the phase 5A contracts."""

from dataclasses import FrozenInstanceError, replace
from datetime import date

import pytest

from cyberhub_manager.ai import (
    AIAccessContext,
    AssistantAnswer,
    Citation,
    KnowledgeChunk,
    KnowledgeDocument,
)


def document(**changes):
    values = dict(
        document_id="staff-payment-process",
        title="Quy trình thanh toán",
        content="Chỉ xác nhận khi đã nhận khoản thanh toán cần thiết.",
        source="staff/payment-process.md",
        audience=("STAFF", "MANAGER", "ADMIN"),
        status="APPROVED",
        version=1,
        tags=("payment",),
        updated_at=date(2026, 11, 9),
    )
    return KnowledgeDocument(**(values | changes))


def citation(**changes):
    values = dict(
        title="Quy trình thanh toán",
        section="Tiền bù",
        source="staff/payment-process.md",
        chunk_id="chunk-v1-settlement",
        document_id="staff-payment-process",
        version=1,
    )
    return Citation(**(values | changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"actor_id": 0},
        {"actor_id": True},
        {"role": "SUPERUSER"},
        {"store_ids": (0,)},
        {"store_ids": (True,)},
        {"store_ids": (1, 1)},
        {"store_ids": [1]},
        {"language": "fr"},
    ],
)
def test_access_context_rejects_invalid_identity_shape(changes):
    values = dict(actor_id=1, role="STAFF", store_ids=(1,))
    with pytest.raises(ValueError):
        AIAccessContext(**(values | changes))


def test_customer_and_employee_ids_are_distinguished_by_role():
    customer = AIAccessContext(actor_id=1, role="CUSTOMER", store_ids=())
    employee = AIAccessContext(actor_id=1, role="STAFF", store_ids=(1,))
    assert customer != employee
    assert customer.store_ids == ()
    with pytest.raises(FrozenInstanceError):
        employee.role = "ADMIN"


@pytest.mark.parametrize(
    "changes",
    [
        {"document_id": "../payment"},
        {"status": "PUBLIC"},
        {"audience": ()},
        {"audience": ("SHARED",)},
        {"audience": ("STAFF", "STAFF")},
        {"audience": ["STAFF"]},
        {"version": 0},
        {"version": True},
        {"content": " "},
        {"source": "../.env"},
        {"source": "/private/policy.md"},
        {"source": "C:/private/policy.md"},
        {"source": "staff\\payment.md"},
        {"source": "./staff/payment.md"},
        {"source": "https://example.com/policy.md"},
        {"source": "staff/guide.txt"},
        {"updated_at": "2026-11-09"},
    ],
)
def test_document_rejects_ambiguous_metadata_and_source(changes):
    with pytest.raises(ValueError):
        document(**changes)


def test_draft_can_be_represented_without_claiming_it_is_approved():
    draft = document(status="DRAFT")
    assert draft.status == "DRAFT"
    with pytest.raises(FrozenInstanceError):
        draft.status = "APPROVED"


def test_chunk_and_citation_keep_document_identity_and_version():
    doc = document(version=2)
    chunk = KnowledgeChunk(
        chunk_id="chunk-v2-settlement",
        document_id=doc.document_id,
        title=doc.title,
        section="Tiền bù",
        content=doc.content,
        source=doc.source,
        audience=doc.audience,
        version=doc.version,
        language=doc.language,
    )
    ref = citation(chunk_id=chunk.chunk_id, version=chunk.version)
    answer = AssistantAnswer(answer="Theo quy trình [1].", citations=(ref,), grounded=True)
    assert answer.citations[0].document_id == chunk.document_id
    assert answer.citations[0].version == 2
    assert chunk.audience == doc.audience
    with pytest.raises(ValueError):
        replace(chunk, audience=("UNKNOWN",))
    with pytest.raises(ValueError):
        replace(ref, version=0)


@pytest.mark.parametrize(
    "citations, grounded",
    [((), True), ((citation(),), False), ([citation()], True), ((), "false")],
)
def test_answer_rejects_missing_grounding_or_mutable_citations(citations, grounded):
    with pytest.raises(ValueError):
        AssistantAnswer(answer="Trả lời.", citations=citations, grounded=grounded)


def test_no_context_result_has_no_citations():
    result = AssistantAnswer(
        answer="Chưa tìm thấy thông tin đã được phê duyệt.",
        citations=(),
        grounded=False,
    )
    assert not result.grounded
    assert result.citations == ()
