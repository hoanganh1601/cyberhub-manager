-- Strict 3NF remediation (Phase C): single source of truth for HR profiles vs
-- login credentials (NF-03), and structured versioned POS promotion pricing
-- eliminating snapshot_json & duplicated promotion attributes (NF-04).

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- 1. NF-03: Separate HR identity (employee_profiles) from credentials (employees)
--    Direction: employees.profile_id (NOT NULL UNIQUE) -> employee_profiles(id)
-- ---------------------------------------------------------------------------
-- Backfill any employees that do not yet have an employee_profiles row.
INSERT INTO employee_profiles (employee_id, code, home_store_id, full_name, employment_status)
SELECT e.id, e.code, e.store_id, e.full_name, 'ACTIVE'
FROM employees AS e
LEFT JOIN employee_profiles AS p ON p.employee_id = e.id
WHERE p.id IS NULL;

ALTER TABLE employees
    ADD COLUMN profile_id BIGINT UNSIGNED NULL AFTER id;

UPDATE employees AS e
JOIN employee_profiles AS p ON p.employee_id = e.id
SET e.profile_id = p.id;

ALTER TABLE employee_profiles
    DROP FOREIGN KEY fk_employee_profiles_employee,
    DROP INDEX uq_employee_profiles_employee,
    DROP COLUMN employee_id,
    ADD CONSTRAINT chk_employee_profiles_code_not_blank CHECK (CHAR_LENGTH(TRIM(code)) > 0),
    ADD CONSTRAINT chk_employee_profiles_full_name_not_blank CHECK (CHAR_LENGTH(TRIM(full_name)) > 0),
    ADD INDEX idx_employee_profiles_store_status (home_store_id, employment_status);

ALTER TABLE employees
    MODIFY COLUMN profile_id BIGINT UNSIGNED NOT NULL,
    DROP FOREIGN KEY fk_employees_store,
    DROP INDEX idx_employees_store_status,
    DROP INDEX uq_employees_code,
    DROP CHECK chk_employees_code_not_blank,
    DROP CHECK chk_employees_full_name_not_blank,
    DROP COLUMN code,
    DROP COLUMN store_id,
    DROP COLUMN full_name,
    ADD CONSTRAINT uq_employees_profile UNIQUE (profile_id),
    ADD CONSTRAINT fk_employees_profile
        FOREIGN KEY (profile_id) REFERENCES employee_profiles (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT;

CREATE OR REPLACE VIEW v_employees AS
SELECT
    e.id,
    e.profile_id,
    p.code,
    p.home_store_id AS store_id,
    p.full_name,
    p.employment_status,
    e.username,
    e.password_hash,
    e.role,
    e.status,
    e.auth_version,
    e.must_change_password,
    e.password_changed_at,
    e.created_at,
    e.updated_at
FROM employees AS e
JOIN employee_profiles AS p ON p.id = e.profile_id;

-- ---------------------------------------------------------------------------
-- 2. NF-04: Immutable menu_promotion_versions & structured menu_order_pricing
-- ---------------------------------------------------------------------------
CREATE TABLE menu_promotion_versions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    promotion_id BIGINT UNSIGNED NOT NULL,
    version INT UNSIGNED NOT NULL,
    code VARCHAR(30) NOT NULL,
    kind VARCHAR(16) NOT NULL,
    item_id BIGINT UNSIGNED NULL,
    value INT UNSIGNED NOT NULL,
    minimum_tier VARCHAR(12) NULL,
    starts_at DATETIME NOT NULL,
    ends_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_menu_promo_ver UNIQUE (promotion_id, version),
    CONSTRAINT fk_menu_promo_ver_promo
        FOREIGN KEY (promotion_id) REFERENCES menu_promotions (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_menu_promo_ver_item
        FOREIGN KEY (item_id) REFERENCES menu_items (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_menu_promo_ver_version CHECK (version >= 1),
    CONSTRAINT chk_menu_promo_ver_kind CHECK (kind IN ('BOGO', 'PLAY_DRINK', 'TIER_PERCENT')),
    CONSTRAINT chk_menu_promo_ver_tier CHECK (
        minimum_tier IS NULL OR minimum_tier IN ('BRONZE', 'SILVER', 'GOLD', 'PLATINUM')
    ),
    CONSTRAINT chk_menu_promo_ver_period CHECK (starts_at < ends_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Seed version 1 for all existing menu_promotions rows.
INSERT INTO menu_promotion_versions
    (promotion_id, version, code, kind, item_id, value, minimum_tier, starts_at, ends_at)
SELECT id, 1, code, kind, item_id, value, minimum_tier, starts_at, ends_at
FROM menu_promotions;

ALTER TABLE menu_order_pricing
    ADD COLUMN promotion_version_id BIGINT UNSIGNED NULL AFTER order_id,
    ADD COLUMN applied_source VARCHAR(12) NOT NULL DEFAULT 'NONE' AFTER promotion_version_id,
    ADD COLUMN member_tier VARCHAR(12) NOT NULL DEFAULT 'BRONZE' AFTER applied_source,
    ADD COLUMN voucher_id BIGINT UNSIGNED NULL AFTER discount_amount,
    ADD COLUMN voucher_discount_amount BIGINT UNSIGNED NOT NULL DEFAULT 0 AFTER voucher_id;

-- Backfill structured pricing columns from existing rows, promotion versions, and vouchers.
UPDATE menu_order_pricing AS mp
LEFT JOIN menu_promotion_versions AS pv
    ON pv.promotion_id = mp.promotion_id AND pv.version = 1
LEFT JOIN customer_vouchers AS v
    ON v.used_order_id = mp.order_id AND v.status = 'USED'
SET
    mp.promotion_version_id = pv.id,
    mp.member_tier = COALESCE(
        CASE
            WHEN JSON_UNQUOTE(JSON_EXTRACT(mp.snapshot_json, '$.member_tier'))
                 IN ('BRONZE', 'SILVER', 'GOLD', 'PLATINUM')
            THEN JSON_UNQUOTE(JSON_EXTRACT(mp.snapshot_json, '$.member_tier'))
            ELSE NULL
        END,
        'BRONZE'
    ),
    mp.voucher_id = v.id,
    mp.voucher_discount_amount = COALESCE(
        CAST(JSON_EXTRACT(mp.snapshot_json, '$.voucher.discount_amount') AS UNSIGNED),
        CASE WHEN v.id IS NOT NULL THEN v.value ELSE 0 END,
        0
    ),
    mp.applied_source = CASE
        WHEN v.id IS NOT NULL
             OR JSON_UNQUOTE(JSON_EXTRACT(mp.snapshot_json, '$.applied_source')) = 'VOUCHER'
        THEN 'VOUCHER'
        WHEN pv.id IS NOT NULL AND mp.discount_amount > 0
        THEN 'PROMOTION'
        ELSE 'NONE'
    END;

ALTER TABLE menu_order_pricing
    DROP FOREIGN KEY fk_menu_pricing_promotion,
    DROP COLUMN promotion_id,
    DROP COLUMN promotion_code,
    DROP COLUMN promotion_kind,
    DROP COLUMN final_amount,
    DROP COLUMN snapshot_json,
    ADD CONSTRAINT fk_menu_pricing_promo_version
        FOREIGN KEY (promotion_version_id) REFERENCES menu_promotion_versions (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    ADD CONSTRAINT fk_menu_pricing_voucher
        FOREIGN KEY (voucher_id) REFERENCES customer_vouchers (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    ADD CONSTRAINT chk_menu_pricing_source
        CHECK (applied_source IN ('NONE', 'PROMOTION', 'VOUCHER')),
    ADD CONSTRAINT chk_menu_pricing_tier
        CHECK (member_tier IN ('BRONZE', 'SILVER', 'GOLD', 'PLATINUM')),
    ADD CONSTRAINT chk_menu_pricing_promo_consistency
        CHECK (
            (promotion_version_id IS NULL AND discount_amount = 0)
            OR (promotion_version_id IS NOT NULL)
        ),
    ADD CONSTRAINT chk_menu_pricing_voucher_consistency
        CHECK (
            (voucher_id IS NULL AND voucher_discount_amount = 0)
            OR (voucher_id IS NOT NULL AND voucher_discount_amount > 0)
        );

CREATE OR REPLACE VIEW v_menu_order_pricing AS
SELECT
    mp.order_id,
    mp.promotion_version_id,
    pv.promotion_id,
    pv.version AS promotion_version,
    pv.code AS promotion_code,
    pv.kind AS promotion_kind,
    mp.applied_source,
    mp.member_tier,
    mp.discount_amount AS promotion_discount_amount,
    mp.voucher_id,
    v.code AS voucher_code,
    mp.voucher_discount_amount,
    LEAST(o.total_amount, GREATEST(mp.discount_amount, mp.voucher_discount_amount)) AS effective_discount_amount,
    GREATEST(
        0,
        CAST(o.total_amount AS SIGNED)
        - CAST(LEAST(o.total_amount, GREATEST(mp.discount_amount, mp.voucher_discount_amount)) AS SIGNED)
    ) AS final_amount
FROM menu_order_pricing AS mp
JOIN menu_orders AS o ON o.id = mp.order_id
LEFT JOIN menu_promotion_versions AS pv ON pv.id = mp.promotion_version_id
LEFT JOIN customer_vouchers AS v ON v.id = mp.voucher_id;
