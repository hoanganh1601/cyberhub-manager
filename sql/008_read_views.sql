-- Read views projecting derived balances, invoice totals, and joined parent scope fields.

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE OR REPLACE VIEW v_employees AS
SELECT
    e.id,
    e.profile_id,
    p.code,
    p.home_store_id AS store_id,
    p.full_name,
    p.employment_status,
    e.username,
    e.password_hash,
    e.role,
    e.status,
    e.auth_version,
    e.must_change_password,
    e.password_changed_at,
    e.created_at,
    e.updated_at
FROM employees AS e
JOIN employee_profiles AS p ON p.id = e.profile_id;

CREATE OR REPLACE VIEW v_accounts AS
SELECT
    a.id,
    a.code,
    a.customer_id,
    a.username,
    a.password_hash,
    a.balance,
    a.bonus_balance,
    (a.balance - a.bonus_balance) AS cash_balance,
    a.status,
    a.auth_version,
    a.web_login_enabled,
    a.created_at,
    a.updated_at
FROM accounts AS a;

CREATE OR REPLACE VIEW v_invoices AS
SELECT
    i.id,
    i.code,
    i.session_id,
    i.customer_id,
    i.employee_id,
    i.store_id,
    i.usage_cost,
    i.settlement_amount,
    i.usage_cost AS total_amount,
    i.bonus_used,
    i.status,
    i.created_at
FROM invoices AS i;

CREATE OR REPLACE VIEW v_menu_items AS
SELECT
    i.id,
    c.store_id,
    i.category_id,
    i.name,
    i.description,
    i.price,
    i.sort_order,
    i.is_visible,
    i.is_available,
    i.created_at,
    i.updated_at
FROM menu_items AS i
JOIN menu_categories AS c ON c.id = i.category_id;

CREATE OR REPLACE VIEW v_menu_orders AS
SELECT
    o.id,
    o.code,
    m.store_id,
    a.id AS account_id,
    o.session_id,
    u.machine_id,
    o.note,
    o.total_amount,
    o.status,
    o.handled_by,
    o.payment_method,
    o.paid_at,
    o.paid_by,
    o.created_at,
    o.reservation_expires_at,
    o.updated_at,
    o.cancel_reason
FROM menu_orders AS o
JOIN usage_sessions AS u ON u.id = o.session_id
JOIN machines AS m ON m.id = u.machine_id
JOIN accounts AS a ON a.customer_id = u.customer_id;

CREATE OR REPLACE VIEW v_menu_order_pricing AS
SELECT
    p.order_id,
    p.promotion_version_id,
    mv.promotion_id,
    mv.code AS promotion_code,
    mv.kind AS promotion_kind,
    p.discount_amount,
    GREATEST(0, o.total_amount - LEAST(o.total_amount, p.discount_amount)) AS final_amount
FROM menu_order_pricing AS p
JOIN menu_orders AS o ON o.id = p.order_id
LEFT JOIN menu_promotion_versions AS mv ON mv.id = p.promotion_version_id;

CREATE OR REPLACE VIEW v_pos_order_reversals AS
SELECT
    r.id,
    r.order_id,
    m.store_id,
    r.requested_by,
    r.reason,
    r.disposition,
    r.status,
    r.decided_by,
    r.decided_at,
    r.refund_amount,
    r.refund_method,
    r.refund_reference,
    r.created_at
FROM pos_order_reversals AS r
JOIN menu_orders AS o ON o.id = r.order_id
JOIN usage_sessions AS u ON u.id = o.session_id
JOIN machines AS m ON m.id = u.machine_id;

CREATE OR REPLACE VIEW v_customer_notification_events AS
SELECT
    e.id,
    a.id AS account_id,
    m.store_id,
    e.order_id,
    o.code AS order_code,
    e.order_status,
    e.created_at
FROM customer_notification_events AS e
JOIN menu_orders AS o ON o.id = e.order_id
JOIN usage_sessions AS u ON u.id = o.session_id
JOIN machines AS m ON m.id = u.machine_id
JOIN accounts AS a ON a.customer_id = u.customer_id;
