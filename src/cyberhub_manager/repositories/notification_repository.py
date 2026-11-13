"""Theo dõi việc gửi thông báo ra ngoài web (MySQL). Không tự commit.

Quy ước thời gian: tham số là datetime có múi giờ; cột DATETIME lưu UTC không múi giờ.
Đọc sổ sự kiện bằng SELECT thường (không khóa) để không bao giờ chặn transaction POS đang ghi sự kiện.
"""

from __future__ import annotations

from datetime import timezone
from typing import Any

from cyberhub_manager.repositories.p1_repository import execute, rows


def _db_time(value):
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _count(conn, sql, params):
    """Số dòng thật sự bị ảnh hưởng (execute() của repo khác trả lastrowid cho INSERT)."""
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        return int(cursor.rowcount)
    finally:
        cursor.close()


def _aware(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


class NotificationDeliveryRepository:
    def enqueue_missing(self, conn: Any, channel: str, now, since, limit: int) -> int:
        """Tạo dòng PENDING cho sự kiện (từ `since`) chưa có dòng gửi của kênh này; chạy lại không trùng."""
        found = rows(
            conn,
            "SELECT e.id FROM customer_notification_events AS e"
            " LEFT JOIN notification_deliveries AS d ON d.event_id = e.id AND d.channel = %s"
            " WHERE d.id IS NULL AND e.created_at >= %s ORDER BY e.id LIMIT %s",
            (channel, _db_time(since), limit),
        )
        if not found:
            return 0
        marks = ",".join(["(%s,%s,'PENDING',%s)"] * len(found))
        params = []
        for row in found:
            params += [int(row["id"]), channel, _db_time(now)]
        return _count(
            conn,
            "INSERT IGNORE INTO notification_deliveries (event_id, channel, status, next_attempt_at)"
            f" VALUES {marks}",
            tuple(params),
        )

    def claim(self, conn: Any, channel: str, now, lease_until, max_attempts: int, limit: int) -> list[dict]:
        """Thuê tối đa `limit` dòng đến hạn. Dòng SENDING hết hạn thuê (worker chết giữa chừng) được nhận lại;
        nếu đã hết số lần thử thì chuyển DEAD thay vì gửi tiếp."""
        execute(
            conn,
            "UPDATE notification_deliveries SET status='DEAD', locked_until=NULL,"
            " last_error='Lease expired after the last attempt'"
            " WHERE channel = %s AND status='SENDING' AND locked_until <= %s AND attempts >= %s",
            (channel, _db_time(now), max_attempts),
        )
        due = rows(
            conn,
            "SELECT id FROM notification_deliveries WHERE channel = %s AND"
            " ((status='PENDING' AND next_attempt_at <= %s) OR (status='SENDING' AND locked_until <= %s))"
            " ORDER BY next_attempt_at, id LIMIT %s FOR UPDATE SKIP LOCKED",
            (channel, _db_time(now), _db_time(now), limit),
        )
        ids = [int(r["id"]) for r in due]
        if not ids:
            return []
        marks = ",".join(["%s"] * len(ids))
        execute(
            conn,
            "UPDATE notification_deliveries SET status='SENDING', attempts = attempts + 1, locked_until = %s"
            f" WHERE id IN ({marks})",
            (_db_time(lease_until), *ids),
        )
        claimed = rows(
            conn,
            "SELECT d.id AS delivery_id, d.attempts, e.id AS event_id, e.notification_key, e.account_id,"
            " e.store_id, e.kind, e.code, e.amount, e.created_at"
            " FROM notification_deliveries AS d JOIN customer_notification_events AS e ON e.id = d.event_id"
            f" WHERE d.id IN ({marks}) ORDER BY d.id",
            tuple(ids),
        )
        for row in claimed:
            row["created_at"] = _aware(row["created_at"])
        return claimed

    def mark_sent(self, conn: Any, delivery_id: int, now) -> bool:
        return bool(execute(
            conn,
            "UPDATE notification_deliveries SET status='SENT', sent_at = %s, locked_until=NULL, last_error=NULL"
            " WHERE id = %s AND status='SENDING'",
            (_db_time(now), delivery_id),
        ))

    def mark_failed(self, conn: Any, delivery_id: int, error: str, retry_at) -> bool:
        """`retry_at` None nghĩa là dừng hẳn (DEAD); ngược lại quay về PENDING, thử lại từ `retry_at`."""
        if retry_at is None:
            return bool(execute(
                conn,
                "UPDATE notification_deliveries SET status='DEAD', locked_until=NULL, last_error = %s"
                " WHERE id = %s AND status='SENDING'",
                (error[:255], delivery_id),
            ))
        return bool(execute(
            conn,
            "UPDATE notification_deliveries SET status='PENDING', locked_until=NULL, last_error = %s,"
            " next_attempt_at = %s WHERE id = %s AND status='SENDING'",
            (error[:255], _db_time(retry_at), delivery_id),
        ))

    def counts(self, conn: Any, channel: str) -> dict[str, int]:
        found = rows(
            conn,
            "SELECT status, COUNT(*) AS n FROM notification_deliveries WHERE channel = %s GROUP BY status",
            (channel,),
        )
        return {r["status"]: int(r["n"]) for r in found}
