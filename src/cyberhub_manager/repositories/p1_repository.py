"""Parameterized P1 persistence. Callers own the transaction and authorization."""

from datetime import timezone
from .portal_repository import PortalRepositoryMixin

from cyberhub_manager.domain.p1 import (
    CustomerSession,
    EmployeeSummary,
    Promotion,
    StoreSummary,
)


def rows(conn, sql, params=()):
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()


def execute(conn, sql, params=()):
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        return cursor.lastrowid or cursor.rowcount
    finally:
        cursor.close()


def utc(value):
    return value.replace(tzinfo=timezone.utc)


class P1Repository(PortalRepositoryMixin):
    def customer_invoice(self, conn, principal, invoice_id):
        from cyberhub_manager.domain.exceptions import NotFoundError
        from cyberhub_manager.domain.dtos import InvoiceDetail, SessionSummary
        from .invoice_repository import InvoiceRepository
        from .session_repository import SessionRepository
        from .machine_repository import MachineRepository
        from .customer_repository import CustomerRepository

        summary = InvoiceRepository().get_summary_by_id(conn, invoice_id)
        if summary is None or summary.customer_id != principal.customer_id:
            raise NotFoundError()
        usage = SessionRepository().get_by_id(conn, summary.session_id)
        machine = MachineRepository().get_by_id(conn, usage.machine_id)
        customer = CustomerRepository().get_by_id(conn, summary.customer_id)
        session = SessionSummary(
            usage.id,
            usage.code,
            customer.id,
            customer.code,
            customer.full_name,
            machine.id,
            machine.code,
            machine.name,
            usage.started_at,
            usage.hourly_rate,
            usage.status,
        )
        return InvoiceDetail(
            summary,
            session,
            usage.ended_at,
            usage.calculate_billed_minutes(usage.ended_at),
        )

    def list_stores(self, conn, store_id=None):
        return [
            StoreSummary(**r)
            for r in rows(
                conn,
                "SELECT id,code,name,address,status FROM stores"
                + (" WHERE id=%s" if store_id else "")
                + " ORDER BY code",
                (store_id,) if store_id else (),
            )
        ]

    def store(self, conn, store_id, lock=False):
        result = rows(
            conn,
            "SELECT id,code,name,address,status FROM stores WHERE id=%s"
            + (
                " FOR UPDATE"
                if lock is True
                else " FOR SHARE" if lock == "share" else ""
            ),
            (store_id,),
        )
        return StoreSummary(**result[0]) if result else None

    def save_store(self, conn, store_id, code, name, address, status):
        if store_id is None:
            store_id = execute(
                conn,
                "INSERT INTO stores(code,name,address,status) VALUES(%s,%s,%s,%s)",
                (code, name, address, status),
            )
        else:
            execute(
                conn,
                "UPDATE stores SET code=%s,name=%s,address=%s,status=%s WHERE id=%s",
                (code, name, address, status, store_id),
            )
        return self.store(conn, store_id)

    def has_active_sessions(self, conn, store_id):
        return bool(
            rows(
                conn,
                "SELECT u.id FROM usage_sessions u JOIN machines m ON m.id=u.machine_id WHERE m.store_id=%s AND u.status='ACTIVE' LIMIT 1",
                (store_id,),
            )
        )

    def list_employees(self, conn, store_id=None, lock=False):
        return [
            EmployeeSummary(**r)
            for r in rows(
                conn,
                "SELECT id,code,store_id,full_name,username,role,status FROM employees"
                + (" WHERE store_id=%s" if store_id else "")
                + " ORDER BY id"
                + (" FOR UPDATE" if lock else ""),
                (store_id,) if store_id else (),
            )
        ]

    def save_employee(self, conn, employee_id, values, password_hash):
        store_id, name, username, role, status = values
        if employee_id is None:
            from uuid import uuid4

            employee_id = execute(
                conn,
                "INSERT INTO employees(code,store_id,full_name,username,password_hash,role,status) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (
                    "NV-" + uuid4().hex[:17],
                    store_id,
                    name,
                    username,
                    password_hash,
                    role,
                    status,
                ),
            )
        else:
            execute(
                conn,
                "UPDATE employees SET store_id=%s,full_name=%s,username=%s,role=%s,status=%s WHERE id=%s",
                (*values, employee_id),
            )
            if password_hash:
                execute(
                    conn,
                    "UPDATE employees SET password_hash=%s WHERE id=%s",
                    (password_hash, employee_id),
                )
        return next(e for e in self.list_employees(conn) if e.id == employee_id)

    def list_promotions(self, conn, store_id=None, lock=False):
        result = rows(
            conn,
            "SELECT id,code,name,store_id,minimum_amount,bonus_percent,starts_at,ends_at,is_active FROM promotions"
            + (" WHERE store_id=%s OR store_id IS NULL" if store_id else "")
            + " ORDER BY minimum_amount DESC,id DESC"
            + (" FOR UPDATE" if lock else ""),
            (store_id,) if store_id else (),
        )
        return [
            Promotion(
                **{
                    **r,
                    "starts_at": utc(r["starts_at"]),
                    "ends_at": utc(r["ends_at"]),
                    "is_active": bool(r["is_active"]),
                }
            )
            for r in result
        ]

    def save_promotion(self, conn, policy):
        fields = (
            policy.code,
            policy.name,
            policy.store_id,
            policy.minimum_amount,
            policy.bonus_percent,
            policy.starts_at.astimezone(timezone.utc).replace(tzinfo=None),
            policy.ends_at.astimezone(timezone.utc).replace(tzinfo=None),
            policy.is_active,
        )
        if policy.id:
            execute(
                conn,
                "UPDATE promotions SET code=%s,name=%s,store_id=%s,minimum_amount=%s,bonus_percent=%s,starts_at=%s,ends_at=%s,is_active=%s WHERE id=%s",
                (*fields, policy.id),
            )
            entity_id = policy.id
        else:
            entity_id = execute(
                conn,
                "INSERT INTO promotions(code,name,store_id,minimum_amount,bonus_percent,starts_at,ends_at,is_active) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                fields,
            )
        return next(p for p in self.list_promotions(conn) if p.id == entity_id)

    def audit(self, conn, actor, action, entity_id):
        execute(
            conn,
            "INSERT INTO management_audit(employee_id,store_id,action,entity_id) VALUES(%s,%s,%s,%s)",
            (actor.employee_id, actor.store_id, action, entity_id),
        )

    def customer_credentials(self, conn, *, username=None, account_id=None):
        column, value = (
            ("a.username", username) if username is not None else ("a.id", account_id)
        )
        result = rows(
            conn,
            "SELECT c.id AS customer_id,a.id AS account_id,c.full_name,a.username,a.password_hash "
            "FROM accounts a JOIN customers c ON c.id=a.customer_id WHERE "
            + column
            + "=%s AND a.status='ACTIVE' AND c.status='ACTIVE'",
            (value,),
        )
        if not result:
            return None
        r = result[0]
        return (
            CustomerSession(
                r["customer_id"], r["account_id"], r["full_name"], r["username"]
            ),
            r["password_hash"],
        )

    def customer_snapshot(self, conn, principal):
        account_id, customer_id = principal.account_id, principal.customer_id
        wallet = rows(
            conn,
            "SELECT a.code AS account_code,a.balance,a.bonus_balance,a.cash_balance,c.phone FROM accounts a JOIN customers c ON c.id=a.customer_id WHERE a.id=%s",
            (account_id,),
        )[0]
        history = rows(
            conn,
            "SELECT t.code,t.type,t.amount,t.method,t.created_at,s.name AS store_name FROM account_transactions t "
            "LEFT JOIN stores s ON s.id=t.store_id WHERE t.account_id=%s ORDER BY t.created_at DESC,t.id DESC LIMIT 100",
            (account_id,),
        )
        sessions = rows(
            conn,
            "SELECT u.code,m.code AS machine_code,s.name AS store_name,u.started_at,u.ended_at,u.hourly_rate,u.status,u.cost "
            "FROM usage_sessions u JOIN machines m ON m.id=u.machine_id JOIN stores s ON s.id=m.store_id "
            "WHERE u.customer_id=%s ORDER BY u.id DESC LIMIT 100",
            (customer_id,),
        )
        invoices = rows(
            conn,
            "SELECT i.id,i.code,i.usage_cost,i.settlement_amount,i.bonus_used,i.status,i.created_at,s.name AS store_name "
            "FROM invoices i JOIN stores s ON s.id=i.store_id WHERE i.customer_id=%s ORDER BY i.id DESC LIMIT 100",
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
