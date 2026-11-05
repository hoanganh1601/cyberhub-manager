"""Component Gallery — Ứng dụng độc lập xem và thử nghiệm bộ UI Component.

Quy định: docs/07_DTO_UI_HANDOFF.md mục 9, 10 và docs/assignments/NGAT_NG01.md.
Khởi chạy độc lập (không cần Docker, MySQL hay file .env):
    python -m cyberhub_manager.ui.component_gallery
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from importlib.resources import files
from typing import Any

import customtkinter as ctk
from PIL import Image

from ..domain.dtos import (
    ActiveSessionSummary,
    CustomerSummary,
    EmployeeSession,
    MachineSummary,
    SessionSummary,
)
from ..domain.enums import (
    AccountStatus,
    CustomerStatus,
    InvoiceStatus,
    MachineStatus,
    PaymentMethod,
    Role,
    SessionStatus,
)
from ..domain.exceptions import ApplicationError, ConflictError
from ..services.contracts import ServiceBundle
from ..services.mocks.factory import build_mock_services
from ..services.mocks.scenarios import MockScenario
from .components import (
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
from .formatters import format_datetime, format_money
from .i18n import (
    DEFAULT_LANGUAGE,
    Language,
    normalize_language,
    translate,
)
from .messages import get_field_errors_safe, get_user_friendly_error
from .state import ViewState
from .theme import (
    ACCENT_HOVER,
    APP_MIN_HEIGHT,
    APP_MIN_WIDTH,
    BG_APP,
    BG_SIDEBAR,
    BG_SURFACE,
    BORDER,
    DANGER,
    FONT_BODY,
    FONT_BODY_STRONG,
    FONT_CAPTION,
    FONT_TITLE_LG,
    FONT_TITLE_MD,
    HEIGHT_HEADER,
    PADDING_CONTENT,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SPACING_XL,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WIDTH_SIDEBAR,
    BG_CARD,
    BG_CONTENT,
    BG_INPUT,
    BG_NAV_ACTIVE,
    BG_NAV_HOVER,
    BG_TOPBAR,
    BORDER_FOCUS,
    BRAND_PRIMARY,
    FONT_SHELL_BODY,
    FONT_SHELL_BODY_STRONG,
    FONT_SHELL_CAPTION,
    FONT_SHELL_SECTION,
    NAV_TEXT,
    NAV_TEXT_ACTIVE,
    SHELL_CONTENT_PADDING,
    SHELL_SIDEBAR_WIDTH,
    SHELL_STATUSBAR_HEIGHT,
    SHELL_TOPBAR_HEIGHT,
    setup_theme,
)

logger = logging.getLogger(__name__)

# Mốc tham chiếu chuẩn theo mục 9: 2026-10-18T09:00:00+00:00 UTC (16:00 giờ VN)
REF_TIME = datetime(2026, 10, 18, 9, 0, 0, tzinfo=timezone.utc)

# 1. FIXTURES DTO MẪU CHUẨN MỤC 9
ACTOR_MANAGER = EmployeeSession(
    employee_id=1,
    employee_code="NV001",
    full_name="Nguyễn Văn Quản Lý",
    username="manager01",
    store_id=1,
    store_code="CH01",
    store_name="CyberHub Central",
    role=Role.MANAGER,
)

ACTOR_STAFF = EmployeeSession(
    employee_id=2,
    employee_code="NV002",
    full_name="Trần Thị Nhân Viên",
    username="staff01",
    store_id=1,
    store_code="CH01",
    store_name="CyberHub Central",
    role=Role.STAFF,
)

# Khách hàng mẫu
CUSTOMERS_FIXTURE = [
    CustomerSummary(1, "KH001", "Nguyễn Văn An", "0912345678", 1, "an.nv", 50000, CustomerStatus.ACTIVE, AccountStatus.ACTIVE),
    CustomerSummary(2, "KH002", "Trần Thị Bình", "0987654321", 2, "binh.tt", 5000, CustomerStatus.ACTIVE, AccountStatus.ACTIVE),
    CustomerSummary(3, "KH003", "Lê Văn Cường", "0901122334", 3, "cuong.lv", 20000, CustomerStatus.ACTIVE, AccountStatus.LOCKED),
    CustomerSummary(4, "KH004", "Phạm Minh Dũng", "0933445566", 4, "dung.pm", -5000, CustomerStatus.INACTIVE, AccountStatus.LOCKED),
    CustomerSummary(5, "KH005", "Hoàng Thị Em", "0977889900", 5, "em.ht", 100000, CustomerStatus.ACTIVE, AccountStatus.ACTIVE),
]

# Máy mẫu chuẩn theo mục 9
# PC01: AVAILABLE
MACHINE_PC01 = MachineSummary(
    machine_id=1,
    machine_code="PC01",
    store_id=1,
    name="Máy 01",
    status=MachineStatus.AVAILABLE,
    hourly_rate=10000,
    is_active=True,
    updated_at=REF_TIME,
    active_session=None,
)

# PC02: IN_USE âm tiền (-10.000 VND)
SESSION_PC02 = SessionSummary(
    session_id=101,
    session_code="SS101",
    customer_id=2,
    customer_code="KH002",
    customer_name="Trần Thị Bình",
    machine_id=2,
    machine_code="PC02",
    machine_name="Máy 02",
    started_at=REF_TIME,
    hourly_rate=10000,
    status=SessionStatus.ACTIVE,
)
ACTIVE_PC02 = ActiveSessionSummary(
    session=SESSION_PC02,
    account_balance=5000,
    elapsed_seconds=5400,  # 90 phút
    estimated_cost=15000,
    projected_balance=-10000,  # Âm 10.000 VND
    as_of=REF_TIME,
)
MACHINE_PC02 = MachineSummary(
    machine_id=2,
    machine_code="PC02",
    store_id=1,
    name="Máy 02",
    status=MachineStatus.IN_USE,
    hourly_rate=10000,
    is_active=True,
    updated_at=REF_TIME,
    active_session=ACTIVE_PC02,
)

# PC03: MAINTENANCE
MACHINE_PC03 = MachineSummary(
    machine_id=3,
    machine_code="PC03",
    store_id=1,
    name="Máy 03",
    status=MachineStatus.MAINTENANCE,
    hourly_rate=10000,
    is_active=True,
    updated_at=REF_TIME,
    active_session=None,
)

# PC05: IN_USE số dư dương
SESSION_PC05 = SessionSummary(
    session_id=102,
    session_code="SS102",
    customer_id=5,
    customer_code="KH005",
    customer_name="Hoàng Thị Em",
    machine_id=5,
    machine_code="PC05",
    machine_name="Máy 05",
    started_at=REF_TIME,
    hourly_rate=10000,
    status=SessionStatus.ACTIVE,
)
ACTIVE_PC05 = ActiveSessionSummary(
    session=SESSION_PC05,
    account_balance=100000,
    elapsed_seconds=1800,  # 30 phút
    estimated_cost=5000,
    projected_balance=95000,
    as_of=REF_TIME,
)
MACHINE_PC05 = MachineSummary(
    machine_id=5,
    machine_code="PC05",
    store_id=1,
    name="Máy 05",
    status=MachineStatus.IN_USE,
    hourly_rate=10000,
    is_active=True,
    updated_at=REF_TIME,
    active_session=ACTIVE_PC05,
)


class ComponentGalleryApp(ctk.CTk):
    """Cửa sổ ứng dụng Component Gallery chạy độc lập ở kích thước 1280x720."""

    def __init__(self) -> None:
        super().__init__()
        setup_theme()

        self.title("CyberHub Manager — Component Gallery (NG-01)")
        self.geometry(f"{APP_MIN_WIDTH}x{APP_MIN_HEIGHT}")
        self.minsize(APP_MIN_WIDTH, APP_MIN_HEIGHT)
        self.configure(fg_color=BG_APP)

        self._scenario: MockScenario = MockScenario.SUCCESS
        self._services: ServiceBundle = build_mock_services(self._scenario)
        self._current_actor: EmployeeSession = ACTOR_STAFF
        self._machine_cards: list[MachineCard] = []
        self._language: Language = DEFAULT_LANGUAGE
        self._brand_image = self._load_brand_image()
        self._brand_nav_labels: list[tuple[ctk.CTkButton, str]] = []

        self._build_layout()

    @staticmethod
    def _load_brand_image() -> ctk.CTkImage:
        """Load the packaged CyberHub logo for the gallery."""

        resource = files("cyberhub_manager.ui.assets").joinpath(
            "cyberhub_logo_dark.png"
        )
        with resource.open("rb") as stream:
            logo = Image.open(stream).convert("RGBA")
            logo.load()

        return ctk.CTkImage(
            light_image=logo,
            dark_image=logo,
            size=(210, 82),
        )
    def _build_layout(self) -> None:
        """Xây dựng khung giao diện chính: Header, Sidebar menu và Vùng nội dung."""
        # 1. Header trên cùng
        self._header = ctk.CTkFrame(
            self,
            fg_color=BG_SURFACE,
            height=HEIGHT_HEADER,
            corner_radius=0,
            border_width=1,
            border_color=BORDER,
        )
        self._header.pack(fill="x", side="top")

        title_lbl = ctk.CTkLabel(
            self._header,
            text="⚡ CyberHub Manager — Component Catalog (NG-01)",
            font=FONT_TITLE_MD,
            text_color=TEXT_PRIMARY,
        )
        title_lbl.pack(side="left", padx=PADDING_CONTENT)

        # Actor Switcher ở header
        actor_box = ctk.CTkFrame(self._header, fg_color="transparent")
        actor_box.pack(side="right", padx=PADDING_CONTENT)

        actor_hint = ctk.CTkLabel(
            actor_box,
            text="Vai trò hiện tại:",
            font=FONT_CAPTION,
            text_color=TEXT_SECONDARY,
        )
        actor_hint.pack(side="left", padx=(0, SPACING_SM))

        self._actor_seg = ctk.CTkSegmentedButton(
            actor_box,
            values=["STAFF (Nhân viên)", "MANAGER (Quản lý)"],
            command=self._on_actor_changed,
            font=FONT_CAPTION,
            selected_color=ACCENT_HOVER,
        )
        self._actor_seg.set("STAFF (Nhân viên)")
        self._actor_seg.pack(side="left")

        # Scenario Switcher ở header
        scenario_box = ctk.CTkFrame(self._header, fg_color="transparent")
        scenario_box.pack(side="right", padx=(0, SPACING_LG))

        scenario_hint = ctk.CTkLabel(
            scenario_box,
            text="Mock Scenario:",
            font=FONT_CAPTION,
            text_color=TEXT_SECONDARY,
        )
        scenario_hint.pack(side="left", padx=(0, SPACING_SM))

        self._scenario_opt = ctk.CTkOptionMenu(
            scenario_box,
            values=[s.value for s in MockScenario],
            command=self._on_scenario_changed,
            font=FONT_CAPTION,
            width=170,
        )
        self._scenario_opt.set(self._scenario.value)
        self._scenario_opt.pack(side="left")

        # 2. Body chứa Sidebar và Content area
        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="both", expand=True)

        # Sidebar trái
        self._sidebar = ctk.CTkFrame(
            self._body,
            fg_color=BG_SIDEBAR,
            width=WIDTH_SIDEBAR,
            corner_radius=0,
        )
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        menu_lbl = ctk.CTkLabel(
            self._sidebar,
            text="DANH MỤC THỬ NGHIỆM",
            font=FONT_CAPTION,
            text_color=TEXT_MUTED,
            anchor="w",
        )
        menu_lbl.pack(fill="x", padx=SPACING_LG, pady=(SPACING_LG, SPACING_SM))

        self._tabs = [
            ("brand_theme", "✦  Brand & Theme"),
            ("machine_cards", "🖥  Machine Cards"),
            ("buttons_inputs", "🔘  Buttons & Inputs"),
            ("data_table", "📊  Data Table"),
            ("badges_feedback", "🔔  Badges & Feedback"),
        ]
        self._nav_buttons: dict[str, ActionButton] = {}

        for key, label in self._tabs:
            btn = ActionButton(
                self._sidebar,
                text=f"  {label}",
                kind="ghost",
                height=38,
                anchor="w",
                command=lambda k=key: self._show_tab(k),
            )
            btn.pack(fill="x", padx=SPACING_SM, pady=2)
            self._nav_buttons[key] = btn

        # Content area bên phải
        self._content_container = ctk.CTkFrame(self._body, fg_color="transparent")
        self._content_container.pack(side="right", fill="both", expand=True, padx=SPACING_LG, pady=SPACING_LG)

        # Khởi tạo các view tab
        self._tab_frames: dict[str, ctk.CTkFrame] = {
            "brand_theme": self._create_tab_brand_theme(),
            "machine_cards": self._create_tab_machine_cards(),
            "buttons_inputs": self._create_tab_buttons_inputs(),
            "data_table": self._create_tab_data_table(),
            "badges_feedback": self._create_tab_badges_feedback(),
        }

        # Mặc định mở Tab 1
        self._show_tab("brand_theme")

    def _show_tab(self, tab_key: str) -> None:
        """Chuyển đổi giữa các tab."""
        for key, frame in self._tab_frames.items():
            if key == tab_key:
                frame.pack(fill="both", expand=True)
                self._nav_buttons[key].configure(kind="primary")
            else:
                frame.pack_forget()
                self._nav_buttons[key].configure(kind="ghost")

    def _on_actor_changed(self, value: str) -> None:
        """Xử lý khi người dùng đổi vai trò để xem thay đổi phân quyền."""
        if "MANAGER" in value:
            self._current_actor = ACTOR_MANAGER
            ToastManager.show(self, "Switched role to: MANAGER (Administrative privileges)", kind="info")
        else:
            self._current_actor = ACTOR_STAFF
            ToastManager.show(self, "Switched role to: STAFF (Operator privileges)", kind="info")

        # Cập nhật lại các MachineCard
        for card in self._machine_cards:
            if card._machine:
                card.render(card._machine, self._current_actor)

    def _on_scenario_changed(self, value: str) -> None:
        """Đổi kịch bản Mock services (SUCCESS, EMPTY, VALIDATION_ERROR, CONFLICT, UNAVAILABLE)."""
        self._scenario = MockScenario(value)
        self._services = build_mock_services(self._scenario)
        ToastManager.show(self, f"Mock Scenario set to: {self._scenario.value}", kind="info")
        self._refresh_gallery_data()

    def _refresh_gallery_data(self) -> None:
        """Đồng bộ lại dữ liệu của các tab sau khi đổi kịch bản mock."""
        self._render_machine_cards()
        self._load_table_data()

    # --------------------------------------------------------------------------
    # TAB 0: BRAND & APP SHELL TOKENS
    # --------------------------------------------------------------------------
    def _create_tab_brand_theme(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(
            self._content_container,
            fg_color="transparent",
        )

        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=0)  # Tiêu đề
        frame.grid_rowconfigure(1, weight=0)  # Logo
        frame.grid_rowconfigure(2, weight=1)  # App Shell nhận chiều cao còn dư
        frame.grid_rowconfigure(3, weight=0)  # Palette
        frame.grid_rowconfigure(4, weight=0)  # Geometry note

        title_row = ctk.CTkFrame(frame, fg_color="transparent")
        title_row.grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(0, SPACING_MD),
        )

        title_box = ctk.CTkFrame(title_row, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)

        title = ctk.CTkLabel(
            title_box,
            text="CyberHub Brand & Unified App Shell",
            font=FONT_TITLE_LG,
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        title.pack(fill="x")

        description = ctk.CTkLabel(
            title_box,
            text=(
                "NG-01 showcase: logo, App Shell tokens, "
                "compact typography and VI/EN navigation."
            ),
            font=FONT_CAPTION,
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        description.pack(fill="x", pady=(4, 0))

        language_control = ctk.CTkSegmentedButton(
            title_row,
            values=["VI", "EN"],
            width=100,
            selected_color=BRAND_PRIMARY,
            selected_hover_color=BRAND_PRIMARY,
            unselected_color=BG_INPUT,
            unselected_hover_color=BG_NAV_HOVER,
            command=self._on_brand_language_changed,
        )
        language_control.set(self._language.upper())
        language_control.pack(side="right")

        brand_section = ctk.CTkFrame(
            frame,
            fg_color=BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=BORDER,
        )
        brand_section.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(0, SPACING_MD),
        )

        brand_logo = ctk.CTkLabel(
            brand_section,
            text="",
            image=self._brand_image,
        )
        brand_logo.pack(
            side="left",
            padx=PADDING_CONTENT,
            pady=SPACING_LG,
        )

        brand_copy = ctk.CTkFrame(
            brand_section,
            fg_color="transparent",
        )
        brand_copy.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, PADDING_CONTENT),
            pady=SPACING_LG,
        )

        self._brand_preview_title = ctk.CTkLabel(
            brand_copy,
            text=translate("app.name", self._language),
            font=FONT_TITLE_MD,
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self._brand_preview_title.pack(fill="x")

        self._brand_preview_status = ctk.CTkLabel(
            brand_copy,
            text=f"● {translate('status.ready', self._language)}",
            font=FONT_SHELL_BODY,
            text_color=BRAND_PRIMARY,
            anchor="w",
        )
        self._brand_preview_status.pack(
            fill="x",
            pady=(SPACING_SM, 0),
        )

        shell_section = ctk.CTkFrame(
            frame,
            fg_color=BG_CONTENT,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_FOCUS,
            height=220,
        )
        shell_section.grid(
            row=2,
            column=0,
            sticky="nsew",
            pady=(0, SPACING_MD),
        )
        shell_section.pack_propagate(False)

        mini_sidebar = ctk.CTkFrame(
            shell_section,
            width=190,
            fg_color=BG_SIDEBAR,
            corner_radius=0,
        )
        mini_sidebar.pack(side="left", fill="y")
        mini_sidebar.pack_propagate(False)

        sidebar_title = ctk.CTkLabel(
            mini_sidebar,
            text="CYBERHUB",
            text_color=BRAND_PRIMARY,
            font=FONT_SHELL_BODY_STRONG,
        )
        sidebar_title.pack(
            fill="x",
            padx=SPACING_MD,
            pady=(SPACING_LG, SPACING_MD),
        )

        self._brand_nav_labels.clear()
        navigation_keys = (
            "nav.dashboard",
            "nav.customers",
            "nav.machines",
            "nav.invoices",
            "nav.reports",
        )

        for index, key in enumerate(navigation_keys):
            active = index == 0
            button = ctk.CTkButton(
                mini_sidebar,
                text=translate(key, self._language),
                height=32,
                fg_color=BG_NAV_ACTIVE if active else "transparent",
                hover_color=BG_NAV_HOVER,
                text_color=NAV_TEXT_ACTIVE if active else NAV_TEXT,
                font=FONT_SHELL_BODY,
                anchor="w",
                corner_radius=7,
            )
            button.pack(
                fill="x",
                padx=SPACING_SM,
                pady=2,
            )
            self._brand_nav_labels.append((button, key))

        mini_workspace = ctk.CTkFrame(
            shell_section,
            fg_color=BG_CONTENT,
            corner_radius=0,
        )
        mini_workspace.pack(
            side="right",
            fill="both",
            expand=True,
        )

        mini_topbar = ctk.CTkFrame(
            mini_workspace,
            height=SHELL_TOPBAR_HEIGHT,
            fg_color=BG_TOPBAR,
            corner_radius=0,
        )
        mini_topbar.pack(fill="x")
        mini_topbar.pack_propagate(False)

        store_label = ctk.CTkLabel(
            mini_topbar,
            text="CyberHub Hà Nội",
            text_color=TEXT_PRIMARY,
            font=FONT_SHELL_BODY_STRONG,
        )
        store_label.pack(
            side="left",
            padx=SPACING_MD,
            pady=SPACING_SM,
        )

        search_preview = ctk.CTkEntry(
            mini_topbar,
            width=260,
            height=30,
            fg_color=BG_INPUT,
            border_color=BORDER,
            placeholder_text=translate(
                "header.search_placeholder",
                self._language,
            ),
            font=FONT_SHELL_CAPTION,
        )
        search_preview.pack(
            side="right",
            padx=SPACING_MD,
            pady=SPACING_SM,
        )
        self._brand_search_preview = search_preview

        card_grid = ctk.CTkFrame(
            mini_workspace,
            fg_color="transparent",
        )
        card_grid.pack(
            fill="both",
            expand=True,
            padx=SHELL_CONTENT_PADDING,
            pady=SHELL_CONTENT_PADDING,
        )

        for column, (label, value, color) in enumerate(
            (
                ("TỔNG SỐ MÁY", "20", TEXT_PRIMARY),
                ("MÁY TRỐNG", "12", BRAND_PRIMARY),
                ("ĐANG SỬ DỤNG", "6", DANGER),
            )
        ):
            card_grid.grid_columnconfigure(column, weight=1)
            card = ctk.CTkFrame(
                card_grid,
                fg_color=BG_CARD,
                corner_radius=8,
                border_width=1,
                border_color=BORDER,
            )
            card.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=SPACING_SM,
            )

            ctk.CTkLabel(
                card,
                text=label,
                text_color=TEXT_MUTED,
                font=FONT_SHELL_CAPTION,
            ).pack(anchor="w", padx=SPACING_MD, pady=(SPACING_MD, 2))

            ctk.CTkLabel(
                card,
                text=value,
                text_color=color,
                font=FONT_SHELL_SECTION,
            ).pack(anchor="w", padx=SPACING_MD, pady=(0, SPACING_MD))

        palette_section = ctk.CTkFrame(
            frame,
            fg_color=BG_SURFACE,
            corner_radius=12,
            border_width=1,
            border_color=BORDER,
        )
        palette_section.grid(
            row=3,
            column=0,
            sticky="ew",
            pady=(0, SPACING_SM),
        )

        ctk.CTkLabel(
            palette_section,
            text="Unified App Shell palette",
            text_color=TEXT_PRIMARY,
            font=FONT_TITLE_MD,
            anchor="w",
        ).pack(
            fill="x",
            padx=PADDING_CONTENT,
            pady=(SPACING_LG, SPACING_MD),
        )

        palette_grid = ctk.CTkFrame(
            palette_section,
            fg_color="transparent",
        )
        palette_grid.pack(
            fill="x",
            padx=PADDING_CONTENT,
            pady=(0, PADDING_CONTENT),
        )

        palette = (
            ("BG_TOPBAR", BG_TOPBAR),
            ("BG_CONTENT", BG_CONTENT),
            ("BG_CARD", BG_CARD),
            ("BG_INPUT", BG_INPUT),
            ("NAV_ACTIVE", BG_NAV_ACTIVE),
            ("BRAND", BRAND_PRIMARY),
        )

        for column, (name, color) in enumerate(palette):
            palette_grid.grid_columnconfigure(column, weight=1)
            swatch = ctk.CTkFrame(
                palette_grid,
                height=72,
                fg_color=color,
                corner_radius=8,
                border_width=1,
                border_color=BORDER,
            )
            swatch.grid(
                row=0,
                column=column,
                sticky="ew",
                padx=SPACING_SM,
            )
            swatch.grid_propagate(False)

            ctk.CTkLabel(
                swatch,
                text=f"{name}\n{color}",
                text_color=(
                    BG_CONTENT
                    if color == BRAND_PRIMARY
                    else TEXT_PRIMARY
                ),
                font=FONT_SHELL_CAPTION,
            ).place(relx=0.5, rely=0.5, anchor="center")

        geometry_text = (
            f"Reference geometry: sidebar {SHELL_SIDEBAR_WIDTH}px · "
            f"topbar {SHELL_TOPBAR_HEIGHT}px · "
            f"status bar {SHELL_STATUSBAR_HEIGHT}px · "
            f"content padding {SHELL_CONTENT_PADDING}px"
        )
        ctk.CTkLabel(
            frame,
            text=geometry_text,
            text_color=TEXT_SECONDARY,
            font=FONT_SHELL_CAPTION,
            anchor="w",
        ).grid(
            row=4,
            column=0,
            sticky="ew",
            pady=(0, SPACING_SM),
        )

        return frame

    def _on_brand_language_changed(self, selected: str) -> None:
        self._language = normalize_language(selected.lower())

        self._brand_preview_title.configure(
            text=translate("app.name", self._language)
        )
        self._brand_preview_status.configure(
            text=f"● {translate('status.ready', self._language)}"
        )
        self._brand_search_preview.configure(
            placeholder_text=translate(
                "header.search_placeholder",
                self._language,
            )
        )

        for button, key in self._brand_nav_labels:
            button.configure(text=translate(key, self._language))

    # --------------------------------------------------------------------------
    # TAB 1: MACHINE CARDS
    # --------------------------------------------------------------------------
    def _create_tab_machine_cards(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._content_container, fg_color="transparent")

        title = ctk.CTkLabel(
            frame,
            text="Machine Cards — Component trung tâm Dashboard",
            font=FONT_TITLE_LG,
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        title.pack(fill="x", pady=(0, 4))

        desc = ctk.CTkLabel(
            frame,
            text="Dữ liệu nạp từ Mock Services chung (LI-02). Hỗ trợ đổi kịch bản Mock (SUCCESS / EMPTY / CONFLICT / UNAVAILABLE) "
                "và đổi vai trò STAFF ↔ MANAGER để kiểm tra quyền và luồng nghiệp vụ. Nút 'Bật lại' chỉ mở cho MANAGER.",
            font=FONT_BODY,
            text_color=TEXT_SECONDARY,
            anchor="w",
            wraplength=980,
            justify="left",
        )
        desc.pack(fill="x", pady=(0, SPACING_LG))

        self._machines_grid = ctk.CTkFrame(frame, fg_color="transparent")
        self._machines_grid.pack(fill="both", expand=True)
        self._machines_grid.columnconfigure(0, weight=1)
        self._machines_grid.columnconfigure(1, weight=1)

        self._render_machine_cards()
        return frame

    def _render_machine_cards(self) -> None:
        for widget in self._machines_grid.winfo_children():
            widget.destroy()
        self._machine_cards.clear()

        try:
            machines = self._services.machines.list_machines(store_id=1)
        except ApplicationError as err:
            logger.warning("Failed to load machines: %s (code=%s)", err, getattr(err, "code", None))
            error_msg = get_user_friendly_error(err)
            err_box = ctk.CTkFrame(self._machines_grid, fg_color="transparent")
            err_box.pack(pady=SPACING_XL)
            ctk.CTkLabel(
                err_box,
                text=f"⚠ Error loading machines: {error_msg}",
                font=FONT_BODY_STRONG,
                text_color=DANGER,
            ).pack(pady=(0, SPACING_SM))
            ActionButton(err_box, text="Retry", kind="primary", command=self._render_machine_cards).pack()
            return

        if not machines:
            ctk.CTkLabel(
                self._machines_grid,
                text="No machines available in this scenario (EMPTY)",
                font=FONT_BODY,
                text_color=TEXT_MUTED,
            ).pack(pady=SPACING_XL)
            return

        # Render tối đa 4 máy mẫu (PC01, PC02, PC03, PC05)
        for idx, m in enumerate(machines[:4]):
            col = idx % 2
            row = idx // 2
            card = MachineCard(
                self._machines_grid,
                machine=m,
                actor=self._current_actor,
                on_open=self._handle_card_open,
                on_checkout=self._handle_card_checkout,
                on_maintenance=self._handle_card_maintenance,
                width=320,
                height=195,
            )
            card.grid(row=row, column=col, padx=SPACING_MD, pady=SPACING_MD, sticky="nsew")
            self._machine_cards.append(card)

    def _handle_card_open(self, machine_id: int) -> None:
        try:
            session = self._services.sessions.open_session(
                customer_id=1,
                machine_id=machine_id,
                actor=self._current_actor,
            )
            ToastManager.show(self, f"Session opened: {session.session_code} on Machine ID={machine_id}", kind="success")
            self._render_machine_cards()
        except ApplicationError as err:
            logger.warning(
                "Failed to open session for machine %s: %s (code=%s)",
                machine_id, err, getattr(err, "code", None),
            )
            err_msg = get_user_friendly_error(err)
            if getattr(err, "code", None) == "CONFLICT":
                ConfirmDialog.alert(
                    self,
                    title="Conflict Warning",
                    message=f"Open session failed: {err_msg}",
                    is_danger=True,
                )
                self._render_machine_cards()
            else:
                ToastManager.show(
                    self, f"Open session failed: {err_msg}", kind="error"
                )

    def _handle_card_checkout(self, machine_id: int) -> None:
        try:
            # Lấy mốc thời gian hiện tại từ mock clock nếu có, fallback về now UTC
            clock = getattr(getattr(self._services, "sessions", None), "_clock", None)
            now = clock.now() if clock else datetime.now(timezone.utc)
            preview = self._services.sessions.preview_checkout(
                machine_id=machine_id,
                current_time=now,
            )
            msg = (
                f"End session for Machine ID={machine_id}?\n"
                f"Usage cost: {format_money(preview.usage_cost)}"
            )
            if preview.settlement_required > 0:
                msg += f"\nSettlement required: {format_money(preview.settlement_required)}"

            confirmed = ConfirmDialog.ask(
                self,
                title="Confirm Checkout",
                message=msg,
                confirm_label="Checkout",
                is_danger=True,
            )
            if confirmed:
                settlement = preview.settlement_required
                method = PaymentMethod.CASH if settlement > 0 else None
                self._services.sessions.complete_checkout(
                    machine_id=machine_id,
                    actor=self._current_actor,
                    settlement_amount=settlement,
                    method=method,
                )
                ToastManager.show(self, f"Checkout completed for Machine ID={machine_id}", kind="success")
                self._render_machine_cards()
            else:
                ToastManager.show(self, "Checkout cancelled", kind="info")
        except ApplicationError as err:
            logger.warning("Failed to checkout machine %s: %s (code=%s)", machine_id, err, getattr(err, "code", None))
            err_msg = get_user_friendly_error(err)
            ConfirmDialog.alert(self, title="Checkout Error", message=f"Checkout failed: {err_msg}", is_danger=True)
            ToastManager.show(self, f"Checkout failed: {err_msg}", kind="error")

    def _handle_card_maintenance(self, machine_id: int) -> None:
        """Thực hiện thao tác kết thúc bảo trì (Bật lại máy) qua ServiceBundle theo quyền P0."""
        if not ConfirmDialog.ask(
            self,
            title = "End Maintenance",
            message = f"Are you sure you want to end maintenance for Machine ID={machine_id}?",
            confirm_label = "End Maintenance",
            cancel_label = "Cancel",
        ):
            return
        try:
            self._services.machines.set_maintenance(
                machine_id=machine_id,
                enabled=False,
                actor=self._current_actor,
            )
            ToastManager.show(
                self,
                f"Maintenance ended for Machine ID={machine_id}. Machine is now available.",
                kind="success",
            )
            self._render_machine_cards()
        except ApplicationError as err:
            logger.warning("Failed maintenance action for machine %s: %s (code=%s)", machine_id, err, getattr(err, "code", None))
            err_msg = get_user_friendly_error(err)
            title = "Permission Denied" if getattr(err, "code", None) == "PERMISSION_DENIED" else "Maintenance Error"
            ConfirmDialog.alert(self, title=title, message=f"Maintenance action failed: {err_msg}", is_danger=True)
            ToastManager.show(self, f"Maintenance action failed: {err_msg}", kind="error")

    # --------------------------------------------------------------------------
    # TAB 2: BUTTONS & INPUTS
    # --------------------------------------------------------------------------
    def _create_tab_buttons_inputs(self) -> ctk.CTkFrame:
        frame = ctk.CTkScrollableFrame(self._content_container, fg_color="transparent")

        title = ctk.CTkLabel(frame, text="ActionButton & FormField", font=FONT_TITLE_LG, text_color=TEXT_PRIMARY, anchor="w")
        title.pack(fill="x", pady=(0, SPACING_LG))

        # Nhóm Buttons
        btn_section = ctk.CTkFrame(frame, fg_color=BG_SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
        btn_section.pack(fill="x", pady=(0, SPACING_LG), padx=2)

        btn_title = ctk.CTkLabel(btn_section, text="Các kiểu ActionButton (Hover / Normal / Busy chống double-click / Disabled)", font=FONT_TITLE_MD, text_color=TEXT_PRIMARY, anchor="w")
        btn_title.pack(fill="x", padx=PADDING_CONTENT, pady=(SPACING_MD, SPACING_MD))

        btn_row = ctk.CTkFrame(btn_section, fg_color="transparent")
        btn_row.pack(fill="x", padx=PADDING_CONTENT, pady=(0, PADDING_CONTENT))

        b_prim = ActionButton(btn_row, text="Primary", kind="primary")
        b_prim.pack(side="left", padx=(0, SPACING_SM))

        b_sec = ActionButton(btn_row, text="Secondary", kind="secondary")
        b_sec.pack(side="left", padx=SPACING_SM)

        b_succ = ActionButton(btn_row, text="Success", kind="success")
        b_succ.pack(side="left", padx=SPACING_SM)

        b_dang = ActionButton(btn_row, text="Danger", kind="danger")
        b_dang.pack(side="left", padx=SPACING_SM)

        b_ghost = ActionButton(btn_row, text="Ghost", kind="ghost")
        b_ghost.pack(side="left", padx=SPACING_SM)

        b_dis = ActionButton(btn_row, text="Disabled", kind="secondary", state="disabled")
        b_dis.pack(side="left", padx=SPACING_SM)

        # Thử nút Busy
        self._test_busy_btn = ActionButton(
            btn_row,
            text="Bấm để thử Busy",
            kind="primary",
            command=self._trigger_busy_demo,
        )
        self._test_busy_btn.pack(side="left", padx=(SPACING_LG, 0))

        # Nhóm Inputs & Demo Form Validation
        input_section = ctk.CTkFrame(frame, fg_color=BG_SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
        input_section.pack(fill="x", pady=(0, SPACING_LG), padx=2)

        input_title = ctk.CTkLabel(
            input_section,
            text="Demo FormField & Validation qua ServiceBundle (Tạo khách hàng)",
            font=FONT_TITLE_MD,
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        input_title.pack(fill="x", padx=PADDING_CONTENT, pady=(SPACING_MD, 4))

        input_desc = ctk.CTkLabel(
            input_section,
            text="Form kết nối trực tiếp với ServiceBundle. Đổi sang kịch bản VALIDATION_ERROR để xem hiển thị lỗi từng trường "
                "(Phone/Password) và Toast tiếng Anh; đổi sang CONFLICT để xem báo trùng số điện thoại; đổi sang SUCCESS để tạo thành công.",
            font=FONT_BODY,
            text_color=TEXT_SECONDARY,
            anchor="w",
            wraplength=980,
            justify="left",
        )
        input_desc.pack(fill="x", padx=PADDING_CONTENT, pady=(0, SPACING_MD))

        inputs_box = ctk.CTkFrame(input_section, fg_color="transparent")
        inputs_box.pack(fill="x", padx=PADDING_CONTENT, pady=(0, PADDING_CONTENT))

        self._f_name = FormField(inputs_box, label="Họ và tên", placeholder="Nhập họ và tên…", initial_value="Nguyễn Văn An")
        self._f_name.pack(fill="x", pady=(0, SPACING_MD))

        self._f_phone = FormField(inputs_box, label="Số điện thoại", placeholder="Nhập số điện thoại 10 số (bắt đầu bằng 0)…", initial_value="0912345678")
        self._f_phone.pack(fill="x", pady=(0, SPACING_MD))
        self._f_err = self._f_phone  # Giữ alias cho tương thích ngược

        self._f_user = FormField(inputs_box, label="Tên đăng nhập", placeholder="Nhập tên đăng nhập…", initial_value="an.nv")
        self._f_user.pack(fill="x", pady=(0, SPACING_MD))

        self._f_pass = FormField(inputs_box, label="Mật khẩu (Có nút Hiện / Ẩn)", is_password=True, initial_value="matkhau123")
        self._f_pass.pack(fill="x", pady=(0, SPACING_MD))

        # Điều hướng bàn phím: Gắn sự kiện Enter trên các trường để submit form
        for field in (self._f_name, self._f_phone, self._f_user, self._f_pass):
            field.bind_return(self._handle_submit_customer_demo)

        # Hàng nút thao tác Form
        form_btn_row = ctk.CTkFrame(inputs_box, fg_color="transparent")
        form_btn_row.pack(fill="x", pady=(SPACING_SM, 0))

        self._btn_submit_demo = ActionButton(
            form_btn_row,
            text="Tạo khách hàng (Submit Demo)",
            kind="primary",
            width=220,
            command=self._handle_submit_customer_demo,
        )
        self._btn_submit_demo.pack(side="left", padx=(0, SPACING_SM))

        toggle_err_btn = ActionButton(
            form_btn_row,
            text="Bật/Tắt lỗi ở ô SĐT",
            kind="secondary",
            width=160,
            command=self._toggle_input_error,
        )
        toggle_err_btn.pack(side="left", padx=SPACING_SM)

        clear_err_btn = ActionButton(
            form_btn_row,
            text="Xóa thông báo lỗi",
            kind="ghost",
            width=140,
            command=self._clear_form_errors,
        )
        clear_err_btn.pack(side="left", padx=SPACING_SM)

        return frame

    def _trigger_busy_demo(self) -> None:
        """Mô phỏng tác vụ mạng bất đồng bộ 1.5 giây với nút bấm chuyển trạng thái busy."""
        self._test_busy_btn.set_busy(True)
        ToastManager.show(self, "Processing request...", kind="info")
        self.after(1500, lambda: [
            self._test_busy_btn.set_busy(False),
            ToastManager.show(self, "Task completed successfully!", kind="success")
        ])

    def _handle_submit_customer_demo(self) -> None:
        """Thử nghiệm submit form gọi create_customer qua ServiceBundle.

        Hỗ trợ kiểm chứng MockScenario.VALIDATION_ERROR (báo lỗi trường phone/password),
        MockScenario.CONFLICT (báo lỗi trùng phone), và MockScenario.SUCCESS.
        Sau lỗi: giữ nguyên dữ liệu người dùng đã nhập, trả nút về is_busy=False trong finally.
        """
        if getattr(self._btn_submit_demo, "is_busy", False):
            return

        self._clear_form_errors()
        self._btn_submit_demo.set_busy(True)

        name = self._f_name.get_value()
        phone = self._f_phone.get_value()
        username = self._f_user.get_value()
        password = self._f_pass.get_value()

        try:
            cust = self._services.customers.create_customer(
                full_name=name,
                phone=phone,
                username=username,
                password=password,
            )
            ToastManager.show(
                self,
                f"Customer created successfully: {cust.code} ({cust.full_name})",
                kind="success",
            )
        except ApplicationError as err:
            logger.warning(
                "Submit customer demo failed: %s (code=%s, fields=%s)",
                err,
                getattr(err, "code", None),
                getattr(err, "field_errors", None),
            )
            safe_field_errors = get_field_errors_safe(err)
            if "phone" in safe_field_errors:
                self._f_phone.set_error(safe_field_errors["phone"])
            if "password" in safe_field_errors:
                self._f_pass.set_error(safe_field_errors["password"])
            if "full_name" in safe_field_errors:
                self._f_name.set_error(safe_field_errors["full_name"])
            if "username" in safe_field_errors:
                self._f_user.set_error(safe_field_errors["username"])

            general_msg = get_user_friendly_error(err)
            is_conflict = (
                getattr(err, "code", None) == "CONFLICT" or isinstance(err, ConflictError)
            )
            if is_conflict and not safe_field_errors:
                # Nếu là lỗi trùng số điện thoại nhưng không có field_errors, hiển thị alert
                ConfirmDialog.alert(
                    self,
                    title="Conflict Warning",
                    message=f"Operation conflict: {general_msg}",
                    is_danger=True,
                )
            else:
                ToastManager.show(self, general_msg, kind = 'error')
        finally:
            self._btn_submit_demo.set_busy(False)

    def _clear_form_errors(self) -> None:
        self._f_name.set_error(None)
        self._f_phone.set_error(None)
        self._f_user.set_error(None)
        self._f_pass.set_error(None)

    def _toggle_input_error(self) -> None:
        if self._f_phone._error_label.winfo_ismapped():
            self._f_phone.set_error(None)
        else:
            self._f_phone.set_error("Phone number must have 10 digits")

    # --------------------------------------------------------------------------
    # TAB 3: DATA TABLE
    # --------------------------------------------------------------------------
    def _create_tab_data_table(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._content_container, fg_color="transparent")

        title = ctk.CTkLabel(frame, text="DataTable & ViewState", font=FONT_TITLE_LG, text_color=TEXT_PRIMARY, anchor="w")
        title.pack(fill="x", pady=(0, 4))

        desc = ctk.CTkLabel(
            frame,
            text="Dữ liệu nạp từ Mock CustomerService. Hỗ trợ 4 trạng thái ViewState: READY, LOADING, EMPTY, ERROR. "
                "Đổi Scenario ở header hoặc dùng các nút chuyển trạng thái bên dưới để kiểm tra.",
            font=FONT_BODY,
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        desc.pack(fill="x", pady=(0, SPACING_MD))

        # Thanh nút chuyển trạng thái
        toolbar = ctk.CTkFrame(frame, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, SPACING_SM))

        btn_ready = ActionButton(toolbar, text="Load Mock Data", kind="primary", width=140, command=self._load_table_data)
        btn_ready.pack(side="left", padx=(0, SPACING_SM))

        btn_loading = ActionButton(toolbar, text="State: LOADING", kind="secondary", width=130, command=self._set_table_loading)
        btn_loading.pack(side="left", padx=SPACING_SM)

        btn_empty = ActionButton(toolbar, text="State: EMPTY", kind="secondary", width=120, command=self._set_table_empty)
        btn_empty.pack(side="left", padx=SPACING_SM)

        btn_error = ActionButton(toolbar, text="State: ERROR", kind="secondary", width=120, command=self._set_table_error)
        btn_error.pack(side="left", padx=SPACING_SM)

        # Cột bảng
        self._table_columns = [
            TableColumn(key="code", label="Mã KH", width=90),
            TableColumn(key="name", label="Họ và tên", width=160),
            TableColumn(key="phone", label="Số điện thoại", width=120),
            TableColumn(key="username", label="Tài khoản", width=120),
            TableColumn(key="balance", label="Số dư", align="right", width=130),
            TableColumn(key="cust_status", label="Trạng thái KH", align="center", width=140),
            TableColumn(key="acc_status", label="Trạng thái TK", align="center", width=130),
        ]

        self._table_rows: list[TableRow] = []
        self._table = DataTable(
            frame,
            columns=self._table_columns,
            rows=self._table_rows,
            on_select=self._on_table_row_select,
        )
        self._table.pack(fill="both", expand=True)

        self._load_table_data()
        return frame

    def _load_table_data(self) -> None:
        self._table.set_state(ViewState.LOADING, message="Loading data…")
        try:
            customers = self._services.customers.search_customers("")
            if not customers:
                self._table.set_state(ViewState.EMPTY, message="No matching data found")
                return
            rows = [
                TableRow(
                    key=c.customer_id,
                    cells={
                        "code": c.customer_code,
                        "name": c.full_name,
                        "phone": c.phone,
                        "username": c.username,
                        "balance": format_money(c.balance),
                        "cust_status": "● Hoạt động" if c.customer_status == CustomerStatus.ACTIVE else "○ Ngừng HĐ",
                        "acc_status": "● Hoạt động" if c.account_status == AccountStatus.ACTIVE else "🔒 Đã khóa",
                    },
                )
                for c in customers
            ]
            self._table_rows = rows
            self._table.set_rows(rows)
        except ApplicationError as err:
            logger.warning("Failed to load customer table data: %s (code=%s)", err, getattr(err, "code", None))
            error_msg = get_user_friendly_error(err)
            self._table.set_state(
                ViewState.ERROR,
                message=f"Unable to load data ({error_msg})",
                on_retry=self._load_table_data,
            )

    def _set_table_loading(self) -> None:
        self._table.set_state(ViewState.LOADING, message="Loading data…")

    def _set_table_empty(self) -> None:
        self._table.set_state(ViewState.EMPTY, message="No matching data found")

    def _set_table_error(self) -> None:
        self._table.set_state(
            ViewState.ERROR,
            message="Unable to load data",
            on_retry=self._load_table_data,
        )

    def _on_table_row_select(self, row_key: int | str) -> None:
        ToastManager.show(self, f"Selected customer ID: {row_key}", kind="info")

    # --------------------------------------------------------------------------
    # TAB 4: BADGES & FEEDBACK
    # --------------------------------------------------------------------------
    def _create_tab_badges_feedback(self) -> ctk.CTkFrame:
        frame = ctk.CTkScrollableFrame(self._content_container, fg_color="transparent")

        title = ctk.CTkLabel(frame, text="StatusBadge, Toast & ConfirmDialog", font=FONT_TITLE_LG, text_color=TEXT_PRIMARY, anchor="w")
        title.pack(fill="x", pady=(0, SPACING_LG))

        # StatusBadges section
        badge_sec = ctk.CTkFrame(frame, fg_color=BG_SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
        badge_sec.pack(fill="x", pady=(0, SPACING_LG), padx=2)

        badge_title = ctk.CTkLabel(badge_sec, text="Toàn bộ các biến thể StatusBadge (Có chữ + Icon + Màu token)", font=FONT_TITLE_MD, text_color=TEXT_PRIMARY, anchor="w")
        badge_title.pack(fill="x", padx=PADDING_CONTENT, pady=(SPACING_MD, SPACING_MD))

        # Dùng lưới 2 hàng x 5 cột để tránh bị tràn/cắt trên màn hình 1280x720 hoặc DPI cao
        b_grid = ctk.CTkFrame(badge_sec, fg_color="transparent")
        b_grid.pack(fill="x", padx=PADDING_CONTENT, pady=(0, PADDING_CONTENT))

        badges_to_show = [
            ("Máy trống", MachineStatus.AVAILABLE),
            ("Máy đang dùng", MachineStatus.IN_USE),
            ("Máy bảo trì", MachineStatus.MAINTENANCE),
            ("Khách hoạt động", CustomerStatus.ACTIVE),
            ("Khách ngừng HĐ", CustomerStatus.INACTIVE),
            ("TK Đã khóa", AccountStatus.LOCKED),
            ("Phiên hoàn thành", SessionStatus.COMPLETED),
            ("Hóa đơn đã trả", InvoiceStatus.PAID),
            ("Role Manager", Role.MANAGER),
            ("Role Staff", Role.STAFF),
        ]

        for idx, (lbl_txt, status_val) in enumerate(badges_to_show):
            row = idx // 5
            col = idx % 5
            box = ctk.CTkFrame(b_grid, fg_color="transparent")
            box.grid(row=row, column=col, padx=SPACING_SM, pady=SPACING_SM, sticky="w")

            t_lbl = ctk.CTkLabel(box, text=lbl_txt, font=FONT_CAPTION, text_color=TEXT_MUTED)
            t_lbl.pack(anchor="w")

            bdg = StatusBadge(box, status=status_val)
            bdg.pack(pady=(4, 0), anchor="w")

        # Feedback & Dialogs section
        dlg_sec = ctk.CTkFrame(frame, fg_color=BG_SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
        dlg_sec.pack(fill="x", pady=(0, SPACING_LG), padx=2)

        dlg_title = ctk.CTkLabel(dlg_sec, text="Thử nghiệm ToastManager & ConfirmDialog", font=FONT_TITLE_MD, text_color=TEXT_PRIMARY, anchor="w")
        dlg_title.pack(fill="x", padx=PADDING_CONTENT, pady=(SPACING_MD, SPACING_MD))

        dlg_row = ctk.CTkFrame(dlg_sec, fg_color="transparent")
        dlg_row.pack(fill="x", padx=PADDING_CONTENT, pady=(0, PADDING_CONTENT))

        t_info = ActionButton(dlg_row, text="Toast Info", kind="secondary", width=110, command=lambda: ToastManager.show(self, "System update notification", kind="info"))
        t_info.pack(side="left", padx=(0, SPACING_SM))

        t_succ = ActionButton(dlg_row, text="Toast Success", kind="success", width=120, command=lambda: ToastManager.show(self, "Top-up 50,000 VND successfully!", kind="success"))
        t_succ.pack(side="left", padx=SPACING_SM)

        t_warn = ActionButton(dlg_row, text="Toast Warning", kind="secondary", width=120, command=lambda: ToastManager.show(self, "Machine PC02 low balance warning!", kind="warning"))
        t_warn.pack(side="left", padx=SPACING_SM)

        t_err = ActionButton(dlg_row, text="Toast Error", kind="danger", width=110, command=lambda: ToastManager.show(self, "Server connection failed!", kind="error"))
        t_err.pack(side="left", padx=SPACING_SM)

        dlg_btn = ActionButton(
            dlg_row,
            text="Open Confirm Dialog",
            kind="primary",
            width=160,
            command=self._test_confirm_dialog,
        )
        dlg_btn.pack(side="left", padx=(SPACING_XL, 0))

        warn_btn = ActionButton(
            dlg_row,
            text="Open Warning Dialog",
            kind="danger",
            width=160,
            command=self._test_warning_dialog,
        )
        warn_btn.pack(side="left", padx=SPACING_SM)

        return frame

    def _test_confirm_dialog(self) -> None:
        confirmed = ConfirmDialog.ask(
            self,
            title="Confirm Action",
            message="Are you sure you want to perform this action? This operation will be logged.",
            confirm_label="Confirm",
            cancel_label="Cancel",
            is_danger=True,
        )
        if confirmed:
            ToastManager.show(self, "Action confirmed", kind="success")
        else:
            ToastManager.show(self, "Action cancelled", kind="info")

    def _test_warning_dialog(self) -> None:
        ConfirmDialog.alert(
            self,
            title="Conflict Warning",
            message="Operation conflict: Another transaction or update may have occurred. Please review and try again.",
            button_label="Close",
            is_danger=True,
        )


def main() -> None:
    app = ComponentGalleryApp()
    app.mainloop()


if __name__ == "__main__":
    main()
