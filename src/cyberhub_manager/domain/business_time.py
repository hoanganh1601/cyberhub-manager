"""Quy ước ngày nghiệp vụ dùng thống nhất trong CyberHub.

Timestamp trong MySQL được lưu ở UTC không kèm timezone. Ngày báo cáo và giới hạn
theo ngày dùng Asia/Ho_Chi_Minh (UTC+7, không có DST).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone


VIETNAM_TIMEZONE = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")


def local_day(moment: datetime) -> date:
    """Trả ngày nghiệp vụ Việt Nam của một thời điểm có timezone."""
    if moment.tzinfo is None:
        raise ValueError("moment must be timezone-aware")
    return moment.astimezone(VIETNAM_TIMEZONE).date()


def utc_day_bounds(day: date) -> tuple[datetime, datetime]:
    """Trả khoảng UTC nửa mở [start, end) tương ứng một ngày Việt Nam."""
    start_local = datetime.combine(day, time.min, tzinfo=VIETNAM_TIMEZONE)
    start_utc = start_local.astimezone(timezone.utc)
    return start_utc, start_utc + timedelta(days=1)
