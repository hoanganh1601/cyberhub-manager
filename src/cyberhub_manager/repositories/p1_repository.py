"""Compatibility facade for portal, loyalty, and management persistence."""

from cyberhub_manager.domain.p1 import CustomerSession

from .loyalty_repository import LoyaltyRepositoryMixin
from .management_repository import ManagementRepositoryMixin
from .portal_repository import PortalRepositoryMixin
from .sql import execute, rows, utc

# ``execute`` and ``rows`` remain imported here for compatibility with scripts
# and integration fixtures. New repository code imports them from ``.sql``.


class P1Repository(
    ManagementRepositoryMixin,
    PortalRepositoryMixin,
    LoyaltyRepositoryMixin,
):
    """Stable facade retained while capability-specific repositories evolve."""

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
            "SELECT a.code AS account_code,a.balance,a.bonus_balance,a.cash_balance,c.phone "
            "FROM accounts a JOIN customers c ON c.id=a.customer_id WHERE a.id=%s",
            (account_id,),
        )[0]
        history = rows(
            conn,
            "SELECT t.code,t.type,t.amount,t.method,t.created_at,s.name AS store_name "
            "FROM account_transactions t LEFT JOIN stores s ON s.id=t.store_id "
            "WHERE t.account_id=%s ORDER BY t.created_at DESC,t.id DESC LIMIT 100",
            (account_id,),
        )
        sessions = rows(
            conn,
            "SELECT u.code,m.code AS machine_code,s.name AS store_name,u.started_at,u.ended_at,"
            "u.hourly_rate,u.status,u.cost FROM usage_sessions u "
            "JOIN machines m ON m.id=u.machine_id JOIN stores s ON s.id=m.store_id "
            "WHERE u.customer_id=%s ORDER BY u.id DESC LIMIT 100",
            (customer_id,),
        )
        invoices = rows(
            conn,
            "SELECT i.id,i.code,i.usage_cost,i.settlement_amount,i.bonus_used,i.status,"
            "i.created_at,s.name AS store_name FROM invoices i "
            "JOIN stores s ON s.id=i.store_id WHERE i.customer_id=%s "
            "ORDER BY i.id DESC LIMIT 100",
            (customer_id,),
        )
        for group in (history, sessions, invoices):
            for row in group:
                for key, value in row.items():
                    if hasattr(value, "tzinfo") and value.tzinfo is None:
                        row[key] = utc(value)
        return {
            "profile": principal,
            "wallet": wallet,
            "transactions": history,
            "sessions": sessions,
            "invoices": invoices,
        }
