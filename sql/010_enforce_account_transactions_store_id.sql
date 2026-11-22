-- Normalize account transaction/session links and enforce transaction store attribution.
-- Migration 003 remains immutable so this runs against both fresh and existing schemas.

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS session_transactions (
    transaction_id BIGINT UNSIGNED NOT NULL,
    session_id BIGINT UNSIGNED NOT NULL,

    CONSTRAINT pk_session_transactions PRIMARY KEY (transaction_id),
    CONSTRAINT fk_session_transactions_tx
        FOREIGN KEY (transaction_id) REFERENCES account_transactions (id)
        ON UPDATE RESTRICT ON DELETE CASCADE,
    CONSTRAINT fk_session_transactions_session
        FOREIGN KEY (session_id) REFERENCES usage_sessions (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

-- A session transaction's store is determined by the store hosting its machine.
UPDATE account_transactions AS t
JOIN usage_sessions AS u ON u.id = t.session_id
JOIN machines AS m ON m.id = u.machine_id
SET t.store_id = m.store_id
WHERE t.store_id IS NULL
  AND t.session_id IS NOT NULL;

-- A store-scoped promotion also provides an unambiguous store for its ledger row.
UPDATE account_transactions AS t
JOIN promotions AS p ON p.id = t.promotion_id
SET t.store_id = p.store_id
WHERE t.store_id IS NULL
  AND p.store_id IS NOT NULL;

-- Do not invent a store for unresolved historical rows. If this ALTER fails,
-- inspect and manually map the rows with:
-- SELECT id, code, type, employee_id, promotion_id, session_id
-- FROM account_transactions WHERE store_id IS NULL;
ALTER TABLE account_transactions
    MODIFY COLUMN store_id BIGINT UNSIGNED NOT NULL;

DROP TRIGGER IF EXISTS trg_session_transactions_bi;

CREATE TRIGGER trg_session_transactions_bi
BEFORE INSERT ON session_transactions
FOR EACH ROW
BEGIN
    DECLARE v_session_customer BIGINT UNSIGNED;
    DECLARE v_session_store BIGINT UNSIGNED;
    DECLARE v_tx_account BIGINT UNSIGNED;
    DECLARE v_tx_store BIGINT UNSIGNED;
    DECLARE v_tx_type VARCHAR(20);
    DECLARE v_account_customer BIGINT UNSIGNED;

    SELECT u.customer_id, m.store_id INTO v_session_customer, v_session_store
    FROM usage_sessions AS u
    JOIN machines AS m ON m.id = u.machine_id
    WHERE u.id = NEW.session_id;

    SELECT account_id, store_id, type
      INTO v_tx_account, v_tx_store, v_tx_type
    FROM account_transactions
    WHERE id = NEW.transaction_id;

    IF v_tx_type NOT IN ('USAGE_PAYMENT', 'DEBT_SETTLEMENT') THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Only usage payments and debt settlements may reference a session';
    END IF;

    SELECT customer_id INTO v_account_customer
    FROM accounts
    WHERE id = v_tx_account;

    IF v_account_customer <> v_session_customer THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Transaction account does not own the referenced usage session';
    END IF;

    IF v_tx_store <> v_session_store THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Transaction store_id must match the referenced usage session store';
    END IF;
END;

-- Copy and validate old links while account_transactions.session_id still exists.
INSERT INTO session_transactions (transaction_id, session_id)
SELECT id, session_id
FROM account_transactions
WHERE session_id IS NOT NULL;

-- Assert that every legacy link was copied exactly before dropping its source.
CREATE TEMPORARY TABLE migration_010_session_link_assertion (
    assertion TINYINT NOT NULL CHECK (assertion = 1)
);

INSERT INTO migration_010_session_link_assertion (assertion)
SELECT IF(
    (SELECT COUNT(*) FROM session_transactions) =
        (SELECT COUNT(*) FROM account_transactions WHERE session_id IS NOT NULL)
    AND NOT EXISTS (
        SELECT 1
        FROM account_transactions AS t
        LEFT JOIN session_transactions AS st ON st.transaction_id = t.id
        WHERE t.session_id IS NOT NULL
          AND (st.transaction_id IS NULL OR st.session_id <> t.session_id)
    ),
    1,
    0
);

DROP TEMPORARY TABLE migration_010_session_link_assertion;

-- The legacy trigger refers to account_transactions.session_id.
DROP TRIGGER IF EXISTS trg_account_transactions_bi;

ALTER TABLE account_transactions
    DROP FOREIGN KEY fk_account_transactions_session,
    DROP COLUMN session_id;

CREATE TRIGGER trg_account_transactions_bi
BEFORE INSERT ON account_transactions
FOR EACH ROW
BEGIN
    DECLARE v_promo_store BIGINT UNSIGNED;

    IF NEW.promotion_id IS NOT NULL THEN
        IF NEW.type <> 'PROMOTION' THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Only PROMOTION transactions may reference a promotion_id';
        END IF;

        SELECT p.store_id INTO v_promo_store
        FROM promotions AS p
        WHERE p.id = NEW.promotion_id;

        IF v_promo_store IS NOT NULL AND v_promo_store <> NEW.store_id THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Promotion transaction store_id must match promotion scope';
        END IF;
    END IF;
END;
