-- Strict 3NF remediation (Phase B): eliminate derived/formula columns (NF-01),
-- eliminate transitive parent-FK columns (NF-02), replace conditional-unique
-- generated columns with 3NF occupancy tables, and normalize table engine/charset
-- metadata (INT-04). Does not modify migrations 001-027.

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- 1. INT-04: Explicit engine/charset/collation on tables from 015, 018, 019
-- ---------------------------------------------------------------------------
ALTER TABLE customer_notification_events
    ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
ALTER TABLE pos_order_reversals
    ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
ALTER TABLE menu_promotions
    ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
ALTER TABLE menu_order_pricing
    ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- 2. NF-01 + NF-04: Immutable loyalty policy versions & normalized invoices
-- ---------------------------------------------------------------------------
CREATE TABLE loyalty_policy_versions (
    version INT UNSIGNED NOT NULL PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    unit_amount BIGINT NOT NULL DEFAULT 10000,
    silver_spend BIGINT NOT NULL DEFAULT 1000000,
    gold_spend BIGINT NOT NULL DEFAULT 3000000,
    platinum_spend BIGINT NOT NULL DEFAULT 5000000,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_loyalty_ver_version CHECK (version >= 1),
    CONSTRAINT chk_loyalty_ver_unit CHECK (unit_amount > 0 AND unit_amount <= 100000000),
    CONSTRAINT chk_loyalty_ver_tiers CHECK (
        silver_spend > 0 AND gold_spend > silver_spend AND platinum_spend > gold_spend
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Backfill active loyalty_settings row first.
INSERT INTO loyalty_policy_versions
    (version, enabled, unit_amount, silver_spend, gold_spend, platinum_spend, created_at)
SELECT version, enabled, unit_amount, silver_spend, gold_spend, platinum_spend, updated_at
FROM loyalty_settings
WHERE id = 1;

-- Backfill any historical invoice loyalty_rule_version not equal to current version.
INSERT IGNORE INTO loyalty_policy_versions
    (version, enabled, unit_amount, silver_spend, gold_spend, platinum_spend, created_at)
SELECT
    i.loyalty_rule_version,
    CASE
        WHEN MAX(CASE WHEN i.loyalty_eligible_amount >= i.loyalty_unit AND i.loyalty_points = 0 THEN 1 ELSE 0 END) = 1
             AND MAX(i.loyalty_points) = 0
        THEN FALSE
        ELSE TRUE
    END,
    MIN(i.loyalty_unit),
    ls.silver_spend,
    ls.gold_spend,
    ls.platinum_spend,
    MIN(i.created_at)
FROM invoices AS i
CROSS JOIN loyalty_settings AS ls
WHERE ls.id = 1
GROUP BY i.loyalty_rule_version, ls.silver_spend, ls.gold_spend, ls.platinum_spend;

ALTER TABLE loyalty_settings
    ADD COLUMN current_version INT UNSIGNED NULL AFTER id;
UPDATE loyalty_settings SET current_version = version WHERE id = 1;
ALTER TABLE loyalty_settings
    MODIFY COLUMN current_version INT UNSIGNED NOT NULL,
    DROP CHECK chk_loyalty_unit,
    DROP CHECK chk_loyalty_tiers,
    DROP COLUMN enabled,
    DROP COLUMN unit_amount,
    DROP COLUMN silver_spend,
    DROP COLUMN gold_spend,
    DROP COLUMN platinum_spend,
    DROP COLUMN version,
    ADD CONSTRAINT fk_loyalty_settings_version
        FOREIGN KEY (current_version) REFERENCES loyalty_policy_versions (version)
        ON UPDATE RESTRICT ON DELETE RESTRICT;

ALTER TABLE invoices
    DROP CHECK chk_invoices_total,
    DROP CHECK chk_invoices_money,
    DROP CHECK chk_invoice_loyalty,
    DROP COLUMN total_amount,
    DROP COLUMN loyalty_eligible_amount,
    DROP COLUMN loyalty_points,
    DROP COLUMN loyalty_unit;

ALTER TABLE invoices
    ADD CONSTRAINT chk_invoices_money CHECK (usage_cost >= 0 AND settlement_amount >= 0),
    ADD CONSTRAINT fk_invoices_loyalty_version
        FOREIGN KEY (loyalty_rule_version) REFERENCES loyalty_policy_versions (version)
        ON UPDATE RESTRICT ON DELETE RESTRICT;

-- ---------------------------------------------------------------------------
-- 3. NF-01: Remove derived/formula columns in accounts, settlements, shifts
-- ---------------------------------------------------------------------------
ALTER TABLE accounts
    DROP COLUMN cash_balance;

ALTER TABLE commercial_settlements
    DROP CHECK chk_commercial_settlements_amount,
    DROP COLUMN net_amount,
    ADD CONSTRAINT chk_commercial_settlements_net_nonnegative
        CHECK (CAST(gross_amount AS SIGNED) + adjustment_amount >= 0);

-- Reconcile legacy CPM seed rows that stored per-impression unit_rate instead of per-1000 contract rate.
UPDATE commercial_settlement_lines AS l
JOIN commercial_settlements AS s ON s.id = l.settlement_id
JOIN commercial_contracts AS ct ON ct.id = s.contract_id
SET l.unit_rate = ct.rate_amount
WHERE l.event_type = 'IMPRESSION'
  AND ct.revenue_model = 'CPM'
  AND FLOOR(l.units * l.unit_rate / 1000) <> l.amount
  AND FLOOR(l.units * ct.rate_amount / 1000) = l.amount;

ALTER TABLE commercial_settlement_lines
    DROP COLUMN amount;

ALTER TABLE cash_shifts
    DROP CHECK chk_cash_shifts_close,
    DROP COLUMN variance;

-- ---------------------------------------------------------------------------
-- 4. NF-01 (Physical 3NF): Replace generated occupancy columns with 3NF tables
-- ---------------------------------------------------------------------------
CREATE TABLE active_usage_sessions (
    session_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    machine_id BIGINT UNSIGNED NOT NULL,
    customer_id BIGINT UNSIGNED NOT NULL,
    CONSTRAINT uq_active_usage_machine UNIQUE (machine_id),
    CONSTRAINT uq_active_usage_customer UNIQUE (customer_id),
    CONSTRAINT fk_active_usage_session
        FOREIGN KEY (session_id) REFERENCES usage_sessions (id)
        ON UPDATE RESTRICT ON DELETE CASCADE,
    CONSTRAINT fk_active_usage_machine
        FOREIGN KEY (machine_id) REFERENCES machines (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_active_usage_customer
        FOREIGN KEY (customer_id) REFERENCES customers (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO active_usage_sessions (session_id, machine_id, customer_id)
SELECT id, machine_id, customer_id
FROM usage_sessions
WHERE status = 'ACTIVE';

ALTER TABLE usage_sessions
    DROP INDEX uq_usage_sessions_active_machine,
    DROP INDEX uq_usage_sessions_active_customer,
    DROP COLUMN active_machine_id,
    DROP COLUMN active_customer_id;

CREATE TRIGGER trg_usage_sessions_ai
AFTER INSERT ON usage_sessions
FOR EACH ROW
INSERT INTO active_usage_sessions (session_id, machine_id, customer_id)
SELECT NEW.id, NEW.machine_id, NEW.customer_id
WHERE NEW.status = 'ACTIVE';

CREATE TRIGGER trg_usage_sessions_au
AFTER UPDATE ON usage_sessions
FOR EACH ROW
DELETE FROM active_usage_sessions
WHERE session_id = OLD.id AND NEW.status <> 'ACTIVE';

CREATE TRIGGER trg_usage_sessions_bu_no_reopen
BEFORE UPDATE ON usage_sessions
FOR EACH ROW
BEGIN
    IF OLD.status <> 'ACTIVE' AND NEW.status = 'ACTIVE' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cannot reopen a closed usage session';
    END IF;
END;

CREATE TABLE active_employee_shifts (
    shift_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    employee_id BIGINT UNSIGNED NOT NULL,
    CONSTRAINT uq_active_shift_employee UNIQUE (employee_id),
    CONSTRAINT fk_active_shift_shift
        FOREIGN KEY (shift_id) REFERENCES cash_shifts (id)
        ON UPDATE RESTRICT ON DELETE CASCADE,
    CONSTRAINT fk_active_shift_employee
        FOREIGN KEY (employee_id) REFERENCES employees (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO active_employee_shifts (shift_id, employee_id)
SELECT id, employee_id
FROM cash_shifts
WHERE status IN ('OPEN', 'PENDING_REVIEW');

ALTER TABLE cash_shifts
    DROP INDEX uq_cash_shifts_active_employee,
    DROP COLUMN active_employee_id;

CREATE TRIGGER trg_cash_shifts_ai
AFTER INSERT ON cash_shifts
FOR EACH ROW
INSERT INTO active_employee_shifts (shift_id, employee_id)
SELECT NEW.id, NEW.employee_id
WHERE NEW.status IN ('OPEN', 'PENDING_REVIEW');

CREATE TRIGGER trg_cash_shifts_au
AFTER UPDATE ON cash_shifts
FOR EACH ROW
DELETE FROM active_employee_shifts
WHERE shift_id = OLD.id AND NEW.status NOT IN ('OPEN', 'PENDING_REVIEW');

CREATE TRIGGER trg_cash_shifts_bu_no_reopen
BEFORE UPDATE ON cash_shifts
FOR EACH ROW
BEGIN
    IF OLD.status = 'CLOSED' AND NEW.status <> 'CLOSED' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cannot reopen a closed cash shift';
    END IF;
END;

-- ---------------------------------------------------------------------------
-- 5. NF-02: Remove transitive parent-FK columns across operational tables
-- ---------------------------------------------------------------------------
ALTER TABLE cash_shift_entries
    DROP FOREIGN KEY fk_cash_entries_store,
    DROP COLUMN store_id;

ALTER TABLE commercial_events
    DROP FOREIGN KEY fk_commercial_events_campaign,
    DROP INDEX idx_commercial_events_campaign,
    DROP COLUMN campaign_id,
    ADD INDEX idx_commercial_events_placement_time (placement_id, event_type, accepted, occurred_at);

ALTER TABLE goods_receipts
    DROP FOREIGN KEY fk_goods_receipts_store,
    DROP COLUMN store_id;

ALTER TABLE supplier_payables
    DROP FOREIGN KEY fk_supplier_payables_supplier,
    DROP FOREIGN KEY fk_supplier_payables_store,
    DROP INDEX idx_supplier_payables_due,
    DROP COLUMN supplier_id,
    DROP COLUMN store_id,
    ADD INDEX idx_supplier_payables_status_due (status, due_date);

ALTER TABLE purchase_orders
    DROP FOREIGN KEY fk_purchase_orders_store,
    DROP COLUMN store_id;

ALTER TABLE pos_order_reversals
    DROP FOREIGN KEY fk_pos_reversal_store,
    DROP INDEX idx_pos_reversal_store_status,
    DROP COLUMN store_id,
    ADD INDEX idx_pos_reversal_status (status, id);

ALTER TABLE inventory_movements
    DROP FOREIGN KEY fk_inventory_movements_ingredient,
    DROP INDEX idx_inventory_movements_store_time,
    DROP COLUMN store_id;

ALTER TABLE inventory_movements
    ADD CONSTRAINT fk_inventory_movements_ingredient
        FOREIGN KEY (ingredient_id) REFERENCES inventory_ingredients (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    ADD INDEX idx_inventory_movements_time (created_at, id);

ALTER TABLE inventory_counts
    DROP FOREIGN KEY fk_inventory_counts_ingredient,
    DROP INDEX idx_inventory_counts_store_status,
    DROP COLUMN store_id;

ALTER TABLE inventory_counts
    ADD CONSTRAINT fk_inventory_counts_ingredient
        FOREIGN KEY (ingredient_id) REFERENCES inventory_ingredients (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    ADD INDEX idx_inventory_counts_status (status, created_at, id);

ALTER TABLE machine_incidents
    DROP FOREIGN KEY fk_incidents_store,
    DROP INDEX idx_incidents_store_status,
    DROP COLUMN store_id,
    ADD INDEX idx_incidents_status_time (status, reported_at, id);

ALTER TABLE menu_orders
    DROP FOREIGN KEY fk_menu_orders_store,
    DROP FOREIGN KEY fk_menu_orders_machine,
    DROP FOREIGN KEY fk_menu_orders_account,
    DROP INDEX idx_menu_orders_store_status,
    DROP INDEX idx_menu_orders_account,
    DROP INDEX idx_menu_orders_paid_at,
    DROP COLUMN store_id,
    DROP COLUMN machine_id,
    DROP COLUMN account_id,
    ADD INDEX idx_menu_orders_session (session_id, status, created_at),
    ADD INDEX idx_menu_orders_status_created (status, created_at),
    ADD INDEX idx_menu_orders_paid_at (paid_at);

ALTER TABLE menu_items
    DROP FOREIGN KEY fk_menu_items_store,
    DROP INDEX uq_menu_items_store_name,
    DROP INDEX idx_menu_items_store_category,
    DROP COLUMN store_id,
    ADD CONSTRAINT uq_menu_items_category_name UNIQUE (category_id, name),
    ADD INDEX idx_menu_items_category_sort (category_id, sort_order);

-- ---------------------------------------------------------------------------
-- 6. Compatibility & reporting read views over normalized 3NF base tables
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_accounts AS
SELECT
    id, code, customer_id, username, password_hash, balance, bonus_balance,
    (balance - bonus_balance) AS cash_balance,
    status, auth_version, web_login_enabled, email_verified_at, created_at, updated_at
FROM accounts;

CREATE OR REPLACE VIEW v_invoices AS
SELECT
    i.id, i.code, i.session_id, i.customer_id, i.employee_id, i.store_id,
    i.usage_cost, i.settlement_amount, i.usage_cost AS total_amount,
    i.bonus_used,
    GREATEST(0, i.usage_cost - i.bonus_used) AS loyalty_eligible_amount,
    CASE
        WHEN v.enabled THEN FLOOR(GREATEST(0, i.usage_cost - i.bonus_used) / v.unit_amount)
        ELSE 0
    END AS loyalty_points,
    v.unit_amount AS loyalty_unit,
    i.loyalty_rule_version,
    i.status, i.created_at
FROM invoices AS i
JOIN loyalty_policy_versions AS v ON v.version = i.loyalty_rule_version;

CREATE OR REPLACE VIEW v_cash_shifts AS
SELECT
    id, code, store_id, employee_id, status, opening_cash,
    expected_cash, counted_cash,
    CASE
        WHEN counted_cash IS NOT NULL AND expected_cash IS NOT NULL
        THEN CAST(counted_cash AS SIGNED) - CAST(expected_cash AS SIGNED)
        ELSE NULL
    END AS variance,
    opened_at, submitted_at, closed_at, reviewed_by, review_note
FROM cash_shifts;

CREATE OR REPLACE VIEW v_cash_shift_entries AS
SELECT
    e.id, e.shift_id, s.store_id, e.employee_id, e.kind, e.payment_method,
    e.amount, e.source_type, e.source_id, e.note, e.created_at
FROM cash_shift_entries AS e
JOIN cash_shifts AS s ON s.id = e.shift_id;

CREATE OR REPLACE VIEW v_commercial_events AS
SELECT
    e.id, e.placement_id, pl.campaign_id, e.play_session_id, e.account_id,
    e.event_type, e.event_key, e.provider_event_id, e.verification_method,
    e.accepted, e.occurred_at, e.verified_at, e.payload_digest, e.created_at
FROM commercial_events AS e
JOIN commercial_placements AS pl ON pl.id = e.placement_id;

CREATE OR REPLACE VIEW v_commercial_settlements AS
SELECT
    id, contract_id, period_start, period_end, gross_amount,
    adjustment_amount, adjustment_reason,
    (CAST(gross_amount AS SIGNED) + adjustment_amount) AS net_amount,
    status, generated_by, reviewed_by, reviewed_at, paid_at, created_at
FROM commercial_settlements;

CREATE OR REPLACE VIEW v_commercial_settlement_lines AS
SELECT
    settlement_id, placement_id, event_type, units, unit_rate,
    CASE event_type
        WHEN 'IMPRESSION' THEN FLOOR(units * unit_rate / 1000)
        WHEN 'FIXED' THEN CASE WHEN units > 0 THEN unit_rate ELSE 0 END
        ELSE units * unit_rate
    END AS amount
FROM commercial_settlement_lines;

CREATE OR REPLACE VIEW v_menu_items AS
SELECT
    i.id, c.store_id, i.category_id, i.name, i.description, i.price,
    i.sort_order, i.is_visible, i.is_available, i.is_stock_tracked,
    i.created_at, i.updated_at
FROM menu_items AS i
JOIN menu_categories AS c ON c.id = i.category_id;

CREATE OR REPLACE VIEW v_menu_orders AS
SELECT
    o.id, o.code, m.store_id, a.id AS account_id, o.session_id, u.machine_id,
    o.note, o.total_amount, o.status, o.handled_by, o.payment_method,
    o.paid_at, o.paid_by, o.cancel_reason, o.created_at,
    o.reservation_expires_at, o.updated_at
FROM menu_orders AS o
JOIN usage_sessions AS u ON u.id = o.session_id
JOIN machines AS m ON m.id = u.machine_id
JOIN accounts AS a ON a.customer_id = u.customer_id;

CREATE OR REPLACE VIEW v_pos_order_reversals AS
SELECT
    r.id, r.order_id, m.store_id, r.requested_by, r.reason, r.disposition,
    r.status, r.decided_by, r.decided_at, r.refund_amount,
    r.refund_method, r.refund_reference, r.created_at
FROM pos_order_reversals AS r
JOIN menu_orders AS o ON o.id = r.order_id
JOIN usage_sessions AS u ON u.id = o.session_id
JOIN machines AS m ON m.id = u.machine_id;

CREATE OR REPLACE VIEW v_inventory_movements AS
SELECT
    mv.id, ing.store_id, mv.ingredient_id, mv.order_id, mv.employee_id,
    mv.account_id, mv.kind, mv.quantity, mv.on_hand_delta, mv.reserved_delta,
    mv.idempotency_key, mv.reference_code, mv.note, mv.created_at
FROM inventory_movements AS mv
JOIN inventory_ingredients AS ing ON ing.id = mv.ingredient_id;

CREATE OR REPLACE VIEW v_inventory_counts AS
SELECT
    ic.id, ing.store_id, ic.ingredient_id, ic.request_id, ic.expected_on_hand,
    ic.expected_reserved, ic.expected_movement_id, ic.counted_on_hand,
    ic.proposed_by, ic.decided_by, ic.status, ic.reason, ic.created_at, ic.decided_at
FROM inventory_counts AS ic
JOIN inventory_ingredients AS ing ON ing.id = ic.ingredient_id;

CREATE OR REPLACE VIEW v_machine_incidents AS
SELECT
    inc.id, inc.code, m.store_id, inc.machine_id, inc.reported_by, inc.assigned_to,
    inc.severity, inc.status, inc.title, inc.description, inc.resolution,
    inc.labor_cost, inc.parts_cost, inc.reported_at, inc.started_at,
    inc.completed_at, inc.verified_at, inc.verified_by
FROM machine_incidents AS inc
JOIN machines AS m ON m.id = inc.machine_id;

CREATE OR REPLACE VIEW v_purchase_orders AS
SELECT
    po.id, po.code, pr.store_id, po.request_id, po.supplier_id, po.created_by,
    po.status, po.ordered_at, po.expected_at, po.total_amount
FROM purchase_orders AS po
JOIN purchase_requests AS pr ON pr.id = po.request_id;

CREATE OR REPLACE VIEW v_goods_receipts AS
SELECT
    gr.id, gr.code, gr.order_id, pr.store_id, gr.received_by, gr.request_id,
    gr.note, gr.received_at, gr.accepted_amount
FROM goods_receipts AS gr
JOIN purchase_orders AS po ON po.id = gr.order_id
JOIN purchase_requests AS pr ON pr.id = po.request_id;

CREATE OR REPLACE VIEW v_supplier_payables AS
SELECT
    sp.id, sp.receipt_id, po.supplier_id, pr.store_id, sp.amount, sp.paid_amount,
    sp.due_date, sp.status, sp.paid_at, sp.paid_by, sp.payment_method
FROM supplier_payables AS sp
JOIN goods_receipts AS gr ON gr.id = sp.receipt_id
JOIN purchase_orders AS po ON po.id = gr.order_id
JOIN purchase_requests AS pr ON pr.id = po.request_id;
