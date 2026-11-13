"""Worker gửi thông báo ra ngoài web: đọc sổ `customer_notification_events`, gọi kênh, ghi kết quả.

Nguyên tắc (xem docs/POS_INVENTORY_LIFECYCLE.md §9):
- Không bao giờ gọi kênh ngoài bên trong transaction POS. Mỗi lượt gồm ba bước độc lập:
  (1) transaction ngắn: tạo dòng PENDING và "thuê" một lô, (2) gọi kênh KHÔNG giữ transaction/khóa,
  (3) transaction ngắn ghi từng kết quả.
- Giao ít nhất một lần. Nếu worker chết sau khi gửi mà trước khi ghi, dòng SENDING hết hạn thuê và được
  gửi lại; bên nhận loại trùng bằng `idempotency_key` (= notification_key, ổn định theo sự kiện).
- Thử lại có giới hạn với backoff gấp đôi; hết số lần hoặc lỗi vĩnh viễn thì DEAD (giữ nguyên để người vận hành xem).
- Chỉ xử lý sự kiện trong `lookback` gần nhất để bật kênh mới không xả cả lịch sử cũ.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from .notification_sinks import PermanentDeliveryError, TransientDeliveryError

logger = logging.getLogger(__name__)

DEFAULT_MAX_ATTEMPTS = 6
# Lease phải dài hơn thời gian gửi cả lô (lô 20 × timeout 5 giây = 100 giây), nếu không lô chưa xong bị gửi lại.
DEFAULT_LEASE_SECONDS = 300
DEFAULT_BASE_DELAY_SECONDS = 30
DEFAULT_MAX_DELAY_SECONDS = 3600
DEFAULT_LOOKBACK_HOURS = 24


class NotificationDispatcher:
    def __init__(self, sink, repo=None, transaction_factory=None, clock=None, *,
                 max_attempts=DEFAULT_MAX_ATTEMPTS, lease_seconds=DEFAULT_LEASE_SECONDS,
                 base_delay_seconds=DEFAULT_BASE_DELAY_SECONDS, max_delay_seconds=DEFAULT_MAX_DELAY_SECONDS,
                 lookback_hours=DEFAULT_LOOKBACK_HOURS):
        if repo is None:
            from cyberhub_manager.database.transaction import transaction
            from cyberhub_manager.repositories.notification_repository import NotificationDeliveryRepository

            repo = NotificationDeliveryRepository()
            transaction_factory = transaction_factory or transaction
        if transaction_factory is None:
            raise ValueError("transaction_factory is required with a custom repository")
        if not 1 <= max_attempts <= 20:
            raise ValueError("max_attempts must be 1..20")
        if not 10 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be 10..3600")
        if not 1 <= base_delay_seconds <= max_delay_seconds <= 86400:
            raise ValueError("delays must satisfy 1 <= base <= max <= 86400")
        if not 1 <= lookback_hours <= 24 * 30:
            raise ValueError("lookback_hours must be 1..720")
        self._sink = sink
        self._repo = repo
        self._transaction = transaction_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._max_attempts = max_attempts
        self._lease = timedelta(seconds=lease_seconds)
        self._base_delay = base_delay_seconds
        self._max_delay = max_delay_seconds
        self._lookback = timedelta(hours=lookback_hours)

    @property
    def channel(self) -> str:
        return self._sink.channel

    def retry_delay(self, attempts: int) -> timedelta:
        """Chờ base·2^(attempts-1) giây, tối đa max_delay."""
        return timedelta(seconds=min(self._base_delay * 2 ** max(attempts - 1, 0), self._max_delay))

    def run_once(self, *, limit: int = 20) -> dict[str, int]:
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be 1..500")
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("clock must return an aware datetime")
        with self._transaction() as conn:
            queued = self._repo.enqueue_missing(conn, self.channel, now, now - self._lookback, limit)
            batch = self._repo.claim(conn, self.channel, now, now + self._lease, self._max_attempts, limit)
        result = dict(queued=queued, sent=0, retried=0, dead=0, unrecorded=0)
        for item in batch:
            outcome = self._deliver(item)
            try:
                with self._transaction() as conn:
                    self._record(conn, item, outcome)
            except Exception:
                # Không ghi được kết quả: dòng vẫn SENDING, hết hạn thuê sẽ được xử lý lại (không mất thông báo).
                logger.exception("Cannot record delivery %s (%s); lease will expire and retry",
                                 item["delivery_id"], item["notification_key"])
                result["unrecorded"] += 1
                continue
            result[outcome[0]] += 1
        return result

    def _deliver(self, item) -> tuple[str, str | None]:
        message = dict(
            id=item["event_id"], idempotency_key=item["notification_key"], kind=item["kind"], code=item["code"],
            amount=item["amount"], account_id=item["account_id"], store_id=item["store_id"],
            created_at=item["created_at"].isoformat(), attempt=item["attempts"])
        try:
            self._sink.deliver(message)
            return "sent", None
        except PermanentDeliveryError as error:
            logger.error("Notification %s failed permanently: %s", item["notification_key"], error)
            return "dead", str(error) or "permanent error"
        except TransientDeliveryError as error:
            return self._retry_or_dead(item, str(error) or "transient error")
        except Exception as error:  # lỗi lạ của sink: ghi traceback, vẫn thử lại có giới hạn
            logger.exception("Notification %s raised an unexpected error", item["notification_key"])
            return self._retry_or_dead(item, f"unexpected {type(error).__name__}")

    def _retry_or_dead(self, item, text):
        if item["attempts"] >= self._max_attempts:
            logger.error("Notification %s gave up after %s attempts: %s", item["notification_key"],
                         item["attempts"], text)
            return "dead", text
        logger.warning("Notification %s attempt %s/%s failed: %s", item["notification_key"],
                       item["attempts"], self._max_attempts, text)
        return "retried", text

    def _record(self, conn, item, outcome):
        kind, text = outcome
        now = self._clock()
        if kind == "sent":
            self._repo.mark_sent(conn, item["delivery_id"], now)
        elif kind == "retried":
            self._repo.mark_failed(conn, item["delivery_id"], text, now + self.retry_delay(item["attempts"]))
        else:
            self._repo.mark_failed(conn, item["delivery_id"], text, None)

    def stats(self) -> dict[str, int]:
        with self._transaction() as conn:
            return self._repo.counts(conn, self.channel)
