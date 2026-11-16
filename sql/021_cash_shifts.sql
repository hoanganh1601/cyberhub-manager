-- Employee cash shifts and immutable tender ledger.
CREATE TABLE cash_shifts (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(24) NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    employee_id BIGINT UNSIGNED NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'OPEN',
    opening_cash BIGINT UNSIGNED NOT NULL,
    expected_cash BIGINT UNSIGNED NULL,
    counted_cash BIGINT UNSIGNED NULL,
    variance BIGINT NULL,
    opened_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    submitted_at DATETIME NULL,
    closed_at DATETIME NULL,
    reviewed_by BIGINT UNSIGNED NULL,
    review_note VARCHAR(255) NULL,
    active_employee_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN status IN ('OPEN','PENDING_REVIEW') THEN employee_id ELSE NULL END
    ) STORED,
    CONSTRAINT uq_cash_shifts_code UNIQUE (code),
    CONSTRAINT uq_cash_shifts_active_employee UNIQUE (active_employee_id),
    CONSTRAINT fk_cash_shifts_store FOREIGN KEY (store_id) REFERENCES stores(id),
    CONSTRAINT fk_cash_shifts_employee FOREIGN KEY (employee_id) REFERENCES employees(id),
    CONSTRAINT fk_cash_shifts_reviewer FOREIGN KEY (reviewed_by) REFERENCES employees(id),
    CONSTRAINT chk_cash_shifts_status CHECK (status IN ('OPEN','PENDING_REVIEW','CLOSED')),
    CONSTRAINT chk_cash_shifts_close CHECK (
        (status='OPEN' AND expected_cash IS NULL AND counted_cash IS NULL
            AND variance IS NULL AND submitted_at IS NULL AND closed_at IS NULL)
        OR
        (status='PENDING_REVIEW' AND expected_cash IS NOT NULL AND counted_cash IS NOT NULL
            AND variance IS NOT NULL AND submitted_at IS NOT NULL AND closed_at IS NULL)
        OR
        (status='CLOSED' AND expected_cash IS NOT NULL AND counted_cash IS NOT NULL
            AND variance IS NOT NULL AND submitted_at IS NOT NULL AND closed_at IS NOT NULL)
    ),
    INDEX idx_cash_shifts_store_time (store_id, opened_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE cash_shift_entries (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    shift_id BIGINT UNSIGNED NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    employee_id BIGINT UNSIGNED NOT NULL,
    kind VARCHAR(12) NOT NULL,
    payment_method VARCHAR(10) NOT NULL,
    amount BIGINT UNSIGNED NOT NULL,
    source_type VARCHAR(24) NOT NULL,
    source_id VARCHAR(64) NOT NULL,
    note VARCHAR(255) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_cash_shift_entries_source UNIQUE (source_type, source_id, payment_method),
    CONSTRAINT fk_cash_entries_shift FOREIGN KEY (shift_id) REFERENCES cash_shifts(id),
    CONSTRAINT fk_cash_entries_store FOREIGN KEY (store_id) REFERENCES stores(id),
    CONSTRAINT fk_cash_entries_employee FOREIGN KEY (employee_id) REFERENCES employees(id),
    CONSTRAINT chk_cash_entries_kind CHECK (kind IN ('RECEIPT','EXPENSE','REFUND','ADJUSTMENT_IN','ADJUSTMENT_OUT')),
    CONSTRAINT chk_cash_entries_method CHECK (payment_method IN ('CASH','TRANSFER')),
    CONSTRAINT chk_cash_entries_amount CHECK (amount > 0),
    INDEX idx_cash_entries_shift_time (shift_id, created_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
