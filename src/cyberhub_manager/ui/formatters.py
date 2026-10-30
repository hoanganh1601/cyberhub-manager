"""Các hàm định dạng hiển thị dữ liệu chuẩn trên giao diện CyberHub Manager.

Quy định: docs/07_DTO_UI_HANDOFF.md mục 2 và 8.
- Tiền tệ: 25.000 VND, số âm là -10.000 VND.
- Thời gian: HH:mm dd/MM/yyyy theo múi giờ Việt Nam (Asia/Ho_Chi_Minh).
- Thời lượng: X giờ Y phút hoặc Y phút.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except ZoneInfoNotFoundError:
    # Fallback cho môi trường thiếu tzdata (Windows/môi trường rút gọn)
    VN_TZ = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")


def format_money(amount: int) -> str:
    """Format số tiền VND với dấu chấm phân cách hàng nghìn.

    Ví dụ:
        format_money(25000) -> "25.000 VND"
        format_money(-10000) -> "-10.000 VND"
        format_money(0) -> "0 VND"
    """
    if amount < 0:
        formatted = f"{abs(amount):,}".replace(",", ".")
        return f"-{formatted} VND"
    formatted = f"{amount:,}".replace(",", ".")
    return f"{formatted} VND"


def format_datetime(value: datetime, *, allow_naive: bool = True) -> str:
    """Format mốc thời gian thành chuỗi HH:mm dd/MM/yyyy theo giờ Việt Nam.

    Quy định: Handoff yêu cầu datetime qua service/DTO là timezone-aware (thường là UTC).
    - Nếu allow_naive=False và value là naive datetime: ném ValueError để bắt lỗi biên.
    - Nếu allow_naive=True (fallback cho dữ liệu legacy): coi naive là UTC.
    - Không đổi hai lần nếu đầu vào đã ở múi giờ địa phương (Asia/Ho_Chi_Minh).
    """
    if value.tzinfo is None:
        if not allow_naive:
            raise ValueError("Datetime must be timezone-aware (missing tzinfo).")
        value = value.replace(tzinfo=timezone.utc)

    local_dt = value.astimezone(VN_TZ)
    return local_dt.strftime("%H:%M %d/%m/%Y")


def format_duration(seconds: int) -> str:
    """Format thời lượng giây thành chuỗi thời gian thân thiện.

    Ví dụ:
        format_duration(4320) -> "1 giờ 12 phút"
        format_duration(3600) -> "1 giờ 0 phút"
        format_duration(1800) -> "30 phút"
        format_duration(0)    -> "0 phút"
    """
    if seconds <= 0:
        return "0 phút"

    total_minutes = seconds // 60
    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours > 0:
        return f"{hours} giờ {minutes} phút"
    return f"{minutes} phút"
