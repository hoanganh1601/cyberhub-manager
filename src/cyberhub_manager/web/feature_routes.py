"""HTTP routes for the menu and POS tables in the compact project scope."""

from datetime import datetime

from flask import g, request

from cyberhub_manager.domain.exceptions import ValidationError


def register_feature_routes(app, *, reply, body) -> None:
    """Expose only menu, order, pricing and reversal workflows."""

    @app.get("/api/portal/menu")
    def portal_menu():
        store_id = request.args.get("store_id")
        if store_id is not None:
            try:
                store_id = int(store_id)
            except ValueError:
                raise ValidationError(field_errors={"store_id": "Mã cửa hàng không hợp lệ"}) from None
        return reply(g.services.menu.portal_menu(g.customer, store_id))

    @app.post("/api/portal/menu/orders")
    def portal_menu_order():
        data = body()
        return reply(
            g.services.menu.place_order(g.customer, data.get("lines"), data.get("note", "")),
            201,
        )

    @app.post("/api/portal/menu/notifications/<int:event_id>/read")
    def portal_menu_notification_read(event_id):
        return reply(g.services.menu.mark_notification_read(g.customer, event_id))

    @app.get("/api/menu")
    def menu_manage():
        return reply(g.services.menu.manage_menu(g.actor))

    @app.route("/api/menu/categories", methods=["POST"])
    @app.route("/api/menu/categories/<int:category_id>", methods=["PATCH"])
    def menu_category_save(category_id=None):
        data = body()
        return reply(g.services.menu.save_category(
            g.actor,
            category_id,
            page=data.get("page"),
            name=data.get("name"),
            sort_order=data.get("sort_order", 0),
            is_active=data.get("is_active", True),
        ))

    @app.route("/api/menu/items", methods=["POST"])
    @app.route("/api/menu/items/<int:item_id>", methods=["PATCH"])
    def menu_item_save(item_id=None):
        data = body()
        return reply(g.services.menu.save_item(
            g.actor,
            item_id,
            category_id=data.get("category_id"),
            name=data.get("name"),
            description=data.get("description", ""),
            price=data.get("price"),
            sort_order=data.get("sort_order", 0),
            is_visible=data.get("is_visible", True),
            is_available=data.get("is_available", True),
        ))

    @app.post("/api/menu/items/<int:item_id>/availability")
    def menu_item_availability(item_id):
        return reply(g.services.menu.set_item_available(
            g.actor, item_id, body().get("available"),
        ))

    @app.get("/api/menu/orders")
    def menu_orders():
        return reply(g.services.menu.list_orders(g.actor, request.args.get("status", "NEW")))

    @app.get("/api/menu/promotions")
    def menu_promotions():
        return reply(g.services.menu.list_promotions(g.actor))

    @app.route("/api/menu/promotions", methods=["POST"])
    @app.route("/api/menu/promotions/<int:promotion_id>", methods=["PATCH"])
    def menu_promotion_save(promotion_id=None):
        data = body()
        try:
            starts_at = datetime.fromisoformat(data.get("starts_at", ""))
            ends_at = datetime.fromisoformat(data.get("ends_at", ""))
        except (TypeError, ValueError):
            raise ValidationError(field_errors={
                "starts_at": "Nhập thời gian hợp lệ có múi giờ",
            }) from None
        return reply(g.services.menu.save_promotion(
            g.actor,
            promotion_id=promotion_id,
            code=data.get("code"),
            kind=data.get("kind"),
            item_id=data.get("item_id"),
            value=data.get("value"),
            starts_at=starts_at,
            ends_at=ends_at,
            is_active=data.get("is_active"),
        ))

    @app.post("/api/menu/orders/<int:order_id>/status")
    def menu_order_status(order_id):
        data = body()
        return reply(g.services.menu.finish_order(
            g.actor, order_id, data.get("status"), reason=data.get("reason"),
        ))

    @app.post("/api/menu/orders/<int:order_id>/payment")
    def menu_order_payment(order_id):
        return reply(g.services.menu.pay_order(g.actor, order_id, body().get("method")))

    @app.post("/api/menu/orders/<int:order_id>/reversal")
    def menu_order_reversal_request(order_id):
        data = body()
        return reply(g.services.menu.request_reversal(
            g.actor, order_id, reason=data.get("reason"),
            disposition=data.get("disposition"),
        ))

    @app.get("/api/menu/reversals")
    def menu_order_reversals():
        return reply(g.services.menu.list_reversals(
            g.actor, request.args.get("status", "PENDING"),
        ))

    @app.post("/api/menu/orders/<int:order_id>/reversal/decision")
    def menu_order_reversal_decision(order_id):
        data = body()
        return reply(g.services.menu.decide_reversal(
            g.actor,
            order_id,
            approve=data.get("approve"),
            refund_confirmed=data.get("refund_confirmed", False),
            refund_method=data.get("refund_method"),
            refund_reference=data.get("refund_reference"),
        ))
