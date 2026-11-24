"""Customer email activation, recovery, outbox and security audit persistence."""

from cyberhub_manager.infrastructure.repositories.sql import execute, rows


class CustomerEmailRepository:
    def set_email(self, conn, customer_id, email):
        execute(conn, "UPDATE customers SET email=%s WHERE id=%s", (email, customer_id))

    def mark_pending(self, conn, account_id):
        execute(conn, "UPDATE accounts SET password_hash=NULL,web_login_enabled=FALSE "
                "WHERE id=%s", (account_id,))

    def account_by_email(self, conn, email, *, lock=False):
        found = rows(conn, "SELECT a.id AS account_id,a.customer_id,a.username,"
                     "a.web_login_enabled,a.email_verified_at,c.email,c.full_name "
                     "FROM accounts a JOIN customers c ON c.id=a.customer_id "
                     "WHERE c.email=%s" + (" FOR UPDATE" if lock else ""), (email,))
        return found[0] if found else None

    def token_by_hash(self, conn, token_hash, *, lock=False):
        found = rows(conn, "SELECT t.*,a.web_login_enabled FROM customer_email_tokens t "
                     "JOIN accounts a ON a.id=t.account_id WHERE t.token_hash=%s" +
                     (" FOR UPDATE" if lock else ""), (token_hash,))
        return found[0] if found else None

    def recent_token(self, conn, account_id, purpose):
        found = rows(conn, "SELECT id FROM customer_email_tokens WHERE account_id=%s "
                     "AND purpose=%s AND created_at>UTC_TIMESTAMP()-INTERVAL 10 MINUTE "
                     "ORDER BY id DESC LIMIT 1", (account_id, purpose))
        return bool(found)

    def issue_token(self, conn, account_id, purpose, token_hash, nonce, ttl_minutes):
        execute(conn, "UPDATE customer_email_tokens SET used_at=UTC_TIMESTAMP() "
                "WHERE account_id=%s AND purpose=%s AND used_at IS NULL", (account_id, purpose))
        token_id = execute(conn, "INSERT INTO customer_email_tokens"
                           "(account_id,purpose,token_hash,nonce,expires_at) "
                           "VALUES(%s,%s,%s,%s,UTC_TIMESTAMP()+INTERVAL %s MINUTE)",
                           (account_id, purpose, token_hash, nonce, ttl_minutes))
        execute(conn, "INSERT INTO customer_mail_outbox(token_id) VALUES(%s)", (token_id,))
        return token_id

    def activate(self, conn, token_id, account_id, password_hash):
        execute(conn, "UPDATE accounts SET password_hash=%s,web_login_enabled=TRUE,"
                "email_verified_at=UTC_TIMESTAMP(),auth_version=auth_version+1 WHERE id=%s",
                (password_hash, account_id))
        execute(conn, "UPDATE customer_email_tokens SET used_at=UTC_TIMESTAMP() WHERE id=%s AND used_at IS NULL",
                (token_id,))

    def reset_password(self, conn, token_id, account_id, password_hash):
        execute(conn, "UPDATE accounts SET password_hash=%s,auth_version=auth_version+1 WHERE id=%s",
                (password_hash, account_id))
        execute(conn, "UPDATE customer_email_tokens SET used_at=UTC_TIMESTAMP() WHERE id=%s AND used_at IS NULL",
                (token_id,))

    def audit(self, conn, account_id, action, actor=None):
        execute(conn, "INSERT INTO customer_security_audit(account_id,employee_id,store_id,action) "
                "VALUES(%s,%s,%s,%s)",
                (account_id, actor.employee_id if actor else None,
                 actor.store_id if actor else None, action))

    def claim_due(self, conn):
        due = rows(conn, "SELECT o.id,o.attempts,t.id AS token_id,t.nonce,t.purpose,t.expires_at,t.used_at,"
                   "a.username,c.email,c.full_name FROM customer_mail_outbox o "
                   "JOIN customer_email_tokens t ON t.id=o.token_id "
                   "JOIN accounts a ON a.id=t.account_id JOIN customers c ON c.id=a.customer_id "
                   "WHERE o.status IN ('PENDING','SENDING') AND o.next_attempt_at<=UTC_TIMESTAMP() "
                   "ORDER BY o.id LIMIT 1 FOR UPDATE SKIP LOCKED", ())
        if not due:
            return None
        item = due[0]
        execute(conn, "UPDATE customer_mail_outbox SET status='SENDING',attempts=attempts+1,"
                "next_attempt_at=UTC_TIMESTAMP()+INTERVAL 5 MINUTE WHERE id=%s", (item["id"],))
        return item

    def finish_delivery(self, conn, outbox_id, *, success, error=None, retry_seconds=60):
        if success:
            execute(conn, "UPDATE customer_mail_outbox SET status='SENT',sent_at=UTC_TIMESTAMP(),"
                    "last_error=NULL WHERE id=%s AND status='SENDING'", (outbox_id,))
        else:
            execute(conn, "UPDATE customer_mail_outbox SET status=CASE WHEN attempts>=5 THEN 'FAILED' "
                    "ELSE 'PENDING' END,last_error=%s,"
                    "next_attempt_at=UTC_TIMESTAMP()+INTERVAL %s SECOND WHERE id=%s AND status='SENDING'",
                    (error, retry_seconds, outbox_id))

    def cancel_delivery(self, conn, outbox_id):
        execute(conn, "UPDATE customer_mail_outbox SET status='FAILED',last_error='token unavailable' "
                "WHERE id=%s AND status='SENDING'", (outbox_id,))
