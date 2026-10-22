"""Customer data access."""

from mysql.connector.pooling import PooledMySQLConnection
from cyberhub_manager.domain.enums import AccountStatus, CustomerStatus
from cyberhub_manager.domain.models import Account, Customer
from cyberhub_manager.domain.dtos import CustomerSummary

class CustomerRepository:
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
                    a.status AS account_status
                FROM customers AS c
                JOIN accounts AS a ON a.customer_id = c.id
                WHERE c.code LIKE %s
                   OR c.full_name LIKE %s
                   OR c.phone LIKE %s
                   OR a.username LIKE %s
                ORDER BY c.id DESC
                LIMIT 50
                """,
                (pattern, pattern, pattern, pattern),
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
            )
            for row in rows
        ]