-- Additive P1 migration. Existing money remains principal; no historical bonus is invented.
ALTER TABLE accounts
    ADD COLUMN bonus_balance BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN cash_balance BIGINT GENERATED ALWAYS AS (balance - bonus_balance) STORED,
    ADD CONSTRAINT chk_accounts_bonus_nonnegative CHECK (bonus_balance >= 0);

CREATE TABLE promotions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    store_id BIGINT UNSIGNED NULL,
    minimum_amount BIGINT NOT NULL,
    bonus_percent INT NOT NULL,
    starts_at DATETIME NOT NULL,
    ends_at DATETIME NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_promotions_store FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE RESTRICT,
    CONSTRAINT chk_promotions_amount CHECK (minimum_amount > 0 AND minimum_amount <= 100000000),
    CONSTRAINT chk_promotions_percent CHECK (bonus_percent BETWEEN 0 AND 100),
    CONSTRAINT chk_promotions_period CHECK (ends_at > starts_at),
    INDEX ix_promotions_eligible(store_id, is_active, minimum_amount)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE account_transactions
    ADD COLUMN store_id BIGINT UNSIGNED NULL,
    ADD COLUMN promotion_id BIGINT UNSIGNED NULL,
    ADD CONSTRAINT fk_transactions_store FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_transactions_promotion FOREIGN KEY (promotion_id) REFERENCES promotions(id) ON DELETE RESTRICT;
UPDATE account_transactions t JOIN employees e ON e.id=t.employee_id SET t.store_id=e.store_id;

ALTER TABLE invoices
    ADD COLUMN bonus_used BIGINT NOT NULL DEFAULT 0,
    ADD CONSTRAINT chk_invoices_bonus_used CHECK (bonus_used >= 0 AND bonus_used <= usage_cost);

CREATE TABLE management_audit (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    employee_id BIGINT UNSIGNED NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    action VARCHAR(40) NOT NULL,
    entity_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_management_audit_employee FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE RESTRICT,
    CONSTRAINT fk_management_audit_store FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
