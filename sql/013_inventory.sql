-- Kho POS theo cửa hàng. Số lượng là số nguyên theo đơn vị g/ml/cái.
CREATE TABLE inventory_ingredients (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    store_id BIGINT UNSIGNED NOT NULL,
    code VARCHAR(32) NOT NULL,
    name VARCHAR(100) NOT NULL,
    unit VARCHAR(4) NOT NULL,
    on_hand BIGINT NOT NULL DEFAULT 0,
    reserved BIGINT NOT NULL DEFAULT 0,
    reorder_point BIGINT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_inventory_ingredients_store_code UNIQUE (store_id, code),
    CONSTRAINT uq_inventory_ingredients_store_id UNIQUE (store_id, id),
    CONSTRAINT fk_inventory_ingredients_store FOREIGN KEY (store_id) REFERENCES stores (id),
    CONSTRAINT chk_inventory_ingredients_unit CHECK (unit IN ('g', 'ml', 'each')),
    CONSTRAINT chk_inventory_ingredients_balance CHECK
        (on_hand >= 0 AND reserved >= 0 AND reserved <= on_hand AND reorder_point >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE menu_items ADD COLUMN is_stock_tracked BOOLEAN NOT NULL DEFAULT FALSE;

-- Keep the reason even for legacy orders that have no recipe snapshot.
ALTER TABLE menu_orders ADD COLUMN cancel_reason VARCHAR(255) NULL;

CREATE TABLE menu_item_recipes (
    item_id BIGINT UNSIGNED NOT NULL,
    ingredient_id BIGINT UNSIGNED NOT NULL,
    quantity_per_unit BIGINT NOT NULL,
    CONSTRAINT pk_menu_item_recipes PRIMARY KEY (item_id, ingredient_id),
    CONSTRAINT fk_menu_item_recipes_item FOREIGN KEY (item_id) REFERENCES menu_items (id),
    CONSTRAINT fk_menu_item_recipes_ingredient FOREIGN KEY (ingredient_id) REFERENCES inventory_ingredients (id),
    CONSTRAINT chk_menu_item_recipes_quantity CHECK (quantity_per_unit > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE menu_order_recipe_snapshots (
    order_id BIGINT UNSIGNED NOT NULL,
    item_id BIGINT UNSIGNED NOT NULL,
    ingredient_id BIGINT UNSIGNED NOT NULL,
    quantity BIGINT NOT NULL,
    CONSTRAINT pk_menu_order_recipe_snapshots PRIMARY KEY (order_id, item_id, ingredient_id),
    CONSTRAINT fk_menu_order_recipe_snapshots_line FOREIGN KEY (order_id, item_id)
        REFERENCES menu_order_items (order_id, item_id),
    CONSTRAINT fk_menu_order_recipe_snapshots_ingredient FOREIGN KEY (ingredient_id)
        REFERENCES inventory_ingredients (id),
    CONSTRAINT chk_menu_order_recipe_snapshots_quantity CHECK (quantity > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE inventory_movements (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    store_id BIGINT UNSIGNED NOT NULL,
    ingredient_id BIGINT UNSIGNED NOT NULL,
    order_id BIGINT UNSIGNED NULL,
    employee_id BIGINT UNSIGNED NULL,
    account_id BIGINT UNSIGNED NULL,
    kind VARCHAR(10) NOT NULL,
    quantity BIGINT NOT NULL,
    on_hand_delta BIGINT NOT NULL DEFAULT 0,
    reserved_delta BIGINT NOT NULL DEFAULT 0,
    idempotency_key VARCHAR(100) NOT NULL,
    reference_code VARCHAR(60) NULL,
    note VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_inventory_movements_key UNIQUE (idempotency_key),
    CONSTRAINT fk_inventory_movements_ingredient FOREIGN KEY (store_id, ingredient_id)
        REFERENCES inventory_ingredients (store_id, id),
    CONSTRAINT fk_inventory_movements_order FOREIGN KEY (order_id) REFERENCES menu_orders (id),
    CONSTRAINT fk_inventory_movements_employee FOREIGN KEY (employee_id) REFERENCES employees (id),
    CONSTRAINT fk_inventory_movements_account FOREIGN KEY (account_id) REFERENCES accounts (id),
    CONSTRAINT chk_inventory_movements_kind CHECK
        (kind IN ('RECEIVE', 'RESERVE', 'RELEASE', 'CONSUME', 'WASTE', 'RETURN', 'ADJUST')),
    CONSTRAINT chk_inventory_movements_quantity CHECK (quantity > 0),
    INDEX idx_inventory_movements_store_time (store_id, created_at, id),
    INDEX idx_inventory_movements_ingredient_id (ingredient_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
