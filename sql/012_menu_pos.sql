-- Đợt 5: POS menu. Đơn hàng đi qua tiếp nhận, chuẩn bị, phục vụ và thanh toán.
-- Thanh toán đồ ăn ghi nhận tại quầy; không trừ ví giờ chơi của khách.

ALTER TABLE menu_orders
    DROP CHECK chk_menu_orders_status,
    ADD COLUMN payment_method VARCHAR(10) NULL AFTER handled_by,
    ADD COLUMN paid_at DATETIME NULL AFTER payment_method,
    ADD COLUMN paid_by BIGINT UNSIGNED NULL AFTER paid_at,
    ADD CONSTRAINT fk_menu_orders_paid_by FOREIGN KEY (paid_by)
        REFERENCES employees (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    ADD CONSTRAINT chk_menu_orders_status CHECK (status IN ('NEW', 'PREPARING', 'SERVED', 'PAID', 'CANCELLED')),
    ADD CONSTRAINT chk_menu_orders_payment CHECK (
        (status = 'PAID' AND payment_method IN ('CASH', 'TRANSFER') AND paid_at IS NOT NULL AND paid_by IS NOT NULL)
        OR (status <> 'PAID' AND payment_method IS NULL AND paid_at IS NULL AND paid_by IS NULL)
    );

CREATE INDEX idx_menu_orders_paid_at ON menu_orders (store_id, paid_at);
