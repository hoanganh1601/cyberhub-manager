"""Đợt 4 — Truy cập dữ liệu quảng cáo nhận thưởng (MySQL). Không tự commit."""

from __future__ import annotations

from datetime import timezone
from typing import Any

from cyberhub_manager.domain.ad import (
    AdCreative,
    AdEvent,
    AdMode,
    AdRewardType,
    AdSettings,
    AdStatus,
)
from cyberhub_manager.repositories.p1_repository import execute, rows


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def _naive(value):
    return None if value is None else value.astimezone(timezone.utc).replace(tzinfo=None)


_EVENT_SELECT = """
    SELECT e.id, e.token, e.account_id, c.full_name AS customer_name, e.creative_id, e.provider, e.reward_type,
           e.reward_amount, e.status, e.played_on, e.issued_at, e.min_complete_at, e.expires_at, e.completed_at,
           e.provider_txn_id, e.reject_reason
    FROM ad_reward_events AS e
    JOIN accounts AS a ON a.id = e.account_id
    JOIN customers AS c ON c.id = a.customer_id
"""


def _event(r: dict) -> AdEvent:
    return AdEvent(
        id=int(r["id"]), token=r["token"], account_id=int(r["account_id"]), customer_name=r["customer_name"],
        creative_id=None if r["creative_id"] is None else int(r["creative_id"]), provider=AdMode(r["provider"]),
        reward_type=AdRewardType(r["reward_type"]), reward_amount=int(r["reward_amount"]),
        status=AdStatus(r["status"]), played_on=r["played_on"], issued_at=_utc(r["issued_at"]),
        min_complete_at=_utc(r["min_complete_at"]), expires_at=_utc(r["expires_at"]),
        completed_at=_utc(r["completed_at"]), provider_txn_id=r["provider_txn_id"], reject_reason=r["reject_reason"],
    )


def _creative(r: dict) -> AdCreative:
    return AdCreative(int(r["id"]), r["code"], r["title"], r["body"], r["cta"], int(r["duration_seconds"]),
                      bool(r["is_active"]))


class AdRepository:
    # ----- Cấu hình -------------------------------------------------------------------
    def settings(self, conn: Any, *, lock: bool = False) -> AdSettings:
        r = rows(conn, "SELECT enabled, mode, daily_cap, reward_type, reward_amount FROM ad_settings WHERE id = 1"
                 + (" FOR UPDATE" if lock else ""))[0]
        return AdSettings(bool(r["enabled"]), AdMode(r["mode"]), int(r["daily_cap"]),
                          AdRewardType(r["reward_type"]), int(r["reward_amount"]))

    def save_settings(self, conn: Any, s: AdSettings) -> None:
        execute(
            conn,
            "UPDATE ad_settings SET enabled = %s, mode = %s, daily_cap = %s, reward_type = %s, reward_amount = %s"
            " WHERE id = 1",
            (s.enabled, s.mode.value, s.daily_cap, s.reward_type.value, s.reward_amount),
        )

    def creatives(self, conn: Any) -> list[AdCreative]:
        return [_creative(r) for r in rows(
            conn, "SELECT id, code, title, body, cta, duration_seconds, is_active FROM ad_creatives ORDER BY id")]

    def creative_code_taken(self, conn: Any, code: str, exclude_id: int | None) -> bool:
        return bool(rows(conn, "SELECT id FROM ad_creatives WHERE code = %s AND id <> %s", (code, exclude_id or 0)))

    def save_creative(self, conn: Any, creative_id: int | None, *, code, title, body, cta, duration_seconds,
                      is_active) -> int:
        values = (code, title, body, cta, duration_seconds, is_active)
        if creative_id is None:
            return int(execute(
                conn,
                "INSERT INTO ad_creatives (code, title, body, cta, duration_seconds, is_active)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                values,
            ))
        execute(
            conn,
            "UPDATE ad_creatives SET code = %s, title = %s, body = %s, cta = %s, duration_seconds = %s,"
            " is_active = %s WHERE id = %s",
            values + (creative_id,),
        )
        return creative_id

    # ----- Sự kiện quảng cáo -------------------------------------------------------------
    def insert_event(self, conn: Any, *, token, account_id, creative_id, provider: AdMode,
                     reward_type: AdRewardType, reward_amount, played_on, issued_at, min_complete_at,
                     expires_at) -> int:
        return int(execute(
            conn,
            "INSERT INTO ad_reward_events (token, account_id, creative_id, provider, reward_type, reward_amount,"
            " played_on, issued_at, min_complete_at, expires_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (token, account_id, creative_id, provider.value, reward_type.value, reward_amount, played_on,
             _naive(issued_at), _naive(min_complete_at), _naive(expires_at)),
        ))

    def get_event(self, conn: Any, token: str, *, lock: bool = False) -> AdEvent | None:
        if lock:
            locked = rows(conn, "SELECT id FROM ad_reward_events WHERE token = %s FOR UPDATE", (token,))
            if not locked:
                return None
        result = rows(conn, _EVENT_SELECT + " WHERE e.token = %s", (token,))
        return _event(result[0]) if result else None

    def txn_used(self, conn: Any, txn_id: str) -> bool:
        return bool(rows(conn, "SELECT id FROM ad_reward_events WHERE provider_txn_id = %s", (txn_id,)))

    def supersede_issued(self, conn: Any, account_id: int) -> None:
        """Bắt đầu lượt mới thì hủy token cũ chưa dùng: mỗi tài khoản chỉ có một token còn hiệu lực."""
        execute(
            conn,
            "UPDATE ad_reward_events SET status = 'REJECTED', reject_reason = 'SUPERSEDED'"
            " WHERE account_id = %s AND status = 'ISSUED'",
            (account_id,),
        )

    def finish_event(self, conn: Any, event_id: int, *, status: AdStatus, completed_at=None, reason=None,
                     txn_id=None) -> bool:
        return bool(execute(
            conn,
            "UPDATE ad_reward_events SET status = %s, completed_at = %s, reject_reason = %s, provider_txn_id = %s"
            " WHERE id = %s AND status = 'ISSUED'",
            (status.value, _naive(completed_at), reason, txn_id, event_id),
        ))

    def count_events(self, conn: Any, account_id: int, day, status: AdStatus | None = None) -> int:
        sql = "SELECT COUNT(*) AS total FROM ad_reward_events WHERE account_id = %s AND played_on = %s"
        params: tuple = (account_id, day)
        if status is not None:
            sql += " AND status = %s"
            params += (status.value,)
        return int(rows(conn, sql, params)[0]["total"])

    def daily_stats(self, conn: Any, since_day, now) -> list[dict]:
        result = rows(
            conn,
            "SELECT played_on AS day, COUNT(*) AS issued,"
            " SUM(status = 'COMPLETED') AS completed,"
            " SUM(status = 'REJECTED') AS rejected,"
            " SUM(status = 'ISSUED' AND expires_at < %s) AS expired,"
            " COALESCE(SUM(CASE WHEN status = 'COMPLETED' AND reward_type = 'EXTRA_SPIN' THEN reward_amount END), 0) AS spins,"
            " COALESCE(SUM(CASE WHEN status = 'COMPLETED' AND reward_type = 'COINS' THEN reward_amount END), 0) AS coins"
            " FROM ad_reward_events WHERE played_on >= %s GROUP BY played_on ORDER BY played_on DESC",
            (_naive(now), since_day),
        )
        return [{k: (int(v) if k != "day" else v) for k, v in r.items()} for r in result]

    def recent_events(self, conn: Any, limit: int = 30) -> list[AdEvent]:
        return [_event(r) for r in rows(conn, _EVENT_SELECT + " ORDER BY e.issued_at DESC, e.id DESC LIMIT %s",
                                        (limit,))]
