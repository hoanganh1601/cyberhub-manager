-- Session occupancy synchronization and cross-store/cross-owner business integrity triggers.
-- All triggers use compound BEGIN...END blocks for clean mysqldump/mysql roundtrip compatibility.

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- 1. Active usage session occupancy synchronization & no-reopen guard
CREATE TRIGGER trg_usage_sessions_ai
AFTER INSERT ON usage_sessions
FOR EACH ROW
BEGIN
    IF NEW.status = 'ACTIVE' THEN
        INSERT INTO active_usage_sessions (session_id, machine_id, customer_id)
        VALUES (NEW.id, NEW.machine_id, NEW.customer_id);
    END IF;
END;

CREATE TRIGGER trg_usage_sessions_au
AFTER UPDATE ON usage_sessions
FOR EACH ROW
BEGIN
    IF NEW.status <> 'ACTIVE' THEN
        DELETE FROM active_usage_sessions WHERE session_id = OLD.id;
    END IF;
END;

CREATE TRIGGER trg_usage_sessions_bu_no_reopen
BEFORE UPDATE ON usage_sessions
FOR EACH ROW
BEGIN
    IF OLD.status <> 'ACTIVE' AND NEW.status = 'ACTIVE' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Cannot reopen a closed usage session';
    END IF;
END;

-- 2. Store-wide unique menu item name across categories
CREATE TRIGGER trg_menu_items_bi
BEFORE INSERT ON menu_items
FOR EACH ROW
BEGIN
    DECLARE v_store_id BIGINT UNSIGNED;
    SELECT store_id INTO v_store_id
    FROM menu_categories
    WHERE id = NEW.category_id;

    IF EXISTS (
        SELECT 1
        FROM menu_items AS mi
        JOIN menu_categories AS mc ON mc.id = mi.category_id
        WHERE mc.store_id = v_store_id
          AND mi.name = NEW.name
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Duplicate menu item name within the same store';
    END IF;
END;

CREATE TRIGGER trg_menu_items_bu
BEFORE UPDATE ON menu_items
FOR EACH ROW
BEGIN
    DECLARE v_store_id BIGINT UNSIGNED;
    SELECT store_id INTO v_store_id
    FROM menu_categories
    WHERE id = NEW.category_id;

    IF EXISTS (
        SELECT 1
        FROM menu_items AS mi
        JOIN menu_categories AS mc ON mc.id = mi.category_id
        WHERE mc.store_id = v_store_id
          AND mi.name = NEW.name
          AND mi.id <> OLD.id
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Duplicate menu item name within the same store';
    END IF;
END;

-- 3. Cross-store guard for POS order items
CREATE TRIGGER trg_menu_order_items_bi
BEFORE INSERT ON menu_order_items
FOR EACH ROW
BEGIN
    DECLARE v_order_store BIGINT UNSIGNED;
    DECLARE v_item_store BIGINT UNSIGNED;

    SELECT m.store_id INTO v_order_store
    FROM menu_orders AS o
    JOIN usage_sessions AS u ON u.id = o.session_id
    JOIN machines AS m ON m.id = u.machine_id
    WHERE o.id = NEW.order_id;

    SELECT mc.store_id INTO v_item_store
    FROM menu_items AS mi
    JOIN menu_categories AS mc ON mc.id = mi.category_id
    WHERE mi.id = NEW.item_id;

    IF v_order_store <> v_item_store THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Menu order item belongs to a different store than the order';
    END IF;
END;

CREATE TRIGGER trg_menu_order_items_bu
BEFORE UPDATE ON menu_order_items
FOR EACH ROW
BEGIN
    DECLARE v_order_store BIGINT UNSIGNED;
    DECLARE v_item_store BIGINT UNSIGNED;

    SELECT m.store_id INTO v_order_store
    FROM menu_orders AS o
    JOIN usage_sessions AS u ON u.id = o.session_id
    JOIN machines AS m ON m.id = u.machine_id
    WHERE o.id = NEW.order_id;

    SELECT mc.store_id INTO v_item_store
    FROM menu_items AS mi
    JOIN menu_categories AS mc ON mc.id = mi.category_id
    WHERE mi.id = NEW.item_id;

    IF v_order_store <> v_item_store THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Menu order item belongs to a different store than the order';
    END IF;
END;

-- 4. Cross-store guard for POS promotion items
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

        IF v_item_store <> NEW.store_id THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Menu promotion item belongs to a different store';
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

        IF v_item_store <> NEW.store_id THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Menu promotion item belongs to a different store';
        END IF;
    END IF;
END;

-- 5. Cross-store & discount ceiling guard for POS order pricing
CREATE TRIGGER trg_menu_order_pricing_bi
BEFORE INSERT ON menu_order_pricing
FOR EACH ROW
BEGIN
    DECLARE v_order_store BIGINT UNSIGNED;
    DECLARE v_order_total BIGINT;
    DECLARE v_promo_store BIGINT UNSIGNED;

    SELECT m.store_id, o.total_amount INTO v_order_store, v_order_total
    FROM menu_orders AS o
    JOIN usage_sessions AS u ON u.id = o.session_id
    JOIN machines AS m ON m.id = u.machine_id
    WHERE o.id = NEW.order_id;

    IF NEW.discount_amount > v_order_total THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Menu order discount cannot exceed order total_amount';
    END IF;

    IF NEW.promotion_version_id IS NOT NULL THEN
        SELECT mp.store_id INTO v_promo_store
        FROM menu_promotion_versions AS mv
        JOIN menu_promotions AS mp ON mp.id = mv.promotion_id
        WHERE mv.id = NEW.promotion_version_id;

        IF v_promo_store <> v_order_store THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Menu promotion belongs to a different store than the order';
        END IF;
    END IF;
END;

CREATE TRIGGER trg_menu_order_pricing_bu
BEFORE UPDATE ON menu_order_pricing
FOR EACH ROW
BEGIN
    DECLARE v_order_store BIGINT UNSIGNED;
    DECLARE v_order_total BIGINT;
    DECLARE v_promo_store BIGINT UNSIGNED;

    SELECT m.store_id, o.total_amount INTO v_order_store, v_order_total
    FROM menu_orders AS o
    JOIN usage_sessions AS u ON u.id = o.session_id
    JOIN machines AS m ON m.id = u.machine_id
    WHERE o.id = NEW.order_id;

    IF NEW.discount_amount > v_order_total THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Menu order discount cannot exceed order total_amount';
    END IF;

    IF NEW.promotion_version_id IS NOT NULL THEN
        SELECT mp.store_id INTO v_promo_store
        FROM menu_promotion_versions AS mv
        JOIN menu_promotions AS mp ON mp.id = mv.promotion_id
        WHERE mv.id = NEW.promotion_version_id;

        IF v_promo_store <> v_order_store THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Menu promotion belongs to a different store than the order';
        END IF;
    END IF;
END;

-- 6. Cross-store & cross-customer guard for invoices
CREATE TRIGGER trg_invoices_bi
BEFORE INSERT ON invoices
FOR EACH ROW
BEGIN
    DECLARE v_session_customer BIGINT UNSIGNED;
    DECLARE v_session_store BIGINT UNSIGNED;

    SELECT u.customer_id, m.store_id INTO v_session_customer, v_session_store
    FROM usage_sessions AS u
    JOIN machines AS m ON m.id = u.machine_id
    WHERE u.id = NEW.session_id;

    IF NEW.customer_id <> v_session_customer OR NEW.store_id <> v_session_store THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invoice customer_id/store_id must match the usage session';
    END IF;
END;

-- 7. Cross-owner & cross-store guard for wallet ledger transactions
CREATE TRIGGER trg_account_transactions_bi
BEFORE INSERT ON account_transactions
FOR EACH ROW
BEGIN
    DECLARE v_session_customer BIGINT UNSIGNED;
    DECLARE v_session_store BIGINT UNSIGNED;
    DECLARE v_account_customer BIGINT UNSIGNED;
    DECLARE v_promo_store BIGINT UNSIGNED;

    IF NEW.session_id IS NOT NULL THEN
        SELECT u.customer_id, m.store_id INTO v_session_customer, v_session_store
        FROM usage_sessions AS u
        JOIN machines AS m ON m.id = u.machine_id
        WHERE u.id = NEW.session_id;

        SELECT a.customer_id INTO v_account_customer
        FROM accounts AS a
        WHERE a.id = NEW.account_id;

        IF v_account_customer <> v_session_customer THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Transaction account does not own the referenced usage session';
        END IF;

        IF NEW.store_id IS NOT NULL AND NEW.store_id <> v_session_store THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Transaction store_id must match the referenced usage session store';
        END IF;
    END IF;

    IF NEW.promotion_id IS NOT NULL THEN
        IF NEW.type <> 'PROMOTION' THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Only PROMOTION transactions may reference a promotion_id';
        END IF;

        SELECT p.store_id INTO v_promo_store
        FROM promotions AS p
        WHERE p.id = NEW.promotion_id;

        IF v_promo_store IS NOT NULL AND NEW.store_id IS NOT NULL AND v_promo_store <> NEW.store_id THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Promotion transaction store_id must match promotion scope';
        END IF;
    END IF;
END;

-- 8. POS reversal lifecycle & refund ceiling guards
CREATE TRIGGER trg_pos_order_reversals_bi
BEFORE INSERT ON pos_order_reversals
FOR EACH ROW
BEGIN
    DECLARE v_order_status VARCHAR(12);
    SELECT status INTO v_order_status
    FROM menu_orders
    WHERE id = NEW.order_id;

    IF v_order_status NOT IN ('SERVED', 'PAID') THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Reversal can only be requested for SERVED or PAID menu orders';
    END IF;
END;

CREATE TRIGGER trg_pos_order_reversals_bu
BEFORE UPDATE ON pos_order_reversals
FOR EACH ROW
BEGIN
    DECLARE v_order_status VARCHAR(12);
    DECLARE v_order_total BIGINT;
    DECLARE v_discount BIGINT UNSIGNED;

    IF OLD.status <> 'PENDING' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Cannot modify an already decided POS reversal';
    END IF;

    IF NEW.status = 'APPROVED' THEN
        SELECT o.status, o.total_amount, COALESCE(p.discount_amount, 0)
          INTO v_order_status, v_order_total, v_discount
        FROM menu_orders AS o
        LEFT JOIN menu_order_pricing AS p ON p.order_id = o.id
        WHERE o.id = NEW.order_id;

        IF NEW.refund_amount > 0 AND v_order_status <> 'PAID' THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Refund amount must be 0 for an unpaid order reversal';
        END IF;

        IF NEW.refund_amount > GREATEST(0, v_order_total - LEAST(v_order_total, v_discount)) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Refund amount cannot exceed net paid order amount';
        END IF;
    END IF;
END;
