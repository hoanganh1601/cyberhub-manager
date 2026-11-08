CREATE TABLE loyalty_settings (
    id TINYINT UNSIGNED NOT NULL PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    unit_amount BIGINT NOT NULL DEFAULT 10000,
    silver_spend BIGINT NOT NULL DEFAULT 1000000,
    gold_spend BIGINT NOT NULL DEFAULT 3000000,
    platinum_spend BIGINT NOT NULL DEFAULT 5000000,
    version INT UNSIGNED NOT NULL DEFAULT 1,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT chk_loyalty_singleton CHECK (id=1),
    CONSTRAINT chk_loyalty_unit CHECK (unit_amount > 0 AND unit_amount <= 100000000),
    CONSTRAINT chk_loyalty_tiers CHECK (silver_spend > 0 AND gold_spend > silver_spend AND platinum_spend > gold_spend)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
INSERT INTO loyalty_settings(id) VALUES(1);

ALTER TABLE invoices
    ADD COLUMN loyalty_eligible_amount BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN loyalty_points BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN loyalty_unit BIGINT NOT NULL DEFAULT 10000,
    ADD COLUMN loyalty_rule_version INT UNSIGNED NOT NULL DEFAULT 1,
    ADD CONSTRAINT chk_invoice_loyalty CHECK (loyalty_eligible_amount >= 0 AND loyalty_points >= 0 AND loyalty_unit > 0);
-- Approved opening rule: backfill points metadata, never wallet money.
-- VOID snapshots are retained for explanation but excluded by every membership aggregate.
UPDATE invoices SET loyalty_eligible_amount=GREATEST(0,usage_cost-bonus_used),
    loyalty_points=FLOOR(GREATEST(0,usage_cost-bonus_used)/10000);

ALTER TABLE promotions
    ADD COLUMN minimum_tier VARCHAR(10) NOT NULL DEFAULT 'BRONZE',
    ADD COLUMN minimum_points BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN target_customer_id BIGINT UNSIGNED NULL,
    ADD CONSTRAINT chk_promotion_tier CHECK (minimum_tier IN ('BRONZE','SILVER','GOLD','PLATINUM')),
    ADD CONSTRAINT chk_promotion_points CHECK (minimum_points >= 0 AND minimum_points <= 1000000000),
    ADD CONSTRAINT fk_promotion_target_customer FOREIGN KEY (target_customer_id) REFERENCES customers(id) ON DELETE RESTRICT;

CREATE TABLE customer_avatars (
    account_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    image_data MEDIUMBLOB NOT NULL,
    digest CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_customer_avatar_account FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
