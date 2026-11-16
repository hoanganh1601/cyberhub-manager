"""Feature routes for menu, inventory, vouchers, games and advertising."""

from datetime import datetime

from flask import Response, g, request

from cyberhub_manager.domain.exceptions import ValidationError


def register_feature_routes(
    app,
    *,
    reply,
    body,
    error,
    real_services,
) -> None:
    """Register feature APIs while keeping the application factory compact."""

    def portal_integer(name, default=None):
        value = request.args.get(name)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            raise ValidationError(
                field_errors={name: "Số nguyên không hợp lệ"}
            ) from None

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

    @app.get("/api/inventory")
    def inventory_overview():
        return reply(g.services.menu.inventory_overview(g.actor))

    @app.post("/api/inventory/ingredients")
    def inventory_ingredient_create():
        data = body()
        return reply(g.services.menu.add_ingredient(
            g.actor, name=data.get("name"), unit=data.get("unit"),
            reorder_point=data.get("reorder_point", 0),
        ), 201)

    @app.post("/api/inventory/ingredients/<int:ingredient_id>/receipts")
    def inventory_ingredient_receive(ingredient_id):
        data = body()
        return reply(g.services.menu.receive_ingredient(
            g.actor, ingredient_id, quantity=data.get("quantity"),
            reference_code=data.get("reference_code"),
            request_id=data.get("request_id"), note=data.get("note", ""),
        ))

    @app.post("/api/inventory/ingredients/<int:ingredient_id>/movements")
    def inventory_ingredient_move(ingredient_id):
        data = body()
        return reply(g.services.menu.move_ingredient(
            g.actor, ingredient_id, kind=data.get("kind"), quantity=data.get("quantity"),
            reference_code=data.get("reference_code"), request_id=data.get("request_id"),
            note=data.get("note", ""),
        ))

    @app.post("/api/inventory/ingredients/<int:ingredient_id>/counts")
    def inventory_count_propose(ingredient_id):
        data = body()
        return reply(g.services.menu.propose_inventory_count(
            g.actor, ingredient_id, counted_on_hand=data.get("counted_on_hand"),
            reason=data.get("reason"), request_id=data.get("request_id"),
        ), 201)

    @app.post("/api/inventory/counts/<int:count_id>/decision")
    def inventory_count_decide(count_id):
        data = body()
        return reply(g.services.menu.decide_inventory_count(
            g.actor, count_id, approve=data.get("approve"),
        ))

    @app.put("/api/inventory/items/<int:item_id>/recipe")
    def inventory_item_recipe(item_id):
        data = body()
        return reply(g.services.menu.set_item_recipe(
            g.actor, item_id, parts=data.get("parts"),
            track_stock=data.get("track_stock", True),
        ))

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
            raise ValidationError(field_errors={"starts_at": "Nhập thời gian hợp lệ có múi giờ"}) from None
        return reply(g.services.menu.save_promotion(g.actor, promotion_id=promotion_id,
            code=data.get("code"), kind=data.get("kind"), item_id=data.get("item_id"),
            value=data.get("value"), minimum_tier=data.get("minimum_tier"),
            starts_at=starts_at, ends_at=ends_at, is_active=data.get("is_active")))

    @app.post("/api/menu/orders/<int:order_id>/status")
    def menu_order_status(order_id):
        payload = body()
        return reply(g.services.menu.finish_order(
            g.actor, order_id, payload.get("status"), reason=payload.get("reason"),
        ))

    @app.post("/api/menu/orders/<int:order_id>/payment")
    def menu_order_payment(order_id):
        return reply(g.services.menu.pay_order(g.actor, order_id, body().get("method")))

    @app.post("/api/menu/orders/<int:order_id>/reversal")
    def menu_order_reversal_request(order_id):
        data = body()
        return reply(g.services.menu.request_reversal(
            g.actor, order_id, reason=data.get("reason"), disposition=data.get("disposition")))

    @app.get("/api/menu/reversals")
    def menu_order_reversals():
        return reply(g.services.menu.list_reversals(g.actor, request.args.get("status", "PENDING")))

    @app.post("/api/menu/orders/<int:order_id>/reversal/decision")
    def menu_order_reversal_decision(order_id):
        data = body()
        return reply(g.services.menu.decide_reversal(
            g.actor, order_id, approve=data.get("approve"),
            refund_confirmed=data.get("refund_confirmed", False),
            refund_method=data.get("refund_method"),
            refund_reference=data.get("refund_reference")))

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
