"""Employee authentication data access."""

from dataclasses import dataclass, field
from cyberhub_manager.domain.dtos import EmployeeSession
from mysql.connector.pooling import PooledMySQLConnection
from cyberhub_manager.domain.enums import Role

@dataclass(frozen = True, slots = True)
class AuthRecord:
    """Authentication data for the service layer; never expose it to the UI."""
    session: EmployeeSession
    password_hash: str = field(repr = False)

class AuthRepository:
    def get_active_by_username(
        self,
        conn: PooledMySQLConnection,
        username: str,
    ) -> AuthRecord | None:
        """Return active employee credentials, or None if login is unavailable."""
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT
                    e.id AS employee_id,
                    e.code AS employee_code,
                    e.full_name,
                    e.username,
                    e.password_hash,
                    e.store_id,
                    e.role,
                    s.code AS store_code,
                    s.name AS store_name
                FROM employees AS e
                JOIN stores AS s ON s.id = e.store_id
                WHERE e.username = %s
                  AND e.status = 'ACTIVE'
                  AND s.status = 'ACTIVE'
                """,
                (username,),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()

        if row is None:
            return None

        session = EmployeeSession(
            employee_id = row["employee_id"],
            employee_code = row["employee_code"],
            full_name = row["full_name"],
            username = row["username"],
            store_id = row["store_id"],
            store_code = row["store_code"],
            store_name = row["store_name"],
            role = Role(row["role"]),
        )
        return AuthRecord(session = session, password_hash = row["password_hash"])