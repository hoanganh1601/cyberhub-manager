-- Secondary query indexes for operational lists, lookups, and revenue reporting.

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX idx_customers_full_name
    ON customers (full_name);

CREATE INDEX ix_promotions_eligible
    ON promotions (store_id, is_active, minimum_amount);

CREATE INDEX idx_machines_store_active_status
    ON machines (store_id, is_active, status);

CREATE INDEX idx_usage_sessions_machine_started_at
    ON usage_sessions (machine_id, started_at);

CREATE INDEX idx_usage_sessions_customer_started_at
    ON usage_sessions (customer_id, started_at);

CREATE INDEX idx_usage_sessions_status_started_at
    ON usage_sessions (status, started_at);

CREATE INDEX idx_account_transactions_account_created_at
    ON account_transactions (account_id, created_at);

CREATE INDEX idx_invoices_store_status_created_at
    ON invoices (store_id, status, created_at);

CREATE INDEX idx_invoices_customer_created_at
    ON invoices (customer_id, created_at);

CREATE INDEX idx_menu_categories_store_page
    ON menu_categories (store_id, page, sort_order);

CREATE INDEX idx_menu_items_category_sort
    ON menu_items (category_id, sort_order);

CREATE INDEX idx_menu_orders_hold_expiry
    ON menu_orders (status, reservation_expires_at, id);

CREATE INDEX idx_menu_orders_session_status
    ON menu_orders (session_id, status, created_at);

CREATE INDEX idx_menu_orders_status_paid
    ON menu_orders (status, paid_at);

CREATE INDEX idx_menu_promo_active
    ON menu_promotions (store_id, is_active, starts_at, ends_at);

CREATE INDEX idx_pos_reversal_status_id
    ON pos_order_reversals (status, id);

CREATE INDEX idx_customer_notification_order_created
    ON customer_notification_events (order_id, created_at, id);
