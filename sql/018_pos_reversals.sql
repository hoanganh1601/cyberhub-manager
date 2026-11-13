-- Full-order cancellation/refund requires a separate manager approval.
ALTER TABLE menu_orders DROP CHECK chk_menu_orders_status;
ALTER TABLE menu_orders ADD CONSTRAINT chk_menu_orders_status
    CHECK (status IN ('NEW','PREPARING','SERVED','PAID','CANCELLED','REFUNDED'));
ALTER TABLE menu_orders DROP CHECK chk_menu_orders_payment;
ALTER TABLE menu_orders ADD CONSTRAINT chk_menu_orders_payment CHECK (
    (status IN ('PAID','REFUNDED') AND payment_method IN ('CASH','TRANSFER')
        AND paid_at IS NOT NULL AND paid_by IS NOT NULL)
    OR (status NOT IN ('PAID','REFUNDED') AND payment_method IS NULL
        AND paid_at IS NULL AND paid_by IS NULL)
);
CREATE TABLE pos_order_reversals (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT UNSIGNED NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    requested_by BIGINT UNSIGNED NOT NULL,
    reason VARCHAR(255) NOT NULL,
    disposition VARCHAR(8) NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'PENDING',
    decided_by BIGINT UNSIGNED NULL,
    decided_at DATETIME NULL,
    refund_amount BIGINT UNSIGNED NOT NULL DEFAULT 0,
    refund_method VARCHAR(10) NULL,
    refund_reference VARCHAR(100) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_pos_reversal_order (order_id),
    KEY idx_pos_reversal_store_status (store_id,status,id),
    CONSTRAINT fk_pos_reversal_order FOREIGN KEY (order_id) REFERENCES menu_orders(id),
    CONSTRAINT fk_pos_reversal_store FOREIGN KEY (store_id) REFERENCES stores(id),
    CONSTRAINT fk_pos_reversal_requester FOREIGN KEY (requested_by) REFERENCES employees(id),
    CONSTRAINT fk_pos_reversal_approver FOREIGN KEY (decided_by) REFERENCES employees(id),
    CONSTRAINT chk_pos_reversal_disposition CHECK (disposition IN ('RESTOCK','WASTE')),
    CONSTRAINT chk_pos_reversal_status CHECK (status IN ('PENDING','APPROVED','REJECTED')),
    CONSTRAINT chk_pos_reversal_decision CHECK (
        (status='PENDING' AND decided_by IS NULL AND decided_at IS NULL)
        OR (status<>'PENDING' AND decided_by IS NOT NULL AND decided_at IS NOT NULL)
    ),
    CONSTRAINT chk_pos_reversal_method CHECK
        (refund_method IS NULL OR refund_method IN ('CASH','TRANSFER'))
);
