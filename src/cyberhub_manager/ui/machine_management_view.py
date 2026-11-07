"""NG-03 — Màn Quản lý máy theo Stitch (chỉ Manager/Admin).

- Bố cục theo Stitch `qu_n_l_m_y_cyberhub_manager_1280x720`: 4 thẻ KPI, ô tìm kiếm + tab
  trạng thái, bảng có badge, phiên hiện tại, cập nhật cuối, nút thao tác từng dòng, phân trang.
- Máy IN_USE: không cho bảo trì hoặc ngừng sử dụng (MAC-04, MAC-06); vẫn sửa được
  tên/đơn giá vì phiên đang chạy giữ giá snapshot (SES-02).
- Ngừng sử dụng luôn hỏi xác nhận; máy chưa có lịch sử bị xóa, có lịch sử thì archive.
- Không có thẻ/tab "Đã lưu trữ": list_machines chỉ trả máy is_active=True (contract LI-02).
- Service vẫn kiểm tra quyền lại dù App Shell đã ẩn menu với STAFF.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import customtkinter as ctk

from ..domain.dtos import MachineArchiveResult, MachineSummary
from ..domain.enums import MachineArchiveAction, MachineStatus
from ..domain.models import Machine
from .app_shell import ViewContext, role_label
from .background import TaskRunner, default_runner
from .components import ConfirmDialog
from .components.action_button import ActionButton
from .components.stitch_button import stitch_button
from .dashboard_view import filter_machines, summarize
from .dialogs.machine_dialog import MachineDialog
from .feedback import notify_error, notify_success
from .formatters import format_datetime
from .messages import MSG_LOADING, MSG_NO_DATA, MSG_RETRY, get_user_friendly_error
from .navigation import MANAGEMENT_ROLES
from .state import ViewState
from .theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_KPI_VALUE,
    FONT_ST_LABEL_CAPS,
    FONT_ST_MONO_11,
    FONT_ST_MONO_BODY,
    FONT_ST_MONO_SM,
    FONT_ST_MONO_XS_STRONG,
    FONT_ST_PAGE_TITLE,
    STITCH_AMBER,
    STITCH_AMBER_HOVER,
    STITCH_BADGE_DANGER_BG,
    STITCH_BADGE_DANGER_BORDER,
    STITCH_BADGE_SUCCESS_BG,
    STITCH_BADGE_SUCCESS_BORDER,
    STITCH_BADGE_WARNING_BG,
    STITCH_BADGE_WARNING_BORDER,
    STITCH_CARD_BG,
    STITCH_CARD_BORDER,
    STITCH_CHIP_BG,
    STITCH_CHIP_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_GAP,
    STITCH_ICON_DANGER_BG,
    STITCH_ICON_DANGER_BORDER,
    STITCH_ICON_SUCCESS_BG,
    STITCH_ICON_SUCCESS_BORDER,
    STITCH_ICON_WARNING_BG,
    STITCH_ICON_WARNING_BORDER,
    STITCH_INPUT_BG,
    STITCH_INPUT_BORDER,
    STITCH_NAV_HOVER,
    STITCH_RADIUS,
    STITCH_RADIUS_LG,
    STITCH_SUCCESS,
    STITCH_TAB_DANGER_BORDER,
    STITCH_TAB_HOVER,
    STITCH_TAB_SUCCESS_BORDER,
    STITCH_TAB_WARNING_BORDER,
    STITCH_TEXT,
    STITCH_TEXT_DIM,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_ON_CYAN,
    STITCH_TEXT_STRONG,
    STITCH_WARNING,
)

IN_USE_HINT = "Máy đang có phiên hoạt động: không thể bảo trì hoặc ngừng sử dụng."


# ----------------------------------------------------------------------
# Hàm thuần (test được không cần Tk)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class MachineActions:
    can_edit: bool
    can_toggle_maintenance: bool
    maintenance_label: str
    can_archive: bool


def machine_actions(machine: MachineSummary | None) -> MachineActions:
    """Nút nào được bật cho một máy."""
    if machine is None:
        return MachineActions(False, False, "Bảo trì", False)
    in_use = machine.status == MachineStatus.IN_USE
    label = "Kết thúc bảo trì" if machine.status == MachineStatus.MAINTENANCE else "Bảo trì"
    return MachineActions(
        can_edit=True,
        can_toggle_maintenance=not in_use,
        maintenance_label=label,
        can_archive=not in_use,
    )


PAGE_SIZE = 7  # số dòng mỗi trang: vừa khít bảng ở cửa sổ 1280x720


def format_short_duration(seconds: int) -> str:
    """Thời lượng gọn cho cột "Phiên hiện tại" theo Stitch: "45m", "1h 30m"."""
    total_minutes = max(seconds, 0) // 60
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def current_session_cells(machine: MachineSummary) -> tuple[str, str]:
    """(tên khách, thời lượng) của phiên đang chạy; máy không có phiên -> ("—", "")."""
    active = machine.active_session
    if active is None:
        return "—", ""
    return active.session.customer_name, format_short_duration(active.elapsed_seconds)


def format_updated_ago(updated_at: datetime, now: datetime) -> str:
    """Cột "Cập nhật cuối": Vừa xong / N phút trước / N giờ trước / dd/mm/yyyy (giờ VN)."""
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    seconds = (now - updated_at).total_seconds()
    if seconds < 60:  # gồm cả lệch đồng hồ (số âm)
        return "Vừa xong"
    if seconds < 3600:
        return f"{int(seconds // 60)} phút trước"
    if seconds < 24 * 3600:
        return f"{int(seconds // 3600)} giờ trước"
    return format_datetime(updated_at).split(" ")[1]  # "HH:MM dd/mm/yyyy" -> "dd/mm/yyyy"


@dataclass(frozen=True)
class Page:
    """Một trang của bảng: items + thông tin cho chân bảng."""

    items: list[Any]
    number: int  # trang hiện tại, bắt đầu từ 1
    total_pages: int
    first: int  # số thứ tự dòng đầu (1-based); 0 khi rỗng
    last: int
    total: int


def paginate(items: Iterable[Any], page: int, page_size: int = PAGE_SIZE) -> Page:
    """Cắt trang; page ngoài khoảng được kéo về trang hợp lệ gần nhất."""
    items = list(items)
    total = len(items)
    total_pages = max(1, math.ceil(total / page_size))
    number = min(max(page, 1), total_pages)
    start = (number - 1) * page_size
    chunk = items[start : start + page_size]
    return Page(chunk, number, total_pages, start + 1 if chunk else 0, start + len(chunk), total)


def page_caption(page: Page) -> str:
    return f"Hiển thị {page.first}-{page.last} trên tổng số {page.total} máy"


def format_number(value: int) -> str:
    """12000 -> "12.000" (Stitch tách "VND/h" thành chữ phụ bên cạnh)."""
    return f"{value:,}".replace(",", ".")


def archive_message(result: MachineArchiveResult) -> str:
    if result.action == MachineArchiveAction.DELETED:
        return "Machine deleted."
    return "Machine archived. Its history is kept."


# ----------------------------------------------------------------------
# Cấu hình giao diện theo Stitch
# ----------------------------------------------------------------------
# (tiêu đề, thuộc tính MachineCounts, màu chữ, nền icon, viền icon, icon)
_KPI_SPECS = (
    ("TỔNG SỐ MÁY", "total", STITCH_TEXT_STRONG, STITCH_CHIP_BG, STITCH_CHIP_BORDER, "▤"),
    ("TRỐNG SẴN SÀNG", "available", STITCH_SUCCESS, STITCH_ICON_SUCCESS_BG, STITCH_ICON_SUCCESS_BORDER, "✓"),
    ("ĐANG SỬ DỤNG", "in_use", STITCH_DANGER, STITCH_ICON_DANGER_BG, STITCH_ICON_DANGER_BORDER, "◷"),
    ("BẢO TRÌ KỸ THUẬT", "maintenance", STITCH_WARNING, STITCH_ICON_WARNING_BG, STITCH_ICON_WARNING_BORDER, "⚒"),
)

# (status, nhãn, màu chữ, viền)
_TAB_SPECS = (
    (None, "Tất cả", STITCH_TEXT, STITCH_CHIP_BORDER),
    (MachineStatus.AVAILABLE, "Trống", STITCH_SUCCESS, STITCH_TAB_SUCCESS_BORDER),
    (MachineStatus.IN_USE, "Đang dùng", STITCH_DANGER, STITCH_TAB_DANGER_BORDER),
    (MachineStatus.MAINTENANCE, "Bảo trì", STITCH_WARNING, STITCH_TAB_WARNING_BORDER),
)

# status -> (nhãn, chữ, nền, viền)
STATUS_BADGES: dict[MachineStatus, tuple[str, str, str, str]] = {
    MachineStatus.AVAILABLE: ("Trống", STITCH_SUCCESS, STITCH_BADGE_SUCCESS_BG, STITCH_BADGE_SUCCESS_BORDER),
    MachineStatus.IN_USE: ("Đang dùng", STITCH_DANGER, STITCH_BADGE_DANGER_BG, STITCH_BADGE_DANGER_BORDER),
    MachineStatus.MAINTENANCE: ("Bảo trì", STITCH_WARNING, STITCH_BADGE_WARNING_BG, STITCH_BADGE_WARNING_BORDER),
}

# (key, tiêu đề, tỉ lệ độ rộng, căn lề) — mọi cột chia theo tỉ lệ để header và dòng thẳng hàng
_COLUMNS = (
    ("code", "MÃ MÁY", 2, "w"),
    ("name", "TÊN MÁY", 3, "w"),
    ("status", "TRẠNG THÁI", 2, "w"),
    ("rate", "GIÁ THEO GIỜ", 2, "w"),
    ("session", "PHIÊN HIỆN TẠI", 3, "w"),
    ("updated", "CẬP NHẬT CUỐI", 2, "w"),
    ("actions", "THAO TÁC", 2, "e"),
)
ROW_HEIGHT = 50


def _gap(index: int, count: int) -> tuple[int, int]:
    half = STITCH_GAP // 2
    return (0 if index == 0 else half, 0 if index == count - 1 else half)


def _bind_hover(row: Any) -> None:
    """Tô nền dòng khi rê chuột (Stitch: hover:bg-[#161d2d]); chuột đi vào ô con không làm tắt."""

    def inside() -> bool:
        widget = row.winfo_containing(row.winfo_pointerx(), row.winfo_pointery())
        while widget is not None:
            if widget is row:
                return True
            widget = widget.master
        return False

    def enter(_event: Any = None) -> None:
        row.configure(fg_color=STITCH_NAV_HOVER)

    def leave(_event: Any = None) -> None:
        if row.winfo_exists() and not inside():
            row.configure(fg_color="transparent")

    def bind_all(widget: Any) -> None:
        widget.bind("<Enter>", enter, add="+")
        widget.bind("<Leave>", leave, add="+")
        for child in widget.winfo_children():
            bind_all(child)

    bind_all(row)


def _configure_columns(frame: Any) -> None:
    """Header và mọi dòng dùng cùng cấu hình cột để thẳng hàng."""
    for index, (_key, _title, weight, _anchor) in enumerate(_COLUMNS):
        frame.grid_columnconfigure(index, weight=weight, uniform="column")


class MachineManagementView(ctk.CTkFrame):
    """Màn Quản lý máy: KPI + tìm kiếm/tab + bảng phân trang, thao tác ngay trên từng dòng."""

    def __init__(
        self,
        master: Any,
        context: ViewContext,
        *,
        runner: TaskRunner | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._context = context
        self._runner = runner or default_runner()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._machines: list[MachineSummary] = []
        self._status_filter: MachineStatus | None = None
        self._keyword = ""
        self._page = 1
        self._state = ViewState.LOADING
        self._busy = False
        self._closed = False
        self._kpi_labels: dict[str, ctk.CTkLabel] = {}
        self._tab_buttons: dict[MachineStatus | None, ctk.CTkButton] = {}
        self._row_buttons: dict[int, dict[str, ActionButton]] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build_header()
        self._build_kpis()
        self._build_toolbar()
        self._build_table()
        self._build_footer()

        if context.session.role not in MANAGEMENT_ROLES:
            # Phòng thủ: App Shell đã chặn, nhưng view vẫn không tải dữ liệu cho STAFF.
            self._add_button.set_enabled(False)
            self._show_state(ViewState.ERROR, get_user_friendly_error("PERMISSION_DENIED"))
            return
        self.reload()

    # ------------------------------------------------------------------
    # Thuộc tính công khai (test)
    # ------------------------------------------------------------------
    @property
    def state(self) -> ViewState:
        return self._state

    @property
    def machines(self) -> list[MachineSummary]:
        return list(self._machines)

    @property
    def add_button(self) -> ActionButton:
        return self._add_button

    @property
    def current_page(self) -> Page:
        return paginate(filter_machines(self._machines, self._status_filter, self._keyword), self._page)

    @property
    def visible_machine_ids(self) -> list[int]:
        return [m.machine_id for m in self.current_page.items]

    def row_buttons(self, machine_id: int) -> dict[str, ActionButton]:
        """Nút "edit" / "maintenance" / "archive" của một dòng đang hiển thị."""
        return self._row_buttons[machine_id]

    def machine(self, machine_id: int) -> MachineSummary | None:
        return next((m for m in self._machines if m.machine_id == machine_id), None)

    # ------------------------------------------------------------------
    # Dựng giao diện
    # ------------------------------------------------------------------
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(
            titles, text="Quản lý máy", font=FONT_ST_PAGE_TITLE, text_color=STITCH_TEXT_STRONG, height=24, anchor="w"
        ).pack(anchor="w")
        ctk.CTkLabel(
            titles,
            text="Cấu hình, bảo trì và quản lý trạng thái máy",
            font=FONT_ST_MONO_BODY,
            text_color=STITCH_TEXT_MUTED,
            height=16,
            anchor="w",
        ).pack(anchor="w")
        self._add_button = stitch_button(header, "＋  Thêm máy", kind="primary", command=self._add, width=120)
        self._add_button.pack(side="right")
        self._refresh_button = stitch_button(header, "⟳  Làm mới", command=self.reload, width=96)
        self._refresh_button.pack(side="right", padx=(0, 8))

    def _build_kpis(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        for index, (title, attr, color, icon_bg, icon_border, icon) in enumerate(_KPI_SPECS):
            row.grid_columnconfigure(index, weight=1, uniform="kpi")
            card = ctk.CTkFrame(
                row,
                height=62,
                fg_color=STITCH_CARD_BG,
                border_width=1,
                border_color=STITCH_CARD_BORDER,
                corner_radius=STITCH_RADIUS_LG,
            )
            card.grid(row=0, column=index, sticky="ew", padx=_gap(index, len(_KPI_SPECS)))
            card.pack_propagate(False)
            text_box = ctk.CTkFrame(card, fg_color="transparent")
            text_box.pack(side="left", padx=14)
            ctk.CTkLabel(
                text_box,
                text=title,
                font=FONT_ST_LABEL_CAPS,
                text_color=STITCH_TEXT_MUTED if attr == "total" else color,
                height=14,
                anchor="w",
            ).pack(anchor="w")
            value = ctk.CTkLabel(text_box, text="–", font=FONT_ST_KPI_VALUE, text_color=color, height=26, anchor="w")
            value.pack(anchor="w")
            self._kpi_labels[attr] = value
            icon_box = ctk.CTkFrame(
                card,
                width=32,
                height=32,
                fg_color=icon_bg,
                border_width=1,
                border_color=icon_border,
                corner_radius=STITCH_RADIUS_LG,
            )
            icon_box.pack(side="right", padx=14)
            icon_box.pack_propagate(False)
            ctk.CTkLabel(
                icon_box, text=icon, font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT if attr == "total" else color
            ).pack(expand=True)

    def _build_toolbar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self._search_entry = ctk.CTkEntry(
            bar,
            width=340,
            height=32,
            placeholder_text="⌕  Tìm theo mã hoặc tên máy…",
            fg_color=STITCH_INPUT_BG,
            border_color=STITCH_INPUT_BORDER,
            border_width=1,
            corner_radius=STITCH_RADIUS,
            text_color=STITCH_TEXT,
            font=FONT_ST_BODY,
        )
        self._search_entry.pack(side="left")
        self._search_entry.bind("<KeyRelease>", lambda _e: self._apply_search(self._search_entry.get()))
        tabs = ctk.CTkFrame(bar, fg_color="transparent")
        tabs.pack(side="right")
        for status, *_style in _TAB_SPECS:
            button = ctk.CTkButton(
                tabs,
                text="",
                width=96,
                height=28,
                corner_radius=STITCH_RADIUS,
                border_width=1,
                font=FONT_ST_BODY,
                command=lambda s=status: self.set_status_filter(s),
            )
            button.pack(side="left", padx=(8, 0))
            self._tab_buttons[status] = button
        self._update_tabs()

    def _build_table(self) -> None:
        table = ctk.CTkFrame(
            self,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
        )
        table.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        header = ctk.CTkFrame(table, fg_color="transparent", height=34)
        header.pack(fill="x", padx=14, pady=(6, 0))
        _configure_columns(header)
        for index, (_key, title, _weight, anchor) in enumerate(_COLUMNS):
            ctk.CTkLabel(
                header, text=title, font=FONT_ST_LABEL_CAPS, text_color=STITCH_TEXT_DIM, anchor=anchor, height=28
            ).grid(row=0, column=index, sticky="ew", padx=4)
        ctk.CTkFrame(table, fg_color=STITCH_CARD_BORDER, height=1, corner_radius=0).pack(fill="x", padx=14)
        self._rows_frame = ctk.CTkFrame(table, fg_color="transparent")
        self._rows_frame.pack(fill="both", expand=True, padx=14)
        # Khung LOADING / EMPTY / ERROR nằm trong vùng dòng.
        self._state_frame = ctk.CTkFrame(table, fg_color="transparent")
        self._state_label = ctk.CTkLabel(self._state_frame, text="", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED)
        self._state_label.pack(pady=(40, 10))
        self._retry_button = stitch_button(self._state_frame, MSG_RETRY, command=self.reload, width=100)

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        role = role_label(self._context.session, self._context.language)
        ctk.CTkLabel(
            footer,
            text=f"⛨  Tài khoản {role} • Yêu cầu xác nhận khi chuyển bảo trì hoặc lưu trữ máy",
            font=FONT_ST_MONO_11,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left")
        self._pager = ctk.CTkFrame(footer, fg_color="transparent")
        self._pager.pack(side="right")
        self._caption_label = ctk.CTkLabel(footer, text="", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED)
        self._caption_label.pack(side="right", padx=(0, 12))

    # ------------------------------------------------------------------
    # Tải dữ liệu
    # ------------------------------------------------------------------
    def reload(self) -> None:
        if self._closed:
            return
        if not self._machines:
            self._show_state(ViewState.LOADING, MSG_LOADING)
        self._refresh_button.set_busy(True)
        services, session = self._context.services, self._context.session
        self._runner.submit(
            self,
            lambda: services.machines.list_machines(session.store_id),
            self._on_loaded,
            self._on_load_failed,
        )

    def _on_loaded(self, machines: list[MachineSummary]) -> None:
        if self._closed:
            return
        self._refresh_button.set_busy(False)
        self._machines = list(machines)
        self._state = ViewState.READY
        self._render()

    def _on_load_failed(self, error: Exception) -> None:
        if self._closed:
            return
        self._refresh_button.set_busy(False)
        self._machines = []
        self._render_kpis()
        self._show_state(ViewState.ERROR, get_user_friendly_error(error))

    # ------------------------------------------------------------------
    # Lọc / tìm kiếm / phân trang
    # ------------------------------------------------------------------
    def set_status_filter(self, status: MachineStatus | None) -> None:
        self._status_filter = status
        self._page = 1
        self._render()

    def handle_search(self, text: str) -> None:
        """Nhận từ khóa từ ô tìm kiếm trên topbar (NG-02); đồng bộ vào ô tìm kiếm của màn."""
        self._search_entry.delete(0, "end")
        if text:
            self._search_entry.insert(0, text)
        self._apply_search(text)

    def _apply_search(self, text: str) -> None:
        self._keyword = text
        self._page = 1
        self._render()

    def go_to_page(self, number: int) -> None:
        self._page = number
        self._render()

    # ------------------------------------------------------------------
    # Vẽ
    # ------------------------------------------------------------------
    def _render(self) -> None:
        self._render_kpis()
        if not self._machines and self._state != ViewState.READY:
            return  # đang tải lần đầu hoặc lỗi: giữ khung trạng thái
        page = self.current_page
        self._page = page.number
        self._render_rows(page)
        self._render_pager(page)

    def _render_kpis(self) -> None:
        counts = summarize(self._machines)
        for attr, label in self._kpi_labels.items():
            label.configure(text=str(getattr(counts, attr)) if self._machines else "–")
        self._update_tabs(counts if self._machines else None)

    def _update_tabs(self, counts: Any = None) -> None:
        for status, label, color, border in _TAB_SPECS:
            active = status == self._status_filter
            self._tab_buttons[status].configure(
                text=label if counts is None else f"{label} ({counts.for_status(status)})",
                fg_color=STITCH_CYAN if active else STITCH_CHIP_BG,
                hover_color=STITCH_CYAN if active else STITCH_TAB_HOVER,
                border_color=STITCH_CYAN if active else border,
                text_color=STITCH_TEXT_ON_CYAN if active else color,
                font=FONT_ST_BODY_STRONG if active else FONT_ST_BODY,
            )

    def _show_state(self, state: ViewState, message: str) -> None:
        self._state = state
        self._rows_frame.pack_forget()
        for child in self._rows_frame.winfo_children():
            child.destroy()
        self._row_buttons.clear()
        self._state_label.configure(text=message, text_color=STITCH_DANGER if state == ViewState.ERROR else STITCH_TEXT_MUTED)
        if state == ViewState.ERROR:
            self._retry_button.pack()
        else:
            self._retry_button.pack_forget()
        self._state_frame.pack(fill="both", expand=True)
        self._caption_label.configure(text="")
        for child in self._pager.winfo_children():
            child.destroy()

    def _render_rows(self, page: Page) -> None:
        for child in self._rows_frame.winfo_children():
            child.destroy()
        self._row_buttons.clear()
        if not page.items:
            self._show_state(ViewState.EMPTY, MSG_NO_DATA)
            return
        self._state = ViewState.READY
        self._state_frame.pack_forget()
        self._rows_frame.pack(fill="both", expand=True, padx=14)
        now = self._clock()
        for index, machine in enumerate(page.items):
            if index:
                ctk.CTkFrame(self._rows_frame, fg_color=STITCH_CARD_BORDER, height=1, corner_radius=0).pack(fill="x")
            self._build_row(machine, now)

    def _build_row(self, machine: MachineSummary, now: datetime) -> None:
        row = ctk.CTkFrame(self._rows_frame, fg_color="transparent", height=ROW_HEIGHT)
        row.pack(fill="x")
        row.grid_propagate(False)
        row.grid_rowconfigure(0, weight=1)
        _configure_columns(row)

        def cell(column: int, widget: Any) -> None:
            widget.grid(row=0, column=column, sticky=_COLUMNS[column][3], padx=4)

        cell(0, ctk.CTkLabel(row, text=machine.machine_code, font=FONT_ST_MONO_SM, text_color=STITCH_CYAN))
        cell(1, ctk.CTkLabel(row, text=machine.name, font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT_STRONG))

        label, color, bg, border = STATUS_BADGES.get(
            machine.status, (str(machine.status), STITCH_TEXT_MUTED, STITCH_CHIP_BG, STITCH_CHIP_BORDER)
        )
        badge = ctk.CTkFrame(row, fg_color=bg, border_width=1, border_color=border, corner_radius=STITCH_RADIUS)
        ctk.CTkLabel(badge, text=f"● {label}", font=FONT_ST_MONO_XS_STRONG, text_color=color, height=18).pack(padx=8, pady=1)
        cell(2, badge)

        rate = ctk.CTkFrame(row, fg_color="transparent")
        ctk.CTkLabel(rate, text=format_number(machine.hourly_rate), font=FONT_ST_MONO_SM, text_color=STITCH_TEXT).pack(side="left")
        ctk.CTkLabel(rate, text=" VND/h", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED).pack(side="left")
        cell(3, rate)

        customer, duration = current_session_cells(machine)
        session_box = ctk.CTkFrame(row, fg_color="transparent")
        ctk.CTkLabel(
            session_box, text=customer, font=FONT_ST_BODY, text_color=STITCH_TEXT if duration else STITCH_TEXT_DIM, height=16, anchor="w"
        ).pack(anchor="w")
        if duration:
            ctk.CTkLabel(session_box, text=duration, font=FONT_ST_MONO_11, text_color=STITCH_CYAN, height=14, anchor="w").pack(anchor="w")
        cell(4, session_box)

        cell(5, ctk.CTkLabel(row, text=format_updated_ago(machine.updated_at, now), font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED))
        cell(6, self._build_row_actions(row, machine))
        _bind_hover(row)

    def _build_row_actions(self, row: Any, machine: MachineSummary) -> ctk.CTkFrame:
        actions = machine_actions(machine)
        in_maintenance = machine.status == MachineStatus.MAINTENANCE
        box = ctk.CTkFrame(row, fg_color="transparent")
        edit = stitch_button(box, "✎", command=lambda: self._edit(machine), width=28, height=26)
        maintenance = stitch_button(
            box, "↺" if in_maintenance else "⚒", command=lambda: self._toggle_maintenance(machine), width=28, height=26
        )
        if in_maintenance:  # Stitch tô nổi nút "Kết thúc bảo trì"
            maintenance.configure(fg_color=STITCH_AMBER, hover_color=STITCH_AMBER_HOVER, text_color=STITCH_TEXT_ON_CYAN, border_color=STITCH_AMBER)
        archive = stitch_button(box, "⊟", kind="danger", command=lambda: self._archive(machine), width=28, height=26)
        for button in (edit, maintenance, archive):
            button.pack(side="left", padx=(6, 0))
        edit.set_enabled(not self._busy and actions.can_edit)
        maintenance.set_enabled(not self._busy and actions.can_toggle_maintenance)
        archive.set_enabled(not self._busy and actions.can_archive)
        self._row_buttons[machine.machine_id] = {"edit": edit, "maintenance": maintenance, "archive": archive}
        return box

    def _render_pager(self, page: Page) -> None:
        self._caption_label.configure(text=page_caption(page))
        for child in self._pager.winfo_children():
            child.destroy()

        def pager_button(text: str, target: int, *, active: bool = False, enabled: bool = True) -> None:
            button = ctk.CTkButton(
                self._pager,
                text=text,
                width=26,
                height=24,
                corner_radius=STITCH_RADIUS,
                font=FONT_ST_MONO_11,
                fg_color=STITCH_CYAN if active else STITCH_CHIP_BG,
                hover_color=STITCH_CYAN if active else STITCH_TAB_HOVER,
                text_color=STITCH_TEXT_ON_CYAN if active else STITCH_TEXT_MUTED,
                state="normal" if enabled else "disabled",
                command=lambda: self.go_to_page(target),
            )
            button.pack(side="left", padx=(4, 0))

        pager_button("‹", page.number - 1, enabled=page.number > 1)
        start = max(1, min(page.number - 2, page.total_pages - 4))
        for number in range(start, min(page.total_pages, start + 4) + 1):
            pager_button(str(number), number, active=number == page.number)
        pager_button("›", page.number + 1, enabled=page.number < page.total_pages)

    # ------------------------------------------------------------------
    # Hành động
    # ------------------------------------------------------------------
    def _add(self) -> None:
        MachineDialog(self.winfo_toplevel(), self._context, runner=self._runner, on_saved=self._after_created)

    def _after_created(self, _machine: Machine) -> None:
        notify_success(self, "Machine created.")
        self.reload()

    def _edit(self, machine: MachineSummary) -> None:
        if self._busy:
            return
        MachineDialog(
            self.winfo_toplevel(),
            self._context,
            machine=machine,
            runner=self._runner,
            on_saved=self._after_updated,
        )

    def _after_updated(self, _machine: Machine) -> None:
        notify_success(self, "Machine updated.")
        self.reload()

    def _toggle_maintenance(self, machine: MachineSummary) -> None:
        if self._busy or not machine_actions(machine).can_toggle_maintenance:
            return
        enable = machine.status != MachineStatus.MAINTENANCE
        question = (
            f"Put machine {machine.machine_code} into maintenance? Customers cannot use it until maintenance ends."
            if enable
            else f"Set machine {machine.machine_code} back to available?"
        )
        if not ConfirmDialog.ask(self.winfo_toplevel(), "Maintenance", question):
            return
        services, session = self._context.services, self._context.session
        self._run_action(
            lambda: services.machines.set_maintenance(machine.machine_id, enable, session),
            lambda _m: "Machine is under maintenance." if enable else "Machine is available again.",
        )

    def _archive(self, machine: MachineSummary) -> None:
        if self._busy or not machine_actions(machine).can_archive:
            return
        confirmed = ConfirmDialog.ask(
            self.winfo_toplevel(),
            "Stop using machine",
            (
                f"Stop using machine {machine.machine_code}? "
                "Machines without history are deleted; machines with history are archived to keep invoices."
            ),
            confirm_label="Stop using",
            is_danger=True,
        )
        if not confirmed:
            return
        services, session = self._context.services, self._context.session
        self._run_action(
            lambda: services.machines.archive_machine(machine.machine_id, session),
            archive_message,
        )

    def _run_action(self, call: Callable[[], Any], success_message: Callable[[Any], str]) -> None:
        """Chạy 1 thao tác quản trị: khóa mọi nút trên dòng, báo kết quả, tải lại bảng."""
        if self._busy:
            return
        self._busy = True
        for buttons in self._row_buttons.values():
            for button in buttons.values():
                button.set_enabled(False)

        def finish() -> None:
            self._busy = False
            self.reload()

        def done(result: Any) -> None:
            finish()
            notify_success(self, success_message(result))

        def failed(error: Exception) -> None:
            finish()
            notify_error(self, error, conflict_as_alert=True)

        self._runner.submit(self, call, done, failed)

    def shutdown(self) -> None:
        """App Shell gọi trước khi hủy view: bỏ qua kết quả tải về sau đó."""
        self._closed = True
