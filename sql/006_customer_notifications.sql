-- Durable customer notifications for POS order lifecycle events and read receipts.

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE customer_notification_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    order_id BIGINT UNSIGNED NOT NULL,
    order_status VARCHAR(12) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_customer_notification_events PRIMARY KEY (id),
    CONSTRAINT uq_customer_notification_order_status UNIQUE (order_id, order_status),
    CONSTRAINT fk_customer_notification_order
        FOREIGN KEY (order_id) REFERENCES menu_orders (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_customer_notification_order_status CHECK (
        order_status IN ('NEW', 'PREPARING', 'SERVED', 'PAID', 'CANCELLED', 'REFUNDED')
    )
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE customer_notification_reads (
    event_id BIGINT UNSIGNED NOT NULL,
    read_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_customer_notification_reads PRIMARY KEY (event_id),
    CONSTRAINT fk_customer_notification_reads_event
        FOREIGN KEY (event_id) REFERENCES customer_notification_events (id)
        ON UPDATE RESTRICT ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;
