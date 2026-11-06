"""Dashboard View — Màn hình sơ đồ phòng máy theo thiết kế Google Stitch.

Hiển thị:
1. Header trang kèm nút làm mới dữ liệu.
2. Hàng 5 KPI Cards chỉ số: Tổng số máy, Máy trống, Đang sử dụng, Bảo trì, Khách online.
3. Thanh lọc trạng thái (FilterBar): Tất cả, Trống, Đang dùng, Bảo trì + telemetry auto-refresh.
4. Lưới thẻ máy tính (MachineCard grid 4 cột) cuộn mượt mà.
5. Footer hiển thị số lượng máy đang xem và thông tin vận hành hệ thống.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from ..domain.enums import MachineStatus, PaymentMethod, Role
from ..domain.exceptions import ApplicationError
from .components import (
    ActionButton,
    ConfirmDialog,
    FilterBar,
    KpiCard,
    MachineCard,
    ToastManager,
)
from .dialogs import PaymentConfirmDialog
from .formatters import format_money
from .icons import get_icon
from .i18n import Language, translate
from .messages import MSG_OPERATION_FAILED, get_user_friendly_error
from .theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_MONO_SM,
    FONT_ST_MONO_XS,
    FONT_ST_PAGE_TITLE,
    STITCH_BORDER,
    STITCH_CYAN,
    STITCH_RADIUS_LG,
    STITCH_TEXT,
    STITCH_TEXT_DIM,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
)

if TYPE_CHECKING:
    from ..domain.dtos import MachineSummary
    from .app_shell import ViewContext

logger = logging.getLogger(__name__)

AUTO_REFRESH_INTERVAL_MS = 5000


class DashboardView(ctk.CTkFrame):
    """Màn hình Tổng quan phòng máy (Dashboard)."""

    def __init__(self, master: Any, context: ViewContext) -> None:
        super().__init__(master, fg_color="transparent")
        self._context = context
        self._language = context.language
        self._actor = context.session
        self._services = context.services

        self._current_filter: str = "all"
        self._search_keyword: str = ""
        self._all_machines: list[MachineSummary] = []
        self._displayed_cards: list[MachineCard] = []
        self._auto_refresh_id: str | None = None
        self._is_disposed = False

        self._build_layout()
        self.refresh()
        self._schedule_auto_refresh()

    # ------------------------------------------------------------------
    # Xây dựng Bố cục giao diện theo thiết kế Stitch
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        # Vùng trên cùng: Header, KPI Cards, Filter Bar
        self._top_container = ctk.CTkFrame(self, fg_color="transparent")
        self._top_container.pack(fill="x", side="top", pady=(0, 8))

        self._build_header_row()
        self._build_kpi_row()
        self._build_filter_bar()

        # Vùng dưới cùng: Footer thông tin (pack trước để neo chặt ở đáy)
        self._build_footer()

        # Vùng giữa: Lưới máy tính cuộn mượt mà
        self._grid_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
        )
        self._grid_scroll.pack(fill="both", expand=True, pady=(0, 6))

        for c in range(4):
            self._grid_scroll.grid_columnconfigure(c, weight=1, uniform="machine_grid")

        self._empty_label = ctk.CTkLabel(
            self._grid_scroll,
            text="",
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
        )

    def _build_header_row(self) -> None:
        row = ctk.CTkFrame(self._top_container, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))

        # Tiêu đề & mô tả phụ
        text_box = ctk.CTkFrame(row, fg_color="transparent")
        text_box.pack(side="left", fill="y")

        title_text = "Tổng quan phòng máy" if self._language == "vi" else "Workstations Overview"
        self._title_label = ctk.CTkLabel(
            text_box,
            text=title_text,
            font=FONT_ST_PAGE_TITLE,
            text_color=STITCH_TEXT_STRONG,
            anchor="w",
        )
        self._title_label.pack(side="left")

        subtitle_text = (
            "Giám sát máy trạm và phiên sử dụng theo thời gian thực"
            if self._language == "vi"
            else "Real-time workstation & session monitoring"
        )
        self._subtitle_label = ctk.CTkLabel(
            text_box,
            text=f" • {subtitle_text}",
            font=FONT_ST_MONO_SM,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
        )
        self._subtitle_label.pack(side="left", padx=(8, 0), pady=(3, 0))

        # Nút Làm mới (vector icon + nhãn text)
        btn_text = "Làm mới" if self._language == "vi" else "Refresh"
        self._refresh_icon = get_icon("refresh", STITCH_CYAN, (14, 14))
        self._refresh_btn = ActionButton(
            row,
            text=f" {btn_text}",
            image=self._refresh_icon,
            compound="left",
            kind="secondary",
            width=96,
            height=28,
            command=self.refresh,
        )
        self._refresh_btn.pack(side="right")

    def _build_kpi_row(self) -> None:
        self._kpi_row = ctk.CTkFrame(self._top_container, fg_color="transparent")
        self._kpi_row.pack(fill="x", pady=(0, 8))

        for c in range(5):
            self._kpi_row.grid_columnconfigure(c, weight=1, uniform="kpi")

        is_vi = self._language == "vi"
        self._kpi_total = KpiCard(
            self._kpi_row,
            title="TỔNG SỐ MÁY" if is_vi else "TOTAL MACHINES",
            value=0,
            icon_name="machines",
            tone="default",
        )
        self._kpi_total.grid(row=0, column=0, padx=(0, 6), sticky="nsew")

        self._kpi_available = KpiCard(
            self._kpi_row,
            title="MÁY TRỐNG" if is_vi else "AVAILABLE",
            value=0,
            icon_name="check",
            tone="emerald",
        )
        self._kpi_available.grid(row=0, column=1, padx=6, sticky="nsew")

        self._kpi_in_use = KpiCard(
            self._kpi_row,
            title="ĐANG SỬ DỤNG" if is_vi else "IN USE",
            value=0,
            icon_name="clock",
            tone="rose",
        )
        self._kpi_in_use.grid(row=0, column=2, padx=6, sticky="nsew")

        self._kpi_maintenance = KpiCard(
            self._kpi_row,
            title="BẢO TRÌ" if is_vi else "MAINTENANCE",
            value=0,
            icon_name="wrench",
            tone="amber",
        )
        self._kpi_maintenance.grid(row=0, column=3, padx=6, sticky="nsew")

        self._kpi_online = KpiCard(
            self._kpi_row,
            title="KHÁCH ĐANG ONLINE" if is_vi else "ONLINE USERS",
            value=0,
            icon_name="users",
            tone="cyan",
        )
        self._kpi_online.grid(row=0, column=4, padx=(6, 0), sticky="nsew")

    def _build_filter_bar(self) -> None:
        is_vi = self._language == "vi"
        options = [
            ("all", "Tất cả" if is_vi else "All", 0, "default"),
            ("available", "Trống" if is_vi else "Available", 0, "emerald"),
            ("in_use", "Đang dùng" if is_vi else "In use", 0, "rose"),
            ("maintenance", "Bảo trì" if is_vi else "Maintenance", 0, "amber"),
        ]
        hint = "● Cập nhật tự động: 5s" if is_vi else "● Auto refresh: 5s"
        self._filter_bar = FilterBar(
            self._top_container,
            options=options,
            on_filter_changed=self._handle_filter_changed,
            right_hint=hint,
            initial_key=self._current_filter,
        )
        self._filter_bar.pack(fill="x")

    def _build_footer(self) -> None:
        self._footer_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
            height=26,
            corner_radius=0,
        )
        self._footer_frame.pack(fill="x", side="bottom")

        # Đường kẻ viền mờ phía trên footer
        line = ctk.CTkFrame(self, fg_color=STITCH_BORDER, height=1)
        line.pack(fill="x", side="bottom", pady=(0, 4))

        self._showing_label = ctk.CTkLabel(
            self._footer_frame,
            text="",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
        )
        self._showing_label.pack(side="left", padx=4)

        self._telemetry_label = ctk.CTkLabel(
            self._footer_frame,
            text="CyberHub Operations • 1280×720",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_DIM,
            anchor="e",
        )
        self._telemetry_label.pack(side="right", padx=4)

    # ------------------------------------------------------------------
    # Nạp và cập nhật dữ liệu (Data Loading & Lifecycle)
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Đọc danh sách máy từ service và cập nhật toàn bộ view."""
        if self._is_disposed:
            return

        try:
            store_id = self._actor.store_id
            machines = self._services.machines.list_machines(store_id)
            self._all_machines = list(machines)
            self._update_kpis()
            self._render_grid()
        except ApplicationError as err:
            logger.warning("Không nạp được danh sách máy: %s", err)
            ToastManager.show(self, get_user_friendly_error(err), kind="error")
        except Exception:
            logger.exception("Lỗi không mong muốn khi tải máy")
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")

    def _schedule_auto_refresh(self) -> None:
        """Tự động hẹn giờ làm mới dữ liệu sau mỗi 5s."""
        if self._is_disposed:
            return
        self._auto_refresh_id = self.after(AUTO_REFRESH_INTERVAL_MS, self._on_auto_refresh_tick)

    def _on_auto_refresh_tick(self) -> None:
        self._auto_refresh_id = None
        self.refresh()
        self._schedule_auto_refresh()

    def shutdown(self) -> None:
        """Hủy timer tự động refresh khi view bị đóng/chuyển màn."""
        self._is_disposed = True
        if self._auto_refresh_id is not None:
            self.after_cancel(self._auto_refresh_id)
            self._auto_refresh_id = None

    # ------------------------------------------------------------------
    # Cập nhật số liệu KPI & Filter Bar
    # ------------------------------------------------------------------
    def _update_kpis(self) -> None:
        total = len(self._all_machines)
        available = sum(1 for m in self._all_machines if m.status == MachineStatus.AVAILABLE)
        in_use = sum(1 for m in self._all_machines if m.status == MachineStatus.IN_USE)
        maintenance = sum(1 for m in self._all_machines if m.status == MachineStatus.MAINTENANCE)
        online = sum(
            1 for m in self._all_machines if m.status == MachineStatus.IN_USE and m.active_session is not None
        )

        self._kpi_total.set_value(total)
        self._kpi_available.set_value(available)
        self._kpi_in_use.set_value(in_use)
        self._kpi_maintenance.set_value(maintenance)
        self._kpi_online.set_value(online)

        self._filter_bar.set_counts({
            "all": total,
            "available": available,
            "in_use": in_use,
            "maintenance": maintenance,
        })

    # ------------------------------------------------------------------
    # Xử lý Lọc & Tìm kiếm
    # ------------------------------------------------------------------
    def _handle_filter_changed(self, filter_key: str) -> None:
        self._current_filter = filter_key
        self._render_grid()

    def handle_search(self, keyword: str) -> None:
        """Nhận từ khóa tìm kiếm từ ô Search trên Topbar của AppShell."""
        self._search_keyword = keyword.strip()
        self._render_grid()

    def _get_filtered_machines(self) -> list[MachineSummary]:
        filtered = self._all_machines

        # 1. Lọc theo trạng thái tab
        if self._current_filter == "available":
            filtered = [m for m in filtered if m.status == MachineStatus.AVAILABLE]
        elif self._current_filter == "in_use":
            filtered = [m for m in filtered if m.status == MachineStatus.IN_USE]
        elif self._current_filter == "maintenance":
            filtered = [m for m in filtered if m.status == MachineStatus.MAINTENANCE]

        # 2. Lọc theo từ khóa tìm kiếm
        if self._search_keyword:
            kw = self._search_keyword.lower()
            res: list[MachineSummary] = []
            for m in filtered:
                code_match = kw in m.machine_code.lower()
                name_match = kw in m.name.lower()
                cust_match = False
                if m.active_session and m.active_session.session:
                    cust_match = kw in m.active_session.session.customer_name.lower()
                if code_match or name_match or cust_match:
                    res.append(m)
            filtered = res

        return filtered

    # ------------------------------------------------------------------
    # Render lưới thẻ máy tính (Machine Cards Grid)
    # ------------------------------------------------------------------
    def _render_grid(self) -> None:
        filtered = self._get_filtered_machines()

        # Dọn dẹp các card cũ khỏi grid
        for card in self._displayed_cards:
            card.grid_forget()
            card.destroy()
        self._displayed_cards.clear()
        self._empty_label.place_forget()

        if not filtered:
            empty_msg = (
                "Không tìm thấy máy trạm phù hợp bộ lọc"
                if self._language == "vi"
                else "No matching machines found"
            )
            self._empty_label.configure(text=empty_msg)
            self._empty_label.place(relx=0.5, rely=0.4, anchor="center")
            self._update_footer_count(0, len(self._all_machines))
            return

        # Dựng lại các MachineCard vào lưới 4 cột
        for idx, machine in enumerate(filtered):
            card = MachineCard(
                self._grid_scroll,
                machine=machine,
                actor=self._actor,
                on_open=self._on_card_open,
                on_checkout=self._on_card_checkout,
                on_maintenance=self._on_card_maintenance,
                height=185,
            )
            row = idx // 4
            col = idx % 4
            card.grid(row=row, column=col, padx=5, pady=6, sticky="nsew")
            self._displayed_cards.append(card)

        self._update_footer_count(len(filtered), len(self._all_machines))

    def _update_footer_count(self, showing: int, total: int) -> None:
        is_vi = self._language == "vi"
        txt = (
            f"● Đang hiển thị {showing}/{total} máy"
            if is_vi
            else f"● Displaying {showing}/{total} machines"
        )
        self._showing_label.configure(text=txt)

    # ------------------------------------------------------------------
    # Xử lý Tác vụ Thao tác trên Card (Open / Checkout / Maintenance)
    # ------------------------------------------------------------------
    def _on_card_open(self, machine_id: int) -> None:
        """Xử lý mở phiên sử dụng."""
        machine = next((m for m in self._all_machines if m.machine_id == machine_id), None)
        code = machine.machine_code if machine else f"ID={machine_id}"

        confirmed = ConfirmDialog.ask(
            self,
            title="Mở phiên sử dụng" if self._language == "vi" else "Open Session",
            message=(
                f"Xác nhận kích hoạt và mở phiên cho máy {code}?"
                if self._language == "vi"
                else f"Confirm open session for machine {code}?"
            ),
            confirm_label="Mở máy" if self._language == "vi" else "Open",
            cancel_label="Hủy" if self._language == "vi" else "Cancel",
            is_danger=False,
        )
        if not confirmed:
            return

        try:
            # Mở phiên cho khách hàng demo (ID=1)
            session = self._services.sessions.open_session(
                customer_id=1,
                machine_id=machine_id,
                actor=self._actor,
            )
            ToastManager.show(
                self,
                f"Đã mở phiên {session.session_code} trên máy {code}"
                if self._language == "vi"
                else f"Session {session.session_code} opened on {code}",
                kind="success",
            )
            self.refresh()
        except ApplicationError as err:
            logger.warning("Lỗi mở phiên máy %s: %s", machine_id, err)
            ToastManager.show(self, get_user_friendly_error(err), kind="error")
        except Exception:
            logger.exception("Lỗi bất ngờ khi mở phiên máy %s", machine_id)
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")

    def _on_card_checkout(self, machine_id: int) -> None:
        """Xử lý thanh toán và đóng phiên sử dụng qua PaymentConfirmDialog."""
        try:
            PaymentConfirmDialog(
                self.winfo_toplevel(),
                context=self._context,
                machine_id=machine_id,
                on_success=lambda _res: self.refresh(),
            )
        except ApplicationError as err:
            logger.warning("Lỗi mở hộp thoại checkout máy %s: %s", machine_id, err)
            ToastManager.show(self, get_user_friendly_error(err), kind="error")
        except Exception:
            logger.exception("Lỗi mở hộp thoại checkout máy %s", machine_id)
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")

    def _on_card_maintenance(self, machine_id: int) -> None:
        """Xử lý bật lại máy đang bảo trì (chỉ Quản lý / Admin)."""
        machine = next((m for m in self._all_machines if m.machine_id == machine_id), None)
        code = machine.machine_code if machine else f"ID={machine_id}"

        confirmed = ConfirmDialog.ask(
            self,
            title="Kết thúc bảo trì" if self._language == "vi" else "End Maintenance",
            message=(
                f"Xác nhận hoàn tất bảo trì và mở lại máy {code} cho khách sử dụng?"
                if self._language == "vi"
                else f"Confirm end maintenance and set machine {code} back to Available?"
            ),
            confirm_label="Bật lại máy" if self._language == "vi" else "Re-enable",
            cancel_label="Hủy" if self._language == "vi" else "Cancel",
            is_danger=False,
        )
        if not confirmed:
            return

        try:
            self._services.machines.set_maintenance(
                machine_id=machine_id,
                enabled=False,
                actor=self._actor,
            )
            ToastManager.show(
                self,
                f"Máy {code} đã sẵn sàng phục vụ"
                if self._language == "vi"
                else f"Machine {code} is now available",
                kind="success",
            )
            self.refresh()
        except ApplicationError as err:
            logger.warning("Lỗi bật lại máy %s: %s", machine_id, err)
            ToastManager.show(self, get_user_friendly_error(err), kind="error")
        except Exception:
            logger.exception("Lỗi bật lại máy %s", machine_id)
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")


def dashboard_view_factory(master: Any, context: ViewContext) -> ctk.CTkFrame:
    """Factory khởi tạo DashboardView từ AppShell."""
    return DashboardView(master, context)


def _run_demo() -> None:
    """Chạy độc lập DashboardView với AppShell và Mock Services."""
    import sys

    from ..services.mocks.factory import build_mock_services
    from ..services.mocks.fixtures import DEMO_PASSWORD
    from .app_shell import AppShell
    from .navigation import NavKey
    from .theme import SHELL_HEIGHT, SHELL_WIDTH, load_stitch_fonts, setup_theme

    username = sys.argv[1] if len(sys.argv) > 1 else "quanly01"
    setup_theme()
    services = build_mock_services()
    session = services.auth.login(username, DEMO_PASSWORD)

    root = ctk.CTk()
    load_stitch_fonts()
    root.title("CyberHub Manager — Dashboard")
    root.geometry(f"{SHELL_WIDTH}x{SHELL_HEIGHT}")
    root.minsize(SHELL_WIDTH, SHELL_HEIGHT)

    factories = {NavKey.DASHBOARD: dashboard_view_factory}
    shell = AppShell(
        root,
        services,
        session,
        view_factories=factories,
        on_logout=lambda: root.after(300, root.destroy),
    )
    shell.pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    _run_demo()
