"""Usage session data access."""

from datetime import datetime, timezone
from mysql.connector.pooling import PooledMySQLConnection
from cyberhub_manager.domain.enums import SessionStatus
from cyberhub_manager.domain.models import UsageSession
from typing import Any, Mapping

class SessionRepository:
    def create(
        self,
        conn: PooledMySQLConnection,
        *,
        code: str,
        customer_id: int,
        machine_id: int,
        opened_by: int,
        started_at: datetime,
        hourly_rate: int,
    ) -> int:
        """Insert an active session without committing."""
        if started_at.tzinfo is None or started_at.utcoffset() is None:
            raise ValueError("started_at must be timezone-aware")

        # MySQL DATETIME has no timezone; the project stores UTC.
        started_at_utc = started_at.astimezone(timezone.utc).replace(tzinfo=None)

        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO usage_sessions
                    (code, customer_id, machine_id, opened_by,
                     started_at, hourly_rate)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    code,
                    customer_id,
                    machine_id,
                    opened_by,
                    started_at_utc,
                    hourly_rate,
                ),
            )
            session_id = cursor.lastrowid
            if not session_id:
                raise RuntimeError("Failed to retrieve the new session ID")
            return int(session_id)
        finally:
            cursor.close()
    def get_by_id(
        self,
        conn: PooledMySQLConnection,
        session_id: int,
        *,
        for_update: bool = False,
    ) -> UsageSession | None:
        """Return a session, optionally locking its row for an update."""
        query = """
            SELECT id, code, customer_id, machine_id, opened_by, closed_by,
                   started_at, ended_at, hourly_rate, cost, status
            FROM usage_sessions
            WHERE id = %s
        """
        if for_update:
            query += " FOR UPDATE"

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, (session_id,))
            row = cursor.fetchone()
        finally:
            cursor.close()

        if row is None:
            return None
        return self._to_model(row)

    def get_active_by_machine(
        self,
        conn: PooledMySQLConnection,
        machine_id: int,
        *,
        for_update: bool = False,
    ) -> UsageSession | None:
        """Return the active session of a machine, if any."""
        query = """
            SELECT id
            FROM usage_sessions
            WHERE machine_id = %s AND status = 'ACTIVE'
        """
        if for_update:
            query += " FOR UPDATE"

        cursor = conn.cursor(buffered = True)
        try:
            cursor.execute(query, (machine_id,))
            row = cursor.fetchone()
        finally:
            cursor.close()

        if row is None:
            return None
        return self.get_by_id(conn, row[0])
    def get_active_by_customer(
        self,
        conn: PooledMySQLConnection,
        customer_id: int,
        *,
        for_update: bool = False,
    ) -> UsageSession | None:
        """Return the active session of a customer, if any."""
        query = """
            SELECT id
            FROM usage_sessions
            WHERE customer_id = %s AND status = 'ACTIVE'
        """
        if for_update:
            query += " FOR UPDATE"

        cursor = conn.cursor(buffered = True)
        try:
            cursor.execute(query, (customer_id,))
            row = cursor.fetchone()
        finally:
            cursor.close()

        if row is None:
            return None
        return self.get_by_id(conn, row[0])
    def complete(
        self,
        conn: PooledMySQLConnection,
        session: UsageSession,
    ) -> bool:
        """Persist a completed session without committing."""
        if (
            session.status != SessionStatus.COMPLETED
            or session.closed_by is None
            or session.ended_at is None
            or session.cost is None
        ):
            raise ValueError("Session must be completed before persistence")

        ended_at_utc = (
            session.ended_at
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )

        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE usage_sessions
                SET closed_by = %s, ended_at = %s,
                    cost = %s, status = 'COMPLETED'
                WHERE id = %s AND status = 'ACTIVE'
                """,
                (
                    session.closed_by,
                    ended_at_utc,
                    session.cost,
                    session.id,
                ),
            )
            return cursor.rowcount == 1
        finally:
            cursor.close()

    @staticmethod
    def _to_model(row: Mapping[str, Any]) -> UsageSession:
        """Map a database row to a domain session."""
        return UsageSession (
            id = row["id"],
            code = row["code"],
            customer_id = row["customer_id"],
            machine_id = row["machine_id"],
            opened_by = row["opened_by"],
            closed_by = row["closed_by"],
            started_at = row["started_at"].replace(tzinfo=timezone.utc),
            ended_at = (
                row["ended_at"].replace(tzinfo=timezone.utc)
                if row["ended_at"] is not None else None
            ),
            hourly_rate = row["hourly_rate"],
            cost = row["cost"],
            status = SessionStatus(row["status"]),
        )
    def list_active_by_store(
        self,
        conn: PooledMySQLConnection,
        store_id: int,
    ) -> list[UsageSession]:
        """Return active sessions for machines in a store."""
        cursor = conn.cursor(dictionary = True)
        try:
            cursor.execute(
                """
                SELECT s.id, s.code, s.customer_id, s.machine_id,
                       s.opened_by, s.closed_by, s.started_at, s.ended_at,
                       s.hourly_rate, s.cost, s.status
                FROM usage_sessions AS s
                JOIN machines AS m ON m.id = s.machine_id
                WHERE m.store_id = %s AND s.status = 'ACTIVE'
                ORDER BY m.code, s.id
                """,
                (store_id,),
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return [self._to_model(row) for row in rows]
