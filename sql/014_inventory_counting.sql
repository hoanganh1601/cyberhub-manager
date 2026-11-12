-- Inventory counts are proposals. Only a different authorized employee may approve.
ALTER TABLE inventory_movements
    DROP CHECK chk_inventory_movements_kind,
    ADD CONSTRAINT chk_inventory_movements_kind CHECK
        (kind IN ('RECEIVE', 'RESERVE', 'RELEASE', 'CONSUME', 'WASTE',
                  'RETURN', 'ADJUST', 'ISSUE'));

CREATE TABLE inventory_counts (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    store_id BIGINT UNSIGNED NOT NULL,
    ingredient_id BIGINT UNSIGNED NOT NULL,
    request_id CHAR(32) NOT NULL,
    expected_on_hand BIGINT NOT NULL,
    expected_reserved BIGINT NOT NULL,
    expected_movement_id BIGINT UNSIGNED NOT NULL,
    counted_on_hand BIGINT NOT NULL,
    proposed_by BIGINT UNSIGNED NOT NULL,
    decided_by BIGINT UNSIGNED NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'PENDING',
    reason VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_at DATETIME NULL,
    CONSTRAINT uq_inventory_counts_request UNIQUE (request_id),
    CONSTRAINT fk_inventory_counts_ingredient FOREIGN KEY (store_id, ingredient_id)
        REFERENCES inventory_ingredients (store_id, id),
    CONSTRAINT fk_inventory_counts_proposer FOREIGN KEY (proposed_by) REFERENCES employees (id),
    CONSTRAINT fk_inventory_counts_decider FOREIGN KEY (decided_by) REFERENCES employees (id),
    CONSTRAINT chk_inventory_counts_quantities CHECK
        (expected_on_hand >= 0 AND expected_reserved >= 0 AND counted_on_hand >= 0),
    CONSTRAINT chk_inventory_counts_status CHECK
        (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    INDEX idx_inventory_counts_store_status (store_id, status, created_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
