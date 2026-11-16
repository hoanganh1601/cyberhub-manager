"""Routes for shifts, machine maintenance and procurement."""

from flask import g, request

from cyberhub_manager.domain.exceptions import ServiceUnavailableError


def register_business_routes(app, *, reply, body):
    def service(name):
        value = getattr(g.services, name, None)
        if value is None:
            raise ServiceUnavailableError("Nghiệp vụ này cần chạy ở chế độ MySQL")
        return value

    @app.get("/api/shifts")
    def shifts_overview():
        return reply(service("shifts").overview(g.actor))

    @app.get("/api/shifts/<int:shift_id>")
    def shift_detail(shift_id):
        return reply(service("shifts").detail(g.actor, shift_id))

    @app.post("/api/shifts/open")
    def shift_open():
        return reply(service("shifts").open_shift(g.actor, body().get("opening_cash")), 201)

    @app.post("/api/shifts/entries")
    def shift_entry():
        data = body()
        return reply(service("shifts").add_entry(
            g.actor, kind=data.get("kind"), payment_method=data.get("payment_method"),
            amount=data.get("amount"), note=data.get("note")))

    @app.post("/api/shifts/close")
    def shift_close():
        return reply(service("shifts").submit_close(g.actor, body().get("counted_cash")))

    @app.post("/api/shifts/<int:shift_id>/review")
    def shift_review(shift_id):
        return reply(service("shifts").review(g.actor, shift_id, body().get("note")))

    @app.get("/api/maintenance")
    def maintenance_overview():
        return reply(service("maintenance").overview(g.actor, request.args.get("status") or None))

    @app.get("/api/maintenance/<int:incident_id>")
    def maintenance_detail(incident_id):
        return reply(service("maintenance").detail(g.actor, incident_id))

    @app.post("/api/maintenance")
    def maintenance_report():
        data = body()
        return reply(service("maintenance").report(
            g.actor, machine_id=data.get("machine_id"), severity=data.get("severity"),
            title=data.get("title"), description=data.get("description")), 201)

    @app.post("/api/maintenance/<int:incident_id>/transition")
    def maintenance_transition(incident_id):
        data = body()
        return reply(service("maintenance").transition(
            g.actor, incident_id, status=data.get("status"), assigned_to=data.get("assigned_to"),
            note=data.get("note", ""), resolution=data.get("resolution"),
            labor_cost=data.get("labor_cost", 0), parts=data.get("parts", [])))

    @app.get("/api/procurement")
    def procurement_overview():
        return reply(service("procurement").overview(g.actor))

    @app.route("/api/procurement/suppliers", methods=["POST"])
    @app.route("/api/procurement/suppliers/<int:supplier_id>", methods=["PATCH"])
    def procurement_supplier(supplier_id=None):
        return reply(service("procurement").save_supplier(g.actor, supplier_id, **body()))

    @app.post("/api/procurement/requests")
    def procurement_request():
        data = body()
        return reply(service("procurement").create_request(
            g.actor, reason=data.get("reason"), lines=data.get("lines")), 201)

    @app.post("/api/procurement/requests/<int:request_id>/decision")
    def procurement_request_decision(request_id):
        return reply(service("procurement").decide_request(g.actor, request_id, body().get("approve")))

    @app.post("/api/procurement/orders")
    def procurement_order():
        data = body()
        return reply(service("procurement").create_order(
            g.actor, request_id=data.get("request_id"), supplier_id=data.get("supplier_id"),
            expected_at=data.get("expected_at"), lines=data.get("lines")), 201)

    @app.post("/api/procurement/orders/<int:order_id>/receipts")
    def procurement_receive(order_id):
        data = body()
        return reply(service("procurement").receive(
            g.actor, order_id, request_id=data.get("request_id"),
            lines=data.get("lines"), note=data.get("note", "")), 201)

    @app.post("/api/procurement/payables/<int:payable_id>/pay")
    def procurement_pay(payable_id):
        return reply(service("procurement").pay_payable(
            g.actor, payable_id, body().get("method")))
