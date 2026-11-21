-- Durable in-app notifications for customer-facing POS order status changes.
-- Events are written in the same transaction as the corresponding order update.

CREATE TABLE customer_notification_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    account_id BIGINT UNSIGNED NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    order_id BIGINT UNSIGNED NOT NULL,
    order_code VARCHAR(20) NOT NULL,
    order_status VARCHAR(12) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_customer_notification_events PRIMARY KEY (id),
    CONSTRAINT uq_customer_notification_order_status UNIQUE (order_id, order_status),
    CONSTRAINT uq_customer_notification_event_owner UNIQUE (id, account_id),
    CONSTRAINT fk_customer_notification_account
        FOREIGN KEY (account_id) REFERENCES accounts(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_customer_notification_store
        FOREIGN KEY (store_id) REFERENCES stores(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_customer_notification_order
        FOREIGN KEY (order_id) REFERENCES menu_orders(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_customer_notification_order_status
        CHECK (order_status IN ('NEW', 'PREPARING', 'SERVED', 'PAID', 'CANCELLED', 'REFUNDED')),
    INDEX idx_customer_notification_account_created (account_id, created_at, id)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE customer_notification_reads (
    event_id BIGINT UNSIGNED NOT NULL,
    account_id BIGINT UNSIGNED NOT NULL,
    read_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_customer_notification_reads PRIMARY KEY (event_id, account_id),
    CONSTRAINT fk_customer_notification_read_owner
        FOREIGN KEY (event_id, account_id)
        REFERENCES customer_notification_events(id, account_id)
        ON UPDATE RESTRICT ON DELETE CASCADE,
    INDEX idx_customer_notification_reads_account (account_id, read_at)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;
