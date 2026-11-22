-- Store food/beverage catalog and counter-settled POS orders.

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE menu_categories (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    store_id BIGINT UNSIGNED NOT NULL,
    page VARCHAR(10) NOT NULL,
    name VARCHAR(60) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_menu_categories PRIMARY KEY (id),
    CONSTRAINT uq_menu_categories_store_name UNIQUE (store_id, name),
    CONSTRAINT fk_menu_categories_store
        FOREIGN KEY (store_id) REFERENCES stores (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_menu_categories_page CHECK (page IN ('FOOD', 'DRINK')),
    CONSTRAINT chk_menu_categories_name CHECK (CHAR_LENGTH(TRIM(name)) > 0),
    CONSTRAINT chk_menu_categories_sort CHECK (sort_order BETWEEN 0 AND 9999)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE menu_items (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    category_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(80) NOT NULL,
    description VARCHAR(200) NOT NULL DEFAULT '',
    price BIGINT NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    is_visible BOOLEAN NOT NULL DEFAULT TRUE,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT pk_menu_items PRIMARY KEY (id),
    CONSTRAINT uq_menu_items_category_name UNIQUE (category_id, name),
    CONSTRAINT fk_menu_items_category
        FOREIGN KEY (category_id) REFERENCES menu_categories (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_menu_items_name CHECK (CHAR_LENGTH(TRIM(name)) > 0),
    CONSTRAINT chk_menu_items_price CHECK (price BETWEEN 1000 AND 10000000),
    CONSTRAINT chk_menu_items_sort CHECK (sort_order BETWEEN 0 AND 9999)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE menu_orders (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(20) NOT NULL,
    session_id BIGINT UNSIGNED NOT NULL,
    note VARCHAR(200) NOT NULL DEFAULT '',
    total_amount BIGINT NOT NULL,
    status VARCHAR(12) NOT NULL DEFAULT 'NEW',
    handled_by BIGINT UNSIGNED NULL,
    payment_method VARCHAR(10) NULL,
    paid_at DATETIME NULL,
    paid_by BIGINT UNSIGNED NULL,
    reservation_expires_at DATETIME NULL,
    cancel_reason VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT pk_menu_orders PRIMARY KEY (id),
    CONSTRAINT uq_menu_orders_code UNIQUE (code),
    CONSTRAINT fk_menu_orders_session
        FOREIGN KEY (session_id) REFERENCES usage_sessions (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_menu_orders_handled_by
        FOREIGN KEY (handled_by) REFERENCES employees (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_menu_orders_paid_by
        FOREIGN KEY (paid_by) REFERENCES employees (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_menu_orders_status CHECK (
        status IN ('NEW', 'PREPARING', 'SERVED', 'PAID', 'CANCELLED', 'REFUNDED')
    ),
    CONSTRAINT chk_menu_orders_total CHECK (total_amount > 0),
    CONSTRAINT chk_menu_orders_handled CHECK (
        (status = 'NEW' AND handled_by IS NULL)
        OR (status = 'CANCELLED' AND handled_by IS NULL AND cancel_reason = 'AUTO_EXPIRED')
        OR (status <> 'NEW' AND handled_by IS NOT NULL)
    ),
    CONSTRAINT chk_menu_orders_payment CHECK (
        (
            status IN ('PAID', 'REFUNDED')
            AND payment_method IS NOT NULL
            AND payment_method IN ('CASH', 'TRANSFER')
            AND paid_at IS NOT NULL
            AND paid_by IS NOT NULL
        )
        OR (
            status NOT IN ('PAID', 'REFUNDED')
            AND payment_method IS NULL
            AND paid_at IS NULL
            AND paid_by IS NULL
        )
    )
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE menu_order_items (
    order_id BIGINT UNSIGNED NOT NULL,
    item_id BIGINT UNSIGNED NOT NULL,
    item_name VARCHAR(80) NOT NULL,
    unit_price BIGINT NOT NULL,
    quantity INT NOT NULL,

    CONSTRAINT pk_menu_order_items PRIMARY KEY (order_id, item_id),
    CONSTRAINT fk_menu_order_items_order
        FOREIGN KEY (order_id) REFERENCES menu_orders (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_menu_order_items_item
        FOREIGN KEY (item_id) REFERENCES menu_items (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_menu_order_items_price CHECK (unit_price BETWEEN 1000 AND 10000000),
    CONSTRAINT chk_menu_order_items_quantity CHECK (quantity BETWEEN 1 AND 20)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;
