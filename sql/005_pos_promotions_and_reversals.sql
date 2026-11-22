-- POS promotion rules, immutable policy versions, order pricing, and maker-checker reversals.

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE menu_promotions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    store_id BIGINT UNSIGNED NOT NULL,
    code VARCHAR(30) NOT NULL,
    kind VARCHAR(16) NOT NULL,
    item_id BIGINT UNSIGNED NULL,
    value INT UNSIGNED NOT NULL,
    starts_at DATETIME NOT NULL,
    ends_at DATETIME NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT pk_menu_promotions PRIMARY KEY (id),
    CONSTRAINT uq_menu_promo_store_code UNIQUE (store_id, code),
    CONSTRAINT fk_menu_promo_store
        FOREIGN KEY (store_id) REFERENCES stores (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_menu_promo_item
        FOREIGN KEY (item_id) REFERENCES menu_items (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_menu_promo_code_not_blank CHECK (CHAR_LENGTH(TRIM(code)) > 0),
    CONSTRAINT chk_menu_promo_kind CHECK (kind IN ('BOGO', 'PLAY_DRINK')),
    CONSTRAINT chk_menu_promo_period CHECK (starts_at < ends_at)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE menu_promotion_versions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    promotion_id BIGINT UNSIGNED NOT NULL,
    version INT UNSIGNED NOT NULL,
    code VARCHAR(30) NOT NULL,
    kind VARCHAR(16) NOT NULL,
    item_id BIGINT UNSIGNED NULL,
    value INT UNSIGNED NOT NULL,
    starts_at DATETIME NOT NULL,
    ends_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_menu_promotion_versions PRIMARY KEY (id),
    CONSTRAINT uq_menu_promo_ver UNIQUE (promotion_id, version),
    CONSTRAINT fk_menu_promo_ver_promo
        FOREIGN KEY (promotion_id) REFERENCES menu_promotions (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_menu_promo_ver_item
        FOREIGN KEY (item_id) REFERENCES menu_items (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_menu_promo_ver_version CHECK (version >= 1),
    CONSTRAINT chk_menu_promo_ver_code_not_blank CHECK (CHAR_LENGTH(TRIM(code)) > 0),
    CONSTRAINT chk_menu_promo_ver_kind CHECK (kind IN ('BOGO', 'PLAY_DRINK')),
    CONSTRAINT chk_menu_promo_ver_period CHECK (starts_at < ends_at)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE menu_order_pricing (
    order_id BIGINT UNSIGNED NOT NULL,
    promotion_version_id BIGINT UNSIGNED NULL,
    discount_amount BIGINT UNSIGNED NOT NULL DEFAULT 0,

    CONSTRAINT pk_menu_order_pricing PRIMARY KEY (order_id),
    CONSTRAINT fk_menu_pricing_order
        FOREIGN KEY (order_id) REFERENCES menu_orders (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_menu_pricing_promo_version
        FOREIGN KEY (promotion_version_id) REFERENCES menu_promotion_versions (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_menu_order_pricing_discount CHECK (
        discount_amount >= 0 AND (promotion_version_id IS NOT NULL OR discount_amount = 0)
    )
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE pos_order_reversals (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    order_id BIGINT UNSIGNED NOT NULL,
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

    CONSTRAINT pk_pos_order_reversals PRIMARY KEY (id),
    CONSTRAINT uq_pos_reversal_order UNIQUE (order_id),
    CONSTRAINT fk_pos_reversal_order
        FOREIGN KEY (order_id) REFERENCES menu_orders (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_pos_reversal_requester
        FOREIGN KEY (requested_by) REFERENCES employees (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_pos_reversal_approver
        FOREIGN KEY (decided_by) REFERENCES employees (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_pos_reversal_reason_not_blank CHECK (CHAR_LENGTH(TRIM(reason)) > 0),
    CONSTRAINT chk_pos_reversal_disposition CHECK (disposition IN ('RESTOCK', 'WASTE')),
    CONSTRAINT chk_pos_reversal_status CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    CONSTRAINT chk_pos_reversal_method CHECK (
        refund_method IS NULL OR refund_method IN ('CASH', 'TRANSFER')
    ),
    CONSTRAINT chk_pos_reversal_decision_and_sod CHECK (
        (
            status = 'PENDING'
            AND decided_by IS NULL
            AND decided_at IS NULL
            AND refund_amount = 0
            AND refund_method IS NULL
        )
        OR (
            status = 'REJECTED'
            AND decided_by IS NOT NULL
            AND decided_at IS NOT NULL
            AND decided_by <> requested_by
            AND refund_amount = 0
            AND refund_method IS NULL
        )
        OR (
            status = 'APPROVED'
            AND decided_by IS NOT NULL
            AND decided_at IS NOT NULL
            AND decided_by <> requested_by
            AND (
                (refund_amount = 0 AND refund_method IS NULL)
                OR (refund_amount > 0 AND refund_method IS NOT NULL AND refund_method IN ('CASH', 'TRANSFER'))
            )
        )
    )
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;
