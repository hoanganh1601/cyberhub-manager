-- Remove the unused loyalty rules after narrowing the project to 24 tables.
-- Existing tier based menu promotions are kept for audit but made inactive.

UPDATE menu_promotions
SET is_active = FALSE
WHERE kind = 'TIER_PERCENT';

ALTER TABLE menu_promotions
    DROP CHECK chk_menu_promo_kind,
    DROP CHECK chk_menu_promo_tier,
    DROP COLUMN minimum_tier,
    ADD CONSTRAINT chk_menu_promo_kind
        CHECK (kind IN ('BOGO', 'PLAY_DRINK'));

ALTER TABLE promotions
    DROP FOREIGN KEY fk_promotion_target_customer,
    DROP CHECK chk_promotion_tier,
    DROP CHECK chk_promotion_points,
    DROP COLUMN minimum_tier,
    DROP COLUMN minimum_points,
    DROP COLUMN target_customer_id;

ALTER TABLE invoices
    DROP CHECK chk_invoice_loyalty,
    DROP COLUMN loyalty_eligible_amount,
    DROP COLUMN loyalty_points,
    DROP COLUMN loyalty_unit,
    DROP COLUMN loyalty_rule_version;
