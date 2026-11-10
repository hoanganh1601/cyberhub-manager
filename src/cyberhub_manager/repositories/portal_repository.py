"""Customer analytics over full history; all predicates are bound to the owner."""

from datetime import timezone


def _rows(conn, sql, params=()):
    # Local import avoids a circular dependency with the existing P1 adapter.
    from .p1_repository import rows

    result = rows(conn, sql, params)
    for item in result:
        for key, value in item.items():
            if hasattr(value, "tzinfo") and value.tzinfo is None:
                item[key] = value.replace(tzinfo=timezone.utc)
    return result


def _db_time(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class PortalRepositoryMixin:
    def list_machine_rooms(self, conn, store_id):
        return _rows(
            conn,
            "SELECT m.id AS machine_id,m.code AS machine_code,m.name,m.status,"
            "COALESCE(r.room_type,'STANDARD') AS room_type FROM machines m "
            "LEFT JOIN machine_room_types r ON r.machine_id=m.id "
            "WHERE m.store_id=%s AND m.is_active=1 ORDER BY m.code",
            (store_id,),
        )

    def room_machine(self, conn, machine_id):
        result = _rows(
            conn,
            "SELECT m.id,m.store_id,m.status,m.is_active,EXISTS(SELECT 1 FROM usage_sessions u "
            "WHERE u.machine_id=m.id AND u.status='ACTIVE') AS active_session FROM machines m WHERE m.id=%s FOR UPDATE",
            (machine_id,),
        )
        return result[0] if result else None

    def set_machine_room(self, conn, machine_id, room_type):
        from .p1_repository import execute

        execute(
            conn,
            "INSERT INTO machine_room_types(machine_id,room_type) VALUES(%s,%s) "
            "ON DUPLICATE KEY UPDATE room_type=%s",
            (machine_id, room_type, room_type),
        )

    def portal_room_counts(self, conn, store_id):
        result = _rows(
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

    def portal_usage_sessions(self, conn, principal, start, end):
        return _rows(
            conn,
            "SELECT u.machine_id,m.store_id,s.name AS store_name,u.started_at,u.ended_at,u.status "
            "FROM usage_sessions u JOIN machines m ON m.id=u.machine_id JOIN stores s ON s.id=m.store_id "
            "WHERE u.customer_id=%s AND u.status IN ('ACTIVE','COMPLETED') "
            "AND u.started_at < %s AND (u.ended_at IS NULL OR u.ended_at>%s) ORDER BY u.started_at,u.id",
            (principal.customer_id, _db_time(end), _db_time(start)),
        )

    def portal_profile(self, conn, principal):
        return _rows(
            conn,
            "SELECT c.code AS customer_code,c.full_name,c.phone,c.created_at AS member_since,"
            "a.code AS account_code,a.username,a.status AS account_status "
            "FROM customers c JOIN accounts a ON a.customer_id=c.id WHERE a.id=%s AND c.id=%s",
            (principal.account_id, principal.customer_id),
        )[0]

    def portal_phone_taken(self, conn, principal, phone):
        return bool(
            _rows(
                conn,
                "SELECT id FROM customers WHERE phone=%s AND id<>%s LIMIT 1",
                (phone, principal.customer_id),
            )
        )

    def portal_update_profile(self, conn, principal, name, phone):
        from .p1_repository import execute

        execute(
            conn,
            "UPDATE customers SET full_name=%s,phone=%s WHERE id=%s",
            (name, phone, principal.customer_id),
        )

    def portal_change_password(self, conn, principal, password_hash):
        from .p1_repository import execute

        execute(
            conn,
            "UPDATE accounts SET password_hash=%s,auth_version=auth_version+1 WHERE id=%s",
            (password_hash, principal.account_id),
        )

    def portal_totals(self, conn, principal, start, end, now):
        start, end, now = map(_db_time, (start, end, now))
        paid = _rows(
            conn,
            "SELECT COALESCE(SUM(usage_cost),0) AS spent, COUNT(*) AS paid_invoices, "
            "COALESCE(SUM(bonus_used),0) AS bonus_spent FROM invoices "
            "WHERE customer_id=%s AND status='PAID' AND created_at >= %s AND created_at < %s",
            (principal.customer_id, start, end),
        )[0]
        credits = _rows(
            conn,
            "SELECT COALESCE(SUM(CASE WHEN type='TOP_UP' THEN amount ELSE 0 END),0) AS topped_up, "
            "COALESCE(SUM(CASE WHEN type='PROMOTION' THEN amount ELSE 0 END),0) AS bonus_received "
            "FROM account_transactions WHERE account_id=%s AND created_at >= %s AND created_at < %s",
            (principal.account_id, start, end),
        )[0]
        usage = _rows(
            conn,
            "SELECT COALESCE(SUM(GREATEST(0,TIMESTAMPDIFF(SECOND,GREATEST(started_at,%s),"
            "LEAST(COALESCE(ended_at,%s),%s,%s)))),0) AS usage_seconds FROM usage_sessions "
            "WHERE customer_id=%s AND status IN ('ACTIVE','COMPLETED') "
            "AND started_at < %s AND (ended_at IS NULL OR ended_at > %s)",
            (start, now, now, end, principal.customer_id, end, start),
        )[0]
        daily_paid = _rows(
            conn,
            "SELECT DATE(DATE_ADD(created_at,INTERVAL 7 HOUR)) AS day, SUM(usage_cost) AS spent "
            "FROM invoices WHERE customer_id=%s AND status='PAID' "
            "AND created_at >= %s AND created_at < %s GROUP BY day ORDER BY day",
            (principal.customer_id, start, end),
        )
        daily_topups = _rows(
            conn,
            "SELECT DATE(DATE_ADD(created_at,INTERVAL 7 HOUR)) AS day, SUM(amount) AS topped_up "
            "FROM account_transactions WHERE account_id=%s AND type='TOP_UP' "
            "AND created_at >= %s AND created_at < %s GROUP BY day ORDER BY day",
            (principal.account_id, start, end),
        )
        return {**paid, **credits, **usage}, daily_paid, daily_topups

    def portal_active_sessions(self, conn, principal):
        return _rows(
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
        total = _rows(
            conn, f"SELECT COUNT(*) AS total FROM {source} WHERE {where}", tuple(params)
        )[0]["total"]
        items = _rows(
            conn,
            f"SELECT {fields} FROM {source} WHERE {where} ORDER BY {time} DESC,h.id DESC LIMIT %s OFFSET %s",
            (*params, page_size, (page - 1) * page_size),
        )
        return dict(items=items, total=total, page=page, page_size=page_size)

    def portal_events(self, conn, principal, since, now):
        # Each source is bounded before merging; the service returns the newest 50.
        params = (principal.account_id, _db_time(since), _db_time(now))
        transactions = _rows(
            conn,
            "SELECT id,code,type AS kind,amount,created_at FROM account_transactions "
            "WHERE account_id=%s AND type IN ('TOP_UP','PROMOTION') "
            "AND created_at >= %s AND created_at <= %s ORDER BY created_at DESC,id DESC LIMIT 50",
            params,
        )
        invoices = _rows(
            conn,
            "SELECT id,code,status AS kind,usage_cost AS amount,created_at FROM invoices "
            "WHERE customer_id=%s AND created_at >= %s AND created_at <= %s "
            "ORDER BY created_at DESC,id DESC LIMIT 50",
            (principal.customer_id, *params[1:]),
        )
        return transactions, invoices

    def portal_read_keys(self, conn, principal, keys):
        if not keys:
            return set()
        return {
            r["notification_key"]
            for r in _rows(
                conn,
                "SELECT notification_key FROM customer_notification_reads WHERE account_id=%s "
                "AND notification_key IN (" + ",".join(["%s"] * len(keys)) + ")",
                (principal.account_id, *keys),
            )
        }

    def portal_mark_read(self, conn, principal, keys):
        from .p1_repository import execute

        for key in keys:
            execute(
                conn,
                "INSERT IGNORE INTO customer_notification_reads(account_id,notification_key) VALUES(%s,%s)",
                (principal.account_id, key),
            )
