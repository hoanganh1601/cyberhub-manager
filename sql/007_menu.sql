-- Đợt 1: menu đồ ăn/đồ uống theo từng cửa hàng và yêu cầu gọi món của khách đang chơi.
-- Gọi món chưa trừ tiền trong ví: nhân viên phục vụ và thu tiền tại quầy, luồng thanh toán phiên giữ nguyên.

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
    CONSTRAINT fk_menu_categories_store FOREIGN KEY (store_id)
        REFERENCES stores (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_menu_categories_page CHECK (page IN ('FOOD', 'DRINK')),
    CONSTRAINT chk_menu_categories_name CHECK (CHAR_LENGTH(TRIM(name)) > 0),
    CONSTRAINT chk_menu_categories_sort CHECK (sort_order BETWEEN 0 AND 9999),
    INDEX idx_menu_categories_store_page (store_id, page, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE menu_items (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    store_id BIGINT UNSIGNED NOT NULL,
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
    CONSTRAINT uq_menu_items_store_name UNIQUE (store_id, name),
    CONSTRAINT fk_menu_items_store FOREIGN KEY (store_id)
        REFERENCES stores (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    -- Món và nhóm món cùng cửa hàng: MenuService kiểm tra trong cùng transaction.
    CONSTRAINT fk_menu_items_category FOREIGN KEY (category_id)
        REFERENCES menu_categories (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_menu_items_name CHECK (CHAR_LENGTH(TRIM(name)) > 0),
    CONSTRAINT chk_menu_items_price CHECK (price BETWEEN 1000 AND 10000000),
    CONSTRAINT chk_menu_items_sort CHECK (sort_order BETWEEN 0 AND 9999),
    INDEX idx_menu_items_store_category (store_id, category_id, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Ảnh đã chuẩn hóa (WebP 512x512, không metadata); món không xóa cứng nên ảnh đi theo món.
CREATE TABLE menu_item_images (
    item_id BIGINT UNSIGNED NOT NULL,
    image_data MEDIUMBLOB NOT NULL,
    digest CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT pk_menu_item_images PRIMARY KEY (item_id),
    CONSTRAINT fk_menu_item_images_item FOREIGN KEY (item_id)
        REFERENCES menu_items (id) ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Lịch sử thay đổi giá và trạng thái bán; chỉ thêm, không sửa/xóa.
CREATE TABLE menu_item_changes (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    item_id BIGINT UNSIGNED NOT NULL,
    employee_id BIGINT UNSIGNED NOT NULL,
    field VARCHAR(20) NOT NULL,
    old_value VARCHAR(200) NULL,
    new_value VARCHAR(200) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_menu_item_changes PRIMARY KEY (id),
    CONSTRAINT fk_menu_item_changes_item FOREIGN KEY (item_id)
        REFERENCES menu_items (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_menu_item_changes_employee FOREIGN KEY (employee_id)
        REFERENCES employees (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_menu_item_changes_field CHECK (
        field IN ('CREATE', 'NAME', 'CATEGORY', 'PRICE', 'AVAILABLE', 'VISIBLE', 'IMAGE')
    ),
    INDEX idx_menu_item_changes_item (item_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Yêu cầu gọi món gắn với phiên ACTIVE của khách; giá được chụp lại lúc đặt.
CREATE TABLE menu_orders (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(20) NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    account_id BIGINT UNSIGNED NOT NULL,
    session_id BIGINT UNSIGNED NOT NULL,
    machine_id BIGINT UNSIGNED NOT NULL,
    note VARCHAR(200) NOT NULL DEFAULT '',
    total_amount BIGINT NOT NULL,
    status VARCHAR(12) NOT NULL DEFAULT 'NEW',
    handled_by BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT pk_menu_orders PRIMARY KEY (id),
    CONSTRAINT uq_menu_orders_code UNIQUE (code),
    CONSTRAINT fk_menu_orders_store FOREIGN KEY (store_id)
        REFERENCES stores (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_menu_orders_account FOREIGN KEY (account_id)
        REFERENCES accounts (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_menu_orders_session FOREIGN KEY (session_id)
        REFERENCES usage_sessions (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_menu_orders_machine FOREIGN KEY (machine_id)
        REFERENCES machines (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_menu_orders_handled_by FOREIGN KEY (handled_by)
        REFERENCES employees (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_menu_orders_status CHECK (status IN ('NEW', 'SERVED', 'CANCELLED')),
    CONSTRAINT chk_menu_orders_total CHECK (total_amount > 0),
    CONSTRAINT chk_menu_orders_handled CHECK (
        (status = 'NEW' AND handled_by IS NULL) OR (status <> 'NEW' AND handled_by IS NOT NULL)
    ),
    INDEX idx_menu_orders_store_status (store_id, status, created_at),
    INDEX idx_menu_orders_account (account_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE menu_order_items (
    order_id BIGINT UNSIGNED NOT NULL,
    item_id BIGINT UNSIGNED NOT NULL,
    item_name VARCHAR(80) NOT NULL,
    unit_price BIGINT NOT NULL,
    quantity INT NOT NULL,
    CONSTRAINT pk_menu_order_items PRIMARY KEY (order_id, item_id),
    CONSTRAINT fk_menu_order_items_order FOREIGN KEY (order_id)
        REFERENCES menu_orders (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_menu_order_items_item FOREIGN KEY (item_id)
        REFERENCES menu_items (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_menu_order_items_price CHECK (unit_price BETWEEN 1000 AND 10000000),
    CONSTRAINT chk_menu_order_items_quantity CHECK (quantity BETWEEN 1 AND 20)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
