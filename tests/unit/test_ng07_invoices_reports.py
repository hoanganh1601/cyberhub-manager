"""Unit tests cho NG-07 — màn Hóa đơn và Doanh thu (bộ lọc ngày, KPI, bảng, chi tiết, trạng thái lỗi)."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from cyberhub_manager.domain.dtos import DailyRevenue, InvoiceFilters
from cyberhub_manager.domain.enums import InvoiceStatus
from cyberhub_manager.domain.exceptions import ValidationError
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.services.mocks.scenarios import MockScenario
from cyberhub_manager.ui import feedback as feedback_module
from cyberhub_manager.ui import invoices_view as invoices_module
from cyberhub_manager.ui import reports_view as reports_module
from cyberhub_manager.ui.app_shell import AppShell, ViewContext
from cyberhub_manager.ui.background import ImmediateTaskRunner
from cyberhub_manager.ui.invoices_view import InvoicesView, count_by_status, invoice_badge, invoice_totals
from cyberhub_manager.ui.navigation import NavKey
from cyberhub_manager.ui.report_filters import (
    DATE_INVALID,
    DATE_ORDER,
    DATE_REQUIRED,
    default_range,
    local_today,
    parse_vn_date,
    range_caption,
    service_now,
    validate_range,
)
from cyberhub_manager.ui.reports_view import NO_REVENUE, ReportsView, newest_first, share_percent, summarize_revenue
from cyberhub_manager.ui.state import ViewState
from cyberhub_manager.ui.theme import STITCH_DANGER, STITCH_SUCCESS
from cyberhub_manager.ui.views import default_view_factories

RUNNER = ImmediateTaskRunner()
TODAY = date(2026, 10, 18)  # MockClock mặc định: 09:00 UTC 18/10/2026 = 16:00 giờ Việt Nam


def _login(username: str = "quanly01", scenario: MockScenario = MockScenario.SUCCESS):
    services = build_mock_services(scenario)
    session = services.auth.login(username, DEMO_PASSWORD)
    context = ViewContext(services=services, session=session, language="vi", navigate=lambda _k: True)
    return services, session, context


@pytest.fixture(autouse=True)
def _silence_toasts():
    with patch.object(feedback_module.ToastManager, "show") as toast:
        yield toast


# ----------------------------------------------------------------------
# 1. Hàm thuần — bộ lọc ngày
# ----------------------------------------------------------------------
def test_parse_vn_date() -> None:
    assert parse_vn_date("05/02/2026") == date(2026, 2, 5)
    assert parse_vn_date(" 5-2-2026 ") == date(2026, 2, 5)
    assert parse_vn_date("31/02/2026") is None  # ngày không tồn tại
    assert parse_vn_date("2026-02-05") is None
    assert parse_vn_date("") is None


def test_validate_range_rules() -> None:
    ok = validate_range("01/10/2026", "18/10/2026", required=True)
    assert ok.ok and (ok.date_from, ok.date_to) == (date(2026, 10, 1), TODAY)
    open_ended = validate_range("", "", required=False)  # danh sách hóa đơn cho bỏ trống
    assert open_ended.ok and open_ended.date_from is None
    assert validate_range("", "18/10/2026", required=True).errors == {"date_from": DATE_REQUIRED}
    assert validate_range("1/13/2026", "", required=False).errors == {"date_from": DATE_INVALID}
    assert validate_range("18/10/2026", "01/10/2026", required=True).errors == {"date_to": DATE_ORDER}


def test_default_range_and_caption() -> None:
    assert default_range(TODAY) == (date(2026, 9, 19), TODAY)
    assert range_caption(date(2026, 2, 1), date(2026, 2, 24)) == "01/02 – 24/02/2026"
    assert range_caption(date(2025, 12, 20), date(2026, 1, 5)) == "20/12/2025 – 05/01/2026"


def test_service_clock_and_local_today() -> None:
    services, _, _ = _login()
    assert service_now(services) == datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)
    assert local_today(services) == TODAY
    late = SimpleNamespace(sessions=SimpleNamespace(_clock=lambda: datetime(2026, 10, 18, 18, 30, tzinfo=timezone.utc)))
    assert local_today(late) == date(2026, 10, 19)  # 01:30 sáng hôm sau theo giờ Việt Nam


# ----------------------------------------------------------------------
# 2. Hàm thuần — hóa đơn / doanh thu
# ----------------------------------------------------------------------
def test_invoice_helpers() -> None:
    services, session, _ = _login()
    invoices = services.reports.list_invoices(session.store_id, InvoiceFilters())
    totals = invoice_totals(invoices)
    assert (totals.count, totals.paid_total, totals.void_count) == (4, 60_000, 1)  # hóa đơn hủy không cộng
    assert count_by_status(invoices) == {None: 4, InvoiceStatus.PAID: 3, InvoiceStatus.VOID: 1}
    assert invoice_badge(InvoiceStatus.PAID).text_color == STITCH_SUCCESS
    assert invoice_badge(InvoiceStatus.VOID).label == "Đã hủy"


def test_summarize_revenue() -> None:
    days = [
        DailyRevenue(date(2026, 10, 16), 1, 30_000),
        DailyRevenue(date(2026, 10, 17), 1, 20_000),
        DailyRevenue(date(2026, 10, 18), 2, 10_000),
    ]
    summary = summarize_revenue(days)
    assert (summary.total, summary.invoice_count, summary.days_with_revenue) == (60_000, 4, 3)
    assert (summary.average_per_invoice, summary.average_per_day) == (15_000, 20_000)
    assert summary.best_day.date == date(2026, 10, 16) and summary.best_share == 50.0
    assert [d.date.day for d in newest_first(days)] == [18, 17, 16]
    assert share_percent(1, 3) == 33.3
    empty = summarize_revenue([])
    assert (empty.total, empty.average_per_invoice, empty.best_day) == (0, 0, None)


# ----------------------------------------------------------------------
# 3. Màn Hóa đơn
# ----------------------------------------------------------------------
def _invoices(tk_root, username: str = "quanly01", scenario: MockScenario = MockScenario.SUCCESS):
    services, session, context = _login(username, scenario)
    return InvoicesView(tk_root, context, runner=RUNNER), services, session


def test_invoices_view_loads_default_range_and_detail(tk_root) -> None:
    view, _, _ = _invoices(tk_root)
    assert view.state == ViewState.READY
    filters = view.applied_filters
    assert (filters.date_from, filters.date_to) == (date(2026, 9, 19), TODAY)
    assert [i.invoice_code for i in view.invoices] == ["HD0004", "HD0003", "HD0002", "HD0001"]  # mới nhất trước
    assert view._kpi_labels["count"].cget("text") == "4 đơn"
    assert view._kpi_labels["paid"].cget("text") == "60.000 VND"
    assert view._kpi_labels["void"].cget("text") == "1 đơn"
    assert view._tab_buttons[InvoiceStatus.PAID].cget("text") == "Đã thanh toán (3)"
    assert view.selected_invoice.invoice_code == "HD0004"
    assert view.detail.session.machine_code == "PC07"
    assert view._total_label.cget("text") == "10.000 VND"
    assert view._caption_label.cget("text") == "Hiển thị 1 - 4 trên 4 hóa đơn"


def test_invoices_status_tab_moves_selection(tk_root) -> None:
    view, _, _ = _invoices(tk_root)
    view.set_status_filter(InvoiceStatus.VOID)
    assert [i.invoice_code for i in view.current_page.items] == ["HD0003"]
    assert view.selected_invoice.invoice_code == "HD0003"
    assert view._total_label.cget("text_color") == STITCH_DANGER
    view.set_status_filter(None)
    assert view.selected_invoice.invoice_code == "HD0003"  # vẫn còn trong danh sách -> giữ
    view.select(1)
    assert view.detail.invoice.invoice_code == "HD0001"


def test_invoices_keyword_and_topbar_search(tk_root) -> None:
    view, _, _ = _invoices(tk_root)
    view.handle_search("dung")
    assert view.applied_filters.keyword == "dung"
    assert [i.invoice_code for i in view.invoices] == ["HD0003"]
    view.handle_search("không-có")
    assert view.state == ViewState.EMPTY
    assert view.selected_invoice is None


def test_invoices_date_filter_validation_does_not_call_service(tk_root) -> None:
    view, services, _ = _invoices(tk_root)
    with patch.object(services.reports, "list_invoices") as list_invoices:
        view.set_dates(None, None)
        view._from_entry.insert(0, "32/10/2026")
        view.apply_filters()
        assert view.filter_error == f"⚠ {DATE_INVALID}"
        assert view._from_entry.cget("border_color") == STITCH_DANGER
        view.set_dates(TODAY, date(2026, 10, 1))
        view.apply_filters()
        assert view.filter_error == f"⚠ {DATE_ORDER}"
        list_invoices.assert_not_called()
    view.set_dates(date(2026, 10, 17), date(2026, 10, 17))
    view.apply_filters()
    assert view.filter_error == ""
    assert [i.invoice_code for i in view.invoices] == ["HD0003", "HD0002"]


def test_invoices_open_ended_range_and_clear(tk_root) -> None:
    view, _, _ = _invoices(tk_root)
    view.set_dates(None, None)
    view.apply_filters()
    assert view.applied_filters.date_from is None and len(view.invoices) == 4
    view.set_status_filter(InvoiceStatus.PAID)
    view.clear_filters()
    assert view.applied_filters.date_from == date(2026, 9, 19)
    assert view._status_filter is None


def test_invoices_service_validation_error_marks_dates(tk_root) -> None:
    view, services, _ = _invoices(tk_root)
    error = ValidationError(field_errors={"date_to": "Ngày kết thúc phải sau hoặc bằng ngày bắt đầu"})
    with patch.object(services.reports, "list_invoices", side_effect=error):
        view.apply_filters()
    assert view.state == ViewState.ERROR
    assert view.filter_error == "⚠ Invalid end date."  # không lộ câu tiếng Việt nội bộ của service
    assert view._retry_button.winfo_manager() == "pack"
    assert view._apply_button.is_enabled and not view._apply_button.is_busy


def test_invoices_unavailable_shows_retry(tk_root) -> None:
    view, _, _ = _invoices(tk_root, scenario=MockScenario.UNAVAILABLE)
    assert view.state == ViewState.ERROR
    assert view._retry_button.winfo_manager() == "pack"
    assert view._kpi_labels["count"].cget("text") == "—"
    assert "Traceback" not in view._state_label.cget("text")


def test_invoices_copy_code(tk_root, _silence_toasts) -> None:
    view, _, _ = _invoices(tk_root, "nhanvien01")  # STAFF cũng xem được hóa đơn cửa hàng mình
    view.copy_invoice_code()
    assert view.clipboard_get() == "HD0004"
    assert _silence_toasts.call_args.args[1] == invoices_module.CODE_COPIED


# ----------------------------------------------------------------------
# 4. Màn Doanh thu
# ----------------------------------------------------------------------
def _reports(tk_root, username: str = "quanly01", scenario: MockScenario = MockScenario.SUCCESS):
    services, session, context = _login(username, scenario)
    return ReportsView(tk_root, context, runner=RUNNER), services, session


def test_reports_view_kpis_rows_and_side_panel(tk_root) -> None:
    view, _, _ = _reports(tk_root)
    assert view.state == ViewState.READY
    assert view.applied_range == (date(2026, 9, 19), TODAY)
    assert [d.date.day for d in view.days] == [18, 17, 16]
    assert view._kpi_labels["total"].cget("text") == "60.000 VND"  # chỉ hóa đơn PAID
    assert view._kpi_labels["count"].cget("text") == "3 đơn"
    assert view._kpi_labels["average"].cget("text") == "20.000 VND"
    assert view._kpi_labels["best"].cget("text") == "16/10/2026"
    assert view._kpi_notes["best"].cget("text") == "30.000 VND • 50.0% tổng kỳ"
    assert view._period_label.cget("text") == "Kỳ: 19/09 – 18/10/2026"
    assert view._caption_label.cget("text") == "Hiển thị 1 - 3 trên 3 ngày"
    assert re.fullmatch(r"Cập nhật: \d{2}:\d{2}:\d{2}", view._synced_label.cget("text"))


def test_reports_requires_both_dates(tk_root) -> None:
    view, services, _ = _reports(tk_root)
    with patch.object(services.reports, "daily_revenue") as daily:
        view.set_dates(None, TODAY)
        view.apply_filters()
        daily.assert_not_called()
    assert view.filter_error == f"⚠ {DATE_REQUIRED}"


def test_reports_empty_range(tk_root) -> None:
    view, _, _ = _reports(tk_root)
    view.set_dates(date(2026, 1, 1), date(2026, 1, 31))
    view.apply_filters()
    assert view.state == ViewState.EMPTY
    assert view._state_label.cget("text") == NO_REVENUE
    assert view._kpi_labels["total"].cget("text") == "0 VND"
    assert view._kpi_labels["best"].cget("text") == "—"


def test_reports_unavailable_and_retry(tk_root) -> None:
    view, services, _ = _reports(tk_root, scenario=MockScenario.UNAVAILABLE)
    assert view.state == ViewState.ERROR
    assert view._retry_button.winfo_manager() == "pack"
    assert view._kpi_labels["total"].cget("text") == "—"
    assert view._refresh_button.is_enabled  # không kẹt trạng thái loading


def test_reports_paginates_long_ranges(tk_root) -> None:
    view, services, _ = _reports(tk_root)
    days = [DailyRevenue(date(2026, 10, d), 1, 1_000 * d) for d in range(1, 13)]
    with patch.object(services.reports, "daily_revenue", return_value=days):
        view.reload()
    assert view._caption_label.cget("text") == "Hiển thị 1 - 10 trên 12 ngày"
    view.go_to_page(2)
    assert [d.date.day for d in view.current_page.items] == [2, 1]


# ----------------------------------------------------------------------
# 5. App Shell
# ----------------------------------------------------------------------
@pytest.mark.parametrize("username", ["quanly01", "nhanvien01"])
def test_shell_registers_invoices_and_reports(tk_root, username: str) -> None:
    factories = default_view_factories()
    assert factories[NavKey.INVOICES] is InvoicesView and factories[NavKey.REPORTS] is ReportsView
    services, session, _ = _login(username)
    with patch.object(invoices_module, "default_runner", return_value=RUNNER), patch.object(
        reports_module, "default_runner", return_value=RUNNER
    ), patch("cyberhub_manager.ui.dashboard_view.default_runner", return_value=RUNNER):
        shell = AppShell(tk_root, services, session, on_logout=lambda: None, view_factories=factories)
        assert shell.navigate(NavKey.INVOICES)
        assert isinstance(shell.current_view, InvoicesView)
        assert shell.navigate(NavKey.REPORTS)
        assert isinstance(shell.current_view, ReportsView)
        shell.destroy()
