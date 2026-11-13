-- One deterministic POS promotion per order; price result is immutable.
CREATE TABLE menu_promotions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    store_id BIGINT UNSIGNED NOT NULL,
    code VARCHAR(30) NOT NULL,
    kind VARCHAR(16) NOT NULL,
    item_id BIGINT UNSIGNED NULL,
    value INT UNSIGNED NOT NULL,
    minimum_tier VARCHAR(12) NULL,
    starts_at DATETIME NOT NULL,
    ends_at DATETIME NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE KEY uq_menu_promo_store_code(store_id,code),
    KEY idx_menu_promo_active(store_id,is_active,starts_at,ends_at),
    CONSTRAINT fk_menu_promo_store FOREIGN KEY(store_id) REFERENCES stores(id),
    CONSTRAINT fk_menu_promo_item FOREIGN KEY(item_id) REFERENCES menu_items(id),
    CONSTRAINT chk_menu_promo_kind CHECK(kind IN ('BOGO','PLAY_DRINK','TIER_PERCENT')),
    CONSTRAINT chk_menu_promo_tier CHECK(minimum_tier IS NULL OR minimum_tier IN
        ('BRONZE','SILVER','GOLD','PLATINUM')),
    CONSTRAINT chk_menu_promo_period CHECK(starts_at < ends_at)
);
CREATE TABLE menu_order_pricing (
    order_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    promotion_id BIGINT UNSIGNED NULL,
    promotion_code VARCHAR(30) NULL,
    promotion_kind VARCHAR(16) NULL,
    discount_amount BIGINT UNSIGNED NOT NULL DEFAULT 0,
    final_amount BIGINT UNSIGNED NOT NULL,
    snapshot_json JSON NOT NULL,
    CONSTRAINT fk_menu_pricing_order FOREIGN KEY(order_id) REFERENCES menu_orders(id),
    CONSTRAINT fk_menu_pricing_promotion FOREIGN KEY(promotion_id) REFERENCES menu_promotions(id)
);
