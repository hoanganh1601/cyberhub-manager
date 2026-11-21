-- Reduce the agreed 24-table scope to 20 business tables.
-- Drops customer email activation/recovery queues, customer security events,
-- and customer-to-store history. Existing rows in these tables are discarded.

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS
    customer_mail_outbox,
    customer_email_tokens,
    customer_security_audit,
    customer_store_links;

SET FOREIGN_KEY_CHECKS = 1;
