"""Phases 5B/5C: backend-filtered live snapshots, role scope and prompt safety."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from cyberhub_manager.ai.fakes import FakeEmbeddingProvider, FakeLLMProvider
from cyberhub_manager.ai.models import AIAccessContext, DynamicAssistantSource, KnowledgeDocument
from cyberhub_manager.ai.policy_store import AssistantLimits
from cyberhub_manager.ai.retrieval import KnowledgeRetriever
from cyberhub_manager.ai.service import RAGAssistantService
from cyberhub_manager.web import create_app


@pytest.fixture
def ctx(tmp_path):
    holder = SimpleNamespace(path=tmp_path / "assistant.sqlite3")

    def factory(sink):
        holder.llm = FakeLLMProvider(response="Phân tích dựa trên snapshot đã lọc. [S1]")
        retriever = KnowledgeRetriever(FakeEmbeddingProvider())
        retriever.rebuild([KnowledgeDocument(
            document_id="shared", title="Quy trình", content="Quy trình CyberHub.",
            source="shared/process.md", audience=("CUSTOMER", "STAFF", "MANAGER", "ADMIN"),
            status="APPROVED", version=1,
        )])
        holder.service = RAGAssistantService(retriever, holder.llm, audit=sink)
        return holder.service

    holder.app = create_app({
        "TESTING": True, "WEB_MODE": "demo", "SECRET_KEY": "5b-5c-tests",
        "ASSISTANT_ENABLED": True, "ASSISTANT_SERVICE_FACTORY": factory,
        "ASSISTANT_AUDIT_PATH": holder.path,
        "ASSISTANT_LIMITS": AssistantLimits(per_minute=20, per_day=100, global_per_day=1000),
    })
    holder.client = holder.app.test_client()
    return holder


def login(ctx, username, kind="employee"):
    csrf = ctx.client.get("/api/session").json["csrf_token"]
    response = ctx.client.post("/api/login", json={
        "username": username, "password": "demo123", "kind": kind,
    }, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200, response.json
    return {"X-CSRF-Token": response.json["csrf_token"]}


def ask(ctx, headers, mode, question="Hãy phân tích", **extra):
    return ctx.client.post("/api/assistant/messages", json={
        "question": question, "language": "vi", "mode": mode, **extra,
    }, headers=headers)


@pytest.mark.parametrize("username,kind,mode", [
    ("nhanvien01", "employee", "analytics"),
    ("nguyenvanan", "customer", "analytics"),
    ("quanly01", "employee", "personalized"),
])
def test_dynamic_modes_cannot_cross_role_boundary(ctx, username, kind, mode):
    headers = login(ctx, username, kind)
    assert ask(ctx, headers, mode).status_code == 403
    assert ctx.llm.calls == []


def test_manager_analytics_contains_only_current_store_aggregates(ctx):
    headers = login(ctx, "quanly01")
    response = ask(ctx, headers, "analytics", days=30)
    assert response.status_code == 200, response.json
    assert response.json["mode"] == "analytics"
    citation, = response.json["citations"]
    assert citation["document_id"] == "analytics-live-snapshot"
    prompt = ctx.llm.calls[0].user_prompt
    assert "CyberHub Cầu Giấy" in prompt
    assert "CyberHub Hà Đông" not in prompt
    assert "customer_name" not in prompt and "phone" not in prompt
    assert "top_machines" in prompt and "low_days" in prompt


def test_admin_analytics_is_filtered_to_all_active_stores(ctx):
    headers = login(ctx, "admin01")
    response = ask(ctx, headers, "analytics", days=7)
    assert response.status_code == 200, response.json
    prompt = ctx.llm.calls[0].user_prompt
    assert "CyberHub Cầu Giấy" in prompt and "CyberHub Hà Đông" in prompt
    assert "password" not in prompt and "username" not in prompt


def test_customer_personalization_uses_only_safe_account_snapshot(ctx):
    headers = login(ctx, "nguyenvanan", "customer")
    response = ask(ctx, headers, "personalized", question="Gợi ý món và voucher")
    assert response.status_code == 200, response.json
    assert response.json["mode"] == "personalized"
    assert {item["document_id"] for item in response.json["citations"]} == {"personalized-membership"}
    prompt = ctx.llm.calls[0].user_prompt
    assert "Cơm chiên" in prompt and "active_vouchers" in prompt and "spins_left" in prompt
    assert "0901000001" not in prompt and "CHDEMO" not in prompt
    assert "password" not in prompt and "customer_name" not in prompt


def test_dynamic_service_rejects_forged_store_source_before_model_call(ctx):
    access = AIAccessContext(1, "MANAGER", (1,))
    forged = DynamicAssistantSource(
        source_id="analytics-forged", title="Forged", section="Other store",
        content="revenue=999999", source="runtime/forged.md",
        audience=("MANAGER",), store_ids=(2,), generated_at=datetime.now(timezone.utc),
    )
    answer = ctx.service.ask_dynamic(
        question="Doanh thu?", access=access, sources=(forged,), mode="analytics",
    )
    assert answer.grounded is False
    assert ctx.llm.calls == []
