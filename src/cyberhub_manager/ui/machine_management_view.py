"""Machine Management View — Màn hình quản lý cấu hình và trạng thái máy trạm.

Tuân thủ thiết kế Stitch:
- Tham chiếu: docs/ui-reference/qu_n_l_m_y_cyberhub_manager_1280x720/code.html
- Phân quyền: Dành cho Quản lý (MANAGER) và Quản trị viên (ADMIN).
- 5 thẻ chỉ số telemetry (TỔNG SỐ MÁY, TRỐNG SẴN SÀNG, ĐANG SỬ DỤNG, BẢO TRÌ KỸ THUẬT, ĐÃ LƯU TRỮ).
- Thanh tìm kiếm và 5 tab trạng thái (Tất cả, Trống, Đang dùng, Bảo trì, Đã lưu trữ).
- Bảng cấu hình DataTable chi tiết 12 cột kèm cột thao tác nhanh (Mở phiên, Sửa, Bảo trì, Lưu trữ).
- Thanh thao tác dòng được chọn và Chân trang quyền hạn Quản lý kèm phân trang.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from ..domain.dtos import MachineSummary
from ..domain.enums import MachineStatus
from ..domain.exceptions import ApplicationError
from .components import (
    ActionButton,
    ConfirmDialog,
    DataTable,
    FilterBar,
    KpiCard,
    TableColumn,
    TableRow,
    ToastManager,
)
from .dialogs.machine_dialog import MachineDialog
from .dialogs.open_session_dialog import OpenSessionDialog
from .dialogs.payment_confirm_dialog import PaymentConfirmDialog
from .formatters import format_datetime, format_money
from .messages import MSG_OPERATION_FAILED, get_user_friendly_error
from .theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_MONO_SM,
    FONT_ST_MONO_XS,
    FONT_ST_MONO_XS_STRONG,
    FONT_ST_PAGE_TITLE,
    STITCH_CARD_BG,
    STITCH_CARD_BORDER,
    STITCH_CHIP_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_EMERALD,
    STITCH_INPUT_BG,
    STITCH_RADIUS_LG,
    STITCH_TEXT,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
    STITCH_WARNING,
)

if TYPE_CHECKING:
    from .app_shell import ViewContext

logger = logging.getLogger(__name__)


class MachineManagementView(ctk.CTkFrame):
    """Màn hình Quản lý cấu hình và danh sách máy trạm."""

    def __init__(self, master: Any, context: ViewContext) -> None:
        super().__init__(master, fg_color="transparent")
        self._context = context
        self._language = context.language
        self._actor = context.session
        self._services = context.services

        self._all_machines: list[MachineSummary] = []
        self._filtered_machines: list[MachineSummary] = []
        self._selected_machine: MachineSummary | None = None
        self._current_filter: str = "all"
        self._search_keyword: str = ""

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        is_vi = self._language == "vi"

        # ------------------------------------------------------------------
        # ROW 1: PAGE HEADING + ACTION BUTTON
        # ------------------------------------------------------------------
        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 6))

        title_box = ctk.CTkFrame(header_row, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box,
            text="Quản lý máy" if is_vi else "Machine Management",
            font=FONT_ST_PAGE_TITLE,
            text_color=STITCH_TEXT_STRONG,
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Cấu hình, bảo trì và quản lý trạng thái máy" if is_vi else "Configure, maintain and manage workstation states",
            font=FONT_ST_MONO_SM,
            text_color=STITCH_TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        self._btn_add = ActionButton(
            header_row,
            text="+ Thêm máy" if is_vi else "+ Add Machine",
            kind="primary",
            width=130,
            height=34,
            command=self._handle_add_machine,
        )
        self._btn_add.pack(side="right")

        # ------------------------------------------------------------------
        # ROW 2: TELEMETRY METRIC CHIPS (5 Cards in 5 equal columns)
        # ------------------------------------------------------------------
        kpi_row = ctk.CTkFrame(self, fg_color="transparent")
        kpi_row.pack(fill="x", pady=(0, 6))
        for c in range(5):
            kpi_row.grid_columnconfigure(c, weight=1, uniform="kpi_machine")

        self._kpi_total = KpiCard(
            kpi_row,
            title="TỔNG SỐ MÁY" if is_vi else "TOTAL MACHINES",
            value=0,
            icon="🖥",
            tone="default",
        )
        self._kpi_total.grid(row=0, column=0, padx=(0, 4), sticky="nsew")

        self._kpi_available = KpiCard(
            kpi_row,
            title="TRỐNG SẴN SÀNG" if is_vi else "AVAILABLE",
            value=0,
            icon="✓",
            tone="emerald",
        )
        self._kpi_available.grid(row=0, column=1, padx=4, sticky="nsew")

        self._kpi_in_use = KpiCard(
            kpi_row,
            title="ĐANG SỬ DỤNG" if is_vi else "IN USE",
            value=0,
            icon="🎮",
            tone="rose",
        )
        self._kpi_in_use.grid(row=0, column=2, padx=4, sticky="nsew")

        self._kpi_maintenance = KpiCard(
            kpi_row,
            title="BẢO TRÌ KỸ THUẬT" if is_vi else "MAINTENANCE",
            value=0,
            icon="🔧",
            tone="amber",
        )
        self._kpi_maintenance.grid(row=0, column=3, padx=4, sticky="nsew")

        self._kpi_archived = KpiCard(
            kpi_row,
            title="ĐÃ LƯU TRỮ" if is_vi else "ARCHIVED",
            value=0,
            icon="📦",
            tone="default",
        )
        self._kpi_archived.grid(row=0, column=4, padx=(4, 0), sticky="nsew")

        # ------------------------------------------------------------------
        # ROW 3: FILTER CONTROLS & LOCAL SEARCH
        # ------------------------------------------------------------------
        filter_box = ctk.CTkFrame(
            self,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
            height=40,
        )
        filter_box.pack(fill="x", pady=(0, 6))
        filter_box.pack_propagate(False)

        search_wrap = ctk.CTkFrame(filter_box, fg_color="transparent")
        search_wrap.pack(side="left", padx=10, pady=4)

        self._search_entry = ctk.CTkEntry(
            search_wrap,
            placeholder_text="Tìm theo mã hoặc tên máy..." if is_vi else "Search by code or name...",
            width=280,
            height=28,
            corner_radius=6,
            fg_color=STITCH_INPUT_BG,
            border_color=STITCH_CHIP_BORDER,
            text_color=STITCH_TEXT,
            font=FONT_ST_BODY,
        )
        self._search_entry.pack(side="left")
        self._search_entry.bind("<KeyRelease>", lambda _e: self._on_search_typed())

        options = [
            ("all", "Tất cả" if is_vi else "All", 0, "default"),
            ("available", "Trống" if is_vi else "Available", 0, "emerald"),
            ("in_use", "Đang dùng" if is_vi else "In use", 0, "rose"),
            ("maintenance", "Bảo trì" if is_vi else "Maintenance", 0, "amber"),
            ("archived", "Đã lưu trữ" if is_vi else "Archived", 0, "default"),
        ]
        self._filter_bar = FilterBar(
            filter_box,
            options=options,
            on_filter_changed=self._set_filter,
            right_hint="● Chế độ quản trị" if is_vi else "● Manager Mode",
            initial_key=self._current_filter,
            height=32,
        )
        self._filter_bar.pack(side="right", padx=10, pady=4)

        # ------------------------------------------------------------------
        # ROW 4: DATA TABLE CONTAINER
        # ------------------------------------------------------------------
        table_card = ctk.CTkFrame(
            self,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
        )
        table_card.pack(fill="both", expand=True, pady=(0, 6))

        cols = [
            TableColumn("code", "MÃ MÁY" if is_vi else "CODE", width=100),
            TableColumn("name", "TÊN MÁY" if is_vi else "NAME", width=170),
            TableColumn("status", "TRẠNG THÁI" if is_vi else "STATUS", align="center", width=130),
            TableColumn("rate", "GIÁ THEO GIỜ" if is_vi else "HOURLY RATE", align="right", width=120),
            TableColumn("session", "PHIÊN HIỆN TẠI" if is_vi else "ACTIVE SESSION", width=170),
            TableColumn("updated", "CẬP NHẬT CUỐI" if is_vi else "LAST UPDATED", width=130),
            TableColumn("actions", "THAO TÁC" if is_vi else "ACTIONS", align="right", width=160),
        ]

        self._table = DataTable(table_card, columns=cols, on_select=self._on_row_selected)
        self._table.pack(fill="both", expand=True, padx=6, pady=(6, 2))

        # Bottom Action Bar when a row is selected
        self._action_bar = ctk.CTkFrame(table_card, fg_color="transparent", height=34)
        self._action_bar.pack(fill="x", side="bottom", padx=10, pady=(2, 6))

        self._selected_info_label = ctk.CTkLabel(
            self._action_bar,
            text="",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        )
        self._selected_info_label.pack(side="left")

        self._btn_checkout = ActionButton(
            self._action_bar,
            text="Thanh toán" if is_vi else "Checkout",
            kind="danger",
            width=100,
            height=28,
            command=self._handle_checkout_selected,
        )
        self._btn_checkout.pack(side="right", padx=(6, 0))

        self._btn_open_session = ActionButton(
            self._action_bar,
            text="Mở phiên" if is_vi else "Open Session",
            kind="primary",
            width=100,
            height=28,
            command=self._handle_open_session_selected,
        )
        self._btn_open_session.pack(side="right", padx=(6, 0))

        self._btn_edit = ActionButton(
            self._action_bar,
            text="Sửa thông tin" if is_vi else "Edit Machine",
            kind="secondary",
            width=105,
            height=28,
            command=self._handle_edit_machine_selected,
        )
        self._btn_edit.pack(side="right", padx=(6, 0))

        self._btn_maint = ActionButton(
            self._action_bar,
            text="Bảo trì" if is_vi else "Maintenance",
            kind="warning",
            width=115,
            height=28,
            command=self._handle_toggle_maintenance_selected,
        )
        self._btn_maint.pack(side="right", padx=(6, 0))

        self._btn_archive = ActionButton(
            self._action_bar,
            text="Ngừng sử dụng" if is_vi else "Archive",
            kind="danger",
            width=115,
            height=28,
            command=self._handle_archive_machine_selected,
        )
        self._btn_archive.pack(side="right")

        self._update_actions_enabled(False)

        # ------------------------------------------------------------------
        # ROW 5: TABLE FOOTER (Role disclaimer + Pagination)
        # ------------------------------------------------------------------
        footer = ctk.CTkFrame(
            self,
            fg_color=STITCH_CARD_BG,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=STITCH_RADIUS_LG,
            height=32,
        )
        footer.pack(fill="x")
        footer.pack_propagate(False)

        role_wrap = ctk.CTkFrame(footer, fg_color="transparent")
        role_wrap.pack(side="left", padx=10, pady=4)
        ctk.CTkLabel(
            role_wrap,
            text="🛡  ",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_CYAN,
        ).pack(side="left")
        ctk.CTkLabel(
            role_wrap,
            text="Tài khoản QUẢN LÝ • Yêu cầu xác thực khi chuyển bảo trì hoặc lưu trữ máy"
            if is_vi
            else "MANAGER account • Authentication required when transitioning maintenance or archiving",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left")

        self._pagination_wrap = ctk.CTkFrame(footer, fg_color="transparent")
        self._pagination_wrap.pack(side="right", padx=10, pady=4)

        self._pagination_lbl = ctk.CTkLabel(
            self._pagination_wrap,
            text="Hiển thị 0/0 máy",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        )
        self._pagination_lbl.pack(side="left", padx=(0, 8))

        p1_btn = ctk.CTkButton(
            self._pagination_wrap,
            text="1",
            width=22,
            height=20,
            corner_radius=4,
            fg_color=STITCH_CYAN,
            text_color="#090E19",
            font=FONT_ST_MONO_XS_STRONG,
        )
        p1_btn.pack(side="left")

    def _update_actions_enabled(self, enabled: bool) -> None:
        if not enabled or not self._selected_machine:
            self._btn_checkout.set_enabled(False)
            self._btn_open_session.set_enabled(False)
            self._btn_edit.set_enabled(False)
            self._btn_maint.set_enabled(False)
            self._btn_archive.set_enabled(False)
            return

        mach = self._selected_machine
        can_checkout = mach.is_active and mach.status == MachineStatus.IN_USE
        can_open = mach.is_active and mach.status == MachineStatus.AVAILABLE
        can_edit = mach.is_active
        can_maint = mach.is_active and mach.status != MachineStatus.IN_USE
        can_archive = mach.is_active and mach.status == MachineStatus.AVAILABLE

        self._btn_checkout.set_enabled(can_checkout)
        self._btn_open_session.set_enabled(can_open)
        self._btn_edit.set_enabled(can_edit)
        self._btn_maint.set_enabled(can_maint)
        self._btn_archive.set_enabled(can_archive)

    # ------------------------------------------------------------------
    # Data Loading & Filtering
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        try:
            store_id = self._actor.store_id
            self._all_machines = self._services.machines.list_machines(store_id)
            self._update_kpis()
            self._apply_filters()
        except ApplicationError as err:
            logger.warning("Không nạp được danh sách máy: %s", err)
            ToastManager.show(self, get_user_friendly_error(err), kind="error")
        except Exception:
            logger.exception("Lỗi không mong muốn khi tải danh sách máy")
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")

    def _update_kpis(self) -> None:
        total = len(self._all_machines)
        available = sum(1 for m in self._all_machines if m.is_active and m.status == MachineStatus.AVAILABLE)
        in_use = sum(1 for m in self._all_machines if m.is_active and m.status == MachineStatus.IN_USE)
        maintenance = sum(1 for m in self._all_machines if m.is_active and m.status == MachineStatus.MAINTENANCE)
        archived = sum(1 for m in self._all_machines if not m.is_active)

        self._kpi_total.set_value(total)
        self._kpi_available.set_value(available)
        self._kpi_in_use.set_value(in_use)
        self._kpi_maintenance.set_value(maintenance)
        self._kpi_archived.set_value(archived)

        self._filter_bar.set_counts({
            "all": total,
            "available": available,
            "in_use": in_use,
            "maintenance": maintenance,
            "archived": archived,
        })

    def _on_search_typed(self) -> None:
        self._search_keyword = self._search_entry.get().strip()
        self._apply_filters()

    def handle_search(self, keyword: str) -> None:
        """Nhận từ khóa tìm kiếm từ Topbar của AppShell."""
        self._search_entry.delete(0, "end")
        self._search_entry.insert(0, keyword)
        self._search_keyword = keyword.strip()
        self._apply_filters()

    def _set_filter(self, key: str) -> None:
        self._current_filter = key
        self._apply_filters()

    def _apply_filters(self) -> None:
        filtered = self._all_machines

        if self._current_filter == "available":
            filtered = [m for m in filtered if m.is_active and m.status == MachineStatus.AVAILABLE]
        elif self._current_filter == "in_use":
            filtered = [m for m in filtered if m.is_active and m.status == MachineStatus.IN_USE]
        elif self._current_filter == "maintenance":
            filtered = [m for m in filtered if m.is_active and m.status == MachineStatus.MAINTENANCE]
        elif self._current_filter == "archived":
            filtered = [m for m in filtered if not m.is_active]

        if self._search_keyword:
            kw = self._search_keyword.lower()
            filtered = [
                m for m in filtered
                if kw in m.machine_code.lower() or kw in m.name.lower()
            ]

        self._filtered_machines = filtered
        self._render_table()

    def _render_table(self) -> None:
        rows: list[TableRow] = []
        is_vi = self._language == "vi"

        for m in self._filtered_machines:
            is_archived = not m.is_active
            if is_archived:
                st_text = "● Đã lưu trữ" if is_vi else "● Archived"
                st_fg = STITCH_TEXT_MUTED
                st_bg = "#1E2430"
            elif m.status == MachineStatus.AVAILABLE:
                st_text = "● Trống" if is_vi else "● Available"
                st_fg = STITCH_EMERALD
                st_bg = "#132E27"
            elif m.status == MachineStatus.IN_USE:
                st_text = "● Đang dùng" if is_vi else "● In use"
                st_fg = STITCH_DANGER
                st_bg = "#381E28"
            elif m.status == MachineStatus.MAINTENANCE:
                st_text = "● Bảo trì" if is_vi else "● Maintenance"
                st_fg = STITCH_WARNING
                st_bg = "#33281E"
            else:
                st_text = f"● {m.status.value}"
                st_fg = STITCH_TEXT
                st_bg = "#171F30"

            sess_main = "—"
            sess_sub = ""
            if m.active_session and m.active_session.session:
                sess_main = m.active_session.session.customer_name
                # duration / code
                sess_sub = f"Mã: {m.active_session.session.session_code}"

            cell_colors: dict[str, str] = {
                "code": STITCH_CYAN if not is_archived else STITCH_TEXT_MUTED,
                "name": STITCH_TEXT_STRONG if not is_archived else STITCH_TEXT_MUTED,
                "rate": STITCH_TEXT_STRONG if not is_archived else STITCH_TEXT_MUTED,
                "updated": STITCH_TEXT_MUTED,
            }

            cell_subs: dict[str, str] = {}
            if sess_sub:
                cell_subs["session"] = sess_sub

            # Inline Action buttons for this row
            actions_list: list[dict[str, Any]] = []
            if not is_archived:
                if m.status == MachineStatus.AVAILABLE:
                    actions_list.append({
                        "text": "▶",
                        "tooltip": "Mở phiên",
                        "command": lambda mach=m: self._handle_open_session(mach),
                        "fg_color": "#0E3E53",
                        "hover_color": "#11526E",
                        "text_color": STITCH_CYAN,
                        "enabled": True,
                    })
                    actions_list.append({
                        "text": "✎",
                        "tooltip": "Sửa",
                        "command": lambda mach=m: self._handle_edit_machine(mach),
                        "fg_color": "#1E273A",
                        "hover_color": "#27344E",
                        "text_color": STITCH_TEXT,
                        "enabled": True,
                    })
                    actions_list.append({
                        "text": "🔧",
                        "tooltip": "Bảo trì",
                        "command": lambda mach=m: self._handle_toggle_maintenance(mach),
                        "fg_color": "#33281E",
                        "hover_color": "#4D3814",
                        "text_color": STITCH_WARNING,
                        "enabled": True,
                    })
                    actions_list.append({
                        "text": "📦",
                        "tooltip": "Lưu trữ",
                        "command": lambda mach=m: self._handle_archive_machine(mach),
                        "fg_color": "#2E1C24",
                        "hover_color": "#4A202E",
                        "text_color": STITCH_DANGER,
                        "enabled": True,
                    })
                elif m.status == MachineStatus.IN_USE:
                    actions_list.append({
                        "text": "✎",
                        "tooltip": "Sửa",
                        "command": lambda mach=m: self._handle_edit_machine(mach),
                        "fg_color": "#1E273A",
                        "hover_color": "#27344E",
                        "text_color": STITCH_TEXT,
                        "enabled": True,
                    })
                    actions_list.append({
                        "text": "🔧",
                        "tooltip": "Máy đang có phiên hoạt động",
                        "command": None,
                        "enabled": False,
                    })
                    actions_list.append({
                        "text": "📦",
                        "tooltip": "Máy đang có phiên hoạt động",
                        "command": None,
                        "enabled": False,
                    })
                elif m.status == MachineStatus.MAINTENANCE:
                    actions_list.append({
                        "text": "✎",
                        "tooltip": "Sửa",
                        "command": lambda mach=m: self._handle_edit_machine(mach),
                        "fg_color": "#1E273A",
                        "hover_color": "#27344E",
                        "text_color": STITCH_TEXT,
                        "enabled": True,
                    })
                    actions_list.append({
                        "text": "🔓",
                        "tooltip": "Kết thúc bảo trì",
                        "command": lambda mach=m: self._handle_toggle_maintenance(mach),
                        "fg_color": "#132E27",
                        "hover_color": "#1B4D3E",
                        "text_color": STITCH_EMERALD,
                        "enabled": True,
                    })
                    actions_list.append({
                        "text": "📦",
                        "tooltip": "Máy đang bảo trì không thể lưu trữ",
                        "command": None,
                        "enabled": False,
                    })

            act_dict: dict[str, list[dict[str, Any]]] = {}
            if actions_list:
                act_dict["actions"] = actions_list

            rows.append(
                TableRow(
                    key=m.machine_id,
                    cells={
                        "code": m.machine_code,
                        "name": m.name,
                        "status": st_text,
                        "rate": f"{format_money(m.hourly_rate)} VND/h",
                        "session": sess_main,
                        "updated": format_datetime(m.updated_at),
                        "actions": "—" if is_archived else "",
                    },
                    cell_colors=cell_colors,
                    cell_subtexts=cell_subs,
                    badges={"status": (st_text, st_fg, st_bg)},
                    action_buttons=act_dict,
                    dimmed=is_archived,
                )
            )

        self._table.set_rows(rows)

        # Update pagination text
        total_all = len(self._all_machines)
        displayed = len(self._filtered_machines)
        self._pagination_lbl.configure(
            text=f"Hiển thị 1-{displayed} trên tổng số {total_all} máy"
            if is_vi
            else f"Showing 1-{displayed} of {total_all} machines"
        )

        if self._filtered_machines:
            if not self._selected_machine or not any(m.machine_id == self._selected_machine.machine_id for m in self._filtered_machines):
                self._select_machine(self._filtered_machines[0])
            else:
                # Update current selected machine with latest summary
                latest = next((m for m in self._filtered_machines if m.machine_id == self._selected_machine.machine_id), None)
                self._select_machine(latest)
        else:
            self._select_machine(None)

    def _on_row_selected(self, row_key: int | str) -> None:
        m = next((mach for mach in self._filtered_machines if mach.machine_id == row_key), None)
        self._select_machine(m)

    def _select_machine(self, machine: MachineSummary | None) -> None:
        self._selected_machine = machine
        is_vi = self._language == "vi"

        if not machine:
            self._selected_info_label.configure(text="")
            self._update_actions_enabled(False)
            return

        txt = (
            f"Đang chọn: {machine.machine_code} • {machine.name} ({format_money(machine.hourly_rate)}/h)"
            if is_vi
            else f"Selected: {machine.machine_code} • {machine.name} ({format_money(machine.hourly_rate)}/h)"
        )
        self._selected_info_label.configure(text=txt)

        if machine.status == MachineStatus.MAINTENANCE:
            self._btn_maint.configure(text="Bật lại máy" if is_vi else "Enable Station")
            self._btn_maint.set_kind("success")
        else:
            self._btn_maint.configure(text="Đặt bảo trì" if is_vi else "Maintenance")
            self._btn_maint.set_kind("warning")

        self._update_actions_enabled(True)

    # ------------------------------------------------------------------
    # Actions & Dialog Openers
    # ------------------------------------------------------------------
    def _handle_add_machine(self) -> None:
        MachineDialog(
            self.winfo_toplevel(),
            self._services,
            actor=self._actor,
            language=self._language,
            on_success=self.refresh,
        )

    def _handle_edit_machine_selected(self) -> None:
        if self._selected_machine:
            self._handle_edit_machine(self._selected_machine)

    def _handle_edit_machine(self, machine: MachineSummary) -> None:
        MachineDialog(
            self.winfo_toplevel(),
            self._services,
            actor=self._actor,
            machine=machine,
            language=self._language,
            on_success=self.refresh,
        )

    def _handle_open_session_selected(self) -> None:
        if self._selected_machine:
            self._handle_open_session(self._selected_machine)

    def _handle_open_session(self, machine: MachineSummary) -> None:
        if not machine.is_active or machine.status != MachineStatus.AVAILABLE:
            ToastManager.show(
                self,
                "Máy không ở trạng thái sẵn sàng để mở phiên!" if self._language == "vi" else "Workstation not available for session!",
                kind="warning",
            )
            return
        OpenSessionDialog(
            self.winfo_toplevel(),
            self._services,
            machine=machine,
            actor=self._actor,
            language=self._language,
            on_success=self.refresh,
        )

    def _handle_checkout_selected(self) -> None:
        if self._selected_machine and self._selected_machine.status == MachineStatus.IN_USE:
            PaymentConfirmDialog(
                self.winfo_toplevel(),
                self._services,
                machine_id=self._selected_machine.machine_id,
                actor=self._actor,
                language=self._language,
                on_success=lambda _res: self.refresh(),
            )

    def _handle_toggle_maintenance_selected(self) -> None:
        if self._selected_machine:
            self._handle_toggle_maintenance(self._selected_machine)

    def _handle_toggle_maintenance(self, mach: MachineSummary) -> None:
        is_vi = self._language == "vi"
        target_enabled = mach.status != MachineStatus.MAINTENANCE

        title = ("Đặt máy sang bảo trì" if target_enabled else "Bật lại máy") if is_vi else ("Set Maintenance" if target_enabled else "Enable Machine")
        msg = (
            f"Xác nhận thay đổi trạng thái máy {mach.machine_code} sang " + ("BẢO TRÌ?" if target_enabled else "SẴN SÀNG?")
            if is_vi
            else f"Confirm change machine {mach.machine_code} status to " + ("MAINTENANCE?" if target_enabled else "AVAILABLE?")
        )

        confirmed = ConfirmDialog.ask(
            self.winfo_toplevel(),
            title=title,
            message=msg,
            confirm_label="Xác nhận" if is_vi else "Confirm",
            cancel_label="Hủy" if is_vi else "Cancel",
            is_danger=target_enabled,
        )
        if not confirmed:
            return

        try:
            self._services.machines.set_maintenance(
                machine_id=mach.machine_id,
                enabled=target_enabled,
                actor=self._actor,
            )
            ToastManager.show(
                self,
                f"Đã cập nhật trạng thái máy {mach.machine_code}!" if is_vi else f"Updated machine {mach.machine_code} status!",
                kind="success",
            )
            self.refresh()
        except ApplicationError as err:
            logger.warning("Lỗi bảo trì máy: %s", err)
            ToastManager.show(self, get_user_friendly_error(err), kind="error")
        except Exception:
            logger.exception("Lỗi không mong muốn khi bảo trì máy")
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")

    def _handle_archive_machine_selected(self) -> None:
        if self._selected_machine:
            self._handle_archive_machine(self._selected_machine)

    def _handle_archive_machine(self, mach: MachineSummary) -> None:
        is_vi = self._language == "vi"

        confirmed = ConfirmDialog.ask(
            self.winfo_toplevel(),
            title="Xác nhận ngừng sử dụng" if is_vi else "Confirm Archive",
            message=(
                f"Bạn có chắc chắn muốn ngừng sử dụng / xóa máy {mach.machine_code} ({mach.name})?\n"
                "Thao tác này sẽ lưu trữ máy và ẩn khỏi sơ đồ vận hành."
                if is_vi
                else f"Are you sure you want to archive / delete machine {mach.machine_code} ({mach.name})?\n"
                "This operation will archive the machine from operational grid."
            ),
            confirm_label="Ngừng sử dụng" if is_vi else "Archive",
            cancel_label="Hủy" if is_vi else "Cancel",
            is_danger=True,
        )
        if not confirmed:
            return

        try:
            res = self._services.machines.archive_machine(
                machine_id=mach.machine_id,
                actor=self._actor,
            )
            ToastManager.show(
                self,
                f"Máy {mach.machine_code} đã được {res.action.lower()}!"
                if is_vi
                else f"Machine {mach.machine_code} {res.action.lower()}d!",
                kind="info",
            )
            self.refresh()
        except ApplicationError as err:
            logger.warning("Lỗi archive máy: %s", err)
            ToastManager.show(self, get_user_friendly_error(err), kind="error")
        except Exception:
            logger.exception("Lỗi không mong muốn khi archive máy")
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")


def machine_management_view_factory(master: Any, context: ViewContext) -> ctk.CTkFrame:
    """Factory khởi tạo MachineManagementView từ AppShell."""
    return MachineManagementView(master, context)
