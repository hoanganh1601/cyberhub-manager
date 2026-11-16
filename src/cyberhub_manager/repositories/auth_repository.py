"""Employee authentication data access."""

from dataclasses import dataclass, field
from cyberhub_manager.domain.dtos import EmployeeSession
from mysql.connector.pooling import PooledMySQLConnection
from cyberhub_manager.domain.enums import Role

"""Return a session only when the employee and store are active"""
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
                    e.auth_version,
                    e.must_change_password,
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
            auth_version = int(row["auth_version"]),
            credential_update_required = bool(row["must_change_password"]),
        )
        return AuthRecord(session = session, password_hash = row["password_hash"])

    def get_active_session_by_id(
        self,
        conn: PooledMySQLConnection,
        employee_id: int,
    ) -> EmployeeSession | None:
        """Return active employee session, or None if login is unavailable."""
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT
                    e.id AS employee_id,
                    e.code AS employee_code,
                    e.full_name,
                    e.username,
                    e.store_id,
                    e.role,
                    e.auth_version,
                    e.must_change_password,
                    s.code AS store_code,
                    s.name AS store_name
                FROM employees AS e
                JOIN stores AS s ON s.id = e.store_id
                WHERE e.id = %s
                  AND e.status = 'ACTIVE'
                  AND s.status = 'ACTIVE'
                FOR SHARE
                """,
                (employee_id,),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()

        if row is None:
            return None

        return EmployeeSession(
            employee_id = row["employee_id"],
            employee_code = row["employee_code"],
            full_name = row["full_name"],
            username = row["username"],
            store_id = row["store_id"],
            store_code = row["store_code"],
            store_name = row["store_name"],
            role = Role(row["role"]),
            auth_version = int(row["auth_version"]),
            credential_update_required = bool(row["must_change_password"]),
        )

    def get_active_record_by_id(self, conn, employee_id: int) -> AuthRecord | None:
        """Return current credentials for an authenticated employee."""
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT e.id AS employee_id,e.code AS employee_code,e.full_name,
                       e.username,e.password_hash,e.store_id,e.role,
                       e.auth_version,e.must_change_password,
                       s.code AS store_code,s.name AS store_name
                FROM employees e JOIN stores s ON s.id=e.store_id
                WHERE e.id=%s AND e.status='ACTIVE' AND s.status='ACTIVE'
                FOR UPDATE
                """,
                (employee_id,),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            return None
        return AuthRecord(
            session=EmployeeSession(
                employee_id=row["employee_id"], employee_code=row["employee_code"],
                full_name=row["full_name"], username=row["username"],
                store_id=row["store_id"], store_code=row["store_code"],
                store_name=row["store_name"], role=Role(row["role"]),
                auth_version=int(row["auth_version"]),
                credential_update_required=bool(row["must_change_password"]),
            ),
            password_hash=row["password_hash"],
        )

    def change_password(self, conn, employee_id: int, password_hash: str) -> None:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """UPDATE employees
                   SET password_hash=%s,auth_version=auth_version+1,
                       must_change_password=FALSE,password_changed_at=CURRENT_TIMESTAMP
                   WHERE id=%s""",
                (password_hash, employee_id),
            )
        finally:
            cursor.close()
