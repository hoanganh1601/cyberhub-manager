"""NG-03 — Màn Quản lý máy (chỉ Manager/Admin).

- Bảng máy + thêm / sửa / bảo trì / ngừng sử dụng (archive).
- Máy IN_USE: không cho bảo trì hoặc ngừng sử dụng (MAC-04, MAC-06); vẫn sửa được
  tên/đơn giá vì phiên đang chạy giữ giá snapshot (SES-02).
- Ngừng sử dụng luôn hỏi xác nhận; máy chưa có lịch sử bị xóa, có lịch sử thì archive.
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
from .app_shell import ViewContext
from .background import TaskRunner, default_runner
from .components import ConfirmDialog, DataTable, TableColumn, TableRow
from .components.stitch_button import stitch_button
from .dialogs.machine_dialog import MachineDialog
from .feedback import notify_error, notify_success
from .formatters import format_datetime, format_money
from .messages import get_user_friendly_error
from .navigation import MANAGEMENT_ROLES
from .state import ViewState
from .theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_MONO_BODY,
    FONT_ST_PAGE_TITLE,
    STITCH_CARD_BG,
    STITCH_CARD_BORDER,
    STITCH_RADIUS_LG,
    STITCH_TEXT,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
    STITCH_WARNING,
)

STATUS_LABELS = {
    MachineStatus.AVAILABLE: "● Trống",
    MachineStatus.IN_USE: "● Đang dùng",
    MachineStatus.MAINTENANCE: "▲ Bảo trì",
}
IN_USE_HINT = "Máy đang có phiên: không thể bảo trì hoặc ngừng sử dụng."
NO_SELECTION = "Chọn một máy trong bảng để thao tác."

COLUMNS = [
    TableColumn("code", "Mã máy", "left", 100),
    TableColumn("name", "Tên máy", "left", 200),
    TableColumn("rate", "Đơn giá/giờ", "right", 130),
    TableColumn("status", "Trạng thái", "left", 120),
    TableColumn("customer", "Khách đang dùng", "left", 180),
]


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
    """Nút nào được bật cho máy đang chọn."""
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


def to_row(machine: MachineSummary) -> TableRow:
    customer = machine.active_session.session.customer_name if machine.active_session else "—"
    return TableRow(
        key=machine.machine_id,
        cells={
            "code": machine.machine_code,
            "name": machine.name,
            "rate": format_money(machine.hourly_rate),
            "status": STATUS_LABELS.get(machine.status, str(machine.status)),
            "customer": customer,
        },
    )


def search_machines(machines: Iterable[MachineSummary], keyword: str) -> list[MachineSummary]:
    needle = keyword.strip().casefold()
    if not needle:
        return list(machines)
    return [m for m in machines if needle in m.machine_code.casefold() or needle in m.name.casefold()]

PAGE_SIZE = 6  # số dòng mỗi trang; chỉnh ở bước dựng bảng nếu cần cho vừa 1280x720


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

def archive_message(result: MachineArchiveResult) -> str:
    if result.action == MachineArchiveAction.DELETED:
        return "Machine deleted."
    return "Machine archived. Its history is kept."


class MachineManagementView(ctk.CTkFrame):
    """Màn Quản lý máy: bảng máy + thanh thao tác cho máy đang chọn."""

    def __init__(
        self,
        master: Any,
        context: ViewContext,
        *,
        runner: TaskRunner | None = None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._context = context
        self._runner = runner or default_runner()
        self._machines: list[MachineSummary] = []
        self._keyword = ""
        self._selected_id: int | None = None
        self._busy = False
        self._closed = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build_header()
        self._build_action_bar()
        self._table = DataTable(self, columns=COLUMNS, on_select=self._on_select)
        self._table.grid(row=2, column=0, sticky="nsew", pady=(10, 0))

        if context.session.role not in MANAGEMENT_ROLES:
            # Phòng thủ: App Shell đã chặn, nhưng view vẫn không tải dữ liệu cho STAFF.
            self._table.set_state(ViewState.ERROR, get_user_friendly_error("PERMISSION_DENIED"))
            self._add_button.set_enabled(False)
            self._refresh_button.set_enabled(False)
            self._update_actions()
            return
        self.reload()

    # ------------------------------------------------------------------
    @property
    def table(self) -> DataTable:
        return self._table

    @property
    def machines(self) -> list[MachineSummary]:
        return list(self._machines)

    @property
    def selected_machine(self) -> MachineSummary | None:
        return next((m for m in self._machines if m.machine_id == self._selected_id), None)

    @property
    def buttons(self) -> dict[str, Any]:
        return {
            "add": self._add_button,
            "edit": self._edit_button,
            "maintenance": self._maintenance_button,
            "archive": self._archive_button,
        }

    # ------------------------------------------------------------------
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            header, text="Quản lý máy", font=FONT_ST_PAGE_TITLE, text_color=STITCH_TEXT_STRONG
        ).pack(side="left")
        ctk.CTkLabel(
            header,
            text="Thêm máy, đổi đơn giá, bảo trì và ngừng sử dụng",
            font=FONT_ST_MONO_BODY,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left", padx=(10, 0), pady=(4, 0))
        self._add_button = stitch_button(header, "＋  Thêm máy", kind="primary", command=self._add)
        self._add_button.pack(side="right")
        self._refresh_button = stitch_button(header, "⟳  Làm mới", command=self.reload, width=96)
        self._refresh_button.pack(side="right", padx=(0, 8))

    def _build_action_bar(self) -> None:
        bar = ctk.CTkFrame(
            self,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
        )
        bar.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        info = ctk.CTkFrame(bar, fg_color="transparent")
        info.pack(side="left", padx=12, pady=8)
        self._selection_label = ctk.CTkLabel(
            info, text="", font=FONT_ST_BODY_STRONG, text_color=STITCH_TEXT, anchor="w", height=16
        )
        self._selection_label.pack(anchor="w")
        self._hint_label = ctk.CTkLabel(
            info, text="", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED, anchor="w", height=16
        )
        self._hint_label.pack(anchor="w")

        # Pack từ phải sang trái: Ngừng sử dụng | Bảo trì | Sửa
        self._archive_button = stitch_button(bar, "Ngừng sử dụng", kind="danger", command=self._archive, width=120)
        self._archive_button.pack(side="right", padx=(0, 12))
        self._maintenance_button = stitch_button(bar, "Bảo trì", command=self._toggle_maintenance, width=130)
        self._maintenance_button.pack(side="right", padx=(0, 8))
        self._edit_button = stitch_button(bar, "Sửa", command=self._edit, width=80)
        self._edit_button.pack(side="right", padx=(0, 8))
        self._update_actions()

    # ------------------------------------------------------------------
    # Tải dữ liệu
    # ------------------------------------------------------------------
    def reload(self) -> None:
        if self._closed:
            return
        self._table.set_state(ViewState.LOADING)
        self._refresh_button.set_busy(True)
        services, session = self._context.services, self._context.session
        self._runner.submit(
            self,
            lambda: services.machines.list_machines(session.store_id),
            self._on_loaded,
            self._on_load_failed,
        )

    def _on_loaded(self, machines: list[MachineSummary]) -> None:
        self._refresh_button.set_busy(False)
        self._machines = list(machines)
        if self.selected_machine is None:
            self._selected_id = None
        self._render_rows()

    def _on_load_failed(self, error: Exception) -> None:
        self._refresh_button.set_busy(False)
        self._machines = []
        self._selected_id = None
        self._table.set_state(ViewState.ERROR, get_user_friendly_error(error), on_retry=self.reload)
        self._update_actions()

    def handle_search(self, text: str) -> None:
        """Nhận từ khóa từ ô tìm kiếm trên topbar (NG-02)."""
        self._keyword = text
        self._render_rows()

    def _render_rows(self) -> None:
        rows = [to_row(m) for m in search_machines(self._machines, self._keyword)]
        self._table.set_rows(rows)  # rỗng -> EMPTY; DataTable tự giữ dòng đang chọn nếu còn
        if self._selected_id not in {r.key for r in rows}:
            self._selected_id = None
        elif self._table.selected_key != self._selected_id:
            self.select(self._selected_id)  # vd. máy vừa tạo
        self._update_actions()

    # ------------------------------------------------------------------
    # Chọn dòng + trạng thái nút
    # ------------------------------------------------------------------
    def _on_select(self, key: int | str) -> None:
        self._selected_id = int(key)
        self._update_actions()

    def select(self, machine_id: int) -> None:
        """Chọn máy theo id. DataTable (NG-01) chưa có API public để chọn dòng."""
        self._table._select_row(machine_id)

    def _update_actions(self) -> None:
        machine = self.selected_machine
        actions = machine_actions(machine)
        enabled = not self._busy
        self._edit_button.set_enabled(enabled and actions.can_edit)
        self._maintenance_button.configure(text=actions.maintenance_label)
        self._maintenance_button.set_enabled(enabled and actions.can_toggle_maintenance)
        self._archive_button.set_enabled(enabled and actions.can_archive)
        if machine is None:
            self._selection_label.configure(text=NO_SELECTION)
            self._hint_label.configure(text="")
            return
        status = STATUS_LABELS.get(machine.status, str(machine.status))
        self._selection_label.configure(text=f"{machine.machine_code} · {machine.name} · {status}")
        if machine.status == MachineStatus.IN_USE:
            self._hint_label.configure(text=IN_USE_HINT, text_color=STITCH_WARNING)
        else:
            self._hint_label.configure(
                text=f"Đơn giá hiện tại: {format_money(machine.hourly_rate)}/giờ", text_color=STITCH_TEXT_MUTED
            )

    # ------------------------------------------------------------------
    # Hành động
    # ------------------------------------------------------------------
    def _add(self) -> None:
        MachineDialog(self.winfo_toplevel(), self._context, runner=self._runner, on_saved=self._after_created)

    def _after_created(self, machine: Machine) -> None:
        self._selected_id = machine.id  # chọn sẵn máy vừa tạo sau khi tải lại
        notify_success(self, "Machine created.")
        self.reload()

    def _edit(self) -> None:
        machine = self.selected_machine
        if machine is None:
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

    def _toggle_maintenance(self) -> None:
        machine = self.selected_machine
        if machine is None or not machine_actions(machine).can_toggle_maintenance:
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
            self._maintenance_button,
            lambda: services.machines.set_maintenance(machine.machine_id, enable, session),
            lambda _m: "Machine is under maintenance." if enable else "Machine is available again.",
        )

    def _archive(self) -> None:
        machine = self.selected_machine
        if machine is None or not machine_actions(machine).can_archive:
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
            self._archive_button,
            lambda: services.machines.archive_machine(machine.machine_id, session),
            archive_message,
        )

    def _run_action(
        self,
        button: Any,
        call: Callable[[], Any],
        success_message: Callable[[Any], str],
    ) -> None:
        """Chạy 1 thao tác quản trị: khóa các nút, báo kết quả, tải lại bảng."""
        if self._busy:
            return
        self._busy = True
        button.set_busy(True)
        self._update_actions()

        def finish() -> None:
            self._busy = False
            button.set_busy(False)
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
