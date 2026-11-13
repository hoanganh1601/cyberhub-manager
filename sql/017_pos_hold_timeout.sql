-- New orders hold stock for a bounded time. Old rows remain exempt.
ALTER TABLE menu_orders ADD COLUMN reservation_expires_at DATETIME NULL AFTER created_at;
CREATE INDEX idx_menu_orders_hold_expiry ON menu_orders(status, reservation_expires_at, id);
ALTER TABLE menu_orders DROP CHECK chk_menu_orders_handled;
ALTER TABLE menu_orders ADD CONSTRAINT chk_menu_orders_handled CHECK (
    (status = 'NEW' AND handled_by IS NULL)
    OR (status = 'CANCELLED' AND handled_by IS NULL AND cancel_reason = 'AUTO_EXPIRED')
    OR (status <> 'NEW' AND handled_by IS NOT NULL)
);
