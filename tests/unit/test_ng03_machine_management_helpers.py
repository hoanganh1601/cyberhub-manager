"""NG-03 (Stitch) — hàm thuần cho màn Quản lý máy: phiên hiện tại, cập nhật cuối, phân trang."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.ui.machine_management_view import (
    current_session_cells,
    format_short_duration,
    format_updated_ago,
    page_caption,
    paginate,
)

NOW = datetime(2026, 2, 24, 7, 35, tzinfo=timezone.utc)  # 14:35 giờ Việt Nam


def _machines():
    services = build_mock_services()
    session = services.auth.login("quanly01", DEMO_PASSWORD)
    return {m.machine_code: m for m in services.machines.list_machines(session.store_id)}


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "0m"), (59, "0m"), (45 * 60, "45m"), (90 * 60, "1h 30m"), (2 * 3600 + 10 * 60 + 59, "2h 10m"), (-5, "0m")],
)
def test_format_short_duration(seconds: int, expected: str) -> None:
    assert format_short_duration(seconds) == expected


def test_current_session_cells() -> None:
    machines = _machines()
    pc02 = machines["PC02"]
    assert current_session_cells(pc02) == (
        pc02.active_session.session.customer_name,
        format_short_duration(pc02.active_session.elapsed_seconds),
    )
    assert current_session_cells(machines["PC01"]) == ("—", "")


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (timedelta(seconds=30), "Vừa xong"),
        (-timedelta(minutes=2), "Vừa xong"),  # đồng hồ lệch: không hiện số âm
        (timedelta(minutes=5), "5 phút trước"),
        (timedelta(minutes=59, seconds=59), "59 phút trước"),
        (timedelta(hours=1), "1 giờ trước"),
        (timedelta(hours=23, minutes=59), "23 giờ trước"),
        (timedelta(days=9), "15/02/2026"),
    ],
)
def test_format_updated_ago(delta: timedelta, expected: str) -> None:
    assert format_updated_ago(NOW - delta, NOW) == expected


def test_format_updated_ago_treats_naive_as_utc() -> None:
    assert format_updated_ago(datetime(2026, 2, 24, 7, 30), NOW) == "5 phút trước"


def test_paginate_splits_and_clamps() -> None:
    items = list(range(1, 21))
    first = paginate(items, 1, page_size=6)
    assert (first.items, first.number, first.total_pages) == ([1, 2, 3, 4, 5, 6], 1, 4)
    last = paginate(items, 4, page_size=6)
    assert (last.items, last.first, last.last) == ([19, 20], 19, 20)
    assert page_caption(last) == "Hiển thị 19-20 trên tổng số 20 máy"
    assert paginate(items, 99, page_size=6).number == 4
    assert paginate(items, 0, page_size=6).number == 1


def test_paginate_empty_list() -> None:
    page = paginate([], 3)
    assert (page.items, page.number, page.total_pages, page.first, page.last) == ([], 1, 1, 0, 0)
    assert page_caption(page) == "Hiển thị 0-0 trên tổng số 0 máy"
