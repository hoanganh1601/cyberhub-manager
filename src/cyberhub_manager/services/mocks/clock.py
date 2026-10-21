"""Đồng hồ cố định, điều khiển được cho mock services."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

DEFAULT_NOW = datetime(2026, 10, 18, 9, 0, 0, tzinfo=timezone.utc)
"""Mốc tham chiếu mục 9: 09:00 UTC, tương ứng 16:00 giờ Việt Nam."""


def _to_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("MockClock chỉ nhận datetime có timezone")
    return value.astimezone(timezone.utc)


class MockClock:
    """Mọi mock trong một bundle đọc giờ từ cùng một clock.

    Clock không tự chạy theo giờ thật; chỉ thay đổi khi gọi advance/set/reset.
    """

    def __init__(self, start: datetime = DEFAULT_NOW) -> None:
        self._start = _to_utc(start)
        self._now = self._start

    def now(self) -> datetime:
        return self._now

    def advance(
        self, *, hours: int = 0, minutes: int = 0, seconds: int = 0
    ) -> datetime:
        """Tiến đồng hồ để demo thời lượng phiên; không cho lùi."""

        delta = timedelta(hours=hours, minutes=minutes, seconds=seconds)
        if delta < timedelta(0):
            raise ValueError("Không thể lùi MockClock bằng advance; dùng set()")
        self._now += delta
        return self._now

    def set(self, value: datetime) -> None:
        self._now = _to_utc(value)

    def reset(self) -> None:
        self._now = self._start
