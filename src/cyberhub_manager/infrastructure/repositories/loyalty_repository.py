"""Membership policy, loyalty points, and customer avatar persistence."""

from datetime import timezone

from cyberhub_manager.domain.loyalty import LoyaltySettings, membership
from cyberhub_manager.infrastructure.repositories.sql import execute, rows


class LoyaltyRepository:
    """Persistence for loyalty policy versions, point history, and customer avatars."""

    def loyalty_settings(self, conn, lock=False):
        row = rows(
            conn,
            "SELECT v.enabled,v.unit_amount,v.silver_spend,v.gold_spend,v.platinum_spend,v.version "
            "FROM loyalty_settings s JOIN loyalty_policy_versions v ON v.version=s.current_version WHERE s.id=1"
            + (" FOR UPDATE" if lock else " FOR SHARE"),
        )[0]
        return LoyaltySettings(**{**row, "enabled": bool(row["enabled"])})

    def save_loyalty_settings(self, conn, settings):
        execute(
            conn,
            "INSERT INTO loyalty_policy_versions(version,enabled,unit_amount,silver_spend,gold_spend,platinum_spend) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (
                settings.version,
                settings.enabled,
                settings.unit_amount,
                settings.silver_spend,
                settings.gold_spend,
                settings.platinum_spend,
            ),
        )
        execute(
            conn,
            "UPDATE loyalty_settings SET current_version=%s WHERE id=1",
            (settings.version,),
        )

    def loyalty_summary(self, conn, customer_id, current=False):
        if current:
            # Financial confirmation must use current rows, not an earlier
            # REPEATABLE READ snapshot established before acquiring the wallet lock.
            awards = rows(
                conn,
                "SELECT GREATEST(0,i.usage_cost-i.bonus_used) AS loyalty_eligible_amount,"
                "CASE WHEN v.enabled THEN FLOOR(GREATEST(0,i.usage_cost-i.bonus_used)/v.unit_amount) ELSE 0 END AS loyalty_points "
                "FROM invoices i JOIN loyalty_policy_versions v ON v.version=i.loyalty_rule_version "
                "WHERE i.customer_id=%s AND i.status='PAID' FOR SHARE",
                (customer_id,),
            )
            return membership(
                sum(r["loyalty_points"] for r in awards) + self._granted_points(conn, customer_id, lock=True),
                sum(r["loyalty_eligible_amount"] for r in awards),
                self.loyalty_settings(conn),
            )
        totals = rows(
            conn,
            "SELECT COALESCE(SUM(CASE WHEN v.enabled THEN FLOOR(GREATEST(0,i.usage_cost-i.bonus_used)/v.unit_amount) ELSE 0 END),0) AS points,"
            "COALESCE(SUM(GREATEST(0,i.usage_cost-i.bonus_used)),0) AS eligible_spend "
            "FROM invoices i JOIN loyalty_policy_versions v ON v.version=i.loyalty_rule_version "
            "WHERE i.customer_id=%s AND i.status='PAID'",
            (customer_id,),
        )[0]
        return membership(
            int(totals["points"]) + self._granted_points(conn, customer_id),
            int(totals["eligible_spend"]),
            self.loyalty_settings(conn),
        )

    def _granted_points(self, conn, customer_id, lock=False):
        """Đợt 2: điểm tặng qua voucher MEMBER_POINTS; cộng vào điểm, không tính vào chi tiêu xét hạng."""
        return int(
            rows(
                conn,
                "SELECT COALESCE(SUM(points),0) AS points FROM loyalty_point_grants WHERE customer_id=%s"
                + (" FOR SHARE" if lock else ""),
                (customer_id,),
            )[0]["points"]
        )

    def loyalty_history(self, conn, customer_id, page=1, page_size=10):
        total = rows(
            conn,
            "SELECT COUNT(*) AS total FROM invoices WHERE customer_id=%s",
            (customer_id,),
        )[0]["total"]
        entries = rows(
            conn,
            "SELECT i.id,i.code,i.status,GREATEST(0,i.usage_cost-i.bonus_used) AS eligible_amount,"
            "CASE WHEN v.enabled THEN FLOOR(GREATEST(0,i.usage_cost-i.bonus_used)/v.unit_amount) ELSE 0 END AS points,"
            "v.unit_amount AS unit_amount,i.loyalty_rule_version AS rule_version,i.created_at,s.name AS store_name "
            "FROM invoices i JOIN loyalty_policy_versions v ON v.version=i.loyalty_rule_version "
            "JOIN stores s ON s.id=i.store_id WHERE i.customer_id=%s ORDER BY i.created_at DESC,i.id DESC LIMIT %s OFFSET %s",
            (customer_id, page_size, (page - 1) * page_size),
        )
        for item in entries:
            item["created_at"] = item["created_at"].replace(tzinfo=timezone.utc)
            item["effective_points"] = item["points"] if item["status"] == "PAID" else 0
        return dict(items=entries, total=total, page=page, page_size=page_size)

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
