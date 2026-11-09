-- Đợt 2: danh mục phần thưởng, voucher của khách, nhật ký phát hành/sử dụng và điểm thành viên được tặng.
-- Voucher không có giá trị tiền mặt: chỉ giảm giá đồ ăn, tặng nước, cộng số dư khuyến mãi (không rút được)
-- hoặc cộng điểm thành viên.

CREATE TABLE reward_catalog (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(80) NOT NULL,
    store_id BIGINT UNSIGNED NULL,  -- NULL: dùng được ở mọi cơ sở
    reward_type VARCHAR(20) NOT NULL,
    value BIGINT NOT NULL,           -- VND (giảm/tặng/cộng giờ) hoặc số điểm (MEMBER_POINTS)
    min_order_amount BIGINT NOT NULL DEFAULT 0,
    valid_days INT NOT NULL,
    coin_cost BIGINT NULL,           -- Đợt 3: giá đổi bằng xu game; NULL = không đổi bằng xu
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_reward_catalog PRIMARY KEY (id),
    CONSTRAINT uq_reward_catalog_code UNIQUE (code),
    CONSTRAINT fk_reward_catalog_store FOREIGN KEY (store_id)
        REFERENCES stores (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_reward_catalog_type CHECK (
        reward_type IN ('FOOD_DISCOUNT', 'FREE_DRINK', 'PLAYTIME_CREDIT', 'MEMBER_POINTS')
    ),
    CONSTRAINT chk_reward_catalog_value CHECK (value BETWEEN 1 AND 1000000),
    CONSTRAINT chk_reward_catalog_min_order CHECK (min_order_amount BETWEEN 0 AND 10000000),
    CONSTRAINT chk_reward_catalog_days CHECK (valid_days BETWEEN 1 AND 365),
    CONSTRAINT chk_reward_catalog_coin CHECK (coin_cost IS NULL OR coin_cost BETWEEN 1 AND 1000000),
    CONSTRAINT chk_reward_catalog_name CHECK (CHAR_LENGTH(TRIM(name)) > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Điều kiện (loại, giá trị, đơn tối thiểu, phạm vi cơ sở, hạn) được chụp lúc phát hành:
-- sửa danh mục sau đó không làm thay đổi voucher đã phát.
CREATE TABLE customer_vouchers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(20) NOT NULL,
    catalog_id BIGINT UNSIGNED NOT NULL,
    account_id BIGINT UNSIGNED NOT NULL,
    store_id BIGINT UNSIGNED NULL,
    reward_type VARCHAR(20) NOT NULL,
    value BIGINT NOT NULL,
    min_order_amount BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(10) NOT NULL DEFAULT 'ISSUED',
    source VARCHAR(10) NOT NULL,
    source_ref VARCHAR(64) NULL,
    issued_by BIGINT UNSIGNED NULL,
    issued_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,
    used_by BIGINT UNSIGNED NULL,
    used_store_id BIGINT UNSIGNED NULL,
    used_order_id BIGINT UNSIGNED NULL,
    revoked_reason VARCHAR(200) NULL,
    CONSTRAINT pk_customer_vouchers PRIMARY KEY (id),
    CONSTRAINT uq_customer_vouchers_code UNIQUE (code),
    -- Một nguồn (vd. một phiên game, một lần đổi xu) chỉ phát được một voucher.
    CONSTRAINT uq_customer_vouchers_source UNIQUE (source, source_ref),
    -- Một yêu cầu gọi món chỉ áp được một voucher.
    CONSTRAINT uq_customer_vouchers_order UNIQUE (used_order_id),
    CONSTRAINT fk_customer_vouchers_catalog FOREIGN KEY (catalog_id)
        REFERENCES reward_catalog (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_customer_vouchers_account FOREIGN KEY (account_id)
        REFERENCES accounts (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_customer_vouchers_store FOREIGN KEY (store_id)
        REFERENCES stores (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_customer_vouchers_issued_by FOREIGN KEY (issued_by)
        REFERENCES employees (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_customer_vouchers_used_by FOREIGN KEY (used_by)
        REFERENCES employees (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_customer_vouchers_used_store FOREIGN KEY (used_store_id)
        REFERENCES stores (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_customer_vouchers_used_order FOREIGN KEY (used_order_id)
        REFERENCES menu_orders (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_customer_vouchers_type CHECK (
        reward_type IN ('FOOD_DISCOUNT', 'FREE_DRINK', 'PLAYTIME_CREDIT', 'MEMBER_POINTS')
    ),
    CONSTRAINT chk_customer_vouchers_status CHECK (status IN ('ISSUED', 'USED', 'REVOKED')),
    CONSTRAINT chk_customer_vouchers_source CHECK (source IN ('MANUAL', 'GAME', 'AD')),
    CONSTRAINT chk_customer_vouchers_value CHECK (value BETWEEN 1 AND 1000000),
    CONSTRAINT chk_customer_vouchers_period CHECK (expires_at > issued_at),
    CONSTRAINT chk_customer_vouchers_used CHECK (
        (status = 'USED' AND used_at IS NOT NULL AND used_by IS NOT NULL AND used_store_id IS NOT NULL)
        OR (status <> 'USED' AND used_at IS NULL AND used_by IS NULL AND used_order_id IS NULL)
    ),
    INDEX idx_customer_vouchers_account (account_id, status, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Nhật ký phát hành, sử dụng, thu hồi và cả các lần bị từ chối; chỉ thêm, không sửa/xóa.
CREATE TABLE voucher_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    voucher_id BIGINT UNSIGNED NULL,  -- NULL khi mã nhập vào không tồn tại
    action VARCHAR(10) NOT NULL,
    employee_id BIGINT UNSIGNED NULL,
    store_id BIGINT UNSIGNED NULL,
    reason VARCHAR(200) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_voucher_events PRIMARY KEY (id),
    CONSTRAINT fk_voucher_events_voucher FOREIGN KEY (voucher_id)
        REFERENCES customer_vouchers (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_voucher_events_employee FOREIGN KEY (employee_id)
        REFERENCES employees (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_voucher_events_store FOREIGN KEY (store_id)
        REFERENCES stores (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_voucher_events_action CHECK (action IN ('ISSUE', 'REDEEM', 'REVOKE', 'REJECT')),
    INDEX idx_voucher_events_store (store_id, created_at),
    INDEX idx_voucher_events_voucher (voucher_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Điểm thành viên được tặng qua voucher; cộng vào tổng điểm nhưng KHÔNG đổi hạng (hạng tính theo chi tiêu).
CREATE TABLE loyalty_point_grants (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    customer_id BIGINT UNSIGNED NOT NULL,
    voucher_id BIGINT UNSIGNED NOT NULL,
    points BIGINT NOT NULL,
    employee_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_loyalty_point_grants PRIMARY KEY (id),
    CONSTRAINT uq_loyalty_point_grants_voucher UNIQUE (voucher_id),
    CONSTRAINT fk_loyalty_point_grants_customer FOREIGN KEY (customer_id)
        REFERENCES customers (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_loyalty_point_grants_voucher FOREIGN KEY (voucher_id)
        REFERENCES customer_vouchers (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_loyalty_point_grants_employee FOREIGN KEY (employee_id)
        REFERENCES employees (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_loyalty_point_grants_points CHECK (points BETWEEN 1 AND 1000000),
    INDEX idx_loyalty_point_grants_customer (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
