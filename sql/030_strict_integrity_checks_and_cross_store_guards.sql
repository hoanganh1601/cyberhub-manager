-- Strict DB integrity remediation (Phase D): NULL-safe CHECK constraints
-- closing MySQL UNKNOWN loopholes (INT-02), Separation-of-Duties constraints,
-- and cross-store / cross-owner guards enforced directly in MySQL (INT-01).

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- 1. INT-02: NULL-safe CHECK constraints & full state lifecycle enforcement
-- ---------------------------------------------------------------------------

-- menu_orders: require payment_method IS NOT NULL explicitly (avoid UNKNOWN).
ALTER TABLE menu_orders
    DROP CHECK chk_menu_orders_payment;

ALTER TABLE menu_orders
    ADD CONSTRAINT chk_menu_orders_payment CHECK (
        (status IN ('PAID', 'REFUNDED')
            AND payment_method IS NOT NULL
            AND payment_method IN ('CASH', 'TRANSFER')
            AND paid_at IS NOT NULL
            AND paid_by IS NOT NULL)
        OR (status NOT IN ('PAID', 'REFUNDED')
            AND payment_method IS NULL
            AND paid_at IS NULL
            AND paid_by IS NULL)
    );

-- inventory_counts: enforce decision metadata, time order, and SoD.
ALTER TABLE inventory_counts
    ADD CONSTRAINT chk_inventory_counts_decision CHECK (
        (status = 'PENDING' AND decided_by IS NULL AND decided_at IS NULL)
        OR (status IN ('APPROVED', 'REJECTED')
            AND decided_by IS NOT NULL
            AND decided_at IS NOT NULL
            AND decided_by <> proposed_by
            AND decided_at >= created_at)
    );

-- supplier_payables: enforce complete UNPAID/PAID state combinations.
ALTER TABLE supplier_payables
    ADD CONSTRAINT chk_supplier_payables_state CHECK (
        (status = 'UNPAID'
            AND paid_amount = 0
            AND paid_at IS NULL
            AND paid_by IS NULL
            AND payment_method IS NULL)
        OR (status = 'PAID'
            AND paid_amount = amount
            AND paid_at IS NOT NULL
            AND paid_by IS NOT NULL
            AND payment_method IS NOT NULL
            AND payment_method IN ('CASH', 'TRANSFER'))
    );

-- machine_incidents: enforce status/timestamp/assignee/verifier invariants.
ALTER TABLE machine_incidents
    ADD CONSTRAINT chk_incidents_lifecycle CHECK (
        (
            (status = 'REPORTED' AND started_at IS NULL AND completed_at IS NULL AND verified_at IS NULL AND verified_by IS NULL)
            OR (status = 'ASSIGNED' AND assigned_to IS NOT NULL AND completed_at IS NULL AND verified_at IS NULL AND verified_by IS NULL)
            OR (status = 'IN_PROGRESS' AND started_at IS NOT NULL AND completed_at IS NULL AND verified_at IS NULL AND verified_by IS NULL)
            OR (status = 'WAITING_PARTS' AND completed_at IS NULL AND verified_at IS NULL AND verified_by IS NULL)
            OR (status = 'COMPLETED' AND completed_at IS NOT NULL AND resolution IS NOT NULL AND CHAR_LENGTH(TRIM(resolution)) > 0 AND verified_at IS NULL AND verified_by IS NULL)
            OR (status = 'VERIFIED' AND completed_at IS NOT NULL AND resolution IS NOT NULL AND CHAR_LENGTH(TRIM(resolution)) > 0 AND verified_at IS NOT NULL AND verified_by IS NOT NULL AND (assigned_to IS NULL OR verified_by <> assigned_to))
            OR (status = 'CANCELLED' AND verified_at IS NULL AND verified_by IS NULL)
        )
        AND (started_at IS NULL OR started_at >= reported_at)
        AND (completed_at IS NULL OR completed_at >= reported_at)
        AND (verified_at IS NULL OR (completed_at IS NOT NULL AND verified_at >= completed_at))
    );

-- cash_shifts: enforce NULL-safe close lifecycle, timestamps, and reviewer SoD.
ALTER TABLE cash_shifts
    ADD CONSTRAINT chk_cash_shifts_close CHECK (
        (
            (status = 'OPEN'
                AND expected_cash IS NULL
                AND counted_cash IS NULL
                AND submitted_at IS NULL
                AND closed_at IS NULL
                AND reviewed_by IS NULL
                AND review_note IS NULL)
            OR (status = 'PENDING_REVIEW'
                AND expected_cash IS NOT NULL
                AND counted_cash IS NOT NULL
                AND submitted_at IS NOT NULL
                AND closed_at IS NULL
                AND reviewed_by IS NULL)
            OR (status = 'CLOSED'
                AND expected_cash IS NOT NULL
                AND counted_cash IS NOT NULL
                AND submitted_at IS NOT NULL
                AND closed_at IS NOT NULL
                AND (
                    (reviewed_by IS NULL AND review_note IS NULL)
                    OR (reviewed_by IS NOT NULL
                        AND reviewed_by <> employee_id
                        AND review_note IS NOT NULL
                        AND CHAR_LENGTH(TRIM(review_note)) > 0)
                ))
        )
        AND (submitted_at IS NULL OR submitted_at >= opened_at)
        AND (closed_at IS NULL OR (submitted_at IS NOT NULL AND closed_at >= submitted_at))
    );

-- commercial_settlements: fix NULL adjustment_reason loophole & add lifecycle CHECK.
ALTER TABLE commercial_settlements
    DROP CHECK chk_commercial_settlements_adjustment;

ALTER TABLE commercial_settlements
    ADD CONSTRAINT chk_commercial_settlements_adjustment CHECK (
        (adjustment_amount = 0 AND adjustment_reason IS NULL)
        OR (adjustment_amount <> 0
            AND adjustment_reason IS NOT NULL
            AND CHAR_LENGTH(TRIM(adjustment_reason)) >= 5)
    ),
    ADD CONSTRAINT chk_commercial_settlements_lifecycle CHECK (
        (status = 'DRAFT' AND reviewed_by IS NULL AND reviewed_at IS NULL AND paid_at IS NULL)
        OR (status = 'APPROVED'
            AND reviewed_by IS NOT NULL
            AND reviewed_at IS NOT NULL
            AND reviewed_by <> generated_by
            AND paid_at IS NULL)
        OR (status = 'PAID'
            AND reviewed_by IS NOT NULL
            AND reviewed_at IS NOT NULL
            AND reviewed_by <> generated_by
            AND paid_at IS NOT NULL
            AND paid_at >= reviewed_at)
        OR (status = 'VOID' AND paid_at IS NULL)
    );

-- commercial_contracts: creator cannot self-approve (enforced via BI/BU triggers so
-- pre-existing historical rows are preserved unmodified while all new/updated rows obey SoD).
CREATE TRIGGER trg_commercial_contracts_sod_bi
BEFORE INSERT ON commercial_contracts
FOR EACH ROW
BEGIN
    IF NEW.approved_by IS NOT NULL AND NEW.approved_by = NEW.created_by THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Commercial contract creator cannot self-approve';
    END IF;
END;

CREATE TRIGGER trg_commercial_contracts_sod_bu
BEFORE UPDATE ON commercial_contracts
FOR EACH ROW
BEGIN
    IF NEW.approved_by IS NOT NULL AND NEW.approved_by = NEW.created_by THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Commercial contract creator cannot self-approve';
    END IF;
END;

-- pos_order_reversals: requester cannot self-approve; NULL-safe refund method.
ALTER TABLE pos_order_reversals
    ADD CONSTRAINT chk_pos_reversal_sod CHECK (
        decided_by IS NULL OR decided_by <> requested_by
    ),
    ADD CONSTRAINT chk_pos_reversal_refund CHECK (
        (status <> 'APPROVED' AND refund_amount = 0 AND refund_method IS NULL AND refund_reference IS NULL)
        OR (status = 'APPROVED' AND refund_amount = 0 AND refund_method IS NULL AND refund_reference IS NULL)
        OR (status = 'APPROVED' AND refund_amount > 0
            AND refund_method IS NOT NULL
            AND refund_method IN ('CASH', 'TRANSFER'))
    );

-- customer_vouchers: ensure used_store_id IS NULL when not USED and revoked_reason matches REVOKED.
ALTER TABLE customer_vouchers
    DROP CHECK chk_customer_vouchers_used;

ALTER TABLE customer_vouchers
    ADD CONSTRAINT chk_customer_vouchers_used CHECK (
        (status = 'USED'
            AND used_at IS NOT NULL
            AND used_by IS NOT NULL
            AND used_store_id IS NOT NULL)
        OR (status <> 'USED'
            AND used_at IS NULL
            AND used_by IS NULL
            AND used_store_id IS NULL
            AND used_order_id IS NULL)
    ),
    ADD CONSTRAINT chk_customer_vouchers_revoked CHECK (
        (status = 'REVOKED' AND revoked_reason IS NOT NULL AND CHAR_LENGTH(TRIM(revoked_reason)) > 0)
        OR (status <> 'REVOKED' AND revoked_reason IS NULL)
    );

-- customer_email_tokens: enforce expiry & usage timestamp order.
ALTER TABLE customer_email_tokens
    ADD CONSTRAINT chk_customer_email_token_times CHECK (
        expires_at > created_at AND (used_at IS NULL OR used_at >= created_at)
    );

-- purchase_requests: requester cannot self-approve.
ALTER TABLE purchase_requests
    ADD CONSTRAINT chk_purchase_requests_sod CHECK (
        decided_by IS NULL OR decided_by <> requested_by
    );

-- ---------------------------------------------------------------------------
-- 2. INT-01: Cross-store & Cross-owner invariants enforced in MySQL triggers
-- ---------------------------------------------------------------------------

-- menu_items: unique item name across all categories of the same store.
CREATE TRIGGER trg_menu_items_bi
BEFORE INSERT ON menu_items
FOR EACH ROW
BEGIN
    DECLARE v_store_id BIGINT UNSIGNED;
    SELECT store_id INTO v_store_id FROM menu_categories WHERE id = NEW.category_id;
    IF EXISTS (
        SELECT 1
        FROM menu_items AS mi
        JOIN menu_categories AS mc ON mc.id = mi.category_id
        WHERE mc.store_id = v_store_id AND mi.name = NEW.name
    ) THEN
        SIGNAL SQLSTATE '23000' SET MESSAGE_TEXT = 'Duplicate menu item name in store';
    END IF;
END;

CREATE TRIGGER trg_menu_items_bu
BEFORE UPDATE ON menu_items
FOR EACH ROW
BEGIN
    DECLARE v_store_id BIGINT UNSIGNED;
    SELECT store_id INTO v_store_id FROM menu_categories WHERE id = NEW.category_id;
    IF EXISTS (
        SELECT 1
        FROM menu_items AS mi
        JOIN menu_categories AS mc ON mc.id = mi.category_id
        WHERE mc.store_id = v_store_id AND mi.name = NEW.name AND mi.id <> OLD.id
    ) THEN
        SIGNAL SQLSTATE '23000' SET MESSAGE_TEXT = 'Duplicate menu item name in store';
    END IF;
END;

-- menu_item_recipes: item and ingredient must belong to the same store.
CREATE TRIGGER trg_menu_item_recipes_bi
BEFORE INSERT ON menu_item_recipes
FOR EACH ROW
BEGIN
    DECLARE v_item_store BIGINT UNSIGNED;
    DECLARE v_ing_store BIGINT UNSIGNED;
    SELECT mc.store_id INTO v_item_store
    FROM menu_items AS mi
    JOIN menu_categories AS mc ON mc.id = mi.category_id
    WHERE mi.id = NEW.item_id;
    SELECT store_id INTO v_ing_store
    FROM inventory_ingredients WHERE id = NEW.ingredient_id;
    IF v_item_store IS NULL OR v_ing_store IS NULL OR v_item_store <> v_ing_store THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Recipe item and ingredient must belong to the same store';
    END IF;
END;

CREATE TRIGGER trg_menu_item_recipes_bu
BEFORE UPDATE ON menu_item_recipes
FOR EACH ROW
BEGIN
    DECLARE v_item_store BIGINT UNSIGNED;
    DECLARE v_ing_store BIGINT UNSIGNED;
    SELECT mc.store_id INTO v_item_store
    FROM menu_items AS mi
    JOIN menu_categories AS mc ON mc.id = mi.category_id
    WHERE mi.id = NEW.item_id;
    SELECT store_id INTO v_ing_store
    FROM inventory_ingredients WHERE id = NEW.ingredient_id;
    IF v_item_store IS NULL OR v_ing_store IS NULL OR v_item_store <> v_ing_store THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Recipe item and ingredient must belong to the same store';
    END IF;
END;

-- menu_promotions: item_id (if set) must belong to menu_promotions.store_id.
CREATE TRIGGER trg_menu_promotions_bi
BEFORE INSERT ON menu_promotions
FOR EACH ROW
BEGIN
    DECLARE v_item_store BIGINT UNSIGNED;
    IF NEW.item_id IS NOT NULL THEN
        SELECT mc.store_id INTO v_item_store
        FROM menu_items AS mi
        JOIN menu_categories AS mc ON mc.id = mi.category_id
        WHERE mi.id = NEW.item_id;
        IF v_item_store IS NULL OR v_item_store <> NEW.store_id THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Menu promotion item must belong to the same store';
        END IF;
    END IF;
END;

CREATE TRIGGER trg_menu_promotions_bu
BEFORE UPDATE ON menu_promotions
FOR EACH ROW
BEGIN
    DECLARE v_item_store BIGINT UNSIGNED;
    IF NEW.item_id IS NOT NULL THEN
        SELECT mc.store_id INTO v_item_store
        FROM menu_items AS mi
        JOIN menu_categories AS mc ON mc.id = mi.category_id
        WHERE mi.id = NEW.item_id;
        IF v_item_store IS NULL OR v_item_store <> NEW.store_id THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Menu promotion item must belong to the same store';
        END IF;
    END IF;
END;

-- purchase_request_lines: ingredient store must match purchase_requests.store_id.
CREATE TRIGGER trg_purchase_request_lines_bi
BEFORE INSERT ON purchase_request_lines
FOR EACH ROW
BEGIN
    DECLARE v_req_store BIGINT UNSIGNED;
    DECLARE v_ing_store BIGINT UNSIGNED;
    SELECT store_id INTO v_req_store FROM purchase_requests WHERE id = NEW.request_id;
    SELECT store_id INTO v_ing_store FROM inventory_ingredients WHERE id = NEW.ingredient_id;
    IF v_req_store IS NULL OR v_ing_store IS NULL OR v_req_store <> v_ing_store THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Purchase request ingredient must belong to the same store';
    END IF;
END;

-- purchase_orders: supplier store must match purchase_requests.store_id.
CREATE TRIGGER trg_purchase_orders_bi
BEFORE INSERT ON purchase_orders
FOR EACH ROW
BEGIN
    DECLARE v_req_store BIGINT UNSIGNED;
    DECLARE v_sup_store BIGINT UNSIGNED;
    SELECT store_id INTO v_req_store FROM purchase_requests WHERE id = NEW.request_id;
    SELECT store_id INTO v_sup_store FROM suppliers WHERE id = NEW.supplier_id;
    IF v_req_store IS NULL OR v_sup_store IS NULL OR v_req_store <> v_sup_store THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Purchase order supplier must belong to the request store';
    END IF;
END;

CREATE TRIGGER trg_purchase_orders_bu
BEFORE UPDATE ON purchase_orders
FOR EACH ROW
BEGIN
    DECLARE v_req_store BIGINT UNSIGNED;
    DECLARE v_sup_store BIGINT UNSIGNED;
    SELECT store_id INTO v_req_store FROM purchase_requests WHERE id = NEW.request_id;
    SELECT store_id INTO v_sup_store FROM suppliers WHERE id = NEW.supplier_id;
    IF v_req_store IS NULL OR v_sup_store IS NULL OR v_req_store <> v_sup_store THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Purchase order supplier must belong to the request store';
    END IF;
END;

-- purchase_order_lines: ingredient store must match PO's store.
CREATE TRIGGER trg_purchase_order_lines_bi
BEFORE INSERT ON purchase_order_lines
FOR EACH ROW
BEGIN
    DECLARE v_po_store BIGINT UNSIGNED;
    DECLARE v_ing_store BIGINT UNSIGNED;
    SELECT pr.store_id INTO v_po_store
    FROM purchase_orders AS po
    JOIN purchase_requests AS pr ON pr.id = po.request_id
    WHERE po.id = NEW.order_id;
    SELECT store_id INTO v_ing_store FROM inventory_ingredients WHERE id = NEW.ingredient_id;
    IF v_po_store IS NULL OR v_ing_store IS NULL OR v_po_store <> v_ing_store THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Purchase order ingredient must belong to the order store';
    END IF;
END;

-- goods_receipt_lines: ingredient store must match receipt's store.
CREATE TRIGGER trg_goods_receipt_lines_bi
BEFORE INSERT ON goods_receipt_lines
FOR EACH ROW
BEGIN
    DECLARE v_gr_store BIGINT UNSIGNED;
    DECLARE v_ing_store BIGINT UNSIGNED;
    SELECT pr.store_id INTO v_gr_store
    FROM goods_receipts AS gr
    JOIN purchase_orders AS po ON po.id = gr.order_id
    JOIN purchase_requests AS pr ON pr.id = po.request_id
    WHERE gr.id = NEW.receipt_id;
    SELECT store_id INTO v_ing_store FROM inventory_ingredients WHERE id = NEW.ingredient_id;
    IF v_gr_store IS NULL OR v_ing_store IS NULL OR v_gr_store <> v_ing_store THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Goods receipt ingredient must belong to the receipt store';
    END IF;
END;

-- invoices: customer_id and store_id must match the referenced usage_session.
CREATE TRIGGER trg_invoices_bi
BEFORE INSERT ON invoices
FOR EACH ROW
BEGIN
    DECLARE v_cust_id BIGINT UNSIGNED;
    DECLARE v_store_id BIGINT UNSIGNED;
    SELECT u.customer_id, m.store_id INTO v_cust_id, v_store_id
    FROM usage_sessions AS u
    JOIN machines AS m ON m.id = u.machine_id
    WHERE u.id = NEW.session_id;
    IF v_cust_id IS NULL OR v_cust_id <> NEW.customer_id OR v_store_id <> NEW.store_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invoice customer and store must match the usage session';
    END IF;
END;

CREATE TRIGGER trg_invoices_bu
BEFORE UPDATE ON invoices
FOR EACH ROW
BEGIN
    DECLARE v_cust_id BIGINT UNSIGNED;
    DECLARE v_store_id BIGINT UNSIGNED;
    SELECT u.customer_id, m.store_id INTO v_cust_id, v_store_id
    FROM usage_sessions AS u
    JOIN machines AS m ON m.id = u.machine_id
    WHERE u.id = NEW.session_id;
    IF v_cust_id IS NULL OR v_cust_id <> NEW.customer_id OR v_store_id <> NEW.store_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invoice customer and store must match the usage session';
    END IF;
END;

-- commercial_reward_grants: account_id must match commercial_events.account_id.
CREATE TRIGGER trg_commercial_reward_grants_bi
BEFORE INSERT ON commercial_reward_grants
FOR EACH ROW
BEGIN
    DECLARE v_acc_id BIGINT UNSIGNED;
    SELECT account_id INTO v_acc_id FROM commercial_events WHERE id = NEW.event_id;
    IF v_acc_id IS NULL OR v_acc_id <> NEW.account_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Commercial reward grant account must match the commercial event';
    END IF;
END;

-- loyalty_point_grants: customer_id must match the owner of customer_vouchers.account_id.
CREATE TRIGGER trg_loyalty_point_grants_bi
BEFORE INSERT ON loyalty_point_grants
FOR EACH ROW
BEGIN
    DECLARE v_cust_id BIGINT UNSIGNED;
    SELECT a.customer_id INTO v_cust_id
    FROM customer_vouchers AS v
    JOIN accounts AS a ON a.id = v.account_id
    WHERE v.id = NEW.voucher_id;
    IF v_cust_id IS NULL OR v_cust_id <> NEW.customer_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Loyalty point grant customer must match voucher owner';
    END IF;
END;

-- supplier_payables: enforce approver != payer when an approval record exists.
CREATE TRIGGER trg_supplier_payables_bu
BEFORE UPDATE ON supplier_payables
FOR EACH ROW
BEGIN
    DECLARE v_approver BIGINT UNSIGNED;
    IF NEW.status = 'PAID' AND NEW.paid_by IS NOT NULL THEN
        SELECT approved_by INTO v_approver
        FROM supplier_payable_approvals
        WHERE payable_id = NEW.id;
        IF v_approver IS NOT NULL AND v_approver = NEW.paid_by THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Payable approver cannot self-pay';
        END IF;
    END IF;
END;
