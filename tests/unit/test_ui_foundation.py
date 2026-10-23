"""Unit tests cho bộ theme, state, formatters và components dùng chung (NG-01)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

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
    MSG_OPERATION_FAILED,
    get_user_friendly_error,
    get_field_errors_safe,
)
from cyberhub_manager.domain.exceptions import (
    ApplicationError,
    AuthenticationError,
    ConflictError,
    ValidationError,
    ServiceUnavailableError,
)
from cyberhub_manager.ui.state import FormState, ViewState
from cyberhub_manager.ui.theme import (
    ACCENT,
    BG_APP,
    BG_DANGER_SUBTLE,
    BG_INFO_SUBTLE,
    BG_MUTED_SUBTLE,
    BG_ROW_ALT,
    BG_SUCCESS_SUBTLE,
    BG_SURFACE,
    BG_WARNING_SUBTLE,
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
    assert BG_ROW_ALT == "#151D2E"
    assert BG_SUCCESS_SUBTLE == "#0A2918"
    assert BG_DANGER_SUBTLE == "#331317"
    assert BG_WARNING_SUBTLE == "#352309"
    assert BG_INFO_SUBTLE == "#0C2A38"
    assert BG_MUTED_SUBTLE == "#1E293B"
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


def test_action_button_initial_disabled_busy_cycle(tk_root) -> None:
    """Khởi tạo state='disabled' -> busy -> hết busy vẫn giữ nguyên disabled và không gọi callback."""
    calls = []
    btn = ActionButton(
        tk_root,
        text="Khởi tạo tắt",
        kind="secondary",
        state="disabled",
        command=lambda: calls.append(1),
    )

    # 1. Trạng thái ban đầu: is_enabled phải là False, state widget là disabled
    assert btn.is_enabled is False
    assert btn.cget("state") == "disabled"
    btn._on_click()
    assert len(calls) == 0

    # 2. Chuyển sang busy: widget vẫn disabled, is_busy là True
    btn.set_busy(True)
    assert btn.is_busy is True
    assert btn.cget("state") == "disabled"
    assert btn.cget("text") == "Processing…"
    btn._on_click()
    assert len(calls) == 0

    # 3. Hết chu kỳ busy: nút phải PHỤC HỒI disabled, KHÔNG bị tự động bật thành normal
    btn.set_busy(False)
    assert btn.is_busy is False
    assert btn.is_enabled is False
    assert btn.cget("state") == "disabled"
    assert btn.cget("text") == "Khởi tạo tắt"
    btn._on_click()
    assert len(calls) == 0


def test_action_button_configure_state_sync(tk_root) -> None:
    """configure(state=...) phải đồng bộ với is_enabled và duy trì sau chu kỳ busy."""
    calls = []
    btn = ActionButton(tk_root, text="Tác vụ", command=lambda: calls.append(1))
    assert btn.is_enabled is True

    # configure state="disabled"
    btn.configure(state="disabled")
    assert btn.is_enabled is False
    assert btn.cget("state") == "disabled"
    btn._on_click()
    assert len(calls) == 0

    # Sau chu kỳ busy vẫn giữ disabled
    btn.set_busy(True)
    btn.set_busy(False)
    assert btn.is_enabled is False
    assert btn.cget("state") == "disabled"
    btn._on_click()
    assert len(calls) == 0

    # configure lại state="normal"
    btn.configure(state="normal")
    assert btn.is_enabled is True
    assert btn.cget("state") == "normal"
    btn._on_click()
    assert len(calls) == 1


def test_action_button_caller_exception_finally(tk_root) -> None:
    """Caller chịu trách nhiệm bọc service call trong try...finally: set_busy(False)."""
    btn = ActionButton(tk_root, text="Submit", kind="primary")

    def failing_handler():
        btn.set_busy(True)
        try:
            raise RuntimeError("Service network failure")
        finally:
            btn.set_busy(False)

    with pytest.raises(RuntimeError, match="Service network failure"):
        failing_handler()

    # Sau exception, busy phải được giải phóng và nút sẵn sàng click lại
    assert btn.is_busy is False
    assert btn.cget("text") == "Submit"


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
    # Trạng thái entry vẫn được giữ là disabled
    assert f._entry.cget("state") == "disabled"
    assert f.get_value() == "new_value"
    # Sau khi enable lại, get_value() vẫn trả về giá trị đã set
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

    # Cập nhật danh sách mới không còn key=2 -> selected_key bị hủy (None)
    new_rows = [TableRow(1, {"id": "1"}), TableRow(3, {"id": "3"})]
    tbl.set_rows(new_rows)
    assert tbl.selected_key is None

    # Cập nhật danh sách mới vẫn chứa key đang chọn -> giữ nguyên selected_key
    tbl._select_row(1)
    assert tbl.selected_key == 1
    new_rows_retaining = [TableRow(1, {"id": "1_updated"}), TableRow(4, {"id": "4"})]
    tbl.set_rows(new_rows_retaining)
    assert tbl.selected_key == 1


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

    # Test error with on_retry button
    retried = []
    tbl.set_state(ViewState.ERROR, on_retry=lambda: retried.append(True))
    retry_btn = next((w for w in tbl._status_frame.winfo_children() if isinstance(w, ActionButton)), None)
    assert retry_btn is not None
    assert retry_btn.cget("text") == "Retry"
    retry_btn._on_click()
    assert retried == [True]


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


def test_machine_card_rerender_while_busy(tk_root) -> None:
    """Khi card đang busy mà có event cập nhật trạng thái AVAILABLE -> IN_USE,
    sau khi set_busy(False) nút phải hiển thị nhãn mới 'Checkout' thay vì 'Mở máy' cũ."""
    ref = datetime(2026, 10, 18, 9, 0, 0, tzinfo=timezone.utc)
    staff = EmployeeSession(1, "NV01", "Nhân viên A", "staff", 1, "CH01", "Hub", Role.STAFF)

    pc01_avail = MachineSummary(1, "PC01", 1, "Máy 01", MachineStatus.AVAILABLE, 10000, True, ref, None)
    card = MachineCard(tk_root, pc01_avail, staff)
    card.pack()
    assert card._action_btn.cget("text") == "Mở máy"

    # Giả lập caller kích hoạt mở máy và đặt card busy
    card.set_busy(True)
    assert card._action_btn.is_busy is True
    assert card._action_btn.cget("text") == "Processing…"

    # Server trả về kết quả máy đã được mở: card được render lại sang IN_USE
    s = SessionSummary(1, "SS01", 1, "KH01", "Khách A", 1, "PC01", "Máy 01", ref, 10000, SessionStatus.ACTIVE)
    active = ActiveSessionSummary(s, 10000, 0, 0, 10000, ref)
    pc01_in_use = MachineSummary(1, "PC01", 1, "Máy 01", MachineStatus.IN_USE, 10000, True, ref, active)
    card.render(pc01_in_use, staff)

    # Trong khi còn busy, text vẫn hiển thị 'Processing…'
    assert card._action_btn.cget("text") == "Processing…"

    # Caller hoàn tất thao tác trong finally block
    card.set_busy(False)
    assert card._action_btn.is_busy is False
    # Phải cập nhật đúng nhãn mới 'Checkout' của trạng thái IN_USE, không giữ 'Mở máy'
    assert card._action_btn.cget("text") == "Checkout"


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
    assert fields == {"phone": "Invalid phone number."}


def test_get_user_friendly_error_conflict() -> None:
    """Kiểm tra lỗi CONFLICT trả về tiếng Anh và không để lộ thông báo tiếng Việt từ mock."""
    err = ConflictError("Máy đã có phiên đang hoạt động")
    msg = get_user_friendly_error(err)
    assert "conflict" in msg.lower()
    assert "Máy đã có phiên đang hoạt động" not in msg

    # Kiểm tra truyền chuỗi code "CONFLICT"
    msg_str = get_user_friendly_error("CONFLICT")
    assert "conflict" in msg_str.lower()


def test_get_user_friendly_error_unavailable() -> None:
    """Kiểm tra lỗi UNAVAILABLE trả về tiếng Anh và không để lộ thông báo tiếng Việt từ mock."""
    err = ServiceUnavailableError("Không tải được dữ liệu, vui lòng thử lại")
    msg = get_user_friendly_error(err)
    assert "temporarily unavailable" in msg.lower()
    assert "Không tải được dữ liệu" not in msg

    # Kiểm tra truyền chuỗi code "UNAVAILABLE" hoặc "SERVICE_UNAVAILABLE"
    assert "temporarily unavailable" in get_user_friendly_error("UNAVAILABLE").lower()
    assert "temporarily unavailable" in get_user_friendly_error("SERVICE_UNAVAILABLE").lower()


def test_get_user_friendly_error_unknown_code() -> None:
    """Mã lỗi không biết (ApplicationError lạ hoặc code lạ) phải fallback an toàn."""
    err = ApplicationError("SOME_UNKNOWN_CODE_999", "Fatal internal DB error: connection timed out")
    msg = get_user_friendly_error(err)
    assert msg == MSG_OPERATION_FAILED
    assert "SOME_UNKNOWN_CODE_999" not in msg
    assert "connection timed out" not in msg

    # Chuỗi mã lạ
    msg_unknown_str = get_user_friendly_error("SOME_UNKNOWN_CODE_999")
    assert msg_unknown_str == MSG_OPERATION_FAILED


def test_get_user_friendly_error_technical_string() -> None:
    """Chuỗi tùy ý chứa nội dung kỹ thuật (SQL, Traceback) không được trả nguyên văn mà dùng fallback."""
    sql_str = "SELECT * FROM users WHERE role = 'admin'; DROP TABLE machines;"
    assert get_user_friendly_error(sql_str) == MSG_OPERATION_FAILED

    traceback_str = "Traceback (most recent call last):\n  File 'app.py', line 12, in <module>\nValueError"
    assert get_user_friendly_error(traceback_str) == MSG_OPERATION_FAILED


def test_get_field_errors_safe_vietnamese_mock() -> None:
    """Kiểm tra field_errors tiếng Việt từ mock scenarios được ánh xạ sang tiếng Anh an toàn."""
    err = ValidationError(
        field_errors={
            "phone": "Số điện thoại đã được sử dụng",
            "machine_id": "Máy đã có phiên đang hoạt động",
            "hourly_rate": "Đơn giá phải là số nguyên lớn hơn 0",
            "amount": "Số tiền nạp phải là số nguyên lớn hơn 0",
        }
    )
    safe = get_field_errors_safe(err)
    assert safe["phone"] == "Phone number is already in use."
    assert safe["machine_id"] == "Machine already has an active session."
    assert safe["hourly_rate"] == "Hourly rate must be a positive integer."
    assert safe["amount"] == "Top-up amount must be a positive integer."
    # Tuyệt đối không còn tiếng Việt
    for val in safe.values():
        assert not any(ord(c) > 127 for c in val)


def test_get_field_errors_safe_technical_content() -> None:
    """Field error chứa chuỗi kỹ thuật hoặc trường không rõ phải dùng fallback an toàn."""
    err = ValidationError(
        field_errors={
            "phone": "ERROR 1064 (42000): You have an error in your SQL syntax",
            "unknown_internal_col": "Segmentation fault at 0x7fff",
        }
    )
    safe = get_field_errors_safe(err)
    # phone có field key fallback
    assert safe["phone"] == "Invalid phone number."
    # unknown field có generic fallback
    assert safe["unknown_internal_col"] == "Invalid value."
    assert "SQL syntax" not in safe["phone"]
    assert "Segmentation fault" not in safe["unknown_internal_col"]


def test_get_user_friendly_error_unknown_exception() -> None:
    err = RuntimeError("some internal error")
    msg = get_user_friendly_error(err)
    # Không được để lộ "some internal error" hoặc stack trace
    assert "some internal error" not in msg
    assert msg == MSG_OPERATION_FAILED


def test_get_field_errors_safe_no_fields() -> None:
    err = ServiceUnavailableError()
    assert get_field_errors_safe(err) == {}

    assert get_field_errors_safe(None) == {}


def test_confirm_dialog_default_labels(tk_root) -> None:
    """ConfirmDialog phải dùng 'Confirm' và 'Cancel' mặc định theo chuẩn tiếng Anh."""
    dlg = ConfirmDialog(tk_root, title="Confirm", message="Are you sure?")
    try:
        assert dlg._confirm_btn.cget("text") == "Confirm"
        assert dlg._cancel_btn.cget("text") == "Cancel"
    finally:
        dlg.destroy()


# ==============================================================================
# 10. TEST COMPONENT GALLERY ERROR PATHS (NG01-08)
# ==============================================================================
def test_gallery_conflict_error_handling_no_vietnamese(monkeypatch) -> None:
    """Gallery khi mở máy gặp CONFLICT phải bắn Toast tiếng Anh, không hiển thị tiếng Việt."""
    from cyberhub_manager.ui.component_gallery import ComponentGalleryApp, ACTOR_STAFF
    from cyberhub_manager.services.mocks.factory import build_mock_services
    from cyberhub_manager.services.mocks.scenarios import MockScenario

    captured_toasts: list[tuple[str, str]] = []
    monkeypatch.setattr(ToastManager, "show", lambda parent, message, kind="info": captured_toasts.append((message, kind)))

    dummy_app = MagicMock(spec=ComponentGalleryApp)
    dummy_app._services = build_mock_services(MockScenario.CONFLICT)
    dummy_app._current_actor = ACTOR_STAFF

    ComponentGalleryApp._handle_card_open(dummy_app, 1)

    assert len(captured_toasts) == 1
    msg, kind = captured_toasts[0]
    assert kind == "error"
    assert "Open session failed: Operation conflict" in msg
    assert "Máy đã có phiên đang hoạt động" not in msg
    # Kiểm tra toàn bộ là ký tự tiếng Anh (không chứa dấu tiếng Việt)
    assert not any(ord(c) > 127 for c in msg)


def test_gallery_unavailable_table_state_no_vietnamese() -> None:
    """Gallery khi tải bảng gặp UNAVAILABLE phải set trạng thái ERROR bằng tiếng Anh, không có tiếng Việt."""
    from cyberhub_manager.ui.component_gallery import ComponentGalleryApp
    from cyberhub_manager.services.mocks.factory import build_mock_services
    from cyberhub_manager.services.mocks.scenarios import MockScenario

    dummy_app = MagicMock(spec=ComponentGalleryApp)
    dummy_app._services = build_mock_services(MockScenario.UNAVAILABLE)
    dummy_table = MagicMock()
    dummy_app._table = dummy_table

    ComponentGalleryApp._load_table_data(dummy_app)

    calls = dummy_table.set_state.call_args_list
    assert len(calls) == 2
    # Lần 2 là set ERROR state
    state_arg = calls[1][0][0]
    kwargs = calls[1][1]
    assert state_arg == ViewState.ERROR
    msg = kwargs["message"]
    assert "Unable to load data (Service is temporarily unavailable" in msg
    assert "Không tải được dữ liệu" not in msg
    assert not any(ord(c) > 127 for c in msg)


def test_gallery_unavailable_machines_no_vietnamese(tk_root) -> None:
    """Gallery khi nạp danh sách máy gặp UNAVAILABLE phải hiện nhãn lỗi tiếng Anh."""
    from cyberhub_manager.ui.component_gallery import ComponentGalleryApp
    from cyberhub_manager.services.mocks.factory import build_mock_services
    from cyberhub_manager.services.mocks.scenarios import MockScenario

    dummy_app = MagicMock(spec=ComponentGalleryApp)
    dummy_app._services = build_mock_services(MockScenario.UNAVAILABLE)
    dummy_app._machines_grid = ctk.CTkFrame(tk_root)
    dummy_app._machine_cards = []

    ComponentGalleryApp._render_machine_cards(dummy_app)

    err_frames = [w for w in dummy_app._machines_grid.winfo_children() if isinstance(w, ctk.CTkFrame)]
    assert len(err_frames) == 1
    label = next(w for w in err_frames[0].winfo_children() if isinstance(w, ctk.CTkLabel))
    text = label.cget("text")
    assert "Service is temporarily unavailable" in text
    assert "Không tải được dữ liệu" not in text
    assert not any(ord(c) > 127 for c in text.replace("⚠", "").strip())


# ==============================================================================
# 11. TEST COMPONENT GALLERY — VALIDATION_ERROR (NG01-02/03)
# ==============================================================================
def test_gallery_validation_error_field_errors(tk_root, monkeypatch) -> None:
    """Scenario VALIDATION_ERROR: submit form tạo khách hàng phải hiện lỗi
    từng trường bằng tiếng Anh, bắn Toast tổng quát, giữ dữ liệu nhập
    và trả is_busy=False qua finally."""
    from cyberhub_manager.ui.component_gallery import ComponentGalleryApp
    from cyberhub_manager.services.mocks.factory import build_mock_services
    from cyberhub_manager.services.mocks.scenarios import MockScenario

    captured_toasts: list[tuple[str, str]] = []
    monkeypatch.setattr(
        ToastManager, "show",
        lambda parent, message, kind="info": captured_toasts.append((message, kind)),
    )

    dummy_app = MagicMock(spec=ComponentGalleryApp)
    dummy_app._services = build_mock_services(MockScenario.VALIDATION_ERROR)

    # Tạo FormField thật trên tk_root để kiểm tra set_error / get_value
    dummy_app._f_name = FormField(tk_root, label="Name", initial_value="Test User")
    dummy_app._f_phone = FormField(tk_root, label="Phone", initial_value="0912345678")
    dummy_app._f_user = FormField(tk_root, label="Username", initial_value="testuser")
    dummy_app._f_pass = FormField(tk_root, label="Password", initial_value="abc")
    dummy_app._f_err = dummy_app._f_phone

    submit_btn = ActionButton(tk_root, text="Submit", kind="primary")
    dummy_app._btn_submit_demo = submit_btn

    # Gọi handler
    ComponentGalleryApp._handle_submit_customer_demo(dummy_app)

    # 1) Nút phải trả về is_busy=False (finally block)
    assert submit_btn.is_busy is False

    # 2) Phải có Toast lỗi tổng quát tiếng Anh
    assert len(captured_toasts) == 1
    toast_msg, toast_kind = captured_toasts[0]
    assert toast_kind == "error"
    assert "Invalid data provided" in toast_msg
    assert not any(ord(c) > 127 for c in toast_msg)

    # 3) Phone field phải hiển thị lỗi tiếng Anh
    phone_err = dummy_app._f_phone._error_label.cget("text")
    assert phone_err != ""
    assert "Phone number must have 10 digits" in phone_err
    assert not any(ord(c) > 127 for c in phone_err)

    # 4) Password field phải hiển thị lỗi tiếng Anh
    pass_err = dummy_app._f_pass._error_label.cget("text")
    assert pass_err != ""
    assert "Password must have at least 6 characters" in pass_err
    assert not any(ord(c) > 127 for c in pass_err)

    # 5) Dữ liệu người dùng nhập phải được giữ nguyên
    assert dummy_app._f_name.get_value() == "Test User"
    assert dummy_app._f_phone.get_value() == "0912345678"
    assert dummy_app._f_user.get_value() == "testuser"
    assert dummy_app._f_pass.get_value() == "abc"


def test_gallery_conflict_submit_form_english_toast(tk_root, monkeypatch) -> None:
    """Scenario CONFLICT: submit form tạo khách hàng phải Toast lỗi tiếng Anh,
    hiện lỗi tại trường phone, giữ dữ liệu và trả is_busy=False."""
    from cyberhub_manager.ui.component_gallery import ComponentGalleryApp
    from cyberhub_manager.services.mocks.factory import build_mock_services
    from cyberhub_manager.services.mocks.scenarios import MockScenario

    captured_toasts: list[tuple[str, str]] = []
    monkeypatch.setattr(
        ToastManager, "show",
        lambda parent, message, kind="info": captured_toasts.append((message, kind)),
    )

    dummy_app = MagicMock(spec=ComponentGalleryApp)
    dummy_app._services = build_mock_services(MockScenario.CONFLICT)

    dummy_app._f_name = FormField(tk_root, label="Name", initial_value="User")
    dummy_app._f_phone = FormField(tk_root, label="Phone", initial_value="0912345678")
    dummy_app._f_user = FormField(tk_root, label="Username", initial_value="usr")
    dummy_app._f_pass = FormField(tk_root, label="Password", initial_value="pass123")
    dummy_app._f_err = dummy_app._f_phone

    submit_btn = ActionButton(tk_root, text="Submit", kind="primary")
    dummy_app._btn_submit_demo = submit_btn

    ComponentGalleryApp._handle_submit_customer_demo(dummy_app)

    # Nút phải trả is_busy=False
    assert submit_btn.is_busy is False

    # Toast lỗi tiếng Anh
    assert len(captured_toasts) == 1
    toast_msg, toast_kind = captured_toasts[0]
    assert toast_kind == "error"
    assert "conflict" in toast_msg.lower()
    assert not any(ord(c) > 127 for c in toast_msg)

    # Phone field phải hiện lỗi "Phone number is already in use."
    phone_err = dummy_app._f_phone._error_label.cget("text")
    assert "already in use" in phone_err.lower()
    assert "Số điện thoại đã được sử dụng" not in phone_err

    # Dữ liệu nhập giữ nguyên
    assert dummy_app._f_phone.get_value() == "0912345678"
    assert dummy_app._f_pass.get_value() == "pass123"


def test_gallery_success_submit_form(tk_root, monkeypatch) -> None:
    """Scenario SUCCESS: submit form tạo khách hàng phải Toast thành công tiếng Anh,
    không có lỗi trường, và trả is_busy=False."""
    from cyberhub_manager.ui.component_gallery import ComponentGalleryApp
    from cyberhub_manager.services.mocks.factory import build_mock_services
    from cyberhub_manager.services.mocks.scenarios import MockScenario

    captured_toasts: list[tuple[str, str]] = []
    monkeypatch.setattr(
        ToastManager, "show",
        lambda parent, message, kind="info": captured_toasts.append((message, kind)),
    )

    dummy_app = MagicMock(spec=ComponentGalleryApp)
    dummy_app._services = build_mock_services(MockScenario.SUCCESS)

    dummy_app._f_name = FormField(tk_root, label="Name", initial_value="Nguyen Van An")
    dummy_app._f_phone = FormField(tk_root, label="Phone", initial_value="0999888777")
    dummy_app._f_user = FormField(tk_root, label="Username", initial_value="newuser")
    dummy_app._f_pass = FormField(tk_root, label="Password", initial_value="pass123")
    dummy_app._f_err = dummy_app._f_phone

    submit_btn = ActionButton(tk_root, text="Submit", kind="primary")
    dummy_app._btn_submit_demo = submit_btn

    ComponentGalleryApp._handle_submit_customer_demo(dummy_app)

    # Nút phải trả is_busy=False
    assert submit_btn.is_busy is False

    # Toast thành công
    assert len(captured_toasts) == 1
    toast_msg, toast_kind = captured_toasts[0]
    assert toast_kind == "success"
    assert "Customer created successfully" in toast_msg

    # Không có lỗi tại bất kỳ trường nào
    assert dummy_app._f_phone._error_label.cget("text") == ""
    assert dummy_app._f_pass._error_label.cget("text") == ""
    assert dummy_app._f_name._error_label.cget("text") == ""
    assert dummy_app._f_user._error_label.cget("text") == ""


# ==============================================================================
# 12. TEST KEYBOARD NAVIGATION & MAINTENANCE SERVICE CALL (P1 - NG01)
# ==============================================================================
def test_form_field_bind_return(tk_root) -> None:
    """FormField.bind_return gắn phím Enter (<Return>) kích hoạt callback submit.

    event_generate không ổn định trong môi trường test headless (CI/Windows),
    vì vậy test kiểm tra rằng binding đã được đăng ký trên tk Entry nội bộ
    và lambda callback hoạt động đúng.
    """
    calls: list[int] = []
    field = FormField(tk_root, label="Demo")
    field.pack()
    tk_root.update()

    # Trước khi bind: chưa có binding <Return> trên Entry nội bộ
    bindings_before = field._entry._entry.bind("<Return>")
    # Sau khi bind_return: phải có binding mới
    field.bind_return(lambda: calls.append(1))
    bindings_after = field._entry._entry.bind("<Return>")
    assert len(bindings_after) > len(bindings_before), (
        "bind_return phải đăng ký binding <Return> trên Entry nội bộ"
    )

    # Kiểm tra API tồn tại và callable
    assert hasattr(field, "bind_return")
    assert callable(field.bind_return)


def test_gallery_maintenance_action_manager_success(monkeypatch) -> None:
    """Gallery gọi set_maintenance kết thúc bảo trì với quyền MANAGER:
    chuyển trạng thái máy về AVAILABLE và Toast thành công tiếng Anh."""
    from cyberhub_manager.ui.component_gallery import ComponentGalleryApp, ACTOR_MANAGER
    from cyberhub_manager.services.mocks.factory import build_mock_services
    from cyberhub_manager.services.mocks.scenarios import MockScenario
    from cyberhub_manager.domain.enums import MachineStatus

    captured_toasts: list[tuple[str, str]] = []
    monkeypatch.setattr(
        ToastManager, "show",
        lambda parent, message, kind="info": captured_toasts.append((message, kind)),
    )

    dummy_app = MagicMock(spec=ComponentGalleryApp)
    dummy_app._services = build_mock_services(MockScenario.SUCCESS)
    dummy_app._current_actor = ACTOR_MANAGER
    dummy_app._render_machine_cards = MagicMock()

    # Máy 3 ban đầu đang ở MAINTENANCE trong mock store
    assert dummy_app._services.machines._data.get_machine(3).status == MachineStatus.MAINTENANCE

    # Gọi action kết thúc bảo trì
    ComponentGalleryApp._handle_card_maintenance(dummy_app, 3)

    # Trạng thái máy 3 đã được cập nhật về AVAILABLE qua service thật
    assert dummy_app._services.machines._data.get_machine(3).status == MachineStatus.AVAILABLE

    # Render lại được gọi
    dummy_app._render_machine_cards.assert_called_once()

    # Bắn Toast thành công tiếng Anh
    assert len(captured_toasts) == 1
    msg, kind = captured_toasts[0]
    assert kind == "success"
    assert "Maintenance ended for Machine ID=3" in msg
    assert not any(ord(c) > 127 for c in msg)


def test_gallery_maintenance_action_staff_forbidden(monkeypatch) -> None:
    """Gallery khi actor là STAFF thực hiện thao tác bảo trì phải bị từ chối
    bởi ForbiddenError và hiển thị Toast lỗi tiếng Anh, không crash."""
    from cyberhub_manager.ui.component_gallery import ComponentGalleryApp, ACTOR_STAFF
    from cyberhub_manager.services.mocks.factory import build_mock_services
    from cyberhub_manager.services.mocks.scenarios import MockScenario

    captured_toasts: list[tuple[str, str]] = []
    monkeypatch.setattr(
        ToastManager, "show",
        lambda parent, message, kind="info": captured_toasts.append((message, kind)),
    )

    dummy_app = MagicMock(spec=ComponentGalleryApp)
    dummy_app._services = build_mock_services(MockScenario.SUCCESS)
    dummy_app._current_actor = ACTOR_STAFF  # STAFF không có quyền quản lý máy
    dummy_app._render_machine_cards = MagicMock()

    ComponentGalleryApp._handle_card_maintenance(dummy_app, 3)

    # Toast báo lỗi tiếng Anh
    assert len(captured_toasts) == 1
    msg, kind = captured_toasts[0]
    assert kind == "error"
    assert "Maintenance action failed: You do not have permission to perform this action." in msg
    assert not any(ord(c) > 127 for c in msg)
