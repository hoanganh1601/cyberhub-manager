"""Ngày nghiệp vụ phải nhất quán ở ranh giới 00:00 Việt Nam."""

from datetime import date, datetime, timezone

import pytest

from cyberhub_manager.domain.business_time import local_day, utc_day_bounds


def test_local_day_changes_at_17_utc() -> None:
    assert local_day(datetime(2026, 11, 20, 16, 59, 59, tzinfo=timezone.utc)) == date(2026, 11, 20)
    assert local_day(datetime(2026, 11, 20, 17, 0, 0, tzinfo=timezone.utc)) == date(2026, 11, 21)


def test_utc_day_bounds_are_half_open_and_24_hours() -> None:
    start, end = utc_day_bounds(date(2026, 11, 21))
    assert start == datetime(2026, 11, 20, 17, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 11, 21, 17, 0, tzinfo=timezone.utc)


def test_local_day_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        local_day(datetime(2026, 11, 21))
