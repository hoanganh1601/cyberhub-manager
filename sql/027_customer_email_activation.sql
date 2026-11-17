-- Existing accounts retain online access; only newly created counter accounts wait for activation.
ALTER TABLE customers ADD COLUMN email VARCHAR(254) NULL;
ALTER TABLE customers ADD CONSTRAINT uq_customers_email UNIQUE (email);
ALTER TABLE accounts DROP CHECK chk_accounts_password_hash_not_blank;
ALTER TABLE accounts MODIFY COLUMN password_hash VARCHAR(255) NULL;
ALTER TABLE accounts ADD CONSTRAINT chk_accounts_password_hash_not_blank
    CHECK (password_hash IS NULL OR CHAR_LENGTH(TRIM(password_hash)) > 0);
ALTER TABLE accounts ADD COLUMN web_login_enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE accounts ADD COLUMN email_verified_at DATETIME NULL;

CREATE TABLE customer_email_tokens (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    account_id BIGINT UNSIGNED NOT NULL,
    purpose VARCHAR(12) NOT NULL,
    token_hash CHAR(64) NOT NULL,
    nonce CHAR(64) NOT NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_customer_email_token_hash UNIQUE (token_hash),
    CONSTRAINT fk_customer_email_token_account FOREIGN KEY (account_id) REFERENCES accounts(id),
    CONSTRAINT chk_customer_email_token_purpose CHECK (purpose IN ('ACTIVATE','RESET')),
    INDEX idx_customer_email_token_account (account_id,purpose,created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE customer_mail_outbox (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    token_id BIGINT UNSIGNED NOT NULL,
    status VARCHAR(12) NOT NULL DEFAULT 'PENDING',
    attempts INT UNSIGNED NOT NULL DEFAULT 0,
    next_attempt_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at DATETIME NULL,
    last_error VARCHAR(120) NULL,
    CONSTRAINT uq_customer_mail_outbox_token UNIQUE (token_id),
    CONSTRAINT fk_customer_mail_outbox_token FOREIGN KEY (token_id) REFERENCES customer_email_tokens(id),
    CONSTRAINT chk_customer_mail_outbox_status CHECK (status IN ('PENDING','SENDING','SENT','FAILED')),
    INDEX idx_customer_mail_outbox_due (status,next_attempt_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE customer_security_audit (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    account_id BIGINT UNSIGNED NOT NULL,
    employee_id BIGINT UNSIGNED NULL,
    store_id BIGINT UNSIGNED NULL,
    action VARCHAR(40) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_customer_security_account FOREIGN KEY (account_id) REFERENCES accounts(id),
    CONSTRAINT fk_customer_security_employee FOREIGN KEY (employee_id) REFERENCES employees(id),
    CONSTRAINT fk_customer_security_store FOREIGN KEY (store_id) REFERENCES stores(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
