"""NG-07 — Hàm thuần dùng chung cho màn Hóa đơn và Doanh thu (không import Tk).

- service_now(): giờ hiện tại theo đồng hồ của SessionService (mock dùng đồng hồ cố định).
- Ngày lọc là ngày địa phương Asia/Ho_Chi_Minh (UTC+7 cố định, quyết định LI-08), nhập dạng dd/mm/yyyy.
- Kiểm tra khoảng ngày trước khi gọi service; service vẫn kiểm tra lại (ValidationError date_from/date_to).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

VN_OFFSET = timedelta(hours=7)
DEFAULT_RANGE_DAYS = 30
DATE_REQUIRED = "Please enter a date (dd/mm/yyyy)."
DATE_INVALID = "Invalid date. Use dd/mm/yyyy."
DATE_ORDER = "End date must be on or after the start date."
_DATE_PATTERN = re.compile(r"^\s*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\s*$")


def service_now(services: Any) -> datetime:
    """Giờ tính phí/báo cáo lấy từ đồng hồ của SessionService.

    complete_checkout tính lại theo đồng hồ của chính service, nên UI phải dùng đúng đồng hồ đó:
    mock dùng MockClock cố định (có .now()), service thật dùng callable trả giờ UTC.
    Không đọc được thì dùng giờ UTC hiện tại.
    """
    clock = getattr(getattr(services, "sessions", None), "_clock", None)
    reader = getattr(clock, "now", clock)
    if callable(reader):
        try:
            value = reader()
        except TypeError:
            value = None
        if isinstance(value, datetime) and value.tzinfo is not None:
            return value
    return datetime.now(timezone.utc)


def local_today(services: Any) -> date:
    """Ngày hôm nay theo giờ Việt Nam của đồng hồ service."""
    return (service_now(services).astimezone(timezone.utc) + VN_OFFSET).date()


def format_vn_date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def parse_vn_date(text: str) -> date | None:
    """'05/02/2026' / '5-2-2026' -> date; sai định dạng hoặc ngày không tồn tại -> None."""
    match = _DATE_PATTERN.match(text or "")
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


@dataclass(frozen=True)
class DateRange:
    date_from: date | None
    date_to: date | None
    errors: dict[str, str]

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_range(text_from: str, text_to: str, *, required: bool) -> DateRange:
    """Đọc 2 ô ngày. Danh sách hóa đơn cho phép bỏ trống (required=False); doanh thu bắt buộc cả hai."""
    errors: dict[str, str] = {}
    values: dict[str, date | None] = {}
    for key, text in (("date_from", text_from), ("date_to", text_to)):
        if not (text or "").strip():
            values[key] = None
            if required:
                errors[key] = DATE_REQUIRED
            continue
        parsed = parse_vn_date(text)
        values[key] = parsed
        if parsed is None:
            errors[key] = DATE_INVALID
    start, end = values["date_from"], values["date_to"]
    if not errors and start and end and start > end:
        errors["date_to"] = DATE_ORDER
    return DateRange(start, end, errors)


def default_range(today: date, days: int = DEFAULT_RANGE_DAYS) -> tuple[date, date]:
    """Khoảng mặc định: `days` ngày gần nhất, tính cả hôm nay."""
    return today - timedelta(days=days - 1), today


def range_caption(start: date, end: date) -> str:
    """'01/02 – 24/02/2026' như Stitch; khác năm thì ghi đủ cả hai đầu."""
    if start.year == end.year:
        return f"{start:%d/%m} – {end:%d/%m/%Y}"
    return f"{start:%d/%m/%Y} – {end:%d/%m/%Y}"
