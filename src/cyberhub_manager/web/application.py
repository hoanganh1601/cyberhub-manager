"""HTTP adapter. Money, permissions and transactions stay in application services."""

from __future__ import annotations

from collections import OrderedDict, deque
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from hmac import compare_digest
from importlib.resources import files
import re
import secrets
from threading import RLock
from time import monotonic
from typing import Any

from flask import (
    Flask,
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

from cyberhub_manager.domain.dtos import EmployeeSession
from cyberhub_manager.domain.enums import PaymentMethod, Role
from cyberhub_manager.domain.exceptions import (
    ApplicationError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationError,
)
from cyberhub_manager.services.bootstrap import create_service_bundle
from cyberhub_manager.domain.p1 import CustomerSession
from cyberhub_manager.domain.p1 import Permission, can, permissions_for
from cyberhub_manager.web.demo import DemoRegistry, build_demo_bundle
from cyberhub_manager.web.config import configure_web_app
from cyberhub_manager.web.serialization import serialize
from cyberhub_manager.web.feature_routes import register_feature_routes
from cyberhub_manager.web.operations_routes import register_operations_routes

UTC = timezone.utc
LOCAL = timezone(timedelta(hours=7))


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    demo = configure_web_app(app, config)
    if not demo:
        from cyberhub_manager.config import load_settings

        load_settings()
    if app.config["TRUST_PROXY"]:
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
        if real_services.identity is None:
            return None
        actor = real_services.identity.resolve(
            session.get("employee_id"),
            session.get("employee_auth_version", 0),
            session.get("store_id"),
        )
        if actor is None:
            return None
        g.services = real_services
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
        if request.path not in ("/api/login", "/api/register"):
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
            if (
                g.actor is not None
                and g.actor.credential_update_required
                and request.path not in ("/api/session", "/api/logout", "/api/employee/password")
            ):
                return error(
                    "PASSWORD_CHANGE_REQUIRED",
                    "Bạn phải đổi mật khẩu tạm trước khi tiếp tục.",
                    "You must change the temporary password before continuing.",
                    403,
                )
            if g.actor is not None and app.config["RBAC_POLICY"] == "separated" and g.actor.role == Role.ADMIN:
                credential_path = (
                    (request.method == "GET" and request.path in
                     ("/api/session", "/api/management", "/api/stores", "/api/employees", "/api/employee-profiles"))
                    or (request.method == "POST" and request.path in
                        ("/api/logout", "/api/employee/password", "/api/employees"))
                    or (request.method == "PATCH" and
                        re.fullmatch(r"/api/employees/[1-9][0-9]*", request.path))
                    or (request.method == "POST" and
                        re.fullmatch(r"/api/employees/[1-9][0-9]*/reset-password", request.path))
                    or (request.method == "POST" and
                        re.fullmatch(r"/api/employees/[1-9][0-9]*/store-assignments", request.path))
                    or (request.method == "GET" and
                        re.fullmatch(r"/api/employees/[1-9][0-9]*/store-assignments", request.path))
                )
                if not credential_path:
                    raise PermissionDeniedError()
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
            "current_password": "Enter the correct current password.",
            "new_password": "Use a different password with at least 6 characters and at most 72 UTF-8 bytes.",
            "confirmation": "Enter the new password again, exactly as above.",
            "room_type": "Choose a valid room category.",
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

    def require_permission(permission):
        def decorate(func):
            @wraps(func)
            def decorated(*args, **kwargs):
                if not can(g.actor.role, permission):
                    raise PermissionDeniedError()
                return func(*args, **kwargs)
            return decorated
        return decorate

    revenue_reader = require_permission(Permission.VIEW_REVENUE)

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
        return render_template("index.html", customer_portal=True)

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
                permissions=sorted(str(p) for p in permissions_for(g.actor.role)) if g.actor else [],
                customer=getattr(g,"customer",None),
                csrf_token=session["csrf"],
                mode=app.config["WEB_MODE"],
                rbac_policy=app.config["RBAC_POLICY"],
                today=today(),
            )
        )

    @app.post("/api/login")
    def login():
        data = body()
        username, password = text(data, "username"), text(data, "password")
        remote = request.remote_addr or "unknown"
        if app.config["LOGIN_RATE_LIMIT_ENABLED"]:
            with attempts_lock:
                now = monotonic()
                times = attempts.setdefault(remote, deque())
                window = app.config["LOGIN_RATE_LIMIT_WINDOW_SECONDS"]
                limit = app.config["LOGIN_RATE_LIMIT_ATTEMPTS"]
                while times and times[0] < now - window:
                    times.popleft()
                if len(times) >= limit:
                    wait_minutes = max(1, (window + 59) // 60)
                    response, status = error(
                        "RATE_LIMITED",
                        f"Thử đăng nhập quá nhiều lần. Vui lòng thử lại sau {wait_minutes} phút.",
                        f"Too many sign-in attempts. Please try again in {wait_minutes} minutes.",
                        429,
                    )
                    response.headers["Retry-After"] = str(window)
                    return response, status
                times.append(now)
                attempts.move_to_end(remote)
                if len(attempts) > 4096:
                    attempts.popitem(last=False)
        customer_login = data.get("kind")=="customer"
        services = build_demo_bundle(customer_portal=customer_login) if demo else real_services
        actor = services.portal.login(username,password) if customer_login else services.auth.login(username, password)
        workspace = registry.add(services, actor) if demo else None
        registry.remove(session.get("workspace"))
        session.clear()
        session.permanent = True
        session["csrf"] = secrets.token_urlsafe(32)
        if customer_login:
            session.update(customer_id=actor.customer_id,account_id=actor.account_id,customer_auth_version=actor.auth_version)
        else:
            session.update(employee_id=actor.employee_id,store_id=actor.store_id,
                           employee_auth_version=actor.auth_version)
        if demo:
            session["workspace"] = workspace
        if app.config["LOGIN_RATE_LIMIT_ENABLED"]:
            with attempts_lock:
                attempts.pop(remote, None)
        return reply(
            dict(
                actor=None if customer_login else actor,
                permissions=sorted(str(p) for p in permissions_for(actor.role)) if not customer_login else [],
                customer=actor if customer_login else None,
                csrf_token=session["csrf"],
                mode=app.config["WEB_MODE"],
                rbac_policy=app.config["RBAC_POLICY"],
                today=today(),
            )
        )

    @app.post("/api/register")
    def register_customer_account():
        data = body()
        password = data.get("password")
        if password != data.get("confirmation"):
            raise ValidationError(
                field_errors={"confirmation": "Xác nhận mật khẩu không khớp"}
            )
        services = build_demo_bundle(customer_portal=True) if demo else real_services
        services.customers.register_customer(
            data.get("full_name"), data.get("phone"), data.get("username"), password
        )
        customer = services.portal.login(data.get("username"), password)
        workspace = registry.add(services, customer) if demo else None
        registry.remove(session.get("workspace"))
        session.clear()
        session.permanent = True
        session["csrf"] = secrets.token_urlsafe(32)
        session.update(
            customer_id=customer.customer_id,
            account_id=customer.account_id,
            customer_auth_version=customer.auth_version,
        )
        if demo:
            session["workspace"] = workspace
        return reply(
            dict(
                actor=None,
                customer=customer,
                csrf_token=session["csrf"],
                mode=app.config["WEB_MODE"],
                today=today(),
            ),
            201,
        )

    @app.post("/api/logout")
    def logout():
        registry.remove(session.get("workspace"))
        session.clear()
        session["csrf"] = secrets.token_urlsafe(32)
        return reply(dict(csrf_token=session["csrf"]))

    register_operations_routes(
        app,
        reply=reply,
        body=body,
        text=text,
        integer=integer,
        method=method,
        query_date=query_date,
        today=today,
        revenue_reader=revenue_reader,
        require_permission=require_permission,
        english=english,
        registry=registry,
        demo=demo,
    )

    register_feature_routes(
        app,
        reply=reply,
        body=body,
    )

    return app
