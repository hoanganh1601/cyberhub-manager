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

    return build_mock_services(clock=RunningClock(datetime.now(UTC)),p1=True,customer_offers=customer_portal)


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
            allowed_customer = g.customer is not None and (customer_route or request.path in ("/api/session","/api/logout"))
            if g.actor is None and request.path != "/api/session" and not allowed_customer:
                return error(
                    "AUTH_REQUIRED",
                    "Vui lòng đăng nhập lại.",
                    "Please sign in again.",
                    401,
                )
        return None

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
            "room_type": "Choose Standard or VIP.",
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
        return render_template("index.html")

    @app.get("/customer")
    def customer_portal_page():
        return render_template("index.html",customer_portal=True)

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
        policy = Promotion(promotion_id or 0,text(d,"code"),text(d,"name"),store_id,
                           integer(d,"minimum_amount",minimum=1),integer(d,"bonus_percent"),start,end,d.get("is_active",True))
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
        return reply(g.services.machines.list_machines(g.actor.store_id))

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
    def revenue():
        start = query_date("date_from", today() - timedelta(days=6))
        end = query_date("date_to", today())
        if start > end or (end - start).days > 3660:
            raise ValidationError(
                field_errors={"date_to": "Chọn khoảng ngày hợp lệ, tối đa 10 năm"}
            )
        days = g.services.reports.daily_revenue(g.actor.store_id, start, end)
        return reply(
            dict(
                days=days,
                date_from=start,
                date_to=end,
                total_revenue=sum(item.revenue for item in days),
                invoice_count=sum(item.invoice_count for item in days),
            )
        )

    return app
