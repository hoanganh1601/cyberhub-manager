-- Read receipts only; financial history stays in its original immutable ledgers.
CREATE TABLE customer_notification_reads (
    account_id BIGINT UNSIGNED NOT NULL,
    notification_key VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    read_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (account_id, notification_key),
    CONSTRAINT fk_customer_notification_account FOREIGN KEY (account_id)
        REFERENCES accounts(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
