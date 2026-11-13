"""Bản bộ nhớ của NotificationDeliveryRepository: cùng chữ ký và ngữ nghĩa, dùng cho test và demo."""

from __future__ import annotations

from contextlib import contextmanager


@contextmanager
def no_transaction():
    yield None


class MemoryNotificationDeliveryRepository:
    def __init__(self, events=None):
        # `events` là danh sách sự kiện sổ thông báo (cùng dạng p1.order_notifications).
        self.events = events if events is not None else []
        self.deliveries: list[dict] = []

    def _find(self, event_id, channel):
        return next((d for d in self.deliveries if d["event_id"] == event_id and d["channel"] == channel), None)

    def enqueue_missing(self, conn, channel, now, since, limit):
        added = 0
        for event in sorted(self.events, key=lambda e: e["id"]):
            if added >= limit:
                break
            if event["created_at"] < since or self._find(event["id"], channel):
                continue
            self.deliveries.append(dict(
                id=len(self.deliveries) + 1, event_id=event["id"], channel=channel, status="PENDING",
                attempts=0, next_attempt_at=now, locked_until=None, last_error=None, sent_at=None))
            added += 1
        return added

    def claim(self, conn, channel, now, lease_until, max_attempts, limit):
        for d in self.deliveries:
            if (d["channel"] == channel and d["status"] == "SENDING" and d["locked_until"] <= now
                    and d["attempts"] >= max_attempts):
                d.update(status="DEAD", locked_until=None, last_error="Lease expired after the last attempt")
        due = [d for d in self.deliveries if d["channel"] == channel and (
            (d["status"] == "PENDING" and d["next_attempt_at"] <= now)
            or (d["status"] == "SENDING" and d["locked_until"] <= now))]
        due.sort(key=lambda d: (d["next_attempt_at"], d["id"]))
        claimed = []
        for d in due[:limit]:
            d.update(status="SENDING", attempts=d["attempts"] + 1, locked_until=lease_until)
            event = next(e for e in self.events if e["id"] == d["event_id"])
            claimed.append(dict(
                delivery_id=d["id"], attempts=d["attempts"], event_id=event["id"],
                notification_key=event["notification_key"], account_id=event["account_id"],
                store_id=event["store_id"], kind=event["kind"], code=event["code"],
                amount=event["amount"], created_at=event["created_at"]))
        return claimed

    def _sending(self, delivery_id):
        return next((d for d in self.deliveries if d["id"] == delivery_id and d["status"] == "SENDING"), None)

    def mark_sent(self, conn, delivery_id, now):
        d = self._sending(delivery_id)
        if d is None:
            return False
        d.update(status="SENT", sent_at=now, locked_until=None, last_error=None)
        return True

    def mark_failed(self, conn, delivery_id, error, retry_at):
        d = self._sending(delivery_id)
        if d is None:
            return False
        d.update(locked_until=None, last_error=error[:255])
        if retry_at is None:
            d["status"] = "DEAD"
        else:
            d.update(status="PENDING", next_attempt_at=retry_at)
        return True

    def counts(self, conn, channel):
        result: dict[str, int] = {}
        for d in self.deliveries:
            if d["channel"] == channel:
                result[d["status"]] = result.get(d["status"], 0) + 1
        return result
