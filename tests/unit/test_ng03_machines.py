"""Unit tests cho NG-03 — Dashboard, card máy, Quản lý máy và dialog máy."""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

import customtkinter as ctk
import pytest

from cyberhub_manager.domain.dtos import MachineArchiveResult
from cyberhub_manager.domain.enums import MachineArchiveAction, MachineStatus, Role
from cyberhub_manager.domain.exceptions import ServiceUnavailableError
from cyberhub_manager.services.mocks.factory import build_mock_services
from cyberhub_manager.services.mocks.fixtures import DEMO_PASSWORD
from cyberhub_manager.services.mocks.scenarios import MockScenario
from cyberhub_manager.ui import dashboard_view as dashboard_module
from cyberhub_manager.ui import feedback as feedback_module
from cyberhub_manager.ui import machine_management_view as management_module
from cyberhub_manager.ui.app_shell import AppShell, ViewContext
from cyberhub_manager.ui.background import ImmediateTaskRunner, ThreadTaskRunner
from cyberhub_manager.ui.components.stitch_machine_card import card_action
from cyberhub_manager.ui.dashboard_view import DashboardView, filter_machines, summarize
from cyberhub_manager.ui.dialogs.machine_dialog import MachineDialog, parse_positive_int
from cyberhub_manager.ui.machine_management_view import (
    MachineManagementView,
    archive_message,
    machine_actions,
)
from cyberhub_manager.ui.navigation import NavKey
from cyberhub_manager.ui.state import ViewState
from cyberhub_manager.ui.theme import STITCH_DANGER, STITCH_INPUT_BORDER
from cyberhub_manager.ui.views import default_view_factories

RUNNER = ImmediateTaskRunner()


def _login(username: str = "quanly01", scenario: MockScenario = MockScenario.SUCCESS):
    services = build_mock_services(scenario)
    session = services.auth.login(username, DEMO_PASSWORD)
    return services, session


def _context(services, session) -> ViewContext:
    return ViewContext(services=services, session=session, language="vi", navigate=lambda _k: True)


def _machine(services, session, code: str):
    return next(m for m in services.machines.list_machines(session.store_id) if m.machine_code == code)


@pytest.fixture(autouse=True)
def _silence_feedback():
    """Toast/Dialog thật cần cửa sổ hiển thị; trong test chỉ ghi lại lời gọi."""
    with patch.object(feedback_module.ToastManager, "show") as toast, patch.object(
        dashboard_module.ToastManager, "show", toast
    ):
        yield toast


# ----------------------------------------------------------------------
# 1. Hàm thuần
# ----------------------------------------------------------------------
def test_summarize_matches_mock_fixture() -> None:
    services, session = _login()
    counts = summarize(services.machines.list_machines(session.store_id))
    assert (counts.total, counts.available, counts.in_use, counts.maintenance) == (20, 17, 2, 1)
    assert counts.online_customers == 2
    assert counts.for_status(None) == 20
    assert counts.for_status(MachineStatus.IN_USE) == 2


def test_filter_by_status_and_keyword() -> None:
    services, session = _login()
    machines = services.machines.list_machines(session.store_id)
    assert {m.machine_code for m in filter_machines(machines, MachineStatus.IN_USE)} == {"PC02", "PC05"}
    assert [m.machine_code for m in filter_machines(machines, keyword=" pc03 ")] == ["PC03"]
    # Tìm theo tên khách đang dùng máy.
    customer = _machine(services, session, "PC02").active_session.session.customer_name
    assert [m.machine_code for m in filter_machines(machines, keyword=customer.lower())] == ["PC02"]
    assert filter_machines(machines, MachineStatus.MAINTENANCE, "PC01") == []


def test_card_action_depends_on_status_and_role() -> None:
    services, manager = _login("quanly01")
    _, staff = _login("nhanvien01")
    pc01, pc02, pc03 = (_machine(services, manager, c) for c in ("PC01", "PC02", "PC03"))
    assert card_action(pc01, staff) == "open"
    assert card_action(pc02, staff) == "checkout"
    assert card_action(pc03, staff) is None
    assert card_action(pc03, manager) == "maintenance"


def test_machine_actions_block_in_use_machine() -> None:
    services, session = _login()
    in_use = machine_actions(_machine(services, session, "PC02"))
    assert in_use.can_edit and not in_use.can_toggle_maintenance and not in_use.can_archive
    maintenance = machine_actions(_machine(services, session, "PC03"))
    assert maintenance.maintenance_label == "Kết thúc bảo trì" and maintenance.can_archive
    nothing = machine_actions(None)  # chưa chọn máy: tắt hết
    assert not (nothing.can_edit or nothing.can_toggle_maintenance or nothing.can_archive)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("12000", 12000), ("12.000", 12000), ("12,000 VND", 12000), (" 8 000 ", 8000), ("0", None), ("-5", None), ("abc", None), ("", None)],
)
def test_parse_positive_int(text: str, expected: int | None) -> None:
    assert parse_positive_int(text) == expected


def test_archive_message() -> None:
    assert "deleted" in archive_message(MachineArchiveResult(1, MachineArchiveAction.DELETED))
    assert "archived" in archive_message(MachineArchiveResult(1, MachineArchiveAction.ARCHIVED))


# ----------------------------------------------------------------------
# 2. Dashboard
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def tk_root():
    root = ctk.CTk()
    root.geometry("1280x720")
    yield root
    root.destroy()


def _dashboard(tk_root, username: str = "quanly01", scenario=MockScenario.SUCCESS, **kwargs):
    services, session = _login(username, scenario)
    view = DashboardView(tk_root, _context(services, session), runner=RUNNER, **kwargs)
    return view, services, session


def test_dashboard_loads_kpis_and_cards(tk_root) -> None:
    view, _, _ = _dashboard(tk_root)
    assert view.state == ViewState.READY
    assert len(view.visible_machine_ids) == 20
    kpis = {attr: label.cget("text") for attr, label in view._kpi_labels.items()}
    assert kpis == {"total": "20", "available": "17", "in_use": "2", "maintenance": "1", "online_customers": "2"}
    assert view._tab_buttons[MachineStatus.IN_USE].cget("text") == "Đang dùng (2)"
    assert "20/20" in view._count_label.cget("text")
    view.destroy()


def test_dashboard_filter_and_search(tk_root) -> None:
    view, services, session = _dashboard(tk_root)
    view.set_status_filter(MachineStatus.IN_USE)
    assert len(view.visible_machine_ids) == 2
    assert "2/20" in view._count_label.cget("text")
    view.set_status_filter(None)
    view.handle_search("PC03")
    assert view.visible_machine_ids == [_machine(services, session, "PC03").machine_id]
    view.handle_search("không-có-máy-này")
    assert view.state == ViewState.EMPTY
    view.destroy()


def test_dashboard_negative_balance_shown_in_red(tk_root) -> None:
    view, services, session = _dashboard(tk_root)
    pc02 = _machine(services, session, "PC02")
    assert pc02.active_session.projected_balance < 0
    card = view.card_for(pc02.machine_id)
    texts = [w.cget("text") for row in card._info_box.winfo_children() for w in row.winfo_children()]
    assert "-10.000 VND" in texts
    view.destroy()


def test_staff_has_no_end_maintenance_button(tk_root) -> None:
    view, services, session = _dashboard(tk_root, "nhanvien01")
    assert session.role == Role.STAFF
    assert view.card_for(_machine(services, session, "PC03").machine_id).action is None
    view.destroy()


def test_manager_ends_maintenance_from_card(tk_root) -> None:
    view, services, session = _dashboard(tk_root)
    pc03 = _machine(services, session, "PC03")
    with patch.object(dashboard_module.ConfirmDialog, "ask", return_value=True):
        view.card_for(pc03.machine_id)._on_click()
    assert _machine(services, session, "PC03").status == MachineStatus.AVAILABLE
    assert view._kpi_labels["maintenance"].cget("text") == "0"
    view.destroy()


def test_cancel_end_maintenance_changes_nothing(tk_root) -> None:
    view, services, session = _dashboard(tk_root)
    pc03 = _machine(services, session, "PC03")
    with patch.object(dashboard_module.ConfirmDialog, "ask", return_value=False):
        view.card_for(pc03.machine_id)._on_click()
    assert _machine(services, session, "PC03").status == MachineStatus.MAINTENANCE
    view.destroy()


def test_open_and_checkout_use_callbacks(tk_root, _silence_feedback) -> None:
    opened: list[int] = []
    view, services, session = _dashboard(tk_root, on_open_session=opened.append)
    pc01, pc02 = _machine(services, session, "PC01"), _machine(services, session, "PC02")
    view.card_for(pc01.machine_id)._on_click()
    assert opened == [pc01.machine_id]
    view.card_for(pc02.machine_id)._on_click()  # chưa có NG-06 -> Toast "chưa hỗ trợ"
    assert _silence_feedback.call_args.args[1] == dashboard_module.FEATURE_PENDING
    view.destroy()


def test_busy_card_ignores_double_click(tk_root) -> None:
    opened: list[int] = []
    view, services, session = _dashboard(tk_root, on_open_session=opened.append)
    card = view.card_for(_machine(services, session, "PC01").machine_id)
    card.set_busy(True)
    card._on_click()
    assert opened == []
    assert card.action_button.cget("text") == "Processing…"
    card.set_busy(False)
    assert card.action_button.cget("text") == "Mở phiên"
    view.destroy()


def test_unavailable_service_shows_error_state(tk_root) -> None:
    view, _, _ = _dashboard(tk_root, scenario=MockScenario.UNAVAILABLE)
    assert view.state == ViewState.ERROR
    assert view._retry_button.winfo_manager() == "pack"
    view.destroy()


def test_failed_background_refresh_keeps_old_snapshot(tk_root) -> None:
    view, services, _ = _dashboard(tk_root)
    with patch.object(services.machines, "list_machines", side_effect=ServiceUnavailableError()):
        view.refresh()
    assert view.is_stale
    assert len(view.machines) == 20 and view.state == ViewState.READY
    view.refresh()
    assert not view.is_stale
    view.destroy()


def test_refresh_is_scheduled_and_shutdown_cancels_it(tk_root) -> None:
    view, _, _ = _dashboard(tk_root)
    assert view.has_scheduled_refresh
    view.shutdown()
    assert not view.has_scheduled_refresh
    view.refresh()  # đã đóng: không tải lại, không hẹn lịch mới
    assert not view.has_scheduled_refresh
    view.destroy()


def test_shell_uses_dashboard_and_stops_refresh_on_navigate(tk_root) -> None:
    services, session = _login()
    with patch.object(dashboard_module, "default_runner", return_value=RUNNER), patch.object(
        management_module, "default_runner", return_value=RUNNER
    ):
        shell = AppShell(tk_root, services, session, on_logout=lambda: None, view_factories=default_view_factories())
        dashboard = shell.current_view
        assert isinstance(dashboard, DashboardView) and dashboard.has_scheduled_refresh
        assert shell.search_enabled  # Dashboard có handle_search
        shell.navigate(NavKey.MACHINES)
        assert isinstance(shell.current_view, MachineManagementView)
        assert not dashboard.has_scheduled_refresh
        shell.destroy()


# ----------------------------------------------------------------------
# 3. Quản lý máy + dialog
# ----------------------------------------------------------------------
def _management(tk_root, username: str = "quanly01"):
    services, session = _login(username)
    view = MachineManagementView(tk_root, _context(services, session), runner=RUNNER)
    return view, services, session


def test_management_lists_machines_and_blocks_in_use_actions(tk_root) -> None:
    view, services, session = _management(tk_root)
    assert len(view.machines) == 20
    assert view.state == ViewState.READY
    assert len(view.visible_machine_ids) == management_module.PAGE_SIZE
    assert view._kpi_labels["in_use"].cget("text") == "2"
    buttons = view.row_buttons(_machine(services, session, "PC02").machine_id)
    assert buttons["edit"].is_enabled
    assert not buttons["maintenance"].is_enabled
    assert not buttons["archive"].is_enabled
    view.destroy()


def test_management_filter_search_and_pages(tk_root) -> None:
    view, services, session = _management(tk_root)
    assert view.current_page.total_pages == 3
    view.go_to_page(3)
    assert len(view.visible_machine_ids) == 6
    assert view._caption_label.cget("text") == "Hiển thị 15-20 trên tổng số 20 máy"
    view.set_status_filter(MachineStatus.IN_USE)
    assert view.current_page.number == 1
    in_use = {_machine(services, session, code).machine_id for code in ("PC02", "PC05")}
    assert set(view.visible_machine_ids) == in_use
    view.set_status_filter(None)
    view.handle_search("pc03")  # từ ô tìm kiếm trên topbar
    assert view.visible_machine_ids == [_machine(services, session, "PC03").machine_id]
    assert view._search_entry.get() == "pc03"
    view.handle_search("không-có-máy-này")
    assert view.state == ViewState.EMPTY
    view.destroy()


def test_management_toggles_maintenance(tk_root) -> None:
    view, services, session = _management(tk_root)
    pc01 = _machine(services, session, "PC01")
    with patch.object(management_module.ConfirmDialog, "ask", return_value=True):
        view._toggle_maintenance(pc01)
    assert _machine(services, session, "PC01").status == MachineStatus.MAINTENANCE
    assert view.row_buttons(pc01.machine_id)["maintenance"].cget("text") == "↺"
    view.destroy()


def test_management_archive_requires_confirmation(tk_root) -> None:
    view, services, session = _management(tk_root)
    pc04 = _machine(services, session, "PC04")
    with patch.object(management_module.ConfirmDialog, "ask", return_value=False):
        view._archive(pc04)
    assert len(view.machines) == 20
    with patch.object(management_module.ConfirmDialog, "ask", return_value=True) as ask:
        view._archive(pc04)
        assert ask.call_args.kwargs["is_danger"] is True
    assert pc04.machine_id not in {m.machine_id for m in view.machines}
    view.destroy()


def test_management_unavailable_service_shows_retry(tk_root) -> None:
    services, session = _login(scenario=MockScenario.UNAVAILABLE)
    view = MachineManagementView(tk_root, _context(services, session), runner=RUNNER)
    assert view.state == ViewState.ERROR
    assert view._retry_button.winfo_manager() == "pack"
    view.destroy()


def test_staff_cannot_load_management_view(tk_root) -> None:
    view, _, session = _management(tk_root, "nhanvien01")
    assert session.role == Role.STAFF
    assert view.machines == []
    assert view.state == ViewState.ERROR
    assert not view.add_button.is_enabled
    view.destroy()


def _dialog(tk_root, services, session, machine=None, saved=None):
    return MachineDialog(tk_root, _context(services, session), machine=machine, runner=RUNNER, on_saved=saved)


def test_dialog_creates_machine(tk_root) -> None:
    services, session = _login()
    saved = []
    dialog = _dialog(tk_root, services, session, saved=saved.append)
    dialog.fields["code"].set_value("pc21")
    dialog.fields["name"].set_value("Máy VIP 21")
    dialog.fields["hourly_rate"].set_value("15.000")
    dialog.submit()
    assert saved and saved[0].code == "PC21" and saved[0].hourly_rate == 15000
    assert not dialog.winfo_exists()
    assert len(services.machines.list_machines(session.store_id)) == 21


def test_dialog_client_validation_keeps_input(tk_root) -> None:
    services, session = _login()
    dialog = _dialog(tk_root, services, session)
    dialog.fields["code"].set_value("PC22")
    dialog.fields["hourly_rate"].set_value("abc")
    with patch.object(services.machines, "create_machine") as create:
        dialog.submit()
        create.assert_not_called()
    assert dialog.fields["name"]._error_label.cget("text") == "This field is required."
    assert dialog.fields["hourly_rate"]._error_label.cget("text") == "Hourly rate must be a positive integer."
    assert dialog.fields["code"].get_value() == "PC22"
    assert not dialog.is_submitting
    dialog.destroy()


def test_dialog_maps_conflict_to_code_field(tk_root) -> None:
    services, session = _login()
    dialog = _dialog(tk_root, services, session)
    dialog.fields["code"].set_value("PC01")
    dialog.fields["name"].set_value("Trùng mã")
    dialog.fields["hourly_rate"].set_value("10000")
    with patch("cyberhub_manager.ui.dialogs.machine_dialog.ToastManager.show"):
        dialog.submit()
    assert dialog.winfo_exists()
    assert dialog.fields["code"]._error_label.cget("text") == "Machine code already exists."
    assert not dialog.is_submitting
    dialog.destroy()


def test_dialog_edits_machine_without_code_field(tk_root) -> None:
    services, session = _login()
    pc01 = _machine(services, session, "PC01")
    dialog = _dialog(tk_root, services, session, machine=pc01)
    assert "code" not in dialog.fields
    assert dialog.fields["hourly_rate"].get_value() == str(pc01.hourly_rate)
    dialog.fields["hourly_rate"].set_value("20000")
    dialog.submit()
    assert _machine(services, session, "PC01").hourly_rate == 20000


def test_dialog_error_border_and_close_button(tk_root) -> None:
    services, session = _login()
    dialog = _dialog(tk_root, services, session)
    code = dialog.fields["code"]
    code.set_error("Machine code already exists.")
    assert code._box.cget("border_color") == STITCH_DANGER
    assert code._error_label.winfo_manager() == "pack"
    code.set_error(None)
    assert code._box.cget("border_color") == STITCH_INPUT_BORDER
    assert code._error_label.winfo_manager() == ""
    dialog._close_button.invoke()  # nút ✕ ở góc phải = Hủy
    assert not dialog.winfo_exists()


# ----------------------------------------------------------------------
# 4. ThreadTaskRunner — kết quả quay về main thread
# ----------------------------------------------------------------------
def _pump(tk_root, done, timeout: float = 10.0) -> None:
    """Chạy vòng sự kiện Tk cho tới khi done() đúng hoặc hết giờ."""
    deadline = time.monotonic() + timeout
    while not done() and time.monotonic() < deadline:
        tk_root.update()
        time.sleep(0.01)


def test_thread_runner_delivers_result_and_error_on_main_thread(tk_root) -> None:
    tk_root.update()  # xử lý hết sự kiện tồn đọng từ các test trước rồi mới đếm giờ
    runner = ThreadTaskRunner()
    main_thread = threading.get_ident()
    results: list[tuple[str, object, int]] = []
    try:
        runner.submit(
            tk_root,
            lambda: threading.get_ident(),
            lambda worker: results.append(("ok", worker, threading.get_ident())),
            lambda error: results.append(("error", error, threading.get_ident())),
        )
        runner.submit(
            tk_root,
            lambda: 1 / 0,
            lambda value: results.append(("ok", value, threading.get_ident())),
            lambda error: results.append(("error", type(error), threading.get_ident())),
        )
        _pump(tk_root, lambda: len(results) == 2)
    finally:
        runner.shutdown()

    assert len(results) == 2, f"Chỉ nhận được {len(results)}/2 kết quả: {results}"
    (kind1, worker, cb_thread1), (kind2, error_type, cb_thread2) = results
    assert kind1 == "ok" and worker != main_thread  # func chạy ở worker
    assert cb_thread1 == main_thread  # callback chạy ở main thread
    assert kind2 == "error" and error_type is ZeroDivisionError and cb_thread2 == main_thread
