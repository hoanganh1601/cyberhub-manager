-- Enforce immutable financial ledger rows and strict RESTRICT referential integrity
-- on session_transactions without altering applied migrations 001-010.

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

ALTER TABLE session_transactions
    DROP FOREIGN KEY fk_session_transactions_tx;

ALTER TABLE session_transactions
    ADD CONSTRAINT fk_session_transactions_tx
        FOREIGN KEY (transaction_id) REFERENCES account_transactions (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT;

DROP TRIGGER IF EXISTS trg_account_transactions_bu;
CREATE TRIGGER trg_account_transactions_bu
BEFORE UPDATE ON account_transactions
FOR EACH ROW
BEGIN
    IF NEW.id <> OLD.id
       OR NEW.code <> OLD.code
       OR NEW.account_id <> OLD.account_id
       OR NEW.employee_id <> OLD.employee_id
       OR NEW.store_id <> OLD.store_id
       OR NOT (NEW.promotion_id <=> OLD.promotion_id)
       OR NEW.type <> OLD.type
       OR NEW.amount <> OLD.amount
       OR NEW.method <> OLD.method THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Account transaction ledger entries are immutable';
    END IF;
END;

DROP TRIGGER IF EXISTS trg_session_transactions_bu;
CREATE TRIGGER trg_session_transactions_bu
BEFORE UPDATE ON session_transactions
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Session transaction links are immutable';
END;
