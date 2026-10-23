"""Employee data access used by authentication and authorization services."""

from mysql.connector.pooling import PooledMySQLConnection

from cyberhub_manager.domain.enums import EmployeeStatus, Role
from cyberhub_manager.domain.models import Employee


class AuthRepository:
    """Read employee records without exposing password hashes."""

    def get_by_id(
        self, conn: PooledMySQLConnection, employee_id: int
    ) -> Employee | None:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT id, code, store_id, full_name, username, role, status
                FROM employees
                WHERE id = %s
                """,
                (employee_id,),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()

        if row is None:
            return None

        return Employee(
            id=row["id"],
            code=row["code"],
            full_name=row["full_name"],
            store_id=row["store_id"],
            username=row["username"],
            role=Role(row["role"]),
            status=EmployeeStatus(row["status"]),
        )

