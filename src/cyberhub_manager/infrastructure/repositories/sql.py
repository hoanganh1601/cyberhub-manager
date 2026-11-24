"""Small cursor helpers shared by MySQL repositories.

Transaction ownership remains in the service layer.  These helpers only execute
parameterized statements on the connection supplied by the caller and always
close their cursor.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timezone
from typing import Any


def rows(conn: Any, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()


def execute(conn: Any, sql: str, params: Sequence[Any] = ()) -> int:
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        return cursor.lastrowid or cursor.rowcount
    finally:
        cursor.close()


def utc(value: Any) -> Any:
    """Attach UTC to a naive timestamp returned by the configured MySQL session."""

    return value.replace(tzinfo=timezone.utc)
