"""Calendar boundaries and aggregation must not invent or lose financial data."""

from datetime import date
from unittest.mock import patch

import pytest

from cyberhub_manager.domain.dtos import DailyRevenue
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.scenarios import MockScenario
from cyberhub_manager.ui.app_shell import ViewContext
from cyberhub_manager.ui.background import ImmediateTaskRunner
from cyberhub_manager.ui.reports_view import ReportsView
from cyberhub_manager.ui.revenue_analysis import calendar_average, revenue_buckets
from cyberhub_manager.ui.state import ViewState


@pytest.mark.parametrize("grain", ["day", "week", "month"])
def test_buckets_preserve_totals_fill_gaps_and_clip_range(grain):
    days = [DailyRevenue(date(2026, 1, 31), 2, 20000),
            DailyRevenue(date(2026, 2, 3), 1, 7000),
            DailyRevenue(date(2026, 3, 1), 1, 999999)]
    start, end = date(2026, 1, 28), date(2026, 2, 6)
    buckets = revenue_buckets(days, start, end, grain)
    assert sum(b.revenue for b in buckets) == 27000
    assert sum(b.invoice_count for b in buckets) == 3
    assert buckets[0].start == start and buckets[-1].end == end
    assert all(left.end.toordinal() + 1 == right.start.toordinal()
               for left, right in zip(buckets, buckets[1:]))
    assert any(b.revenue == 0 for b in revenue_buckets(days, start, end, "day"))


def test_monthly_buckets_use_calendar_boundaries_and_leap_days():
    buckets = revenue_buckets([DailyRevenue(date(2024, 2, 29), 3, 3000)],
                              date(2024, 1, 31), date(2024, 3, 2), "month")
    assert [(b.start, b.end) for b in buckets] == [
        (date(2024, 1, 31), date(2024, 1, 31)),
        (date(2024, 2, 1), date(2024, 2, 29)),
        (date(2024, 3, 1), date(2024, 3, 2))]
    assert buckets[1].revenue == 3000


def test_weeks_start_on_monday_and_clip_partial_weeks():
    buckets = revenue_buckets([], date(2026, 10, 16), date(2026, 10, 26), "week")
    assert [(b.start.day, b.end.day) for b in buckets] == [(16, 18), (19, 25), (26, 26)]


@pytest.mark.parametrize("grain", ["day", "week", "month"])
def test_long_ranges_are_bounded_even_at_date_limits(grain):
    buckets = revenue_buckets([DailyRevenue(date.max, 1, 12345)], date.min, date.max, grain)
    assert 1 <= len(buckets) <= 60
    assert buckets[-1].end == date.max
    assert sum(b.revenue for b in buckets) == 12345


def test_calendar_average_counts_days_without_revenue():
    days = [DailyRevenue(date(2026, 1, 1), 1, 9000)]
    assert calendar_average(days, date(2026, 1, 1), date(2026, 1, 3)) == 3000
    assert calendar_average([], date(2026, 1, 1), date(2026, 1, 1)) == 0


def test_invalid_range_or_grouping_is_rejected():
    with pytest.raises(ValueError):
        revenue_buckets([], date(2026, 2, 1), date(2026, 1, 1))
    with pytest.raises(ValueError):
        revenue_buckets([], date.today(), date.today(), "cash")


def make_view(root, scenario=MockScenario.SUCCESS):
    services = build_mock_services(scenario)
    actor = services.auth.login("quanly01", "demo123")
    context = ViewContext(services, actor, "vi", lambda _key: True)
    return ReportsView(root, context, runner=ImmediateTaskRunner()), services


def test_charts_match_kpis_and_fill_zero_days(tk_root):
    view, _ = make_view(tk_root)
    buckets = view.revenue_chart.buckets
    assert len(buckets) == 30
    assert sum(b.revenue for b in buckets) == view.summary.total == 60000
    assert sum(b.invoice_count for b in view.invoice_chart.buckets) == 3
    assert sum(b.revenue == 0 for b in buckets) == 27


def test_chart_selection_filters_detail_without_changing_period_totals(tk_root):
    view, _ = make_view(tk_root)
    bucket = next(b for b in view.revenue_chart.buckets if b.start == date(2026, 10, 16))
    view.select_bucket(bucket)
    assert [d.date for d in view.current_page.items] == [date(2026, 10, 16)]
    assert view.summary.total == 60000
    assert view._kpi_labels["total"].cget("text") == "60.000 VND"
    view.select_bucket(None)
    assert len(view.current_page.items) == 3


def test_zero_day_drilldown_is_empty_and_can_be_cleared(tk_root):
    view, _ = make_view(tk_root)
    view.select_bucket(view.revenue_chart.buckets[0])
    assert view.state == ViewState.EMPTY and not view.current_page.items
    view.select_bucket(None)
    assert view.state == ViewState.READY
    assert len(view.current_page.items) == 3


def test_grain_and_chart_mode_preserve_data_and_clear_drilldown(tk_root):
    view, _ = make_view(tk_root)
    view.select_bucket(view.revenue_chart.buckets[-1])
    view.set_grain("month")
    assert view._selected_bucket is None
    assert len(view.current_page.items) == 3
    assert sum(b.revenue for b in view.revenue_chart.buckets) == 60000
    view.set_chart_mode("bar")
    assert view.revenue_chart.mode == "bar"
    assert sum(b.invoice_count for b in view.invoice_chart.buckets) == 3


def test_error_charts_do_not_show_stale_financial_data(tk_root):
    view, services = make_view(tk_root)
    with patch.object(services.reports, "daily_revenue", side_effect=RuntimeError("private SQL secret")):
        view.reload()
    assert view.state == ViewState.ERROR
    assert not view.revenue_chart.buckets and not view.invoice_chart.buckets
    assert "secret" not in view.revenue_chart._message


def test_quick_ranges_use_service_clock(tk_root):
    view, _ = make_view(tk_root)
    view.preset_range(7)
    assert view.applied_range == (date(2026, 10, 12), date(2026, 10, 18))
    assert len(view.revenue_chart.buckets) == 7
    view.preset_range("month")
    assert view.applied_range == (date(2026, 10, 1), date(2026, 10, 18))


def test_pointer_click_on_chart_drills_into_correct_date(tk_root):
    view, _ = make_view(tk_root)
    view.pack(fill="both", expand=True)
    tk_root.update()
    chart = view.revenue_chart
    chart._draw_chart()
    left, top, right, bottom = chart._plot
    index = next(i for i, b in enumerate(chart.buckets) if b.start == date(2026, 10, 16))
    x = int(left + (index + .5) * (right - left) / len(chart.buckets))
    y = int((top + bottom) / 2)
    chart.canvas.event_generate("<Button-1>", x=x, y=y)
    tk_root.update()
    assert view._selected_bucket.start == date(2026, 10, 16)
    assert [day.date for day in view.current_page.items] == [date(2026, 10, 16)]
    assert "30.000 VND" in chart.detail.cget("text")
