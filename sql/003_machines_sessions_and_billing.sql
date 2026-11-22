-- Workstations, room classifications, usage sessions, occupancy tracking, wallet ledger, and invoices.

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE machines (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(20) NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
    hourly_rate BIGINT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT pk_machines PRIMARY KEY (id),
    CONSTRAINT uq_machines_code UNIQUE (code),
    CONSTRAINT fk_machines_store
        FOREIGN KEY (store_id) REFERENCES stores (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_machines_code_not_blank CHECK (CHAR_LENGTH(TRIM(code)) > 0),
    CONSTRAINT chk_machines_name_not_blank CHECK (CHAR_LENGTH(TRIM(name)) > 0),
    CONSTRAINT chk_machines_hourly_rate CHECK (hourly_rate > 0),
    CONSTRAINT chk_machines_status CHECK (status IN ('AVAILABLE', 'IN_USE', 'MAINTENANCE')),
    CONSTRAINT chk_machines_is_active CHECK (is_active IN (FALSE, TRUE)),
    CONSTRAINT chk_machines_archived_not_in_use CHECK (is_active = TRUE OR status <> 'IN_USE')
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE machine_room_types (
    machine_id BIGINT UNSIGNED NOT NULL,
    room_type VARCHAR(10) NOT NULL,

    CONSTRAINT pk_machine_room_types PRIMARY KEY (machine_id),
    CONSTRAINT fk_machine_room_machine
        FOREIGN KEY (machine_id) REFERENCES machines (id)
        ON UPDATE RESTRICT ON DELETE CASCADE,
    CONSTRAINT chk_machine_room_type CHECK (
        room_type IN ('STANDARD', 'VIP', 'COUPLE', 'SUPER_VIP')
    )
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE usage_sessions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(20) NOT NULL,
    customer_id BIGINT UNSIGNED NOT NULL,
    machine_id BIGINT UNSIGNED NOT NULL,
    opened_by BIGINT UNSIGNED NOT NULL,
    closed_by BIGINT UNSIGNED NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME NULL,
    hourly_rate BIGINT NOT NULL,
    cost BIGINT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',

    CONSTRAINT pk_usage_sessions PRIMARY KEY (id),
    CONSTRAINT uq_usage_sessions_code UNIQUE (code),
    CONSTRAINT fk_usage_sessions_customer
        FOREIGN KEY (customer_id) REFERENCES customers (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_usage_sessions_machine
        FOREIGN KEY (machine_id) REFERENCES machines (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_usage_sessions_opened_by
        FOREIGN KEY (opened_by) REFERENCES employees (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_usage_sessions_closed_by
        FOREIGN KEY (closed_by) REFERENCES employees (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_usage_sessions_code_not_blank CHECK (CHAR_LENGTH(TRIM(code)) > 0),
    CONSTRAINT chk_usage_sessions_hourly_rate CHECK (hourly_rate > 0),
    CONSTRAINT chk_usage_sessions_cost CHECK (cost IS NULL OR cost >= 0),
    CONSTRAINT chk_usage_sessions_status CHECK (status IN ('ACTIVE', 'COMPLETED', 'CANCELLED')),
    CONSTRAINT chk_usage_sessions_time_order CHECK (ended_at IS NULL OR ended_at >= started_at),
    CONSTRAINT chk_usage_sessions_state CHECK (
        (status = 'ACTIVE' AND closed_by IS NULL AND ended_at IS NULL AND cost IS NULL)
        OR (status = 'COMPLETED' AND closed_by IS NOT NULL AND ended_at IS NOT NULL AND cost IS NOT NULL)
        OR (status = 'CANCELLED' AND ended_at IS NOT NULL)
    )
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE active_usage_sessions (
    session_id BIGINT UNSIGNED NOT NULL,
    machine_id BIGINT UNSIGNED NOT NULL,
    customer_id BIGINT UNSIGNED NOT NULL,

    CONSTRAINT pk_active_usage_sessions PRIMARY KEY (session_id),
    CONSTRAINT uq_active_usage_machine UNIQUE (machine_id),
    CONSTRAINT uq_active_usage_customer UNIQUE (customer_id),
    CONSTRAINT fk_active_usage_session
        FOREIGN KEY (session_id) REFERENCES usage_sessions (id)
        ON UPDATE RESTRICT ON DELETE CASCADE,
    CONSTRAINT fk_active_usage_machine
        FOREIGN KEY (machine_id) REFERENCES machines (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_active_usage_customer
        FOREIGN KEY (customer_id) REFERENCES customers (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE account_transactions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(20) NOT NULL,
    account_id BIGINT UNSIGNED NOT NULL,
    employee_id BIGINT UNSIGNED NOT NULL,
    session_id BIGINT UNSIGNED NULL,
    store_id BIGINT UNSIGNED NULL,
    promotion_id BIGINT UNSIGNED NULL,
    type VARCHAR(20) NOT NULL,
    amount BIGINT NOT NULL,
    method VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_account_transactions PRIMARY KEY (id),
    CONSTRAINT uq_account_transactions_code UNIQUE (code),
    CONSTRAINT fk_account_transactions_account
        FOREIGN KEY (account_id) REFERENCES accounts (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_account_transactions_employee
        FOREIGN KEY (employee_id) REFERENCES employees (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_account_transactions_session
        FOREIGN KEY (session_id) REFERENCES usage_sessions (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_transactions_store
        FOREIGN KEY (store_id) REFERENCES stores (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_transactions_promotion
        FOREIGN KEY (promotion_id) REFERENCES promotions (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_account_transactions_code_not_blank CHECK (CHAR_LENGTH(TRIM(code)) > 0),
    CONSTRAINT chk_account_transactions_type CHECK (
        type IN ('TOP_UP', 'PROMOTION', 'USAGE_PAYMENT', 'DEBT_SETTLEMENT')
    ),
    CONSTRAINT chk_account_transactions_amount CHECK (
        (type IN ('TOP_UP', 'PROMOTION', 'DEBT_SETTLEMENT') AND amount > 0)
        OR (type = 'USAGE_PAYMENT' AND amount < 0)
    ),
    CONSTRAINT chk_account_transactions_method CHECK (
        method IN ('CASH', 'TRANSFER', 'ACCOUNT_BALANCE', 'PROMOTION')
    ),
    CONSTRAINT chk_account_transactions_type_method CHECK (
        (type IN ('TOP_UP', 'DEBT_SETTLEMENT') AND method IN ('CASH', 'TRANSFER'))
        OR (type = 'USAGE_PAYMENT' AND method = 'ACCOUNT_BALANCE')
        OR (type = 'PROMOTION' AND method = 'PROMOTION')
    )
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE invoices (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(20) NOT NULL,
    session_id BIGINT UNSIGNED NOT NULL,
    customer_id BIGINT UNSIGNED NOT NULL,
    employee_id BIGINT UNSIGNED NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    usage_cost BIGINT NOT NULL,
    settlement_amount BIGINT NOT NULL DEFAULT 0,
    bonus_used BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'PAID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_invoices PRIMARY KEY (id),
    CONSTRAINT uq_invoices_code UNIQUE (code),
    CONSTRAINT uq_invoices_session UNIQUE (session_id),
    CONSTRAINT fk_invoices_session
        FOREIGN KEY (session_id) REFERENCES usage_sessions (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_invoices_customer
        FOREIGN KEY (customer_id) REFERENCES customers (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_invoices_employee
        FOREIGN KEY (employee_id) REFERENCES employees (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_invoices_store
        FOREIGN KEY (store_id) REFERENCES stores (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_invoices_code_not_blank CHECK (CHAR_LENGTH(TRIM(code)) > 0),
    CONSTRAINT chk_invoices_money CHECK (usage_cost >= 0 AND settlement_amount >= 0),
    CONSTRAINT chk_invoices_settlement CHECK (settlement_amount <= usage_cost),
    CONSTRAINT chk_invoices_bonus_used CHECK (bonus_used >= 0 AND bonus_used <= usage_cost),
    CONSTRAINT chk_invoices_status CHECK (status IN ('PAID', 'VOID'))
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;
