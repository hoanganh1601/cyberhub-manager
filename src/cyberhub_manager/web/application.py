"""HTTP adapter. Money, permissions and transactions stay in application services."""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import asdict, dataclass, field, is_dataclass, replace
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from hmac import compare_digest
from importlib.resources import files
import os
import secrets
from threading import RLock
from time import monotonic
from typing import Any

from flask import (
    Flask,
    Response,
    g,
    jsonify,
    render_template,
    request,
    send_from_directory,
    session,
)
from mysql.connector import Error as MySQLError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from cyberhub_manager.domain.dtos import EmployeeSession, InvoiceFilters
from cyberhub_manager.domain.enums import (
    CustomerStatus,
    InvoiceStatus,
    PaymentMethod,
    Role,
)
from cyberhub_manager.domain.exceptions import (
    ApplicationError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationError,
)
from cyberhub_manager.services.bootstrap import create_service_bundle
from cyberhub_manager.services.contracts import ServiceBundle
from cyberhub_manager.domain.p1 import CustomerSession, Promotion, ROLE_PERMISSIONS
from cyberhub_manager.domain.loyalty import LoyaltySettings
from cyberhub_manager.services.invoice_export import invoice_html, invoice_csv

UTC = timezone.utc
LOCAL = timezone(timedelta(hours=7))


def serialize(value: Any) -> Any:
    """Serialize DTOs only. Domain models use explicit public-field projections."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        data = asdict(value)
        if hasattr(value,"cash_balance"):
            data["cash_balance"] = value.cash_balance
        return serialize(data)
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [serialize(item) for item in value]
    return value


def customer_public(customer: Any) -> dict:
    account = customer.account
    return dict(
        customer_id=customer.id,
        customer_code=customer.code,
        full_name=customer.full_name,
        phone=customer.phone,
        customer_status=customer.status,
        account_id=account.id,
        account_code=account.code,
        username=account.username,
        balance=account.balance,
        cash_balance=account.cash_balance,
        bonus_balance=account.bonus_balance,
        account_status=account.status,
    )


def machine_public(machine: Any) -> dict:
    return dict(
        machine_id=machine.id,
        machine_code=machine.code,
        store_id=machine.store_id,
        name=machine.name,
        status=machine.status,
        hourly_rate=machine.hourly_rate,
        is_active=machine.is_active,
        updated_at=machine.updated_at,
    )


@dataclass
class DemoWorkspace:
    services: ServiceBundle
    actor: EmployeeSession
    expires: float
    lock: RLock = field(default_factory=RLock)


class DemoRegistry:
    """One independent, bounded demo dataset per login; single-worker deployment."""

    def __init__(self, limit: int = 64) -> None:
        self.entries: dict[str, DemoWorkspace] = {}
        self.lock = RLock()
        self.limit = limit

    def get(self, key: str | None) -> DemoWorkspace | None:
        with self.lock:
            now = monotonic()
            for expired in [
                sid for sid, item in self.entries.items() if item.expires <= now
            ]:
                del self.entries[expired]
            return self.entries.get(key or "")

    def add(self, services: ServiceBundle, actor: EmployeeSession) -> str:
        with self.lock:
            self.get(None)
            if len(self.entries) >= self.limit:
                raise ServiceUnavailableError(
                    "Bản demo đang có nhiều người dùng. Vui lòng thử lại sau."
                )
            key = secrets.token_urlsafe(32)
            self.entries[key] = DemoWorkspace(services, actor, monotonic() + 8 * 3600)
            return key

    def remove(self, key: str | None) -> None:
        with self.lock:
            self.entries.pop(key or "", None)


def _demo_bundle(*, customer_portal=False) -> ServiceBundle:
    from cyberhub_manager.services.mocks.clock import MockClock
    from cyberhub_manager.services.mocks.factory import build_mock_services

    class RunningClock(MockClock):
        def now(self) -> datetime:
            return datetime.now(UTC)

    return build_mock_services(clock=RunningClock(datetime.now(UTC)),p1=True,
                               customer_offers=customer_portal, pos_samples=not customer_portal)


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("CYBERHUB_SECRET_KEY") or secrets.token_hex(32),
        WEB_MODE=os.getenv("CYBERHUB_WEB_MODE", "demo"),
        SESSION_COOKIE_NAME="cyberhub_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("CYBERHUB_COOKIE_SECURE", "false").lower()
        == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=16 * 1024,
        TRUSTED_HOSTS=os.getenv("CYBERHUB_ALLOWED_HOSTS", "").split(",")
        if os.getenv("CYBERHUB_ALLOWED_HOSTS")
        else None,
    )
    app.config.update(config or {})
    if app.config["WEB_MODE"] not in ("demo", "mysql"):
        raise RuntimeError("CYBERHUB_WEB_MODE must be demo or mysql")
    demo = app.config["WEB_MODE"] == "demo"
    if not demo:
        if len(str(app.config["SECRET_KEY"])) < 32 or not (
            os.getenv("CYBERHUB_SECRET_KEY") or (config or {}).get("SECRET_KEY")
        ):
            raise RuntimeError(
                "MySQL web mode requires a stable CYBERHUB_SECRET_KEY of at least 32 characters"
            )
        from cyberhub_manager.config import load_settings

        load_settings()
    if os.getenv("CYBERHUB_TRUST_PROXY", "false").lower() == "true":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0)
    registry = DemoRegistry()
    app.extensions["cyberhub_demo"] = registry
    # Flask g is local to the request; never keep the actor in a process-global variable.
    real_services = (
        None
        if demo
        else create_service_bundle(actor_provider=lambda: getattr(g, "actor", None))
    )
    attempts: OrderedDict[str, deque] = OrderedDict()
    attempts_lock = RLock()

    def reply(data: Any, status: int = 200):
        return jsonify(serialize(data)), status

    def english() -> bool:
        return request.headers.get("X-Language", "vi") == "en"

    def error(code: str, vi: str, en: str, status: int):
        return reply(
            dict(error=dict(code=code, message=en if english() else vi)), status
        )

    def current_actor() -> EmployeeSession | None:
        g.customer = None
        if session.get("customer_id"):
            if demo:
                workspace = registry.get(session.get("workspace"))
                if workspace is None:
                    return None
                workspace.lock.acquire()
                g.workspace_lock = workspace.lock
                g.services = workspace.services
            else:
                g.services = real_services
            principal = CustomerSession(session["customer_id"],session["account_id"],"","",session.get("customer_auth_version",0))
            g.customer = g.services.portal.validate(principal)
            return None
        if demo:
            workspace = registry.get(session.get("workspace"))
            if workspace is None:
                return None
            workspace.lock.acquire()
            g.workspace_lock = workspace.lock
            g.services = workspace.services
            return workspace.services.management.validate_actor(workspace.actor)
        employee_id = session.get("employee_id")
        if type(employee_id) is not int:
            return None
        from cyberhub_manager.database.transaction import transaction
        from cyberhub_manager.repositories.auth_repository import AuthRepository
        from cyberhub_manager.services.db_errors import translate_db_errors

        with translate_db_errors():
            with transaction() as conn:
                actor = AuthRepository().get_active_session_by_id(conn, employee_id)
        if actor is None:
            return None
        g.services = real_services
        if actor.store_id!=session.get("store_id"):
            from cyberhub_manager.services.access import operating_actor
            with translate_db_errors(), transaction() as conn:
                actor = operating_actor(conn,AuthRepository(),replace(actor,store_id=session["store_id"]))
        return actor

    @app.before_request
    def prepare_request():
        if request.path=="/api/portal/avatar":
            request.max_content_length=2*1024*1024+32768
        # Đợt 1: ảnh món ăn cùng giới hạn 2 MB như ảnh đại diện.
        if request.method=="POST" and request.path.startswith("/api/menu/items/") and request.path.endswith("/image"):
            request.max_content_length=2*1024*1024+32768
        if not request.path.startswith("/api/"):
            return None
        session.setdefault("csrf", secrets.token_urlsafe(32))
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            token = request.headers.get("X-CSRF-Token", "")
            if not compare_digest(str(session["csrf"]), token):
                return error(
                    "CSRF_INVALID",
                    "Phiên thao tác không hợp lệ. Vui lòng tải lại trang.",
                    "Invalid request token. Please reload the page.",
                    403,
                )
        if request.path not in ("/api/login",):
            g.actor = current_actor()
            customer_route = request.path.startswith("/api/portal/")
            if customer_route and g.customer is None:
                raise PermissionDeniedError()
            allowed_customer = g.customer is not None and (customer_route or request.path in ("/api/session","/api/logout", "/api/assistant/messages"))
            if g.actor is None and request.path != "/api/session" and not allowed_customer:
                return error(
                    "AUTH_REQUIRED",
                    "Vui lòng đăng nhập lại.",
                    "Please sign in again.",
                    401,
                )
        return None

    from .assistant import register_assistant
    if "ASSISTANT_ENABLED" not in (config or {}):
        from cyberhub_manager.ai.runtime import configure_assistant
        configure_assistant(app)
    register_assistant(app)

    @app.teardown_request
    def release_workspace(_exc):
        lock = getattr(g, "workspace_lock", None)
        if lock is not None:
            lock.release()

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.path.startswith("/api/") or request.path == "/":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ApplicationError)
    def business_error(exc):
        status = {
            "AUTH_INVALID_CREDENTIALS": 401,
            "PERMISSION_DENIED": 403,
            "NOT_FOUND": 404,
            "CONFLICT": 409,
            "SETTLEMENT_REQUIRED": 409,
            "INSUFFICIENT_BALANCE": 409,
            "SERVICE_UNAVAILABLE": 503,
        }.get(exc.code, 422)
        messages = {
            "AUTH_INVALID_CREDENTIALS": "Incorrect username or password.",
            "PERMISSION_DENIED": "You do not have permission to perform this operation.",
            "NOT_FOUND": "The requested record was not found.",
            "CONFLICT": "The data has changed or conflicts with an existing record. Please refresh and try again.",
            "SETTLEMENT_REQUIRED": "The outstanding payment has changed. Please refresh the checkout preview.",
            "INSUFFICIENT_BALANCE": "The account balance is insufficient.",
            "SERVICE_UNAVAILABLE": "The service is temporarily unavailable. Please try again.",
            "VALIDATION_ERROR": "Please check the highlighted fields.",
        }
        hints = {
            "full_name": "Enter a name between 2 and 100 characters.",
            "phone": "Enter 10 digits starting with 0, using an unused phone number.",
            "username": "Use an unused username of 4–30 letters, digits, underscores or dots.",
            "password": "Use at least 6 characters and at most 72 UTF-8 bytes.",
            "amount": "Enter a whole amount from 1 to 100,000,000 VND.",
            "method": "Select cash or bank transfer.",
            "settlement_amount": "The settlement must equal the current outstanding amount.",
            "hourly_rate": "Enter a positive whole hourly rate.",
            "days": "Choose a 7, 30 or 90 day period.",
            "store_id": "Select an active store.",
            "date_from": "Enter a valid start date.",
            "date_to": "Enter a valid end date on or after the start date.",
            "page": "Select a valid page.",
            "keys": "These notifications are no longer available. Please refresh.",
            "current_password": "Enter the correct current password.",
            "new_password": "Use a different password with at least 6 characters and at most 72 UTF-8 bytes.",
            "confirmation": "Enter the new password again, exactly as above.",
            "room_type": "Choose a valid room category.",
            "avatar": "Choose a static JPEG, PNG or WebP image up to 2 MB and 16 megapixels.",
            "minimum_tier": "Choose a valid membership tier.",
            "minimum_points": "Enter a whole point threshold from 0 to 1,000,000,000.",
            "target_customer_id": "Select an existing customer or all eligible customers.",
            "unit_amount": "Enter a positive whole VND amount per point.",
            "platinum_spend": "Tier thresholds must be positive and strictly increasing.",
        }
        return reply(
            dict(
                error=dict(
                    code=exc.code,
                    message=messages.get(
                        exc.code, "The operation could not be completed."
                    )
                    if english()
                    else exc.message,
                    field_errors={
                        key: hints.get(key, "Please check this value.")
                        if english()
                        else value
                        for key, value in exc.field_errors.items()
                    },
                    details={key: value for key, value in exc.details.items()
                             if key in {"settlement_required", "usage_cost", "balance_before"}},
                )
            ),
            status,
        )

    @app.errorhandler(MySQLError)
    def database_error(_exc):
        from cyberhub_manager.services.db_errors import to_application_error

        return business_error(to_application_error(_exc))

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return error(
            exc.name.upper().replace(" ", "_"),
            "Yêu cầu không hợp lệ.",
            exc.name,
            exc.code or 500,
        )

    @app.errorhandler(Exception)
    def unexpected_error(exc):
        app.logger.exception("Unhandled web request failure")
        return error(
            "INTERNAL_ERROR",
            "Không thể xử lý yêu cầu. Vui lòng thử lại.",
            "Unable to process the request. Please try again.",
            500,
        )

    def manager_only(func):
        @wraps(func)
        def decorated(*args, **kwargs):
            if g.actor.role not in (Role.MANAGER, Role.ADMIN):
                raise PermissionDeniedError()
            return func(*args, **kwargs)

        return decorated

    def body() -> dict:
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise ValidationError("Nội dung yêu cầu phải là JSON object")
        return value

    def text(data: dict, key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or len(value) > 500:
            raise ValidationError(field_errors={key: "Giá trị không hợp lệ"})
        return value

    def integer(data: dict, key: str, *, minimum: int = 0) -> int:
        value = data.get(key)
        if type(value) is not int or not minimum <= value <= 2**53 - 1:
            raise ValidationError(
                field_errors={key: "Giá trị phải là số nguyên hợp lệ"}
            )
        return value

    def method(data: dict, *, optional: bool = False) -> PaymentMethod | None:
        value = data.get("method")
        if optional and value is None:
            return None
        if not isinstance(value, str) or value not in ("CASH", "TRANSFER"):
            raise ValidationError(
                field_errors={"method": "Chọn tiền mặt hoặc chuyển khoản"}
            )
        return PaymentMethod(value)

    def query_date(key: str, fallback: date) -> date:
        value = request.args.get(key)
        try:
            return date.fromisoformat(value) if value else fallback
        except ValueError:
            raise ValidationError(field_errors={key: "Ngày không hợp lệ"}) from None

    def today() -> date:
        return datetime.now(LOCAL).date()

    @app.get("/")
    def index():
        return render_template("index.html", assistant_enabled="cyberhub_assistant" in app.extensions)

    @app.get("/customer")
    def customer_portal_page():
        return render_template("index.html",customer_portal=True, assistant_enabled="cyberhub_assistant" in app.extensions)

    @app.get("/healthz")
    def health():
        return reply(dict(status="ok", mode=app.config["WEB_MODE"]))

    @app.get("/assets/<path:name>")
    def assets(name):
        return send_from_directory(str(files("cyberhub_manager.ui.assets")), name)

    @app.get("/api/session")
    def session_state():
        return reply(
            dict(
                actor=g.actor,
                customer=getattr(g,"customer",None),
                csrf_token=session["csrf"],
                mode=app.config["WEB_MODE"],
                today=today(),
            )
        )

    @app.post("/api/login")
    def login():
        data = body()
        username, password = text(data, "username"), text(data, "password")
        remote = request.remote_addr or "unknown"
        with attempts_lock:
            now = monotonic()
            times = attempts.setdefault(remote, deque())
            while times and times[0] < now - 600:
                times.popleft()
            if len(times) >= 10:
                response, status = error(
                    "RATE_LIMITED",
                    "Thử đăng nhập quá nhiều lần. Vui lòng thử lại sau 10 phút.",
                    "Too many sign-in attempts. Please try again in 10 minutes.",
                    429,
                )
                response.headers["Retry-After"] = "600"
                return response, status
            times.append(now)
            attempts.move_to_end(remote)
            if len(attempts) > 4096:
                attempts.popitem(last=False)
        customer_login = data.get("kind")=="customer"
        services = _demo_bundle(customer_portal=customer_login) if demo else real_services
        actor = services.portal.login(username,password) if customer_login else services.auth.login(username, password)
        workspace = registry.add(services, actor) if demo else None
        registry.remove(session.get("workspace"))
        session.clear()
        session.permanent = True
        session["csrf"] = secrets.token_urlsafe(32)
        if customer_login:
            session.update(customer_id=actor.customer_id,account_id=actor.account_id,customer_auth_version=actor.auth_version)
        else:
            session.update(employee_id=actor.employee_id,store_id=actor.store_id)
        if demo:
            session["workspace"] = workspace
        with attempts_lock:
            attempts.pop(remote, None)
        return reply(
            dict(
                actor=None if customer_login else actor,
                customer=actor if customer_login else None,
                csrf_token=session["csrf"],
                mode=app.config["WEB_MODE"],
                today=today(),
            )
        )

    @app.post("/api/logout")
    def logout():
        registry.remove(session.get("workspace"))
        session.clear()
        session["csrf"] = secrets.token_urlsafe(32)
        return reply(dict(csrf_token=session["csrf"]))

    @app.get("/api/management")
    def management_overview():
        return reply(dict(stores=g.services.management.list_stores(g.actor),permissions=sorted(str(p) for p in ROLE_PERMISSIONS[g.actor.role])))

    @app.post("/api/store/switch")
    def switch_store():
        actor = g.services.management.switch_store(g.actor,integer(body(),"store_id",minimum=1))
        session["store_id"] = actor.store_id
        if demo:
            registry.get(session["workspace"]).actor = actor
        return reply(dict(actor=actor))

    @app.get("/api/stores")
    def list_stores():
        return reply(g.services.management.list_stores(g.actor))

    @app.route("/api/stores",methods=["POST"])
    @app.route("/api/stores/<int:store_id>",methods=["PATCH"])
    def save_store(store_id=None):
        d = body()
        return reply(g.services.management.save_store(g.actor,store_id,text(d,"code"),text(d,"name"),text(d,"address"),d.get("status","ACTIVE")))

    @app.get("/api/employees")
    def list_employees():
        return reply(g.services.management.list_employees(g.actor))

    @app.route("/api/employees",methods=["POST"])
    @app.route("/api/employees/<int:employee_id>",methods=["PATCH"])
    def save_employee(employee_id=None):
        d = body()
        return reply(g.services.management.save_employee(g.actor,employee_id,integer(d,"store_id",minimum=1),
            text(d,"full_name"),text(d,"username"),d.get("role","STAFF"),d.get("status","ACTIVE"),d.get("password","")))

    @app.get("/api/promotions")
    def list_promotions():
        return reply(g.services.management.list_promotions(g.actor))

    @app.route("/api/promotions",methods=["POST"])
    @app.route("/api/promotions/<int:promotion_id>",methods=["PATCH"])
    def save_promotion(promotion_id=None):
        d = body()
        try:
            start,end = datetime.fromisoformat(text(d,"starts_at")),datetime.fromisoformat(text(d,"ends_at"))
        except ValueError:
            raise ValidationError(field_errors={"ends_at":"Ngày giờ không hợp lệ"}) from None
        store_id = None if d.get("store_id") is None else integer(d,"store_id",minimum=1)
        old=next((p for p in g.services.management.list_promotions(g.actor) if p.id==promotion_id),None) if promotion_id else None
        target=d.get('target_customer_id',old.target_customer_id if old else None)
        if target is not None:
            target=integer({'target_customer_id':target},'target_customer_id',minimum=1)
        policy = Promotion(promotion_id or 0,text(d,"code"),text(d,"name"),store_id,
                           integer(d,"minimum_amount",minimum=1),integer(d,"bonus_percent"),start,end,d.get("is_active",True),
                           d.get('minimum_tier',old.minimum_tier if old else 'BRONZE'),
                           d.get('minimum_points',old.minimum_points if old else 0),target)
        return reply(g.services.management.save_promotion(g.actor,policy))

    @app.post("/api/customers/<int:customer_id>/topup-preview")
    def topup_preview(customer_id):
        return reply(g.services.wallet.preview_top_up(customer_id,integer(body(),"amount",minimum=1),g.actor.employee_id))

    def exported(detail):
        csv_format = request.args.get("format")=="csv"
        import re
        filename = re.sub(r"[^A-Za-z0-9_-]","_",detail.invoice.invoice_code)
        content = invoice_csv(detail) if csv_format else invoice_html(detail,"en" if english() else "vi")
        response = Response(content,content_type="text/csv; charset=utf-8" if csv_format else "text/html; charset=utf-8")
        disposition = "attachment" if csv_format or request.args.get("download")=="1" else "inline"
        response.headers["Content-Disposition"] = f'{disposition}; filename="{filename}.{ "csv" if csv_format else "html" }"'
        return response

    @app.get("/api/invoices/<int:invoice_id>/export")
    def export_invoice(invoice_id):
        detail = g.services.reports.get_invoice(invoice_id)
        if detail.invoice.store_id!=g.actor.store_id:
            raise PermissionDeniedError()
        return exported(detail)

    @app.get("/api/portal/snapshot")
    def portal_snapshot():
        return reply(g.services.portal.snapshot(g.customer))

    def portal_integer(name, default=None):
        value = request.args.get(name)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            raise ValidationError(field_errors={name: "Số nguyên không hợp lệ"}) from None

    @app.get("/api/portal/dashboard")
    def portal_dashboard():
        return reply(g.services.portal.dashboard(g.customer, portal_integer("days", 30), portal_integer("store_id")))

    @app.get("/api/portal/history")
    def portal_history():
        return reply(g.services.portal.history(
            g.customer, request.args.get("kind", "transactions"), request.args.get("status", "all"),
            request.args.get("date_from"), request.args.get("date_to"),
            portal_integer("page", 1), portal_integer("page_size", 10)))

    @app.post("/api/portal/topup-preview")
    def portal_promotion_quote():
        data = body()
        return reply(g.services.portal.promotion_quote(
            g.customer, integer(data, "store_id", minimum=1), integer(data, "amount", minimum=1)))

    @app.get("/api/portal/notifications")
    def portal_notifications():
        return reply(g.services.portal.notifications(g.customer))

    @app.post("/api/portal/notifications/read")
    def portal_notifications_read():
        return reply(g.services.portal.mark_notifications_read(g.customer, body().get("keys")))

    @app.get("/api/portal/availability")
    def portal_availability():
        return reply(g.services.portal.availability(g.customer,portal_integer("store_id")))

    @app.get("/api/portal/usage")
    def portal_usage():
        return reply(g.services.portal.usage_analysis(g.customer,portal_integer("days",30)))

    @app.get("/api/portal/profile")
    def portal_profile():
        return reply(g.services.portal.profile(g.customer))

    @app.patch("/api/portal/profile")
    def portal_profile_update():
        data=body()
        return reply(g.services.portal.update_profile(g.customer,text(data,"full_name"),text(data,"phone"),data.get("current_password")))

    @app.post("/api/portal/password")
    def portal_password():
        data=body()
        customer=g.services.portal.change_password(g.customer,data.get("current_password"),data.get("new_password"),data.get("confirmation"))
        session["customer_auth_version"]=customer.auth_version
        session["csrf"]=secrets.token_urlsafe(32)
        return reply(dict(customer=customer,csrf_token=session["csrf"]))

    @app.get('/api/portal/member')
    def portal_member():
        return reply(g.services.portal.member(g.customer,portal_integer('page',1)))

    @app.get('/api/portal/avatar')
    def portal_avatar():
        image=g.services.portal.avatar(g.customer)
        return Response(image['image_data'],content_type='image/webp')

    @app.post('/api/portal/avatar')
    def portal_avatar_upload():
        upload=request.files.get('avatar')
        if upload is None:
            raise ValidationError(field_errors={'avatar':'Vui lòng chọn ảnh đại diện'})
        return reply(g.services.portal.update_avatar(g.customer,upload.read(2*1024*1024+1)))

    @app.delete('/api/portal/avatar')
    def portal_avatar_remove():
        return reply(g.services.portal.remove_avatar(g.customer))

    @app.get('/api/loyalty/settings')
    def loyalty_settings():
        return reply(g.services.management.loyalty_settings(g.actor))

    @app.put('/api/loyalty/settings')
    def loyalty_settings_update():
        data=body()
        values={k:integer(data,k,minimum=1) for k in ('unit_amount','silver_spend','gold_spend','platinum_spend','version')}
        return reply(g.services.management.update_loyalty_settings(g.actor,LoyaltySettings(enabled=data.get('enabled'),**values)))

    @app.get("/api/machine-rooms")
    def machine_rooms():
        return reply(g.services.management.list_machine_rooms(g.actor))

    @app.patch("/api/machines/<int:machine_id>/room-type")
    def machine_room_update(machine_id):
        return reply(g.services.management.set_machine_room(g.actor,machine_id,body().get("room_type")))

    @app.get("/api/portal/invoices/<int:invoice_id>/export")
    def portal_export(invoice_id):
        return exported(g.services.portal.invoice(g.customer,invoice_id))

    @app.get("/api/machines")
    def machines():
        rooms = {item["machine_id"]: item["room_type"] for item in g.services.management.list_machine_rooms(g.actor)}
        return reply([
            dict(serialize(machine), room_type=rooms.get(machine.machine_id, "STANDARD"))
            for machine in g.services.machines.list_machines(g.actor.store_id)
        ])

    @app.post("/api/machines")
    @manager_only
    def create_machine():
        data = body()
        machine = g.services.machines.create_machine(
            text(data, "code"),
            g.actor.store_id,
            text(data, "name"),
            integer(data, "hourly_rate", minimum=1),
            g.actor,
        )
        return reply(machine_public(machine), 201)

    @app.patch("/api/machines/<int:machine_id>")
    @manager_only
    def update_machine(machine_id):
        data = body()
        return reply(
            machine_public(
                g.services.machines.update_machine(
                    machine_id,
                    text(data, "name"),
                    integer(data, "hourly_rate", minimum=1),
                    g.actor,
                )
            )
        )

    @app.post("/api/machines/<int:machine_id>/maintenance")
    @manager_only
    def maintenance(machine_id):
        enabled = body().get("enabled")
        if type(enabled) is not bool:
            raise ValidationError(field_errors={"enabled": "Giá trị phải là boolean"})
        return reply(
            machine_public(
                g.services.machines.set_maintenance(machine_id, enabled, g.actor)
            )
        )

    @app.post("/api/machines/<int:machine_id>/archive")
    @manager_only
    def archive(machine_id):
        return reply(g.services.machines.archive_machine(machine_id, g.actor))

    @app.get("/api/customers")
    def customers():
        return reply(
            g.services.customers.search_customers(request.args.get("keyword", "")[:200])
        )

    @app.get("/api/customers/<int:customer_id>")
    def customer(customer_id):
        return reply(
            dict(
                customer=customer_public(
                    g.services.customers.get_customer(customer_id)
                ),
                history=g.services.wallet.get_history(customer_id),
            )
        )

    @app.post("/api/customers")
    def create_customer():
        data = body()
        return reply(
            customer_public(
                g.services.customers.create_customer(
                    text(data, "full_name"),
                    text(data, "phone"),
                    text(data, "username"),
                    text(data, "password"),
                )
            ),
            201,
        )

    @app.patch("/api/customers/<int:customer_id>")
    def update_customer(customer_id):
        data = body()
        return reply(
            customer_public(
                g.services.customers.update_customer(
                    customer_id, text(data, "full_name"), text(data, "phone")
                )
            )
        )

    @app.post("/api/customers/<int:customer_id>/status")
    @manager_only
    def customer_status(customer_id):
        value = body().get("status")
        if value not in ("ACTIVE", "INACTIVE"):
            raise ValidationError(field_errors={"status": "Trạng thái không hợp lệ"})
        return reply(
            customer_public(
                g.services.customers.set_customer_status(
                    customer_id, CustomerStatus(value), g.actor
                )
            )
        )

    @app.post("/api/customers/<int:customer_id>/topup")
    def topup(customer_id):
        data = body()
        return reply(
            g.services.wallet.top_up(
                customer_id,
                integer(data, "amount", minimum=1),
                method(data),
                g.actor.employee_id,
            )
        )

    @app.post("/api/machines/<int:machine_id>/open-preview")
    def open_preview(machine_id):
        return reply(
            g.services.sessions.preview_open(
                integer(body(), "customer_id", minimum=1), machine_id, g.actor
            )
        )

    @app.post("/api/machines/<int:machine_id>/open")
    def open_session(machine_id):
        return reply(
            g.services.sessions.open_session(
                integer(body(), "customer_id", minimum=1), machine_id, g.actor
            ),
            201,
        )

    @app.get("/api/machines/<int:machine_id>/checkout-preview")
    def checkout_preview(machine_id):
        return reply(
            g.services.sessions.preview_checkout(machine_id, datetime.now(UTC))
        )

    @app.post("/api/machines/<int:machine_id>/checkout")
    def checkout(machine_id):
        data = body()
        amount = integer(data, "settlement_amount")
        payment = method(data, optional=True)
        if amount == 0 and payment is not None:
            raise ValidationError(
                field_errors={"method": "Không chọn phương thức khi không cần tiền bù"}
            )
        # Real service rechecks under database locks. Mirror the exact contract in demo.
        if demo:
            preview = g.services.sessions.preview_checkout(
                machine_id, datetime.now(UTC)
            )
            if amount != preview.settlement_required:
                raise ValidationError(
                    field_errors={
                        "settlement_amount": "Tiền bù phải bằng đúng số tiền còn thiếu"
                    },
                    details={"settlement_required": preview.settlement_required},
                )
        return reply(
            g.services.sessions.complete_checkout(machine_id, g.actor, amount, payment)
        )

    @app.get("/api/invoices")
    def invoices():
        status = request.args.get("status") or None
        if status not in (None, "PAID", "VOID"):
            raise ValidationError(field_errors={"status": "Trạng thái không hợp lệ"})
        filters = InvoiceFilters(
            date_from=query_date("date_from", today() - timedelta(days=30)),
            date_to=query_date("date_to", today()),
            keyword=request.args.get("keyword", "")[:200],
            status=InvoiceStatus(status) if status else None,
        )
        return reply(g.services.reports.list_invoices(g.actor.store_id, filters))

    @app.get("/api/invoices/<int:invoice_id>")
    def invoice(invoice_id):
        detail = g.services.reports.get_invoice(invoice_id)
        if detail.invoice.store_id!=g.actor.store_id:
            raise PermissionDeniedError()
        return reply(detail)

    @app.get("/api/revenue")
    @manager_only
    def revenue():
        start = query_date("date_from", today() - timedelta(days=6))
        end = query_date("date_to", today())
        if start > end or (end - start).days > 3660:
            raise ValidationError(
                field_errors={"date_to": "Chọn khoảng ngày hợp lệ, tối đa 10 năm"}
            )
        days = g.services.reports.daily_revenue(g.actor.store_id, start, end)
        pos = g.services.menu.paid_revenue(g.actor, start, end)
        by_day = {item.date: dict(date=item.date, invoice_count=item.invoice_count,
                                  machine_revenue=item.revenue, menu_order_count=0,
                                  menu_revenue=0, revenue=item.revenue) for item in days}
        for item in pos["days"]:
            day = by_day.setdefault(item["date"], dict(date=item["date"], invoice_count=0,
                                    machine_revenue=0, menu_order_count=0,
                                    menu_revenue=0, revenue=0))
            day["menu_order_count"] = item["order_count"]
            day["menu_revenue"] = item["revenue"]
            day["revenue"] += item["revenue"]
        combined = [by_day[day] for day in sorted(by_day)]
        return reply(
            dict(
                days=combined,
                date_from=start,
                date_to=end,
                machine_revenue=sum(item.revenue for item in days),
                menu_revenue=sum(item["revenue"] for item in pos["days"]),
                menu_order_count=sum(item["order_count"] for item in pos["days"]),
                top_menu_items=pos["top_items"],
                total_revenue=sum(item["revenue"] for item in combined),
                invoice_count=sum(item.invoice_count for item in days),
            )
        )

    # ----- Đợt 1: menu đồ ăn/đồ uống ----------------------------------------------
    # Kiểu dữ liệu (int/bool) được MenuService kiểm tra; route chỉ chuyển giá trị thô.
    @app.get("/api/portal/menu")
    def portal_menu():
        return reply(g.services.menu.portal_menu(g.customer, portal_integer("store_id")))

    @app.post("/api/portal/menu/orders")
    def portal_menu_order():
        data = body()
        return reply(
            g.services.menu.place_order(g.customer, data.get("lines"), data.get("note", "")), 201
        )

    @app.get("/api/portal/menu/items/<int:item_id>/image")
    def portal_menu_image(item_id):
        return Response(g.services.menu.portal_image(g.customer, item_id), content_type="image/webp")

    @app.get("/api/menu")
    def menu_manage():
        return reply(g.services.menu.manage_menu(g.actor))

    @app.route("/api/menu/categories", methods=["POST"])
    @app.route("/api/menu/categories/<int:category_id>", methods=["PATCH"])
    def menu_category_save(category_id=None):
        data = body()
        return reply(
            g.services.menu.save_category(
                g.actor,
                category_id,
                page=data.get("page"),
                name=data.get("name"),
                sort_order=data.get("sort_order", 0),
                is_active=data.get("is_active", True),
            )
        )

    @app.route("/api/menu/items", methods=["POST"])
    @app.route("/api/menu/items/<int:item_id>", methods=["PATCH"])
    def menu_item_save(item_id=None):
        data = body()
        return reply(
            g.services.menu.save_item(
                g.actor,
                item_id,
                category_id=data.get("category_id"),
                name=data.get("name"),
                description=data.get("description", ""),
                price=data.get("price"),
                sort_order=data.get("sort_order", 0),
                is_visible=data.get("is_visible", True),
                is_available=data.get("is_available", True),
            )
        )

    @app.post("/api/menu/items/<int:item_id>/availability")
    def menu_item_availability(item_id):
        return reply(g.services.menu.set_item_available(g.actor, item_id, body().get("available")))

    @app.get("/api/menu/items/<int:item_id>/image")
    def menu_item_image(item_id):
        return Response(g.services.menu.item_image(g.actor, item_id), content_type="image/webp")

    @app.post("/api/menu/items/<int:item_id>/image")
    def menu_item_image_upload(item_id):
        upload = request.files.get("image")
        if upload is None:
            raise ValidationError(field_errors={"image": "Vui lòng chọn ảnh món"})
        return reply(g.services.menu.upload_item_image(g.actor, item_id, upload.read(2 * 1024 * 1024 + 1)))

    @app.get("/api/menu/items/<int:item_id>/history")
    def menu_item_history(item_id):
        return reply(g.services.menu.item_history(g.actor, item_id))

    @app.get("/api/menu/orders")
    def menu_orders():
        return reply(g.services.menu.list_orders(g.actor, request.args.get("status", "NEW")))

    @app.post("/api/menu/orders/<int:order_id>/status")
    def menu_order_status(order_id):
        return reply(g.services.menu.finish_order(g.actor, order_id, body().get("status")))

    @app.post("/api/menu/orders/<int:order_id>/payment")
    def menu_order_payment(order_id):
        return reply(g.services.menu.pay_order(g.actor, order_id, body().get("method")))

    # ----- Đợt 2: voucher và phần thưởng ------------------------------------------
    @app.get("/api/portal/vouchers")
    def portal_vouchers():
        return reply(g.services.vouchers.portal_vouchers(g.customer))

    @app.get("/api/vouchers")
    def vouchers_overview():
        return reply(g.services.vouchers.overview(g.actor))

    @app.route("/api/rewards", methods=["POST"])
    @app.route("/api/rewards/<int:catalog_id>", methods=["PATCH"])
    def reward_save(catalog_id=None):
        data = body()
        return reply(
            g.services.vouchers.save_reward(
                g.actor,
                catalog_id,
                code=data.get("code"),
                name=data.get("name"),
                reward_type=data.get("reward_type"),
                value=data.get("value"),
                min_order_amount=data.get("min_order_amount", 0),
                valid_days=data.get("valid_days"),
                coin_cost=data.get("coin_cost"),
                is_active=data.get("is_active", True),
                all_stores=data.get("all_stores", False),
            )
        )

    @app.post("/api/vouchers/issue")
    def voucher_issue():
        data = body()
        return reply(g.services.vouchers.issue_voucher(g.actor, data.get("catalog_id"), data.get("customer_id")), 201)

    @app.get("/api/vouchers/lookup")
    def voucher_lookup():
        return reply(g.services.vouchers.lookup(g.actor, request.args.get("code", "")[:40]))

    @app.post("/api/vouchers/redeem")
    def voucher_redeem():
        data = body()
        return reply(
            g.services.vouchers.redeem(g.actor, data.get("code"), data.get("customer_id"), data.get("order_id"))
        )

    @app.post("/api/vouchers/<int:voucher_id>/revoke")
    def voucher_revoke(voucher_id):
        return reply(g.services.vouchers.revoke(g.actor, voucher_id, body().get("reason")))

    # ----- Đợt 3: vòng quay và xu game ----------------------------------------------
    @app.get("/api/portal/game")
    def portal_game():
        return reply(g.services.games.portal_game(g.customer))

    @app.post("/api/portal/game/spin")
    def portal_game_spin():
        # Không đọc body: kết quả do máy chủ bốc thăm, trình duyệt không gửi điểm/kết quả.
        return reply(g.services.games.spin(g.customer))

    @app.post("/api/portal/game/redeem")
    def portal_game_redeem():
        data = body()
        return reply(g.services.games.redeem(g.customer, data.get("catalog_id"), data.get("request_key")))

    @app.get("/api/games")
    def games_manage():
        return reply(g.services.games.manage(g.actor))

    @app.put("/api/games")
    def games_save():
        data = body()
        return reply(
            g.services.games.save_game(
                g.actor,
                is_active=data.get("is_active"),
                daily_limit=data.get("daily_limit"),
                min_interval_seconds=data.get("min_interval_seconds"),
                prizes=data.get("prizes"),
            )
        )

    @app.post("/api/games/wallets/<int:account_id>/lock")
    def games_wallet_lock(account_id):
        data = body()
        return reply(g.services.games.set_wallet_lock(g.actor, account_id, data.get("locked"), data.get("reason", "")))

    # ----- Đợt 4: quảng cáo nhận thưởng ----------------------------------------------
    @app.get("/api/portal/ads")
    def portal_ads():
        return reply(g.services.ads.portal_ads(g.customer))

    @app.post("/api/portal/ads/start")
    def portal_ads_start():
        return reply(g.services.ads.start(g.customer))

    @app.post("/api/portal/ads/complete")
    def portal_ads_complete():
        # Chỉ nhận token; thời lượng xem do máy chủ tự đo, không tin số giây trình duyệt gửi.
        return reply(g.services.ads.complete(g.customer, body().get("token")))

    @app.get("/api/ads")
    def ads_overview():
        return reply(g.services.ads.overview(g.actor))

    @app.put("/api/ads/settings")
    def ads_settings():
        data = body()
        return reply(
            g.services.ads.save_settings(
                g.actor,
                enabled=data.get("enabled"),
                mode=data.get("mode"),
                daily_cap=data.get("daily_cap"),
                reward_type=data.get("reward_type"),
                reward_amount=data.get("reward_amount"),
            )
        )

    @app.route("/api/ads/creatives", methods=["POST"])
    @app.route("/api/ads/creatives/<int:creative_id>", methods=["PATCH"])
    def ads_creative_save(creative_id=None):
        data = body()
        return reply(
            g.services.ads.save_creative(
                g.actor,
                creative_id,
                code=data.get("code"),
                title=data.get("title"),
                body=data.get("body"),
                cta=data.get("cta", ""),
                duration_seconds=data.get("duration_seconds"),
                is_active=data.get("is_active", True),
            )
        )

    @app.get("/ads/callback")
    def ads_network_callback():
        # Callback server-to-server của mạng quảng cáo: không có phiên đăng nhập, xác thực bằng chữ ký HMAC.
        # Nằm ngoài /api nên không qua kiểm tra đăng nhập/CSRF; chỉ hoạt động ở chế độ MySQL.
        if real_services is None:
            return error("NOT_AVAILABLE", "Không hỗ trợ ở chế độ demo", "Not available in demo mode", 404)
        result = real_services.ads.verify_network_callback(
            request.args.get("token", "")[:64], request.args.get("txn", "")[:100], request.args.get("sig", "")[:128]
        )
        return reply(dict(ok=True, reward_type=result["reward_type"], reward_amount=result["reward_amount"]))

    return app
