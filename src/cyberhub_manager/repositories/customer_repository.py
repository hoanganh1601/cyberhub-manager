"""Customer data access."""

from mysql.connector.pooling import PooledMySQLConnection
from cyberhub_manager.domain.enums import AccountStatus, CustomerStatus
from cyberhub_manager.domain.models import Account, Customer
from cyberhub_manager.domain.dtos import CustomerSummary
from .sql import execute, rows

class CustomerRepository:
    def customer_id_by_code_phone(self, conn, code, phone):
        found = rows(conn, "SELECT id FROM customers WHERE code=%s AND phone=%s", (code,phone))
        return found[0]["id"] if found else None
    def link_store(self, conn, customer_id, store_id, source):
        execute(conn, "INSERT IGNORE INTO customer_store_links(customer_id,store_id,source) "
                "VALUES(%s,%s,%s)", (customer_id,store_id,source))

    def has_store_link(self, conn, customer_id, store_id):
        return bool(rows(conn, "SELECT customer_id FROM customer_store_links "
                         "WHERE customer_id=%s AND store_id=%s", (customer_id,store_id)))

    def audit_store_link(self, conn, employee_id, store_id, customer_id):
        execute(conn, "INSERT INTO management_audit(employee_id,store_id,action,entity_id) "
                "VALUES(%s,%s,'CUSTOMER_STORE_LINK',%s)",
                (employee_id,store_id,customer_id))
    def create(
        self,
        conn: PooledMySQLConnection,
        *,
        code: str,
        full_name: str,
        phone: str,
    ) -> int:
        """Insert a customer and return its ID without committing."""
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO customers (code, full_name, phone)
                VALUES (%s, %s, %s)
                """,
                (code, full_name, phone),
            )
            customer_id = cursor.lastrowid
            if not customer_id:
                raise RuntimeError("Failed to retrieve the new customer ID")
            return int(customer_id)
        finally:
            cursor.close()
    def get_by_id(
        self, conn: PooledMySQLConnection, customer_id: int
    ) -> Customer | None:
        """Return a customer with its account, or None if not found."""
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT
                    c.id AS customer_id,
                    c.code AS customer_code,
                    c.full_name,
                    c.phone,
                    c.status AS customer_status,
                    a.id AS account_id,
                    a.code AS account_code,
                    a.username,
                    a.balance,
                    a.bonus_balance,
                    a.status AS account_status
                FROM customers AS c
                JOIN accounts AS a ON a.customer_id = c.id
                WHERE c.id = %s
                """,
                (customer_id,),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()

        if row is None:
            return None

        account = Account(
            id = row["account_id"],
            code = row["account_code"],
            customer_id = row["customer_id"],
            username = row["username"],
            balance = row["balance"],
            status = AccountStatus(row["account_status"]),
            bonus_balance = row.get("bonus_balance",0),
        )
        return Customer(
            id = row["customer_id"],
            code = row["customer_code"],
            full_name = row["full_name"],
            phone = row["phone"],
            status = CustomerStatus(row["customer_status"]),
            account = account,
        )
    def update_profile(
            self,
            conn: PooledMySQLConnection,
            customer_id: int,
            *,
            full_name: str,
            phone: str,
        ) -> bool:
            """Update customer profile without committing."""
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    UPDATE customers
                    SET full_name = %s, phone = %s
                    WHERE id = %s
                    """,
                    (full_name, phone, customer_id),
                )
                return cursor.rowcount == 1
            finally:
                cursor.close()
    def set_status(
        self,
        conn: PooledMySQLConnection,
        customer_id: int,
        status: CustomerStatus,
    ) -> bool:
        """Change customer status without committing."""
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE customers SET status = %s WHERE id = %s",
                (status.value, customer_id),
            )
            return cursor.rowcount == 1
        finally:
            cursor.close()
    def search(
        self,
        conn: PooledMySQLConnection,
        keyword: str,
        store_id: int | None = None,
    ) -> list[CustomerSummary]:
        """Search customers by code, name, phone, or username."""
        pattern = f"%{keyword.strip()}%"

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT
                    c.id AS customer_id,
                    c.code AS customer_code,
                    c.full_name,
                    c.phone,
                    c.status AS customer_status,
                    a.id AS account_id,
                    a.username,
                    a.balance,
                    a.bonus_balance,
                    a.status AS account_status
                FROM customers AS c
                JOIN accounts AS a ON a.customer_id = c.id
                WHERE (%s IS NULL OR EXISTS(SELECT 1 FROM customer_store_links l
                       WHERE l.customer_id=c.id AND l.store_id=%s))
                  AND (c.code LIKE %s
                   OR c.full_name LIKE %s
                   OR c.phone LIKE %s
                   OR a.username LIKE %s)
                ORDER BY c.id DESC
                LIMIT 50
                """,
                (store_id, store_id, pattern, pattern, pattern, pattern),
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()

        return [
            CustomerSummary(
                customer_id = row["customer_id"],
                customer_code = row["customer_code"],
                full_name = row["full_name"],
                phone = row["phone"],
                account_id = row["account_id"],
                username = row["username"],
                balance = row["balance"],
                customer_status = CustomerStatus(row["customer_status"]),
                account_status = AccountStatus(row["account_status"]),
                bonus_balance = row.get("bonus_balance",0),
            )
            for row in rows
        ]
