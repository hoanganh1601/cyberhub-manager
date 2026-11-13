-- Lịch sử thay đổi khuyến mãi POS: ai bật/tắt/sửa, lúc nào, giá trị cũ và mới. Chỉ thêm, không sửa/xóa.
-- Giá của đơn đã đặt vẫn nằm trong menu_order_pricing (bản chụp bất biến) nên sửa ưu đãi không đổi đơn cũ.
CREATE TABLE menu_promotion_changes (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    promotion_id BIGINT UNSIGNED NOT NULL,
    employee_id BIGINT UNSIGNED NOT NULL,
    action VARCHAR(10) NOT NULL,
    changes_json JSON NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_menu_promo_changes_promotion (promotion_id, created_at, id),
    CONSTRAINT fk_menu_promo_changes_promotion FOREIGN KEY (promotion_id) REFERENCES menu_promotions (id),
    CONSTRAINT fk_menu_promo_changes_employee FOREIGN KEY (employee_id) REFERENCES employees (id),
    CONSTRAINT chk_menu_promo_changes_action CHECK (action IN ('CREATE', 'UPDATE', 'ENABLE', 'DISABLE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
