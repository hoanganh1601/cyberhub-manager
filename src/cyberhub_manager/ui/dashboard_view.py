"""NG-03 — Dashboard tổng quan phòng máy theo Stitch export.

- KPI, tab lọc theo trạng thái, lưới card 4 cột, chân trang "Đang hiển thị X/Y máy".
- Tự làm mới mỗi 15 giây (docs/04_LINEAR_BACKLOG.md NG-03); shutdown() hủy lịch khi rời màn.
- Làm mới nền thất bại: giữ snapshot cũ và đánh dấu "chưa cập nhật" (07 mục 7).
- Không tự tính phí/số dư: chỉ hiển thị số liệu service trả về (07 mục 4.2).
- Mở phiên/Thanh toán gọi callback do NG-05/NG-06 cung cấp; chưa có thì báo "chưa hỗ trợ".
"""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import customtkinter as ctk

from ..domain.dtos import MachineSummary
from ..domain.enums import MachineStatus
from .app_shell import ViewContext
from .background import TaskRunner, default_runner
from .components import ConfirmDialog, ToastManager
from .components.stitch_button import stitch_button
from .components.stitch_machine_card import StitchMachineCard
from .feedback import notify_error, notify_success
from .messages import MSG_LOADING, MSG_NO_DATA, MSG_RETRY, MSG_UNABLE_TO_LOAD
from .state import ViewState
from .theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_KPI_VALUE,
    FONT_ST_LABEL_CAPS,
    FONT_ST_MONO_11,
    FONT_ST_MONO_BODY,
    FONT_ST_PAGE_TITLE,
    STITCH_BADGE_SUCCESS_BORDER,
    STITCH_BORDER,
    STITCH_CARD_BG,
    STITCH_CARD_BORDER,
    STITCH_CHIP_BG,
    STITCH_CHIP_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_GAP,
    STITCH_GRID_COLUMNS,
    STITCH_ICON_CYAN_BG,
    STITCH_ICON_CYAN_BORDER,
    STITCH_ICON_DANGER_BG,
    STITCH_ICON_DANGER_BORDER,
    STITCH_ICON_SUCCESS_BG,
    STITCH_ICON_SUCCESS_BORDER,
    STITCH_ICON_WARNING_BG,
    STITCH_ICON_WARNING_BORDER,
    STITCH_KPI_SUCCESS_CARD_BG,
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

logger = logging.getLogger(__name__)

REFRESH_MS = 15_000
FEATURE_PENDING = "This feature is not available yet."
END_MAINTENANCE_TITLE = "End maintenance"
MAINTENANCE_DONE = "Machine is available again."


# ----------------------------------------------------------------------
# Hàm thuần (test được không cần Tk)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class MachineCounts:
    total: int
    available: int
    in_use: int
    maintenance: int

    @property
    def online_customers(self) -> int:
        # Mỗi khách tối đa 1 phiên ACTIVE (business rule 2) nên bằng số máy đang dùng.
        return self.in_use

    def for_status(self, status: MachineStatus | None) -> int:
        return {
            None: self.total,
            MachineStatus.AVAILABLE: self.available,
            MachineStatus.IN_USE: self.in_use,
            MachineStatus.MAINTENANCE: self.maintenance,
        }[status]


def summarize(machines: Iterable[MachineSummary]) -> MachineCounts:
    machines = list(machines)

    def count(status: MachineStatus) -> int:
        return sum(1 for m in machines if m.status == status)

    return MachineCounts(
        total=len(machines),
        available=count(MachineStatus.AVAILABLE),
        in_use=count(MachineStatus.IN_USE),
        maintenance=count(MachineStatus.MAINTENANCE),
    )


def filter_machines(
    machines: Iterable[MachineSummary],
    status: MachineStatus | None = None,
    keyword: str = "",
) -> list[MachineSummary]:
    """Lọc theo trạng thái và từ khóa (mã máy, tên máy, tên/mã khách đang dùng)."""
    needle = keyword.strip().casefold()
    result: list[MachineSummary] = []
    for machine in machines:
        if status is not None and machine.status != status:
            continue
        if needle:
            haystack = [machine.machine_code, machine.name]
            if machine.active_session is not None:
                session = machine.active_session.session
                haystack += [session.customer_name, session.customer_code]
            if not any(needle in value.casefold() for value in haystack):
                continue
        result.append(machine)
    return result


def _gap(index: int, count: int) -> tuple[int, int]:
    """padx để các ô trong một hàng cách nhau STITCH_GAP, sát mép hai đầu."""
    half = STITCH_GAP // 2
    return (0 if index == 0 else half, 0 if index == count - 1 else half)


# (tiêu đề, thuộc tính MachineCounts, màu chữ, nền icon, viền icon, icon)
_KPI_SPECS = (
    ("TỔNG SỐ MÁY", "total", STITCH_TEXT_STRONG, STITCH_CHIP_BG, STITCH_CHIP_BORDER, "▭"),
    ("MÁY TRỐNG", "available", STITCH_SUCCESS, STITCH_ICON_SUCCESS_BG, STITCH_ICON_SUCCESS_BORDER, "✓"),
    ("ĐANG SỬ DỤNG", "in_use", STITCH_DANGER, STITCH_ICON_DANGER_BG, STITCH_ICON_DANGER_BORDER, "◷"),
    ("BẢO TRÌ", "maintenance", STITCH_WARNING, STITCH_ICON_WARNING_BG, STITCH_ICON_WARNING_BORDER, "✎"),
    ("KHÁCH ĐANG ONLINE", "online_customers", STITCH_CYAN, STITCH_ICON_CYAN_BG, STITCH_ICON_CYAN_BORDER, "☻"),
)

# (status, nhãn, màu chữ, viền)
_TAB_SPECS = (
    (None, "Tất cả", STITCH_TEXT, STITCH_CHIP_BORDER),
    (MachineStatus.AVAILABLE, "Trống", STITCH_SUCCESS, STITCH_TAB_SUCCESS_BORDER),
    (MachineStatus.IN_USE, "Đang dùng", STITCH_DANGER, STITCH_TAB_DANGER_BORDER),
    (MachineStatus.MAINTENANCE, "Bảo trì", STITCH_WARNING, STITCH_TAB_WARNING_BORDER),
)
class DashboardView(ctk.CTkFrame):
    """Màn Tổng quan: nhận (parent, context) như mọi ViewFactory của App Shell."""

    def __init__(
        self,
        master: Any,
        context: ViewContext,
        *,
        runner: TaskRunner | None = None,
        refresh_ms: int = REFRESH_MS,
        on_open_session: Callable[[int], None] | None = None,
        on_checkout: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._context = context
        self._runner = runner or default_runner()
        self._refresh_ms = refresh_ms
        self._on_open_session = on_open_session
        self._on_checkout = on_checkout

        self._machines: list[MachineSummary] = []
        self._status_filter: MachineStatus | None = None
        self._keyword = ""
        self._cards: dict[int, StitchMachineCard] = {}
        self._kpi_labels: dict[str, ctk.CTkLabel] = {}
        self._tab_buttons: dict[MachineStatus | None, ctk.CTkButton] = {}
        self._state = ViewState.LOADING
        self._loaded_once = False
        self._loading = False
        self._refresh_again = False
        self._stale = False
        self._after_id: str | None = None
        self._closed = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)  # lưới card nhận phần chiều cao còn lại
        self._build_header()
        self._build_kpis()
        self._build_filter_bar()
        self._build_body()
        self._build_footer()
        self.refresh()

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
    def visible_machine_ids(self) -> list[int]:
        return [m.machine_id for m in filter_machines(self._machines, self._status_filter, self._keyword)]

    @property
    def is_stale(self) -> bool:
        return self._stale

    @property
    def has_scheduled_refresh(self) -> bool:
        return self._after_id is not None

    def card_for(self, machine_id: int) -> StitchMachineCard | None:
        return self._cards.get(machine_id)

    # ------------------------------------------------------------------
    # Dựng giao diện
    # ------------------------------------------------------------------
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            header, text="Tổng quan phòng máy", font=FONT_ST_PAGE_TITLE, text_color=STITCH_TEXT_STRONG
        ).pack(side="left")
        ctk.CTkLabel(
            header,
            text="Giám sát máy trạm và phiên sử dụng theo thời gian thực",
            font=FONT_ST_MONO_BODY,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left", padx=(10, 0), pady=(4, 0))
        self._refresh_button = stitch_button(
            header, "⟳  Làm mới", command=lambda: self.refresh(manual=True), width=96, height=28
        )
        self._refresh_button.pack(side="right")

    def _build_kpis(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        for index, (title, attr, color, icon_bg, icon_border, icon) in enumerate(_KPI_SPECS):
            row.grid_columnconfigure(index, weight=1, uniform="kpi")
            highlighted = attr == "available"  # Stitch làm nổi thẻ "Máy trống"
            card = ctk.CTkFrame(
                row,
                height=62,
                fg_color=STITCH_KPI_SUCCESS_CARD_BG if highlighted else STITCH_CARD_BG,
                border_width=1,
                border_color=STITCH_BADGE_SUCCESS_BORDER if highlighted else STITCH_CARD_BORDER,
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
                icon_box,
                text=icon,
                font=FONT_ST_BODY_STRONG,
                text_color=STITCH_TEXT if attr == "total" else color,
            ).pack(expand=True)

    def _build_filter_bar(self) -> None:
        bar = ctk.CTkFrame(
            self,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
        )
        bar.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        tabs = ctk.CTkFrame(bar, fg_color="transparent")
        tabs.pack(side="left", padx=10, pady=6)
        for status, *_style in _TAB_SPECS:
            button = ctk.CTkButton(
                tabs,
                text="",
                width=96,
                height=26,
                corner_radius=STITCH_RADIUS,
                border_width=1,
                font=FONT_ST_BODY,
                command=lambda s=status: self.set_status_filter(s),
            )
            button.pack(side="left", padx=(0, 8))
            self._tab_buttons[status] = button
        self._auto_label = ctk.CTkLabel(bar, text="", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED)
        self._auto_label.pack(side="right", padx=12)
        self._update_tabs()
        self._update_auto_label()

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=3, column=0, sticky="nsew", pady=(10, 0))

        # Lưới card (cuộn được khi nhiều hơn 2 hàng).
        self._grid = ctk.CTkScrollableFrame(body, fg_color="transparent", corner_radius=0)
        for column in range(STITCH_GRID_COLUMNS):
            self._grid.grid_columnconfigure(column, weight=1, uniform="card")

        # Khung LOADING / EMPTY / ERROR, thay chỗ lưới khi không có card để hiện.
        self._state_frame = ctk.CTkFrame(body, fg_color="transparent")
        self._state_label = ctk.CTkLabel(self._state_frame, text="", font=FONT_ST_BODY, text_color=STITCH_TEXT_MUTED)
        self._state_label.pack(pady=(60, 12))
        self._retry_button = stitch_button(
            self._state_frame, MSG_RETRY, command=lambda: self.refresh(manual=True), width=100
        )

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        tk.Frame(footer, height=1, bg=STITCH_BORDER, bd=0, highlightthickness=0).pack(fill="x", pady=(0, 6))
        self._count_label = ctk.CTkLabel(footer, text="", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_MUTED)
        self._count_label.pack(side="left")
        self._updated_label = ctk.CTkLabel(footer, text="", font=FONT_ST_MONO_11, text_color=STITCH_TEXT_DIM)
        self._updated_label.pack(side="right")
    # ------------------------------------------------------------------
    # Tải dữ liệu + làm mới định kỳ
    # ------------------------------------------------------------------
    def refresh(self, *, manual: bool = False) -> None:
        """Tải lại danh sách máy. Đang tải dở thì hẹn tải thêm một lần sau đó."""
        if self._closed:
            return
        if self._loading:
            self._refresh_again = True
            return
        self._loading = True
        self._refresh_button.set_enabled(False)
        if not self._loaded_once:
            self._show_state(ViewState.LOADING)
        services, session = self._context.services, self._context.session
        self._runner.submit(
            self,
            lambda: services.machines.list_machines(session.store_id),
            self._on_loaded,
            lambda error: self._on_load_failed(error, manual),
        )

    def _on_loaded(self, machines: list[MachineSummary]) -> None:
        self._finish_loading()
        self._machines = list(machines)
        self._loaded_once = True
        self._stale = False
        self._updated_label.configure(text=f"Cập nhật lúc {datetime.now():%H:%M:%S}")
        self._render()
        self._after_load()

    def _on_load_failed(self, error: Exception, manual: bool) -> None:
        self._finish_loading()
        logger.warning("Tải danh sách máy thất bại: %s", type(error).__name__)
        if not self._loaded_once:
            self._show_state(ViewState.ERROR)
        else:
            # Giữ snapshot cũ, chỉ đánh dấu chưa cập nhật (07 mục 7).
            self._stale = True
            self._update_auto_label()
            if manual:
                notify_error(self, error)
        self._after_load()

    def _finish_loading(self) -> None:
        self._loading = False
        if not self._closed:
            self._refresh_button.set_enabled(True)

    def _after_load(self) -> None:
        if self._refresh_again:
            self._refresh_again = False
            self.refresh()
            return
        self._schedule_next()

    def _schedule_next(self) -> None:
        if self._closed:
            return
        self._cancel_timer()
        self._after_id = self.after(self._refresh_ms, self._on_timer)

    def _on_timer(self) -> None:
        self._after_id = None
        self.refresh()

    def _cancel_timer(self) -> None:
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None

    def shutdown(self) -> None:
        """App Shell gọi trước khi hủy view: dừng vòng làm mới."""
        self._closed = True
        self._cancel_timer()

    def destroy(self) -> None:
        self.shutdown()
        super().destroy()

    # ------------------------------------------------------------------
    # Lọc / tìm kiếm
    # ------------------------------------------------------------------
    def set_status_filter(self, status: MachineStatus | None) -> None:
        self._status_filter = status
        if self._loaded_once:
            self._render()
        else:
            self._update_tabs()

    def handle_search(self, text: str) -> None:
        """Nhận từ khóa từ ô tìm kiếm trên topbar (NG-02)."""
        self._keyword = text
        if self._loaded_once:
            self._render()

    # ------------------------------------------------------------------
    # Hiển thị
    # ------------------------------------------------------------------
    def _render(self) -> None:
        counts = summarize(self._machines)
        for attr, label in self._kpi_labels.items():
            label.configure(text=str(getattr(counts, attr)))
        self._update_tabs(counts)
        self._update_auto_label()

        visible = filter_machines(self._machines, self._status_filter, self._keyword)
        self._count_label.configure(text=f"●  Đang hiển thị {len(visible)}/{counts.total} máy")
        if not visible:
            self._show_state(ViewState.EMPTY)
            return
        self._show_state(ViewState.READY)
        self._render_cards(visible)

    def _render_cards(self, visible: list[MachineSummary]) -> None:
        """Dùng lại card cũ theo machine_id để không nhấp nháy mỗi lần làm mới."""
        actor = self._context.session
        current_ids = {m.machine_id for m in self._machines}
        for machine_id in [mid for mid in self._cards if mid not in current_ids]:
            self._cards.pop(machine_id).destroy()  # máy đã bị xóa/archive
        for card in self._cards.values():
            card.grid_forget()

        for index, machine in enumerate(visible):
            card = self._cards.get(machine.machine_id)
            if card is None:
                card = StitchMachineCard(
                    self._grid,
                    on_open=self._open_session,
                    on_checkout=self._checkout,
                    on_maintenance=self._end_maintenance,
                )
                self._cards[machine.machine_id] = card
            card.render(machine, actor)
            row, column = divmod(index, STITCH_GRID_COLUMNS)
            card.grid(
                row=row,
                column=column,
                sticky="ew",
                padx=_gap(column, STITCH_GRID_COLUMNS),
                pady=(0, STITCH_GAP),
            )

    def _show_state(self, state: ViewState) -> None:
        self._state = state
        if state == ViewState.READY:
            self._state_frame.pack_forget()
            self._grid.pack(fill="both", expand=True)
            return
        self._grid.pack_forget()
        self._retry_button.pack_forget()
        text = {
            ViewState.LOADING: MSG_LOADING,
            ViewState.EMPTY: MSG_NO_DATA,
            ViewState.ERROR: MSG_UNABLE_TO_LOAD,
        }[state]
        self._state_label.configure(
            text=text, text_color=STITCH_DANGER if state == ViewState.ERROR else STITCH_TEXT_MUTED
        )
        if state == ViewState.ERROR:
            self._retry_button.pack()
        self._state_frame.pack(fill="both", expand=True)

    def _update_tabs(self, counts: MachineCounts | None = None) -> None:
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

    def _update_auto_label(self) -> None:
        if self._stale:
            self._auto_label.configure(text="▲  Dữ liệu chưa cập nhật", text_color=STITCH_WARNING)
        else:
            seconds = self._refresh_ms // 1000
            self._auto_label.configure(text=f"●  Cập nhật tự động: {seconds}s", text_color=STITCH_TEXT_MUTED)

    # ------------------------------------------------------------------
    # Hành động trên card
    # ------------------------------------------------------------------
    def _open_session(self, machine_id: int) -> None:
        if self._on_open_session is None:
            ToastManager.show(self, FEATURE_PENDING, kind="info")  # NG-05 sẽ cắm dialog vào đây
            return
        self._on_open_session(machine_id)

    def _checkout(self, machine_id: int) -> None:
        if self._on_checkout is None:
            ToastManager.show(self, FEATURE_PENDING, kind="info")  # NG-06 sẽ cắm dialog vào đây
            return
        self._on_checkout(machine_id)

    def _end_maintenance(self, machine_id: int) -> None:
        card = self._cards.get(machine_id)
        if card is None or card.is_busy or card.machine is None:
            return
        confirmed = ConfirmDialog.ask(
            self.winfo_toplevel(),
            title=END_MAINTENANCE_TITLE,
            message=f"Set machine {card.machine.machine_code} back to available?",
        )
        if not confirmed:
            return
        card.set_busy(True)
        services, session = self._context.services, self._context.session

        def done(_machine: Any) -> None:
            card.set_busy(False)
            notify_success(self, MAINTENANCE_DONE)
            self.refresh()

        def failed(error: Exception) -> None:
            card.set_busy(False)
            notify_error(self, error, conflict_as_alert=True)
            self.refresh()

        self._runner.submit(
            self,
            lambda: services.machines.set_maintenance(machine_id, False, session),
            done,
            failed,
        )


dashboard_view_factory = DashboardView

