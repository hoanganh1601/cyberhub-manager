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
    EmployeeStatus,
    InvoiceStatus,
    MachineStatus,
    Role,
    SessionStatus,
    StoreStatus,
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
from cyberhub_manager.ui.messages import (
    MSG_PROCESSING,
    MSG_LOADING,
    MSG_NO_DATA,
    MSG_UNABLE_TO_LOAD,
    MSG_RETRY,
    MSG_CONFIRM,
    MSG_CANCEL,
    MSG_INVALID_CREDENTIALS,
    get_user_friendly_error,
    get_field_errors_safe,
)
from cyberhub_manager.domain.exceptions import (
    AuthenticationError,
    ValidationError,
    ServiceUnavailableError,
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


def test_format_datetime_utc_aware() -> None:
    # UTC-aware: 09:00 UTC -> 16:00 VN (+07:00)
    dt_utc = datetime(2026, 10, 18, 9, 0, 0, tzinfo=timezone.utc)
    assert format_datetime(dt_utc) == "16:00 18/10/2026"


def test_format_datetime_vn_aware() -> None:
    # VN-aware datetime (UTC+7) không bị double-convert
    from datetime import timedelta
    vn_tz = timezone(timedelta(hours=7))
    dt_vn = datetime(2026, 10, 18, 16, 0, 0, tzinfo=vn_tz)
    assert format_datetime(dt_vn) == "16:00 18/10/2026"


def test_format_datetime_naive_fallback() -> None:
    # Naive datetime fallback: coi như UTC (allow_naive=True mặc định)
    dt_naive = datetime(2026, 10, 18, 9, 0, 0)
    assert format_datetime(dt_naive) == "16:00 18/10/2026"


def test_format_datetime_naive_strict_raises() -> None:
    # allow_naive=False phải raise ValueError để bắt lỗi biên DB
    dt_naive = datetime(2026, 10, 18, 9, 0, 0)
    with pytest.raises(ValueError, match="timezone-aware"):
        format_datetime(dt_naive, allow_naive=False)


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

    # Khi bận: hiển thị "Processing…" (tiếng Anh), chặn gọi thêm callback
    btn.set_busy(True)
    assert btn.cget("text") == "Processing…"
    assert btn.is_busy is True
    btn._on_click()
    assert len(calls) == 1

    # Thoát bận: phục hồi text ban đầu
    btn.set_busy(False)
    assert btn.cget("text") == "Xác nhận"
    assert btn.is_busy is False
    btn._on_click()
    assert len(calls) == 2


def test_action_button_configure_while_busy(tk_root) -> None:
    """configure(text=...) khi đang busy phải lưu nhãn gốc mới, không đổi text hiển thị."""
    btn = ActionButton(tk_root, text="Mở máy", kind="success")
    btn.set_busy(True)
    assert btn.cget("text") == "Processing…"

    # Giả sử card render lại khi đang busy: đổi text qua configure
    btn.configure(text="Bật lại")
    # Hiển thị vẫn là "Processing…" vì đang busy
    assert btn.cget("text") == "Processing…"

    # Sau khi thoát busy: phải hiện nhãn mới nhất "Bật lại", không phải "Mở máy" cũ
    btn.set_busy(False)
    assert btn.cget("text") == "Bật lại"


def test_action_button_disabled(tk_root) -> None:
    """set_enabled(False) phải chặn click; set_enabled(True) mở lại."""
    calls = []
    btn = ActionButton(tk_root, text="Nút tắt", kind="secondary", command=lambda: calls.append(1))
    btn.set_enabled(False)
    assert btn.is_enabled is False
    btn._on_click()
    assert len(calls) == 0

    btn.set_enabled(True)
    btn._on_click()
    assert len(calls) == 1


# ==============================================================================
# 5. TEST STATUS BADGE — bao gồm kiểm tra StrEnum trùng giá trị
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


def test_status_badge_strenum_collision(tk_root) -> None:
    """
    P0 — NG01-01: StrEnum INACTIVE có giá trị chuỗi giống nhau ở nhiều enum.
    Phải dùng type(status) để phân biệt, không được dùng == so sánh chuỗi đơn.
    """
    # Xác nhận va chạm StrEnum thực sự tồn tại
    assert CustomerStatus.INACTIVE == EmployeeStatus.INACTIVE  # cùng giá trị chuỗi
    assert CustomerStatus.INACTIVE == StoreStatus.INACTIVE

    # CustomerStatus.INACTIVE -> "Ngừng hoạt động"
    bc = StatusBadge(tk_root, CustomerStatus.INACTIVE)
    assert "Ngừng hoạt động" in bc._label.cget("text")

    # EmployeeStatus.INACTIVE -> "Nghỉ việc" (không được hiện "Ngừng hoạt động")
    be = StatusBadge(tk_root, EmployeeStatus.INACTIVE)
    assert "Nghỉ việc" in be._label.cget("text")
    assert "Ngừng hoạt động" not in be._label.cget("text")

    # StoreStatus.INACTIVE -> "Ngừng HĐ"
    bs = StatusBadge(tk_root, StoreStatus.INACTIVE)
    assert "Ngừng HĐ" in bs._label.cget("text")
    assert "Nghỉ việc" not in bs._label.cget("text")

    # AccountStatus.ACTIVE -> "Hoạt động" với icon ●, không bị nhầm sang MachineStatus
    ba = StatusBadge(tk_root, AccountStatus.ACTIVE)
    assert "Hoạt động" in ba._label.cget("text")

    # EmployeeStatus.LOCKED -> Đã khóa (icon 🔒, giống AccountStatus.LOCKED — không va nhau vì key type khác)
    bl = StatusBadge(tk_root, EmployeeStatus.LOCKED)
    assert "Đã khóa" in bl._label.cget("text")
    assert "🔒" in bl._label.cget("text")


def test_status_badge_invoice_status(tk_root) -> None:
    bi = StatusBadge(tk_root, InvoiceStatus.PAID)
    assert "Đã thanh toán" in bi._label.cget("text")

    bv = StatusBadge(tk_root, InvoiceStatus.VOID)
    assert "Đã hủy" in bv._label.cget("text")


def test_status_badge_role(tk_root) -> None:
    br = StatusBadge(tk_root, Role.ADMIN)
    assert "Admin" in br._label.cget("text")
    assert "★" in br._label.cget("text")

    bm = StatusBadge(tk_root, Role.MANAGER)
    assert "Quản lý" in bm._label.cget("text")

    bs2 = StatusBadge(tk_root, Role.STAFF)
    assert "Nhân viên" in bs2._label.cget("text")


def test_status_badge_raw_string_fallback(tk_root) -> None:
    """Nếu truyền raw str 'INACTIVE', không được đoán nhầm thành CustomerStatus."""
    raw_badge = StatusBadge(tk_root, status="INACTIVE")
    text = raw_badge._label.cget("text")
    # Phải hiển thị fallback chuỗi gốc + bullet, không lấy nhãn "Ngừng hoạt động"
    assert "INACTIVE" in text
    assert "Ngừng hoạt động" not in text
    assert "Nghỉ việc" not in text


def test_status_badge_set_status(tk_root) -> None:
    """set_status() thay đổi nhãn và màu sắc tương ứng."""
    badge = StatusBadge(tk_root, status=MachineStatus.AVAILABLE)
    assert "Trống" in badge._label.cget("text")

    badge.set_status(MachineStatus.MAINTENANCE)
    assert "Bảo trì" in badge._label.cget("text")
    assert "▲" in badge._label.cget("text")


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


def test_form_field_set_value_while_disabled(tk_root) -> None:
    """set_value() khi entry đang disabled phải không raise và lưu giá trị đúng."""
    f = FormField(tk_root, label="Disabled field")
    f.set_enabled(False)
    # Không raise lỗi
    f.set_value("new_value")
    # Sau khi enable lại, get_value() phải trả về giá trị đã set
    f.set_enabled(True)
    assert f.get_value() == "new_value"


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


def test_data_table_set_rows_clears_stale_selection(tk_root) -> None:
    """set_rows() với danh sách mới không chứa key đang chọn phải hủy selected_key."""
    cols = [TableColumn("id", "ID", width=60)]
    rows = [TableRow(1, {"id": "1"}), TableRow(2, {"id": "2"})]
    tbl = DataTable(tk_root, columns=cols, rows=rows)

    tbl._select_row(2)
    assert tbl.selected_key == 2

    # Cập nhật danh sách mới không còn key=2
    new_rows = [TableRow(1, {"id": "1"}), TableRow(3, {"id": "3"})]
    tbl.set_rows(new_rows)
    assert tbl.selected_key is None


def test_data_table_default_messages(tk_root) -> None:
    """Các trạng thái LOADING/EMPTY/ERROR phải dùng thông báo tiếng Anh mặc định."""
    cols = [TableColumn("id", "ID", width=60)]
    tbl = DataTable(tk_root, columns=cols)

    tbl.set_state(ViewState.LOADING)
    # Tìm label trong status_frame
    children_text = [w.cget("text") for w in tbl._status_frame.winfo_children()
                     if hasattr(w, "cget")]
    assert any("Loading data" in t for t in children_text)

    tbl.set_state(ViewState.EMPTY)
    children_text = [w.cget("text") for w in tbl._status_frame.winfo_children()
                     if hasattr(w, "cget")]
    assert any("No matching data found" in t for t in children_text)

    tbl.set_state(ViewState.ERROR)
    children_text = [w.cget("text") for w in tbl._status_frame.winfo_children()
                     if hasattr(w, "cget")]
    assert any("Unable to load data" in t for t in children_text)


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


# ==============================================================================
# 9. TEST MESSAGES MODULE — English feedback strings
# ==============================================================================
def test_default_message_constants() -> None:
    """Các constant trong messages.py phải là tiếng Anh nhất quán."""
    assert MSG_PROCESSING == "Processing…"
    assert MSG_LOADING == "Loading data…"
    assert MSG_NO_DATA == "No matching data found"
    assert MSG_UNABLE_TO_LOAD == "Unable to load data"
    assert MSG_RETRY == "Retry"
    assert MSG_CONFIRM == "Confirm"
    assert MSG_CANCEL == "Cancel"
    assert MSG_INVALID_CREDENTIALS == "Invalid username or password"


def test_get_user_friendly_error_auth() -> None:
    err = AuthenticationError()
    msg = get_user_friendly_error(err)
    assert "Invalid username or password" in msg


def test_get_user_friendly_error_validation() -> None:
    err = ValidationError(field_errors={"phone": "Invalid phone"})
    msg = get_user_friendly_error(err)
    assert "Invalid data provided" in msg
    fields = get_field_errors_safe(err)
    assert fields == {"phone": "Invalid phone"}


def test_get_user_friendly_error_unavailable() -> None:
    err = ServiceUnavailableError()
    msg = get_user_friendly_error(err)
    assert "temporarily unavailable" in msg.lower() or "Unable" in msg


def test_get_user_friendly_error_unknown_exception() -> None:
    err = RuntimeError("some internal error")
    msg = get_user_friendly_error(err)
    # Không được để lộ "some internal error" hoặc stack trace
    assert "some internal error" not in msg
    assert len(msg) > 0


def test_get_field_errors_safe_no_fields() -> None:
    err = ServiceUnavailableError()
    assert get_field_errors_safe(err) == {}

    assert get_field_errors_safe(None) == {}
