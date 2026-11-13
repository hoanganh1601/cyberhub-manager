-- Delivery tracking for the customer notification ledger (external channels).
-- Applied after 020_pos_promotion_history.sql.
--
-- customer_notification_events stays append-only and is written inside POS
-- transactions. A separate worker creates one delivery row per (event, channel),
-- claims it with a lease, calls the channel OUTSIDE any POS transaction and
-- records the outcome. All times are naive UTC, like the rest of the schema.

CREATE TABLE notification_deliveries (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    event_id BIGINT UNSIGNED NOT NULL,
    channel VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    status VARCHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL DEFAULT 'PENDING',
    attempts SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    next_attempt_at DATETIME NOT NULL,
    locked_until DATETIME NULL,
    last_error VARCHAR(255) NULL,
    sent_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_notification_delivery_event_channel (event_id, channel),
    KEY idx_notification_delivery_due (channel, status, next_attempt_at, id),
    CONSTRAINT chk_notification_delivery_status
        CHECK (status IN ('PENDING', 'SENDING', 'SENT', 'DEAD')),
    CONSTRAINT fk_notification_delivery_event
        FOREIGN KEY (event_id) REFERENCES customer_notification_events (id)
);
