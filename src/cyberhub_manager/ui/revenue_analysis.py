"""Calendar-aware chart aggregation. All amounts come from DailyRevenue DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import ceil
from typing import Iterable

from ..domain.dtos import DailyRevenue


@dataclass(frozen=True)
class RevenueBucket:
    start: date
    end: date
    revenue: int = 0
    invoice_count: int = 0

    @property
    def label(self) -> str:
        if self.start == self.end:
            return self.start.strftime("%d/%m/%Y")
        if self.start.year == self.end.year:
            return f"{self.start:%d/%m}–{self.end:%d/%m/%Y}"
        return f"{self.start:%d/%m/%Y}–{self.end:%d/%m/%Y}"


def revenue_buckets(days: Iterable[DailyRevenue], start: date, end: date,
                    grain: str = "day", limit: int = 60) -> list[RevenueBucket]:
    """Fill missing dates with zero and cap render cost for very long ranges.

    Weeks are Monday-based, clipped to the requested range. Monthly groups follow
    calendar months. Longer ranges combine adjacent periods without losing totals.
    """
    if start > end:
        raise ValueError("Reversed date range")
    if grain not in ("day", "week", "month") or limit < 1:
        raise ValueError("Invalid chart grouping")
    spans: list[tuple[date, date]] = []
    if grain == "month":
        first = start.year * 12 + start.month - 1
        last = end.year * 12 + end.month - 1
        step = max(1, ceil((last - first + 1) / limit))
        for month in range(first, last + 1, step):
            year, index = divmod(month, 12)
            left = max(start, date(year, index + 1, 1))
            following = month + step
            if following > last:
                right = end
            else:
                year, index = divmod(following, 12)
                right = min(end, date.fromordinal(date(year, index + 1, 1).toordinal() - 1))
            spans.append((left, right))
    else:
        period = 7 if grain == "week" else 1
        anchor = start.toordinal() - (start.weekday() if grain == "week" else 0)
        period_count = ceil((end.toordinal() - anchor + 1) / period)
        step = period * max(1, ceil(period_count / limit))
        for ordinal in range(anchor, end.toordinal() + 1, step):
            left = date.fromordinal(max(start.toordinal(), ordinal))
            right = date.fromordinal(min(end.toordinal(), ordinal + step - 1))
            spans.append((left, right))
    totals = [[0, 0] for _ in spans]
    for day in days:
        if start <= day.date <= end:
            if grain == "month":
                index = (day.date.year * 12 + day.date.month - 1 - first) // step
            else:
                index = (day.date.toordinal() - anchor) // step
            totals[index][0] += day.revenue
            totals[index][1] += day.invoice_count
    return [RevenueBucket(left, right, *values) for (left, right), values in zip(spans, totals)]


def calendar_average(days: Iterable[DailyRevenue], start: date, end: date) -> int:
    if start > end:
        raise ValueError("Reversed date range")
    return round(sum(day.revenue for day in days if start <= day.date <= end) / ((end - start).days + 1))
