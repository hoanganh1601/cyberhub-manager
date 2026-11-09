"""Single-host durable admission limits and metadata audit, never chat history.

All web workers must share this local persistent SQLite file. This adapter is
not a distributed limiter: multiple hosts need a shared database adapter before
enabling the feature. Accepted requests consume quota even on timeout/fallback.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3
from typing import Iterator

from .audit import AssistantAuditEvent
from .models import AIAccessContext


class AssistantQuotaExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__("assistant request limit exceeded")


@dataclass(frozen=True)
class AssistantLimits:
    per_minute: int = 10
    per_day: int = 100
    global_per_day: int = 1000
    retention_days: int = 30

    def __post_init__(self) -> None:
        for value in (self.per_minute, self.per_day, self.global_per_day, self.retention_days):
            if type(value) is not int or value <= 0:
                raise ValueError("assistant limits must be positive integers")


class SQLiteAssistantPolicyStore:
    def __init__(self, path: str | Path, *, limits: AssistantLimits | None = None) -> None:
        path = Path(path)
        if not path.is_absolute() or path.is_symlink():
            raise ValueError("assistant audit path must be an absolute regular file path")
        self.path = path
        self.limits = AssistantLimits() if limits is None else limits
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Create a private file before SQLite opens it; no raw text is stored.
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.close(fd)
        path.chmod(0o600)
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS assistant_requests (
                    request_id TEXT PRIMARY KEY,
                    actor_kind TEXT NOT NULL,
                    actor_id INTEGER NOT NULL,
                    actor_role TEXT NOT NULL,
                    store_ids TEXT NOT NULL,
                    language TEXT NOT NULL,
                    accepted_at INTEGER NOT NULL,
                    result TEXT NOT NULL,
                    chunk_ids TEXT NOT NULL DEFAULT '[]',
                    latency_ms INTEGER,
                    finished_at TEXT
                );
                CREATE INDEX IF NOT EXISTS assistant_requests_actor_time
                    ON assistant_requests(actor_kind, actor_id, accepted_at);
                CREATE INDEX IF NOT EXISTS assistant_requests_time
                    ON assistant_requests(accepted_at);
            """)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=2, isolation_level=None)
        try:
            conn.execute("PRAGMA synchronous=FULL")
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _identity(access: AIAccessContext) -> tuple[str, int, str, str, str]:
        return (
            "account" if access.role == "CUSTOMER" else "employee",
            access.actor_id, access.role, json.dumps(access.store_ids), access.language,
        )

    def reserve(self, request_id: str, access: AIAccessContext, *, now: datetime) -> None:
        """Atomically check all quotas and persist ACCEPTED before provider use."""
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("quota time must be timezone-aware")
        stamp = int(now.timestamp())
        minute, day = stamp // 60 * 60, stamp // 86400 * 86400
        identity = self._identity(access)
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    "DELETE FROM assistant_requests WHERE accepted_at < ?",
                    (day - self.limits.retention_days * 86400,),
                )
                actor_counts = conn.execute(
                    """SELECT COUNT(*), COALESCE(SUM(accepted_at >= ?), 0)
                       FROM assistant_requests
                       WHERE actor_kind = ? AND actor_id = ? AND accepted_at >= ?""",
                    (minute, identity[0], identity[1], day),
                ).fetchone()
                global_count = conn.execute(
                    "SELECT COUNT(*) FROM assistant_requests WHERE accepted_at >= ?", (day,),
                ).fetchone()[0]
                if actor_counts[1] >= self.limits.per_minute:
                    raise AssistantQuotaExceeded(minute + 60 - stamp)
                if actor_counts[0] >= self.limits.per_day or global_count >= self.limits.global_per_day:
                    raise AssistantQuotaExceeded(day + 86400 - stamp)
                conn.execute(
                    """INSERT INTO assistant_requests
                       (request_id, actor_kind, actor_id, actor_role, store_ids,
                        language, accepted_at, result) VALUES (?, ?, ?, ?, ?, ?, ?, 'ACCEPTED')""",
                    (request_id, *identity, stamp),
                )
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise

    def record(self, event: AssistantAuditEvent) -> None:
        access = AIAccessContext(event.actor_id, event.actor_role, event.store_ids, event.language)
        with self._connection() as conn:
            cursor = conn.execute(
                """UPDATE assistant_requests SET result = ?, chunk_ids = ?, latency_ms = ?,
                   finished_at = ? WHERE request_id = ? AND actor_kind = ? AND actor_id = ?
                   AND actor_role = ? AND store_ids = ? AND language = ? AND result = 'ACCEPTED'""",
                (event.result, json.dumps(event.retrieved_chunk_ids), event.latency_ms,
                 event.created_at.isoformat(), event.request_id, *self._identity(access)),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("assistant audit admission is absent or already completed")

    def result(self, request_id: str) -> str | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT result FROM assistant_requests WHERE request_id = ?", (request_id,),
            ).fetchone()
        return row[0] if row else None

    def suppress(self, request_id: str) -> None:
        """Do not retain successful source metadata after identity revalidation fails."""
        with self._connection() as conn:
            conn.execute(
                "UPDATE assistant_requests SET result = 'ACCESS_CHANGED', chunk_ids = '[]' WHERE request_id = ?",
                (request_id,),
            )
