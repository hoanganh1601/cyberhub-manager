"""Membership and avatar persistence; callers supply the authenticated account."""

from cyberhub_manager.domain.loyalty import LoyaltySettings, membership


def rows(conn, sql, params=()):
    from .p1_repository import rows as query

    return query(conn, sql, params)


def execute(conn, sql, params=()):
    from .p1_repository import execute as command

    return command(conn, sql, params)


class LoyaltyRepositoryMixin:
    def loyalty_settings(self, conn, lock=False):
        row = rows(
            conn,
            "SELECT enabled,unit_amount,silver_spend,gold_spend,platinum_spend,version FROM loyalty_settings WHERE id=1"
            + (" FOR UPDATE" if lock else " FOR SHARE"),
        )[0]
        return LoyaltySettings(**{**row, "enabled": bool(row["enabled"])})

    def save_loyalty_settings(self, conn, settings):
        execute(
            conn,
            "UPDATE loyalty_settings SET enabled=%s,unit_amount=%s,silver_spend=%s,gold_spend=%s,platinum_spend=%s,version=%s WHERE id=1",
            (
                settings.enabled,
                settings.unit_amount,
                settings.silver_spend,
                settings.gold_spend,
                settings.platinum_spend,
                settings.version,
            ),
        )

    def loyalty_summary(self, conn, customer_id, current=False):
        if current:
            # Financial confirmation must use current rows, not an earlier
            # REPEATABLE READ snapshot established before acquiring the wallet lock.
            awards = rows(
                conn,
                "SELECT loyalty_points,loyalty_eligible_amount FROM invoices "
                "WHERE customer_id=%s AND status='PAID' FOR SHARE",
                (customer_id,),
            )
            return membership(
                sum(r["loyalty_points"] for r in awards),
                sum(r["loyalty_eligible_amount"] for r in awards),
                self.loyalty_settings(conn),
            )
        totals = rows(
            conn,
            "SELECT COALESCE(SUM(loyalty_points),0) AS points,COALESCE(SUM(loyalty_eligible_amount),0) AS eligible_spend "
            "FROM invoices WHERE customer_id=%s AND status='PAID'",
            (customer_id,),
        )[0]
        return membership(
            int(totals["points"]),
            int(totals["eligible_spend"]),
            self.loyalty_settings(conn),
        )

    def loyalty_history(self, conn, customer_id, page=1, page_size=10):
        total = rows(
            conn,
            "SELECT COUNT(*) AS total FROM invoices WHERE customer_id=%s",
            (customer_id,),
        )[0]["total"]
        entries = rows(
            conn,
            "SELECT i.id,i.code,i.status,i.loyalty_eligible_amount AS eligible_amount,i.loyalty_points AS points,"
            "i.loyalty_unit AS unit_amount,i.loyalty_rule_version AS rule_version,i.created_at,s.name AS store_name "
            "FROM invoices i JOIN stores s ON s.id=i.store_id WHERE i.customer_id=%s ORDER BY i.created_at DESC,i.id DESC LIMIT %s OFFSET %s",
            (customer_id, page_size, (page - 1) * page_size),
        )
        from datetime import timezone

        for item in entries:
            item["created_at"] = item["created_at"].replace(tzinfo=timezone.utc)
            item["effective_points"] = item["points"] if item["status"] == "PAID" else 0
        return dict(items=entries, total=total, page=page, page_size=page_size)

    def target_customer_exists(self, conn, customer_id):
        return bool(rows(conn, "SELECT id FROM customers WHERE id=%s", (customer_id,)))

    def avatar_metadata(self, conn, account_id):
        result = rows(
            conn,
            "SELECT digest FROM customer_avatars WHERE account_id=%s",
            (account_id,),
        )
        return result[0]["digest"] if result else None

    def avatar_image(self, conn, account_id):
        result = rows(
            conn,
            "SELECT image_data,digest FROM customer_avatars WHERE account_id=%s",
            (account_id,),
        )
        return result[0] if result else None

    def save_avatar(self, conn, account_id, image, digest):
        execute(
            conn,
            "INSERT INTO customer_avatars(account_id,image_data,digest) VALUES(%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE image_data=%s,digest=%s",
            (account_id, image, digest, image, digest),
        )

    def delete_avatar(self, conn, account_id):
        execute(conn, "DELETE FROM customer_avatars WHERE account_id=%s", (account_id,))
