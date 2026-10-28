"""Invoice and revenue data access."""
from datetime import timezone, datetime
from cyberhub_manager.domain.models import Invoice
from mysql.connector.pooling import PooledMySQLConnection
from cyberhub_manager.domain.enums import InvoiceStatus
from cyberhub_manager.domain.dtos import InvoiceSummary, DailyRevenue

def _to_mysql_utc(value: datetime, field: str) -> datetime:
    """Convert an aware datetime to UTC for MySQL DATETIME columns."""
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc).replace(tzinfo = None)

class InvoiceRepository:
    def create(
        self,
        conn: PooledMySQLConnection,
        *,
        code: str,
        session_id: int,
        customer_id: int,
        employee_id: int,
        store_id: int,
        usage_cost: int,
        settlement_amount: int,
    ) -> int:
        """Insert a paid invoice without committing."""
        for name, value in (
            ("usage_cost", usage_cost),
            ("settlement_amount", settlement_amount),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if settlement_amount > usage_cost:
            raise ValueError("Settlement cannot exceed usage cost")

        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO invoices
                    (code, session_id, customer_id, employee_id, store_id,
                     usage_cost, settlement_amount, total_amount, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    code,
                    session_id,
                    customer_id,
                    employee_id,
                    store_id,
                    usage_cost,
                    settlement_amount,
                    usage_cost,
                    InvoiceStatus.PAID.value,
                ),
            )
            invoice_id = cursor.lastrowid
            if not invoice_id:
                raise RuntimeError("Failed to retrieve the new invoice ID")
            return int(invoice_id)
        finally:
            cursor.close()

    def get_by_id (
        self,
        conn: PooledMySQLConnection,
        invoice_id: int,
    ) -> Invoice | None:
        """Return an invoice by ID, or None if it does not exist."""
        cursor = conn.cursor(dictionary = True)
        try:
            cursor.execute(
                """
                SELECT id, code, session_id, customer_id, employee_id,
                       store_id, usage_cost, settlement_amount,
                       total_amount, status, created_at
                FROM invoices
                WHERE id = %s
                """,
                (invoice_id,),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()

        if row is None:
            return None

        return Invoice (
            id = row["id"],
            code = row["code"],
            session_id = row["session_id"],
            customer_id = row["customer_id"],
            employee_id = row["employee_id"],
            store_id = row["store_id"],
            usage_cost = row["usage_cost"],
            settlement_amount = row["settlement_amount"],
            total_amount = row["total_amount"],
            status = InvoiceStatus(row["status"]),
            created_at = row["created_at"].replace(tzinfo=timezone.utc),
        )

    def list_by_store(
        self,
        conn: PooledMySQLConnection,
        store_id: int,
        *,
        created_from_utc: datetime | None = None,
        created_before_utc: datetime | None = None,
        keyword: str = "",
        customer_id: int | None = None,
        status: InvoiceStatus | None = None,
    ) -> list[InvoiceSummary]:
        """List invoices for one store using optional filters."""
        conditions = ["i.store_id = %s"]
        params: list[object] = [store_id]

        if created_from_utc is not None:
            conditions.append("i.created_at >= %s")
            params.append(_to_mysql_utc(created_from_utc, "created_from_utc"))
        if created_before_utc is not None:
            conditions.append("i.created_at < %s")
            params.append(_to_mysql_utc(created_before_utc, "created_before_utc"))
        if customer_id is not None:
            conditions.append("i.customer_id = %s")
            params.append(customer_id)
        if status is not None:
            conditions.append("i.status = %s")
            params.append(status.value)
        if keyword.strip():
            conditions.append("(i.code LIKE %s OR c.full_name LIKE %s)")
            pattern = f"%{keyword.strip()}%"
            params.extend((pattern, pattern))

        query = f"""
            SELECT i.id AS invoice_id, i.code AS invoice_code,
                   i.session_id, i.customer_id,
                   c.full_name AS customer_name,
                   i.employee_id, e.full_name AS employee_name,
                   i.store_id, st.name AS store_name,
                   i.usage_cost, i.settlement_amount, i.total_amount,
                   i.status, i.created_at
            FROM invoices AS i
            JOIN customers AS c ON c.id = i.customer_id
            JOIN employees AS e ON e.id = i.employee_id
            JOIN stores AS st ON st.id = i.store_id
            WHERE {" AND ".join(conditions)}
            ORDER BY i.created_at DESC, i.id DESC
        """

        cursor = conn.cursor(dictionary = True)
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        finally:
            cursor.close()

        return [
            InvoiceSummary(
                invoice_id = row["invoice_id"],
                invoice_code = row["invoice_code"],
                session_id = row["session_id"],
                customer_id = row["customer_id"],
                customer_name = row["customer_name"],
                employee_id = row["employee_id"],
                employee_name = row["employee_name"],
                store_id = row["store_id"],
                store_name = row["store_name"],
                usage_cost = row["usage_cost"],
                settlement_amount = row["settlement_amount"],
                total_amount = row["total_amount"],
                status = InvoiceStatus(row["status"]),
                created_at = row["created_at"].replace(tzinfo=timezone.utc),
            )
            for row in rows
        ]

    def daily_revenue_by_store(
        self,
        conn: PooledMySQLConnection,
        store_id: int,
        *,
        created_from_utc: datetime,
        created_before_utc: datetime,
    ) -> list[DailyRevenue]:
        """Summarize PAID invoice usage cost by Vietnam local date."""
        start = _to_mysql_utc(created_from_utc, "created_from_utc")
        end = _to_mysql_utc(created_before_utc, "created_before_utc")

        if start >= end:
            raise ValueError("created_from_utc must be earlier than created_before_utc")

        cursor = conn.cursor(dictionary = True)
        try:
            cursor.execute(
                """
                SELECT
                    DATE(DATE_ADD(i.created_at, INTERVAL 7 HOUR)) AS local_day,
                    COUNT(*) AS invoice_count,
                    SUM(i.usage_cost) AS revenue
                FROM invoices AS i
                WHERE i.store_id = %s
                  AND i.status = %s
                  AND i.created_at >= %s
                  AND i.created_at < %s
                GROUP BY local_day
                ORDER BY local_day
                """,
                (store_id, InvoiceStatus.PAID.value, start, end),
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()

        return [
            DailyRevenue(
                date = row["local_day"],
                invoice_count = int(row["invoice_count"]),
                revenue = int(row["revenue"]),
            )
            for row in rows
        ]
