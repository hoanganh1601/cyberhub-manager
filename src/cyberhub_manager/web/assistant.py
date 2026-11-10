"""Opt-in authenticated, stateless assistant API; no business action hooks."""

from dataclasses import asdict
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, g, jsonify, request, session

from cyberhub_manager.ai.errors import InvalidQuestionError
from cyberhub_manager.ai.models import AIAccessContext
from cyberhub_manager.ai.policy_store import (
    AssistantLimits, AssistantQuotaExceeded, SQLiteAssistantPolicyStore,
)
from cyberhub_manager.ai.retrieval import normalize_question
from cyberhub_manager.ai.service import RAGAssistantService
from cyberhub_manager.domain.exceptions import PermissionDeniedError
from .assistant_context import analytics_sources, personalized_sources, validate_mode

_blueprint = Blueprint("assistant", __name__)


def register_assistant(app) -> None:
    """Default off; only backend composition may inject evaluated providers."""
    enabled = app.config.setdefault("ASSISTANT_ENABLED", False)
    if type(enabled) is not bool:
        raise ValueError("ASSISTANT_ENABLED must be a boolean")
    if enabled:
        factory = app.config.get("ASSISTANT_SERVICE_FACTORY")
        path = app.config.get("ASSISTANT_AUDIT_PATH")
        if not callable(factory) or not path:
            raise ValueError("assistant requires a service factory and a private persistent audit path")
        resolved = Path(path).resolve()
        public_roots = (Path(app.root_path).resolve(), Path(str(files("cyberhub_manager.ui.assets"))).resolve())
        if any(resolved.is_relative_to(root) for root in public_roots):
            raise ValueError("assistant audit file must be outside web and asset directories")
        store = SQLiteAssistantPolicyStore(path, limits=app.config.get("ASSISTANT_LIMITS", AssistantLimits()))
        service = factory(store)
        if not isinstance(service, RAGAssistantService) or service._audit is not store:
            raise ValueError("assistant factory must return RAGAssistantService using the supplied audit sink")
        app.extensions["cyberhub_assistant"] = (service, store)
    app.register_blueprint(_blueprint)


def _access(language: str, *, revalidate: bool = False, mode: str = "knowledge") -> AIAccessContext:
    if revalidate and current_app.config["WEB_MODE"] == "demo":
        workspace = current_app.extensions["cyberhub_demo"].get(session.get("workspace"))
        if workspace is None or workspace.services is not g.services:
            raise PermissionDeniedError()
        actor = getattr(g, "actor", None)
        if actor is not None and any(getattr(workspace.actor, field) != getattr(actor, field)
                                     for field in ("employee_id", "role", "store_id")):
            raise PermissionDeniedError()
    customer = getattr(g, "customer", None)
    if customer is not None:
        if revalidate:
            customer = g.services.portal.validate(customer)
        # Accounts are global; 5A does not grant any live store-data permission.
        return AIAccessContext(customer.account_id, "CUSTOMER", (), language)
    actor = getattr(g, "actor", None)
    if actor is None:
        raise PermissionDeniedError()
    if revalidate:
        actor = g.services.management.validate_actor(actor)
    store_ids = (actor.store_id,)
    if actor.role.value == "ADMIN" and mode == "analytics":
        store_ids = tuple(
            store.id for store in g.services.management.list_stores(actor)
            if store.status == "ACTIVE"
        )
    return AIAccessContext(actor.employee_id, actor.role.value, store_ids, language)


def _error(code: str, vi: str, en: str, status: int, request_id: str):
    english = request.headers.get("X-Language") == "en"
    return jsonify(error={"code": code, "message": en if english else vi}, request_id=request_id), status


@_blueprint.post("/api/assistant/messages")
def messages():
    request_id = uuid4().hex  # Never accepted from a body/header supplied by the browser.
    extension = current_app.extensions.get("cyberhub_assistant")
    if extension is None:
        return _error("ASSISTANT_DISABLED", "Trợ lý chưa được bật.", "The assistant is not enabled.", 503, request_id)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) - {
        "question", "language", "conversation_id", "mode", "days", "store_id",
    }:
        return _error("VALIDATION_ERROR", "Chỉ gửi câu hỏi và ngôn ngữ hợp lệ.", "Send only a question and valid language.", 422, request_id)
    language = data.get("language", "vi")
    if not isinstance(language, str) or language not in ("vi", "en") or data.get("conversation_id") is not None:
        return _error("VALIDATION_ERROR", "Ngôn ngữ không hợp lệ hoặc hội thoại chưa được hỗ trợ.", "Invalid language or unsupported saved conversation.", 422, request_id)
    try:
        question = normalize_question(data.get("question"))
    except InvalidQuestionError:
        return _error("VALIDATION_ERROR", "Nhập câu hỏi từ 1 đến 2.000 ký tự.", "Enter a question of 1 to 2,000 characters.", 422, request_id)
    access = _access(language)
    mode = validate_mode(data.get("mode"), access)
    if mode == "analytics":
        access = _access(language, mode=mode)
    days = data.get("days", 30)
    store_id = data.get("store_id")
    if type(days) is not int or days not in (7, 30, 90):
        return _error("VALIDATION_ERROR", "Chọn kỳ 7, 30 hoặc 90 ngày.", "Choose a 7, 30 or 90-day period.", 422, request_id)
    if store_id is not None and (type(store_id) is not int or store_id <= 0):
        return _error("VALIDATION_ERROR", "Cơ sở không hợp lệ.", "Invalid store.", 422, request_id)
    dynamic_sources = ()
    if mode == "analytics":
        dynamic_sources = analytics_sources(
            services=g.services, actor=g.actor, access=access, days=days,
        )
    elif mode == "personalized":
        dynamic_sources = personalized_sources(
            services=g.services, customer=g.customer, access=access, store_id=store_id,
        )
    service, store = extension
    try:
        store.reserve(request_id, access, now=datetime.now(timezone.utc))
    except AssistantQuotaExceeded as exc:
        response, status = _error("RATE_LIMITED", "Đã đạt giới hạn hỏi đáp. Vui lòng thử lại sau.", "Assistant request limit reached. Try again later.", 429, request_id)
        response.headers["Retry-After"] = str(exc.retry_after)
        return response, status
    except Exception:
        current_app.logger.error("Assistant admission failed; request_id=%s", request_id)
        return _unavailable(request_id)
    try:
        # Demo mutations use a workspace lock. Model inference must not hold it
        # and block checkout/logout. Reacquire before checking identity again.
        lock = getattr(g, "workspace_lock", None)
        if lock is not None:
            g.workspace_lock = None
            lock.release()
        try:
            answer = (
                service.ask(question=question, access=access, request_id=request_id)
                if mode == "knowledge" else
                service.ask_dynamic(
                    question=question, access=access, sources=dynamic_sources,
                    mode=mode, request_id=request_id,
                )
            )
        finally:
            if lock is not None:
                lock.acquire()
                g.workspace_lock = lock
        try:
            refreshed = _access(language, revalidate=True, mode=mode)
            if refreshed != access:
                raise PermissionDeniedError()
        except PermissionDeniedError:
            store.suppress(request_id)
            raise
        except Exception:
            store.suppress(request_id)
            return _unavailable(request_id)
        result = store.result(request_id)
        if result in {None, "ACCEPTED"}:
            return _unavailable(request_id)
        if result == "PROVIDER_RATE_LIMITED":
            response, status = _error("ASSISTANT_QUOTA_EXCEEDED",
                                     "Dịch vụ AI đã đạt hạn mức. Vui lòng thử lại sau.",
                                     "The AI provider quota has been reached. Please try again later.",
                                     429, request_id)
            response.headers["Retry-After"] = "60"
            return response, status
        if result == "PROVIDER_AUTH_ERROR":
            return _error("ASSISTANT_CONFIGURATION_ERROR",
                          "Trợ lý chưa được cấp quyền kết nối AI. Vui lòng liên hệ quản trị viên.",
                          "The assistant cannot access its AI provider. Please contact an administrator.",
                          503, request_id)
        if result not in {"ANSWERED", "NO_CONTEXT", "LOW_RELEVANCE"}:
            return _unavailable(request_id)
    except PermissionDeniedError:
        raise
    except Exception:
        # No provider exception, raw question or prompt in HTTP/log output.
        current_app.logger.error("Assistant request failed; request_id=%s", request_id)
        return _unavailable(request_id)
    return jsonify(
        answer=answer.answer, grounded=answer.grounded,
        citations=[asdict(citation) for citation in answer.citations],
        request_id=request_id, conversation_id=None, mode=mode,
    )


def _unavailable(request_id):
    return _error("ASSISTANT_UNAVAILABLE", "Trợ lý hiện không khả dụng. Vui lòng thử lại sau.", "The assistant is unavailable. Please try again later.", 503, request_id)
