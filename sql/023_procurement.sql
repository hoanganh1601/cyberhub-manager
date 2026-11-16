-- Supplier purchasing: request, approval, purchase order, receipt and payable.
CREATE TABLE suppliers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    store_id BIGINT UNSIGNED NOT NULL,
    code VARCHAR(24) NOT NULL,
    name VARCHAR(120) NOT NULL,
    phone VARCHAR(20) NULL,
    email VARCHAR(120) NULL,
    address VARCHAR(255) NULL,
    payment_terms_days INT UNSIGNED NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_suppliers_store_code UNIQUE (store_id, code),
    CONSTRAINT fk_suppliers_store FOREIGN KEY (store_id) REFERENCES stores(id),
    CONSTRAINT chk_suppliers_terms CHECK (payment_terms_days <= 365)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE purchase_requests (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(24) NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    requested_by BIGINT UNSIGNED NOT NULL,
    status VARCHAR(12) NOT NULL DEFAULT 'PENDING',
    reason VARCHAR(255) NOT NULL,
    decided_by BIGINT UNSIGNED NULL,
    decided_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_purchase_requests_code UNIQUE (code),
    CONSTRAINT fk_purchase_requests_store FOREIGN KEY (store_id) REFERENCES stores(id),
    CONSTRAINT fk_purchase_requests_requester FOREIGN KEY (requested_by) REFERENCES employees(id),
    CONSTRAINT fk_purchase_requests_decider FOREIGN KEY (decided_by) REFERENCES employees(id),
    CONSTRAINT chk_purchase_requests_status CHECK (status IN ('PENDING','APPROVED','REJECTED','ORDERED')),
    CONSTRAINT chk_purchase_requests_decision CHECK (
        (status='PENDING' AND decided_by IS NULL AND decided_at IS NULL)
        OR (status<>'PENDING' AND decided_by IS NOT NULL AND decided_at IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE purchase_request_lines (
    request_id BIGINT UNSIGNED NOT NULL,
    ingredient_id BIGINT UNSIGNED NOT NULL,
    quantity BIGINT UNSIGNED NOT NULL,
    CONSTRAINT pk_purchase_request_lines PRIMARY KEY (request_id, ingredient_id),
    CONSTRAINT fk_purchase_request_lines_request FOREIGN KEY (request_id) REFERENCES purchase_requests(id),
    CONSTRAINT fk_purchase_request_lines_ingredient FOREIGN KEY (ingredient_id) REFERENCES inventory_ingredients(id),
    CONSTRAINT chk_purchase_request_lines_quantity CHECK (quantity > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE purchase_orders (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(24) NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    request_id BIGINT UNSIGNED NOT NULL,
    supplier_id BIGINT UNSIGNED NOT NULL,
    created_by BIGINT UNSIGNED NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    ordered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expected_at DATETIME NULL,
    total_amount BIGINT UNSIGNED NOT NULL,
    CONSTRAINT uq_purchase_orders_code UNIQUE (code),
    CONSTRAINT uq_purchase_orders_request UNIQUE (request_id),
    CONSTRAINT fk_purchase_orders_store FOREIGN KEY (store_id) REFERENCES stores(id),
    CONSTRAINT fk_purchase_orders_request FOREIGN KEY (request_id) REFERENCES purchase_requests(id),
    CONSTRAINT fk_purchase_orders_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
    CONSTRAINT fk_purchase_orders_creator FOREIGN KEY (created_by) REFERENCES employees(id),
    CONSTRAINT chk_purchase_orders_status CHECK (status IN ('OPEN','PARTIALLY_RECEIVED','RECEIVED','CANCELLED')),
    CONSTRAINT chk_purchase_orders_total CHECK (total_amount > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE purchase_order_lines (
    order_id BIGINT UNSIGNED NOT NULL,
    ingredient_id BIGINT UNSIGNED NOT NULL,
    quantity BIGINT UNSIGNED NOT NULL,
    unit_cost BIGINT UNSIGNED NOT NULL,
    received_quantity BIGINT UNSIGNED NOT NULL DEFAULT 0,
    damaged_quantity BIGINT UNSIGNED NOT NULL DEFAULT 0,
    CONSTRAINT pk_purchase_order_lines PRIMARY KEY (order_id, ingredient_id),
    CONSTRAINT fk_purchase_order_lines_order FOREIGN KEY (order_id) REFERENCES purchase_orders(id),
    CONSTRAINT fk_purchase_order_lines_ingredient FOREIGN KEY (ingredient_id) REFERENCES inventory_ingredients(id),
    CONSTRAINT chk_purchase_order_lines_quantity CHECK (quantity > 0 AND unit_cost > 0),
    CONSTRAINT chk_purchase_order_lines_received CHECK (received_quantity + damaged_quantity <= quantity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE goods_receipts (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(24) NOT NULL,
    order_id BIGINT UNSIGNED NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    received_by BIGINT UNSIGNED NOT NULL,
    request_id CHAR(32) NOT NULL,
    note VARCHAR(255) NOT NULL DEFAULT '',
    received_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    accepted_amount BIGINT UNSIGNED NOT NULL,
    CONSTRAINT uq_goods_receipts_code UNIQUE (code),
    CONSTRAINT uq_goods_receipts_request UNIQUE (request_id),
    CONSTRAINT fk_goods_receipts_order FOREIGN KEY (order_id) REFERENCES purchase_orders(id),
    CONSTRAINT fk_goods_receipts_store FOREIGN KEY (store_id) REFERENCES stores(id),
    CONSTRAINT fk_goods_receipts_receiver FOREIGN KEY (received_by) REFERENCES employees(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE goods_receipt_lines (
    receipt_id BIGINT UNSIGNED NOT NULL,
    ingredient_id BIGINT UNSIGNED NOT NULL,
    accepted_quantity BIGINT UNSIGNED NOT NULL,
    damaged_quantity BIGINT UNSIGNED NOT NULL DEFAULT 0,
    missing_quantity BIGINT UNSIGNED NOT NULL DEFAULT 0,
    unit_cost BIGINT UNSIGNED NOT NULL,
    CONSTRAINT pk_goods_receipt_lines PRIMARY KEY (receipt_id, ingredient_id),
    CONSTRAINT fk_goods_receipt_lines_receipt FOREIGN KEY (receipt_id) REFERENCES goods_receipts(id),
    CONSTRAINT fk_goods_receipt_lines_ingredient FOREIGN KEY (ingredient_id) REFERENCES inventory_ingredients(id),
    CONSTRAINT chk_goods_receipt_lines_quantity CHECK (accepted_quantity + damaged_quantity + missing_quantity > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE supplier_payables (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    receipt_id BIGINT UNSIGNED NOT NULL,
    supplier_id BIGINT UNSIGNED NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    amount BIGINT UNSIGNED NOT NULL,
    paid_amount BIGINT UNSIGNED NOT NULL DEFAULT 0,
    due_date DATE NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'UNPAID',
    paid_at DATETIME NULL,
    paid_by BIGINT UNSIGNED NULL,
    payment_method VARCHAR(10) NULL,
    CONSTRAINT uq_supplier_payables_receipt UNIQUE (receipt_id),
    CONSTRAINT fk_supplier_payables_receipt FOREIGN KEY (receipt_id) REFERENCES goods_receipts(id),
    CONSTRAINT fk_supplier_payables_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
    CONSTRAINT fk_supplier_payables_store FOREIGN KEY (store_id) REFERENCES stores(id),
    CONSTRAINT fk_supplier_payables_employee FOREIGN KEY (paid_by) REFERENCES employees(id),
    CONSTRAINT chk_supplier_payables_amount CHECK (amount > 0 AND paid_amount <= amount),
    CONSTRAINT chk_supplier_payables_status CHECK (status IN ('UNPAID','PAID')),
    CONSTRAINT chk_supplier_payables_method CHECK (payment_method IS NULL OR payment_method IN ('CASH','TRANSFER')),
    INDEX idx_supplier_payables_due (store_id, status, due_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
