"""Management, portal, machine, customer and reporting HTTP routes."""

from datetime import datetime, timedelta, timezone
import secrets

from flask import Response, g, request, session

from cyberhub_manager.domain.dtos import InvoiceFilters
from cyberhub_manager.domain.enums import CustomerStatus, InvoiceStatus
from cyberhub_manager.domain.exceptions import (
    PermissionDeniedError,
    ValidationError,
)
from cyberhub_manager.domain.loyalty import LoyaltySettings
from cyberhub_manager.domain.p1 import Permission, Promotion, permissions_for
from cyberhub_manager.services.invoice_export import invoice_csv, invoice_html
from cyberhub_manager.web.serialization import customer_public, machine_public, serialize

UTC = timezone.utc


def register_operations_routes(
    app,
    *,
    reply,
    body,
    text,
    integer,
    method,
    query_date,
    today,
    revenue_reader,
    require_permission,
    english,
    registry,
    demo,
) -> None:
    """Register authenticated operational APIs."""

    @app.get("/api/management")
    def management_overview():
        return reply(dict(stores=g.services.management.list_stores(g.actor),permissions=sorted(str(p) for p in permissions_for(g.actor.role))))

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

    @app.get("/api/employee-profiles")
    def list_employee_profiles():
        return reply(g.services.management.list_employee_profiles(g.actor))

    @app.post("/api/employee-profiles")
    @app.patch("/api/employee-profiles/<int:profile_id>")
    def save_employee_profile(profile_id=None):
        d = body()
        return reply(g.services.management.save_employee_profile(
            g.actor, profile_id, integer(d, "store_id", minimum=1),
            text(d, "full_name"), d.get("employment_status", "ACTIVE")))

    @app.post("/api/employees/<int:employee_id>/store-assignments")
    def set_manager_store_assignment(employee_id):
        d = body()
        return reply(g.services.management.set_manager_store_assignment(
            g.actor, employee_id, integer(d, "store_id", minimum=1), d.get("enabled")))

    @app.get("/api/employees/<int:employee_id>/store-assignments")
    def list_manager_store_assignments(employee_id):
        return reply(g.services.management.list_manager_store_assignments(g.actor, employee_id))

    @app.route("/api/employees",methods=["POST"])
    @app.route("/api/employees/<int:employee_id>",methods=["PATCH"])
    def save_employee(employee_id=None):
        d = body()
        profile_id = integer(d, "profile_id", minimum=1) if d.get("profile_id") is not None else None
        return reply(g.services.management.save_employee(g.actor,employee_id,integer(d,"store_id",minimum=1),
            text(d,"full_name"),text(d,"username"),d.get("role","STAFF"),d.get("status","ACTIVE"),d.get("password",""),profile_id))

    @app.post("/api/employees/<int:employee_id>/reset-password")
    def reset_employee_password(employee_id):
        d = body()
        temporary = d.get("temporary_password")
        if temporary != d.get("confirm_password"):
            raise ValidationError(field_errors={"confirm_password": "Mật khẩu xác nhận không khớp"})
        return reply(g.services.management.reset_employee_password(g.actor, employee_id, temporary))

    @app.post("/api/employee/password")
    def change_employee_password():
        d = body()
        new_password = d.get("new_password")
        if new_password != d.get("confirm_password"):
            raise ValidationError(field_errors={"confirm_password": "Mật khẩu xác nhận không khớp"})
        actor = g.services.auth.change_password(
            g.actor, d.get("current_password"), new_password
        )
        session["employee_auth_version"] = actor.auth_version
        if demo:
            registry.get(session["workspace"]).actor = actor
        return reply(dict(actor=actor, csrf_token=session["csrf"]))

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
    @require_permission(Permission.MANAGE_MACHINES)
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
    @require_permission(Permission.MANAGE_MACHINES)
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
    @require_permission(Permission.MANAGE_MACHINES)
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
    @require_permission(Permission.MANAGE_MACHINES)
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

    @app.post("/api/customers/link-store")
    def link_customer_store():
        data = body()
        return reply(customer_public(g.services.customers.link_customer_to_store(
            text(data, "code"), text(data, "phone"))))

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

    @app.post("/api/customers/register-counter")
    def register_customer_at_counter():
        if demo or g.services.customer_email is None:
            raise PermissionDeniedError()
        data = body()
        return reply(g.services.customer_email.register_at_counter(
            data.get("full_name"), data.get("phone"), data.get("email"),
            data.get("username")), 201)

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
    @require_permission(Permission.LOCK_CUSTOMERS)
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
    @revenue_reader
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
                                  menu_revenue=0, refund_count=0, revenue=item.revenue) for item in days}
        for item in pos["days"]:
            day = by_day.setdefault(item["date"], dict(date=item["date"], invoice_count=0,
                                    machine_revenue=0, menu_order_count=0,
                                    menu_revenue=0, refund_count=0, revenue=0))
            day["menu_order_count"] = item["order_count"]
            day["menu_revenue"] = item["revenue"]
            day["refund_count"] = item["refund_count"]
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
                refund_count=sum(item["refund_count"] for item in pos["days"]),
                top_menu_items=pos["top_items"],
                total_revenue=sum(item["revenue"] for item in combined),
                invoice_count=sum(item.invoice_count for item in days),
            )
        )
