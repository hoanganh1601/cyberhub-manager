-- Durable customer notification ledger for menu-order lifecycle events.
-- Applied after 012_menu_order_cancel_reason.sql and the inventory migrations.

CREATE TABLE customer_notification_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    notification_key VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    account_id BIGINT UNSIGNED NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    kind VARCHAR(40) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    code VARCHAR(20) NOT NULL,
    amount INT UNSIGNED NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_customer_notification_event_key (notification_key),
    KEY idx_customer_notification_account_created (account_id, created_at, id),
    CONSTRAINT fk_customer_notification_event_account
        FOREIGN KEY (account_id) REFERENCES accounts (id),
    CONSTRAINT fk_customer_notification_event_store
        FOREIGN KEY (store_id) REFERENCES stores (id)
);
