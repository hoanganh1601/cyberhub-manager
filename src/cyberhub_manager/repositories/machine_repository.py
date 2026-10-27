"""Machine data access."""

from datetime import timezone

from mysql.connector.pooling import PooledMySQLConnection
from cyberhub_manager.domain.enums import MachineArchiveAction, MachineStatus
from cyberhub_manager.domain.exceptions import ConflictError
from cyberhub_manager.domain.models import Machine

class MachineRepository:
    def get_by_id(
        self,
        conn: PooledMySQLConnection,
        machine_id: int,
        *,
        for_update: bool = False,
    ) -> Machine | None:
        """Return a machine, optionally locking its row for an update."""
        query = """
            SELECT id, code, store_id, name, status,
                   hourly_rate, is_active, updated_at
            FROM machines
            WHERE id = %s
        """
        if for_update:
            query += " FOR UPDATE"

        cursor = conn.cursor(dictionary = True)
        try:
            cursor.execute(query, (machine_id,))
            row = cursor.fetchone()
        finally:
            cursor.close()

        if row is None:
            return None

        return Machine(
            id = row["id"],
            code = row["code"],
            store_id = row["store_id"],
            name = row["name"],
            status = MachineStatus(row["status"]),
            hourly_rate = row["hourly_rate"],
            is_active = bool(row["is_active"]),
            updated_at = row["updated_at"].replace(tzinfo=timezone.utc),
        )

    def create(
        self,
        conn: PooledMySQLConnection,
        *,
        code: str,
        store_id: int,
        name: str,
        hourly_rate: int,
    ) -> int:
        """Insert a machine and return its ID without committing."""
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO machines (code, store_id, name, hourly_rate)
                VALUES (%s, %s, %s, %s)
                """,
                (code, store_id, name, hourly_rate),
            )
            machine_id = cursor.lastrowid
            if not machine_id:
                raise RuntimeError("Failed to retrieve the new machine ID")
            return int(machine_id)
        finally:
            cursor.close()

    def list_by_store(
        self,
        conn: PooledMySQLConnection,
        store_id: int,
        *,
        include_archived: bool = False,
    ) -> list[Machine]:
        """List machines in a store without committing."""
        query = """
            SELECT id, code, store_id, name, status,
                   hourly_rate, is_active, updated_at
            FROM machines
            WHERE store_id = %s
        """
        if not include_archived:
            query += " AND is_active = TRUE"
        query += " ORDER BY code, id"

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, (store_id,))
            rows = cursor.fetchall()
        finally:
            cursor.close()

        return [
            Machine(
                id = row["id"],
                code = row["code"],
                store_id = row["store_id"],
                name = row["name"],
                status = MachineStatus(row["status"]),
                hourly_rate = row["hourly_rate"],
                is_active = bool(row["is_active"]),
                updated_at = row["updated_at"].replace(tzinfo=timezone.utc),
            )
            for row in rows
        ]

    def update_info(
        self,
        conn: PooledMySQLConnection,
        machine_id: int,
        *,
        name: str,
        hourly_rate: int,
    ) -> bool:
        """Update an active machine without committing."""
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE machines
                SET name = %s, hourly_rate = %s
                WHERE id = %s AND is_active = TRUE
                """,
                (name, hourly_rate, machine_id),
            )
            if cursor.rowcount == 1:
                return True

            # MySQL may report 0 changed rows when values are unchanged.
            cursor.execute(
                "SELECT 1 FROM machines WHERE id = %s AND is_active = TRUE",
                (machine_id,),
            )
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    def set_maintenance(
        self,
        conn: PooledMySQLConnection,
        machine_id: int,
        enabled: bool,
    ) -> bool:
        """Toggle maintenance for an active, unused machine without committing."""
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")

        target = (
            MachineStatus.MAINTENANCE
            if enabled
            else MachineStatus.AVAILABLE
        )
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE machines
                SET status = %s
                WHERE id = %s
                  AND is_active = TRUE
                  AND status <> 'IN_USE'
                """,
                (target.value, machine_id),
            )
            if cursor.rowcount == 1:
                return True

            # An unchanged status is still a successful, idempotent request.
            cursor.execute(
                """
                SELECT status FROM machines
                WHERE id = %s AND is_active = TRUE
                """,
                (machine_id,),
            )
            row = cursor.fetchone()
            return row is not None and row[0] == target.value
        finally:
            cursor.close()

    def has_session_history(
        self,
        conn: PooledMySQLConnection,
        machine_id: int,
    ) -> bool:
        """Return whether a machine has ever had a usage session."""
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT 1
                FROM usage_sessions
                WHERE machine_id = %s
                LIMIT 1
                """,
                (machine_id,),
            )
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    def archive_or_delete(
        self,
        conn: PooledMySQLConnection,
        machine_id: int,
    ) -> MachineArchiveAction | None:
        """Delete a history-free machine; otherwise archive it.

        The caller must use a transaction. This method does not commit.
        """
        cursor = conn.cursor(buffered = True)
        try:
            cursor.execute(
                "SELECT status FROM machines WHERE id = %s FOR UPDATE",
                (machine_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            if row[0] == MachineStatus.IN_USE.value:
                raise ConflictError("Machine is in use")

            # Also guard against inconsistent machine/session states.
            cursor.execute(
                """
                SELECT 1 FROM usage_sessions
                WHERE active_machine_id = %s
                LIMIT 1
                """,
                (machine_id,),
            )
            if cursor.fetchone() is not None:
                raise ConflictError("Machine has an active session")

            if self.has_session_history(conn, machine_id):
                cursor.execute(
                    "UPDATE machines SET is_active = FALSE WHERE id = %s",
                    (machine_id,),
                )
                return MachineArchiveAction.ARCHIVED

            cursor.execute(
                "DELETE FROM machines WHERE id = %s",
                (machine_id,),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Failed to delete the machine")
            return MachineArchiveAction.DELETED
        finally:
            cursor.close()
