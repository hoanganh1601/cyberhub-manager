"""Unit tests cho bộ theme, state, formatters và components dùng chung (NG-01)."""

from __future__ import annotations

from datetime import datetime, timezone

import customtkinter as ctk
import pytest

from cyberhub_manager.domain.dtos import (
    ActiveSessionSummary,
    CustomerSummary,
    EmployeeSession,
    MachineSummary,
    SessionSummary,
)
from cyberhub_manager.domain.enums import (
    AccountStatus,
    CustomerStatus,
    InvoiceStatus,
    MachineStatus,
    Role,
    SessionStatus,
)
from cyberhub_manager.ui.components import (
    ActionButton,
    ConfirmDialog,
    DataTable,
    FormField,
    MachineCard,
    StatusBadge,
    TableColumn,
    TableRow,
    ToastManager,
)
from cyberhub_manager.ui.formatters import (
    format_datetime,
    format_duration,
    format_money,
)
from cyberhub_manager.ui.state import FormState, ViewState
from cyberhub_manager.ui.theme import (
    ACCENT,
    BG_APP,
    BG_SURFACE,
    BORDER,
    DANGER,
    FONT_BODY,
    FONT_TITLE_XL,
    SUCCESS,
)


@pytest.fixture(scope="module")
def tk_root():
    root = ctk.CTk()
    root.geometry("800x600")
    yield root
    root.destroy()


# ==============================================================================
# 1. TEST THEME & TOKENS
# ==============================================================================
def test_theme_tokens() -> None:
    assert BG_APP == "#0B1120"
    assert BG_SURFACE == "#172033"
    assert BORDER == "#334155"
    assert ACCENT == "#3B82F6"
    assert SUCCESS == "#22C55E"
    assert DANGER == "#EF4444"
    assert FONT_TITLE_XL[1] == 28
    assert FONT_BODY[1] == 14


# ==============================================================================
# 2. TEST VIEW STATE & FORM STATE
# ==============================================================================
def test_view_state() -> None:
    assert ViewState.LOADING == "LOADING"
    assert ViewState.READY == "READY"
    assert ViewState.EMPTY == "EMPTY"
    assert ViewState.ERROR == "ERROR"


def test_form_state_lifecycle() -> None:
    fs = FormState()
    assert not fs.is_submitting
    assert fs.error_message is None

    fs.start_submitting()
    assert fs.is_submitting

    fs.finish_submitting("Lỗi kết nối")
    assert not fs.is_submitting
    assert fs.error_message == "Lỗi kết nối"


# ==============================================================================
# 3. TEST FORMATTERS
# ==============================================================================
def test_format_money() -> None:
    assert format_money(25000) == "25.000 VND"
    assert format_money(0) == "0 VND"
    assert format_money(-10000) == "-10.000 VND"
    assert format_money(1000000) == "1.000.000 VND"


def test_format_datetime() -> None:
    # 09:00 UTC -> 16:00 VN (+07:00)
    dt_utc = datetime(2026, 10, 18, 9, 0, 0, tzinfo=timezone.utc)
    assert format_datetime(dt_utc) == "16:00 18/10/2026"

    # Naive datetime được coi là UTC
    dt_naive = datetime(2026, 10, 18, 9, 0, 0)
    assert format_datetime(dt_naive) == "16:00 18/10/2026"


def test_format_duration() -> None:
    assert format_duration(4320) == "1 giờ 12 phút"
    assert format_duration(3600) == "1 giờ 0 phút"
    assert format_duration(1800) == "30 phút"
    assert format_duration(0) == "0 phút"
    assert format_duration(-10) == "0 phút"


# ==============================================================================
# 4. TEST ACTION BUTTON
# ==============================================================================
def test_action_button_busy_and_double_click(tk_root) -> None:
    calls = []

    def on_click():
        calls.append(1)

    btn = ActionButton(tk_root, text="Xác nhận", kind="primary", command=on_click)
    btn._on_click()
    assert len(calls) == 1

    # Khi bận: chặn gọi thêm callback
    btn.set_busy(True)
    assert btn.cget("text") == "Đang xử lý…"
    btn._on_click()
    assert len(calls) == 1

    # Thoát bận: phục hồi text ban đầu
    btn.set_busy(False)
    assert btn.cget("text") == "Xác nhận"
    btn._on_click()
    assert len(calls) == 2


# ==============================================================================
# 5. TEST STATUS BADGE
# ==============================================================================
def test_status_badge_enum_mapping(tk_root) -> None:
    b1 = StatusBadge(tk_root, MachineStatus.AVAILABLE)
    assert "Trống" in b1._label.cget("text")
    assert "●" in b1._label.cget("text")

    b2 = StatusBadge(tk_root, MachineStatus.IN_USE)
    assert "Đang dùng" in b2._label.cget("text")

    b3 = StatusBadge(tk_root, MachineStatus.MAINTENANCE)
    assert "Bảo trì" in b3._label.cget("text")

    b4 = StatusBadge(tk_root, AccountStatus.LOCKED)
    assert "Đã khóa" in b4._label.cget("text")
    assert "🔒" in b4._label.cget("text")


# ==============================================================================
# 6. TEST FORM FIELD
# ==============================================================================
def test_form_field_value_and_error(tk_root) -> None:
    f = FormField(tk_root, label="Username", placeholder="nhập username")
    f.set_value("ngat_dev")
    assert f.get_value() == "ngat_dev"

    f.set_error("Tên đăng nhập đã tồn tại")
    assert f._error_label.cget("text") == "Tên đăng nhập đã tồn tại"
    assert f._entry.cget("border_color") == DANGER

    f.set_error(None)
    assert f._error_label.cget("text") == ""
    assert f._entry.cget("border_color") == BORDER


def test_form_field_password_toggle(tk_root) -> None:
    f = FormField(tk_root, label="Password", is_password=True, initial_value="secret")
    assert f._entry.cget("show") == "*"

    f._toggle_password_visibility()
    assert f._entry.cget("show") == ""

    f._toggle_password_visibility()
    assert f._entry.cget("show") == "*"


# ==============================================================================
# 7. TEST DATA TABLE
# ==============================================================================
def test_data_table_states_and_selection(tk_root) -> None:
    cols = [
        TableColumn("id", "ID", width=60),
        TableColumn("name", "Tên", width=120),
        TableColumn("rate", "Đơn giá", align="right", width=100),
    ]
    rows = [
        TableRow(1, {"id": "1", "name": "PC01", "rate": "10.000 VND"}),
        TableRow(2, {"id": "2", "name": "PC02", "rate": "15.000 VND"}),
    ]

    selected = []
    tbl = DataTable(tk_root, columns=cols, rows=rows, on_select=lambda k: selected.append(k))

    assert tbl._state == ViewState.READY
    assert len(tbl._rows) == 2

    tbl._select_row(2)
    assert selected == [2]

    tbl.set_state(ViewState.LOADING)
    assert tbl._state == ViewState.LOADING

    tbl.set_state(ViewState.EMPTY)
    assert tbl._state == ViewState.EMPTY

    tbl.set_state(ViewState.ERROR, message="Lỗi")
    assert tbl._state == ViewState.ERROR


# ==============================================================================
# 8. TEST MACHINE CARD
# ==============================================================================
def test_machine_card_rendering_and_negative_balance(tk_root) -> None:
    ref = datetime(2026, 10, 18, 9, 0, 0, tzinfo=timezone.utc)
    staff = EmployeeSession(1, "NV01", "Nhân viên A", "staff", 1, "CH01", "Hub", Role.STAFF)
    manager = EmployeeSession(2, "QL01", "Quản lý B", "mgr", 1, "CH01", "Hub", Role.MANAGER)

    # PC02 IN_USE số dư dự kiến âm -10.000 VND
    s = SessionSummary(1, "SS01", 1, "KH01", "Khách A", 2, "PC02", "Máy 02", ref, 10000, SessionStatus.ACTIVE)
    active = ActiveSessionSummary(s, 5000, 5400, 15000, -10000, ref)
    pc02 = MachineSummary(2, "PC02", 1, "Máy 02", MachineStatus.IN_USE, 10000, True, ref, active)

    card = MachineCard(tk_root, pc02, staff)
    card.pack()
    assert "Âm 10.000 VND" in card._balance_label.cget("text")
    assert card._action_btn.cget("text") == "Checkout"

    # PC03 MAINTENANCE: STAFF không có nút "Bật lại", MANAGER có nút "Bật lại"
    pc03 = MachineSummary(3, "PC03", 1, "Máy 03", MachineStatus.MAINTENANCE, 10000, True, ref, None)

    card_staff = MachineCard(tk_root, pc03, staff)
    card_staff.pack()
    assert card_staff._maintenance_text_label.winfo_manager() == "pack"
    assert card_staff._action_btn.winfo_manager() == ""

    card_manager = MachineCard(tk_root, pc03, manager)
    card_manager.pack()
    assert card_manager._maintenance_text_label.winfo_manager() == ""
    assert card_manager._action_btn.winfo_manager() == "pack"
    assert card_manager._action_btn.cget("text") == "Bật lại"
