"""Customer account data access."""

from datetime import timezone
from mysql.connector.pooling import PooledMySQLConnection
from cyberhub_manager.domain.enums import AccountStatus, PaymentMethod, TransactionType
from cyberhub_manager.domain.models import Account
from cyberhub_manager.domain.dtos import TransactionSummary

class AccountRepository:
    def create(
        self,
        conn: PooledMySQLConnection,
        *,
        code: str,
        customer_id: int,
        username: str,
        password_hash: str,
    ) -> int:
        """Insert an account and return its ID without committing."""
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO accounts
                    (code, customer_id, username, password_hash)
                VALUES (%s, %s, %s, %s)
                """,
                (code, customer_id, username, password_hash),
            )
            account_id = cursor.lastrowid
            if not account_id:
                raise RuntimeError("Failed to retrieve the new account ID")
            return int(account_id)
        finally:
            cursor.close()

    def get_by_id(
        self,
        conn: PooledMySQLConnection,
        account_id: int,
        *,
        for_update: bool = False,
    ) -> Account | None:
        """Return an account, optionally locking its row for an update."""
        query = """
            SELECT id, code, customer_id, username, balance, status
            FROM accounts
            WHERE id = %s
        """
        if for_update:
            query += " FOR UPDATE"

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, (account_id,))
            row = cursor.fetchone()
        finally:
            cursor.close()

        if row is None:
            return None

        return Account(
            id = row["id"],
            code = row["code"],
            customer_id = row["customer_id"],
            username = row["username"],
            balance = row["balance"],
            status = AccountStatus(row["status"]),
        )

    def set_status(
        self,
        conn: PooledMySQLConnection,
        account_id: int,
        status: AccountStatus,
    ) -> bool:
        """Change account status without committing."""
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE accounts SET status = %s WHERE id = %s",
                (status.value, account_id),
            )
            return cursor.rowcount == 1
        finally:
            cursor.close()

    def credit_balance(
        self,
        conn: PooledMySQLConnection,
        account_id: int,
        amount: int,
    ) -> bool:
        """Add a positive amount to the balance without committing."""
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ValueError("Amount must be a positive integer")

        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE accounts
                SET balance = balance + %s
                WHERE id = %s
                """,
                (amount, account_id),
            )
            return cursor.rowcount == 1
        finally:
            cursor.close()

    def insert_top_up_transaction(
        self,
        conn: PooledMySQLConnection,
        *,
        code: str,
        account_id: int,
        employee_id: int,
        amount: int,
        method: PaymentMethod,
    ) -> int:
        """Record a top-up without committing."""
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ValueError("Amount must be a positive integer")
        if method not in (PaymentMethod.CASH, PaymentMethod.TRANSFER):
            raise ValueError("Top-up method must be CASH or TRANSFER")

        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO account_transactions
                    (code, account_id, employee_id, type, amount, method)
                VALUES (%s, %s, %s, 'TOP_UP', %s, %s)
                """,
                (code, account_id, employee_id, amount, method.value),
            )
            transaction_id = cursor.lastrowid
            if not transaction_id:
                raise RuntimeError("Failed to retrieve the new transaction ID")
            return int(transaction_id)
        finally:
            cursor.close()

    def list_transactions(
        self,
        conn: PooledMySQLConnection,
        account_id: int,
        *,
        limit: int = 50,
    ) -> list[TransactionSummary]:
        """Return the most recent transactions for an account."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("Limit must be an integer from 1 to 100")

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT
                    t.id AS transaction_id,
                    t.code AS transaction_code,
                    t.account_id,
                    t.session_id,
                    t.type,
                    t.amount,
                    t.method,
                    t.employee_id,
                    e.full_name AS employee_name,
                    t.created_at
                FROM account_transactions AS t
                JOIN employees AS e ON e.id = t.employee_id
                WHERE t.account_id = %s
                ORDER BY t.created_at DESC, t.id DESC
                LIMIT %s
                """,
                (account_id, limit),
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()

        return [
            TransactionSummary(
                transaction_id = row["transaction_id"],
                transaction_code = row["transaction_code"],
                account_id = row["account_id"],
                session_id = row["session_id"],
                type = TransactionType(row["type"]),
                amount = row["amount"],
                method = PaymentMethod(row["method"]),
                employee_id = row["employee_id"],
                employee_name = row["employee_name"],
                created_at = row["created_at"].replace(tzinfo = timezone.utc),
            )
            for row in rows
        ]

    def insert_usage_payment_transaction(
        self,
        conn: PooledMySQLConnection,
        *,
        code: str,
        account_id: int,
        employee_id: int,
        session_id: int,
        usage_cost: int,
    ) -> int:
        """Record a session charge without committing."""
        if isinstance(usage_cost, bool) or not isinstance(usage_cost, int) or usage_cost <= 0:
            raise ValueError("Usage cost must be a positive integer")

        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO account_transactions
                    (code, account_id, employee_id, session_id,
                     type, amount, method)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    code,
                    account_id,
                    employee_id,
                    session_id,
                    TransactionType.USAGE_PAYMENT.value,
                    -usage_cost,
                    PaymentMethod.ACCOUNT_BALANCE.value,
                ),
            )
            transaction_id = cursor.lastrowid
            if not transaction_id:
                raise RuntimeError("Failed to retrieve the new transaction ID")
            return int(transaction_id)
        finally:
            cursor.close()

    def insert_debt_settlement_transaction(
        self,
        conn: PooledMySQLConnection,
        *,
        code: str,
        account_id: int,
        employee_id: int,
        session_id: int,
        settlement_amount: int,
        method: PaymentMethod,
    ) -> int:
        """Record a cash or transfer settlement without committing."""
        if (
            isinstance(settlement_amount, bool)
            or not isinstance(settlement_amount, int)
            or settlement_amount <= 0
        ):
            raise ValueError("Settlement amount must be a positive integer")
        if method not in (PaymentMethod.CASH, PaymentMethod.TRANSFER):
            raise ValueError("Settlement method must be CASH or TRANSFER")

        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO account_transactions
                    (code, account_id, employee_id, session_id,
                     type, amount, method)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    code,
                    account_id,
                    employee_id,
                    session_id,
                    TransactionType.DEBT_SETTLEMENT.value,
                    settlement_amount,
                    method.value,
                ),
            )
            transaction_id = cursor.lastrowid
            if not transaction_id:
                raise RuntimeError("Failed to retrieve the new transaction ID")
            return int(transaction_id)
        finally:
            cursor.close()

