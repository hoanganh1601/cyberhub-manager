"""Customer self-service portal persistence; all queries are strictly owner-scoped.

Owned read/write concerns:
- Customer portal authentication (``accounts`` + ``customers``)
- Customer wallet snapshot, profile updates, and password changes
- Owner-scoped usage analytics, active sessions, and paginated history
- Aggregate-only room availability counts per store (``machines`` + ``machine_room_types``)
"""

from __future__ import annotations

from datetime import timezone

from cyberhub_manager.domain.p1 import CustomerSession

from .sql import execute, rows, utc


def _utc_rows(conn, sql, params=()):
    result = rows(conn, sql, params)
    for item in result:
        for key, value in item.items():
            if hasattr(value, "tzinfo") and value.tzinfo is None:
                item[key] = utc(value)
    return result


def _db_time(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class PortalRepository:
    """MySQL repository for customer portal authentication, profile, and analytics."""

    # ----- Authentication & wallet snapshot -----------------------------------

    def customer_credentials(self, conn, *, username=None, account_id=None, lock=False):
        column, value = (
            ("a.username", username) if username is not None else ("a.id", account_id)
        )
        result = rows(
            conn,
            "SELECT c.id AS customer_id,a.id AS account_id,c.full_name,a.username,"
            "a.password_hash,a.auth_version "
            "FROM accounts a JOIN customers c ON c.id=a.customer_id WHERE "
            + column
            + "=%s AND a.status='ACTIVE' AND a.web_login_enabled=TRUE AND c.status='ACTIVE'"
            + (" FOR UPDATE" if lock else ""),
            (value,),
        )
        if not result:
            return None
        record = result[0]
        return (
            CustomerSession(
                record["customer_id"],
                record["account_id"],
                record["full_name"],
                record["username"],
                record["auth_version"],
            ),
            record["password_hash"],
        )

    def customer_snapshot(self, conn, principal):
        account_id, customer_id = principal.account_id, principal.customer_id
        wallet = rows(
            conn,
            "SELECT a.code AS account_code,a.balance,a.bonus_balance,"
            "(a.balance - a.bonus_balance) AS cash_balance,c.phone "
            "FROM accounts a JOIN customers c ON c.id=a.customer_id WHERE a.id=%s",
            (account_id,),
        )[0]
        history = _utc_rows(
            conn,
            "SELECT t.code,t.type,t.amount,t.method,t.created_at,s.name AS store_name "
            "FROM account_transactions t LEFT JOIN stores s ON s.id=t.store_id "
            "WHERE t.account_id=%s ORDER BY t.created_at DESC,t.id DESC LIMIT 100",
            (account_id,),
        )
        sessions = _utc_rows(
            conn,
            "SELECT u.code,m.code AS machine_code,s.name AS store_name,u.started_at,u.ended_at,"
            "u.hourly_rate,u.status,u.cost FROM usage_sessions u "
            "JOIN machines m ON m.id=u.machine_id JOIN stores s ON s.id=m.store_id "
            "WHERE u.customer_id=%s ORDER BY u.id DESC LIMIT 100",
            (customer_id,),
        )
        invoices = _utc_rows(
            conn,
            "SELECT i.id,i.code,i.usage_cost,i.settlement_amount,i.bonus_used,i.status,"
            "i.created_at,s.name AS store_name FROM invoices i "
            "JOIN stores s ON s.id=i.store_id WHERE i.customer_id=%s "
            "ORDER BY i.id DESC LIMIT 100",
            (customer_id,),
        )
        return {
            "profile": principal,
            "wallet": wallet,
            "transactions": history,
            "sessions": sessions,
            "invoices": invoices,
        }

    # ----- Aggregate room availability ----------------------------------------

    def portal_room_counts(self, conn, store_id):
        result = _utc_rows(
            conn,
            "SELECT COALESCE(r.room_type,'STANDARD') AS room_type,COUNT(*) AS total,"
            "SUM(CASE WHEN m.status='AVAILABLE' AND NOT EXISTS(SELECT 1 FROM usage_sessions u "
            "WHERE u.machine_id=m.id AND u.status='ACTIVE') THEN 1 ELSE 0 END) AS available,"
            "MIN(m.hourly_rate) AS min_hourly_rate,MAX(m.hourly_rate) AS max_hourly_rate "
            "FROM machines m LEFT JOIN machine_room_types r ON r.machine_id=m.id "
            "WHERE m.store_id=%s AND m.is_active=1 GROUP BY COALESCE(r.room_type,'STANDARD')",
            (store_id,),
        )
        values = {r["room_type"]: r for r in result}
        return [
            dict(
                room_type=kind,
                total=int(values.get(kind, {}).get("total", 0)),
                available=int(values.get(kind, {}).get("available", 0)),
                min_hourly_rate=(
                    int(values[kind]["min_hourly_rate"]) if kind in values else None
                ),
                max_hourly_rate=(
                    int(values[kind]["max_hourly_rate"]) if kind in values else None
                ),
            )
            for kind in ("STANDARD", "VIP", "COUPLE", "SUPER_VIP")
        ]

    # ----- Profile & credentials management -----------------------------------

    def portal_profile(self, conn, principal):
        return _utc_rows(
            conn,
            "SELECT c.code AS customer_code,c.full_name,c.phone,c.created_at AS member_since,"
            "a.code AS account_code,a.username,a.status AS account_status "
            "FROM customers c JOIN accounts a ON a.customer_id=c.id WHERE a.id=%s AND c.id=%s",
            (principal.account_id, principal.customer_id),
        )[0]

    def portal_phone_taken(self, conn, principal, phone):
        return bool(
            _utc_rows(
                conn,
                "SELECT id FROM customers WHERE phone=%s AND id<>%s LIMIT 1",
                (phone, principal.customer_id),
            )
        )

    def portal_update_profile(self, conn, principal, name, phone):
        execute(
            conn,
            "UPDATE customers SET full_name=%s,phone=%s WHERE id=%s",
            (name, phone, principal.customer_id),
        )

    def portal_change_password(self, conn, principal, password_hash):
        execute(
            conn,
            "UPDATE accounts SET password_hash=%s,auth_version=auth_version+1 WHERE id=%s",
            (password_hash, principal.account_id),
        )

    # ----- Owner-scoped analytics, active sessions & history ------------------

    def portal_usage_sessions(self, conn, principal, start, end):
        return _utc_rows(
            conn,
            "SELECT u.machine_id,m.store_id,s.name AS store_name,u.started_at,u.ended_at,u.status "
            "FROM usage_sessions u JOIN machines m ON m.id=u.machine_id JOIN stores s ON s.id=m.store_id "
            "WHERE u.customer_id=%s AND u.status IN ('ACTIVE','COMPLETED') "
            "AND u.started_at < %s AND (u.ended_at IS NULL OR u.ended_at>%s) ORDER BY u.started_at,u.id",
            (principal.customer_id, _db_time(end), _db_time(start)),
        )

    def portal_totals(self, conn, principal, start, end, now):
        start, end, now = map(_db_time, (start, end, now))
        paid = _utc_rows(
            conn,
            "SELECT COALESCE(SUM(usage_cost),0) AS spent, COUNT(*) AS paid_invoices, "
            "COALESCE(SUM(bonus_used),0) AS bonus_spent FROM invoices "
            "WHERE customer_id=%s AND status='PAID' AND created_at >= %s AND created_at < %s",
            (principal.customer_id, start, end),
        )[0]
        credits = _utc_rows(
            conn,
            "SELECT COALESCE(SUM(CASE WHEN type='TOP_UP' THEN amount ELSE 0 END),0) AS topped_up, "
            "COALESCE(SUM(CASE WHEN type='PROMOTION' THEN amount ELSE 0 END),0) AS bonus_received "
            "FROM account_transactions WHERE account_id=%s AND created_at >= %s AND created_at < %s",
            (principal.account_id, start, end),
        )[0]
        usage = _utc_rows(
            conn,
            "SELECT COALESCE(SUM(GREATEST(0,TIMESTAMPDIFF(SECOND,GREATEST(started_at,%s),"
            "LEAST(COALESCE(ended_at,%s),%s,%s)))),0) AS usage_seconds FROM usage_sessions "
            "WHERE customer_id=%s AND status IN ('ACTIVE','COMPLETED') "
            "AND started_at < %s AND (ended_at IS NULL OR ended_at > %s)",
            (start, now, now, end, principal.customer_id, end, start),
        )[0]
        daily_paid = _utc_rows(
            conn,
            "SELECT DATE(DATE_ADD(created_at,INTERVAL 7 HOUR)) AS day, SUM(usage_cost) AS spent "
            "FROM invoices WHERE customer_id=%s AND status='PAID' "
            "AND created_at >= %s AND created_at < %s GROUP BY day ORDER BY day",
            (principal.customer_id, start, end),
        )
        daily_topups = _utc_rows(
            conn,
            "SELECT DATE(DATE_ADD(created_at,INTERVAL 7 HOUR)) AS day, SUM(amount) AS topped_up "
            "FROM account_transactions WHERE account_id=%s AND type='TOP_UP' "
            "AND created_at >= %s AND created_at < %s GROUP BY day ORDER BY day",
            (principal.account_id, start, end),
        )
        return {**paid, **credits, **usage}, daily_paid, daily_topups

    def portal_active_sessions(self, conn, principal):
        return _utc_rows(
            conn,
            "SELECT u.id,u.code,m.code AS machine_code,s.name AS store_name,u.started_at,u.hourly_rate "
            "FROM usage_sessions u JOIN machines m ON m.id=u.machine_id JOIN stores s ON s.id=m.store_id "
            "WHERE u.customer_id=%s AND u.status='ACTIVE' ORDER BY u.id DESC",
            (principal.customer_id,),
        )

    def portal_history(
        self, conn, principal, kind, status, start, end, page, page_size
    ):
        if kind == "transactions":
            source = "account_transactions h LEFT JOIN stores s ON s.id=h.store_id"
            owner, owner_id, time = "h.account_id", principal.account_id, "h.created_at"
            fields = (
                "h.id,h.code,h.type,h.amount,h.method,h.created_at,s.name AS store_name"
            )
            status_column = "h.type"
        elif kind == "invoices":
            source = "invoices h JOIN stores s ON s.id=h.store_id"
            owner, owner_id, time = (
                "h.customer_id",
                principal.customer_id,
                "h.created_at",
            )
            fields = "h.id,h.code,h.usage_cost,h.bonus_used,h.settlement_amount,h.status,h.created_at,s.name AS store_name"
            status_column = "h.status"
        else:
            source = "usage_sessions h JOIN machines m ON m.id=h.machine_id JOIN stores s ON s.id=m.store_id"
            owner, owner_id, time = (
                "h.customer_id",
                principal.customer_id,
                "h.started_at",
            )
            fields = "h.id,h.code,m.code AS machine_code,s.name AS store_name,h.started_at,h.ended_at,h.hourly_rate,h.status,h.cost"
            status_column = "h.status"
        where, params = f"{owner}=%s", [owner_id]
        if start:
            where += f" AND {time} >= %s"
            params.append(_db_time(start))
        if end:
            where += f" AND {time} < %s"
            params.append(_db_time(end))
        if status != "all":
            where += f" AND {status_column}=%s"
            params.append(status)
        total = _utc_rows(
            conn, f"SELECT COUNT(*) AS total FROM {source} WHERE {where}", tuple(params)
        )[0]["total"]
        items = _utc_rows(
            conn,
            f"SELECT {fields} FROM {source} WHERE {where} ORDER BY {time} DESC,h.id DESC LIMIT %s OFFSET %s",
            (*params, page_size, (page - 1) * page_size),
        )
        return dict(items=items, total=total, page=page, page_size=page_size)
