"""NG-02 — Ngát: App Shell theo Stitch export (sidebar 220 px + topbar 52 px).

Quy định:
- Bố cục/màu: Stitch export (code.html, DESIGN.md) — token STITCH_* trong theme.py.
- Phân quyền menu, đăng xuất an toàn: docs/diagrams/ui_wireflow.md mục 3 và 4.4.
- Nhận ServiceBundle từ ngoài, quyền theo role: docs/07_DTO_UI_HANDOFF.md mục 5 và 8.

Shell không import repository/database và không tự khởi tạo service.
Login (HA-11) do composition root xử lý thông qua callback `on_logout`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

import customtkinter as ctk
from PIL import Image

from ..domain.dtos import EmployeeSession
from ..services.contracts import ServiceBundle
from .components import ConfirmDialog, ToastManager
from .i18n import Language, normalize_language, translate
from .messages import MSG_CANCEL, MSG_OPERATION_FAILED, get_user_friendly_error
from .navigation import DEFAULT_NAV_KEY, NavKey, can_access, get_nav_item, visible_nav_items
from .theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_BRAND,
    FONT_ST_MONO_BODY,
    FONT_ST_MONO_SM,
    FONT_ST_MONO_XS,
    FONT_ST_MONO_XS_STRONG,
    FONT_ST_PAGE_TITLE,
    STITCH_AVATAR_BG,
    STITCH_BG_CANVAS,
    STITCH_BG_CHROME,
    STITCH_BG_CHROME_FOOT,
    STITCH_BORDER,
    STITCH_BRAND_HEIGHT,
    STITCH_CHIP_BG,
    STITCH_CHIP_BORDER,
    STITCH_CONTENT_PADX,
    STITCH_CONTENT_PADY,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_DANGER_HOVER_BG,
    STITCH_INPUT_BG,
    STITCH_INPUT_BORDER,
    STITCH_NAV_ACTIVE_BG,
    STITCH_NAV_ACTIVE_BORDER,
    STITCH_NAV_HOVER,
    STITCH_NAV_ITEM_HEIGHT,
    STITCH_RADIUS,
    STITCH_RADIUS_LG,
    STITCH_SIDEBAR_WIDTH,
    STITCH_SUCCESS,
    STITCH_TEXT,
    STITCH_TEXT_DIM,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_ON_CYAN,
    STITCH_TEXT_STRONG,
    STITCH_TOPBAR_HEIGHT,
)

logger = logging.getLogger(__name__)

LOGOUT_TITLE = "Confirm Logout"
LOGOUT_MESSAGE = "Are you sure you want to log out?"
LOGOUT_CONFIRM_LABEL = "Log out"

# Vùng đầu bò trong cyberhub_logo_dark.png (bỏ phần chữ bên phải).
_LOGO_ICON_BOX = (50, 50, 930, 750)
_LOGO_ICON_HEIGHT = 36


# ----------------------------------------------------------------------
# Hàm thuần (test được không cần Tk)
# ----------------------------------------------------------------------
def initials(full_name: str) -> str:
    """'Nguyễn Tuấn Kiệt' -> 'TK'; 'An' -> 'AN'; '' -> '?'."""
    words = full_name.split()
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[-2][0] + words[-1][0]).upper()


def role_label(session: EmployeeSession, language: Language) -> str:
    """Nhãn role in hoa, ví dụ 'QUẢN LÝ' / 'MANAGER'."""
    return translate(f"role.{session.role.value.lower()}", language).upper()


# ----------------------------------------------------------------------
# Giao kèo giữa shell và view nghiệp vụ
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ViewContext:
    """Những gì một view nghiệp vụ được nhận từ shell."""

    services: ServiceBundle
    session: EmployeeSession
    language: Language
    navigate: Callable[[NavKey], bool]


ViewFactory = Callable[[Any, ViewContext], ctk.CTkFrame]
"""Hàm tạo view: nhận (parent, context), trả về một CTkFrame CHƯA pack/grid.

View có thể khai báo thêm (không bắt buộc):
- shutdown(): hủy after/refresh trước khi bị destroy.
- handle_search(text: str): nhận từ khóa từ ô tìm kiếm trên topbar.
"""


class PlaceholderView(ctk.CTkFrame):
    """Màn tạm cho các view chưa được triển khai (NG-03, NG-04, NG-07...)."""

    def __init__(self, master: Any, title: str, language: Language) -> None:
        super().__init__(master, fg_color="transparent")
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x")
        ctk.CTkLabel(
            header,
            text=title,
            font=FONT_ST_PAGE_TITLE,
            text_color=STITCH_TEXT_STRONG,
        ).pack(side="left")
        ctk.CTkLabel(
            header,
            text=translate("view.placeholder_title", language),
            font=FONT_ST_MONO_BODY,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left", padx=(10, 0), pady=(4, 0))
        ctk.CTkLabel(
            self,
            text=translate("view.placeholder_message", language),
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", pady=(10, 0))


def placeholder_factory(nav_key: NavKey) -> ViewFactory:
    """Tạo factory hiển thị PlaceholderView cho một mục menu."""

    def build(parent: Any, context: ViewContext) -> ctk.CTkFrame:
        title = translate(get_nav_item(nav_key).i18n_key, context.language)
        return PlaceholderView(parent, title, context.language)

    return build


def _load_logo_icon() -> ctk.CTkImage | None:
    """Cắt phần biểu tượng từ logo; lỗi thì trả None (sidebar chỉ hiện chữ)."""
    try:
        resource = files("cyberhub_manager.ui.assets").joinpath("cyberhub_logo_dark.png")
        with resource.open("rb") as stream:
            image = Image.open(stream).convert("RGBA").crop(_LOGO_ICON_BOX)
        width = round(image.width * _LOGO_ICON_HEIGHT / image.height)
        return ctk.CTkImage(light_image=image, dark_image=image, size=(width, _LOGO_ICON_HEIGHT))
    except Exception:
        logger.exception("Không tải được logo")
        return None


def _hline(master: Any) -> tk.Frame:
    """Đường kẻ ngang 1px. Dùng tk.Frame vì CTkFrame 1px không được vẽ ổn định."""
    return tk.Frame(master, height=1, bg=STITCH_BORDER, bd=0, highlightthickness=0)


def _vline(master: Any, height: int | None = None) -> tk.Frame:
    """Đường kẻ dọc 1px."""
    frame = tk.Frame(master, width=1, bg=STITCH_BORDER, bd=0, highlightthickness=0)
    if height is not None:
        frame.configure(height=height)
    return frame

class AppShell(ctk.CTkFrame):
    """Khung ứng dụng sau đăng nhập: sidebar | (topbar / content)."""

    def __init__(
        self,
        master: Any,
        services: ServiceBundle,
        session: EmployeeSession,
        *,
        on_logout: Callable[[], None],
        view_factories: Mapping[NavKey, ViewFactory] | None = None,
        language: str | None = None,
    ) -> None:
        super().__init__(master, fg_color=STITCH_BG_CANVAS, corner_radius=0)
        self._services = services
        self._session: EmployeeSession | None = session
        self._on_logout = on_logout
        self._factories: dict[NavKey, ViewFactory] = dict(view_factories or {})
        self._language: Language = normalize_language(language)

        self._nav_buttons: dict[NavKey, ctk.CTkButton] = {}
        self._lang_buttons: dict[Language, ctk.CTkButton] = {}
        self._current_key: NavKey | None = None
        self._current_view: ctk.CTkFrame | None = None
        self._is_closed = False
        self._logo_icon = _load_logo_icon()
        self._shortcut_ids: list[tuple[str, str]] = []

        self.grid_columnconfigure(0, weight=0)  # sidebar
        self.grid_columnconfigure(1, weight=0)  # đường kẻ dọc
        self.grid_columnconfigure(2, weight=1)  # main
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        _vline(self).grid(row=0, column=1, sticky="ns")
        self._build_main()
        self._apply_language()
        self._bind_shortcuts()
        self.navigate(DEFAULT_NAV_KEY)

    # ------------------------------------------------------------------
    # Thuộc tính công khai (dùng cho test và composition root)
    # ------------------------------------------------------------------
    @property
    def session(self) -> EmployeeSession | None:
        return self._session

    @property
    def current_key(self) -> NavKey | None:
        return self._current_key

    @property
    def current_view(self) -> ctk.CTkFrame | None:
        return self._current_view

    @property
    def nav_keys(self) -> tuple[NavKey, ...]:
        """Các menu đang hiển thị trên sidebar, theo thứ tự."""
        return tuple(self._nav_buttons)

    @property
    def language(self) -> Language:
        return self._language

    @property
    def search_enabled(self) -> bool:
        return self._search_entry.cget("state") == "normal"

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    def _build_sidebar(self) -> None:
        assert self._session is not None
        sidebar = ctk.CTkFrame(
            self, width=STITCH_SIDEBAR_WIDTH, fg_color=STITCH_BG_CHROME, corner_radius=0
        )
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.pack_propagate(False)

        # Logo + tên ứng dụng (cao 60 px, kẻ dưới).
        brand = ctk.CTkFrame(
            sidebar, height=STITCH_BRAND_HEIGHT, fg_color="transparent", corner_radius=0
        )
        brand.pack(fill="x")
        brand.pack_propagate(False)
        if self._logo_icon is not None:
            ctk.CTkLabel(brand, text="", image=self._logo_icon).pack(side="left", padx=(16, 12))
        brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        brand_text.pack(side="left", padx=(0 if self._logo_icon else 16, 0))
        name_row = ctk.CTkFrame(brand_text, fg_color="transparent")
        name_row.pack(anchor="w")
        ctk.CTkLabel(
            name_row, text="CyberHub", font=FONT_ST_BRAND, text_color=STITCH_TEXT_STRONG, height=18
        ).pack(side="left")
        ctk.CTkLabel(
            name_row, text="●", font=FONT_ST_MONO_XS, text_color=STITCH_CYAN, height=18
        ).pack(side="left", padx=(6, 0))
        ctk.CTkLabel(
            brand_text,
            text="MANAGER",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            height=14,
        ).pack(anchor="w")
        _hline(sidebar).pack(fill="x")

        # Khối trạng thái ở đáy (pack trước với side=bottom để luôn nằm dưới cùng).
        foot = ctk.CTkFrame(sidebar, fg_color=STITCH_BG_CHROME_FOOT, corner_radius=0)
        foot.pack(side="bottom", fill="x")
        _hline(sidebar).pack(side="bottom", fill="x")
        foot_row = ctk.CTkFrame(foot, fg_color="transparent")
        foot_row.pack(fill="x", padx=12, pady=10)
        self._status_label = ctk.CTkLabel(
            foot_row, text="", font=FONT_ST_MONO_SM, text_color=STITCH_SUCCESS, height=16
        )
        self._status_label.pack(side="left")
        ctk.CTkLabel(
            foot_row,
            text=self._session.store_code,
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            height=16,
        ).pack(side="right")

        # Menu điều hướng theo role.
        nav = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav.pack(fill="x", padx=12, pady=12)
        for item in visible_nav_items(self._session.role):
            button = ctk.CTkButton(
                nav,
                text="",
                height=STITCH_NAV_ITEM_HEIGHT,
                anchor="w",
                corner_radius=STITCH_RADIUS_LG,
                border_width=1,
                border_color=STITCH_BG_CHROME,
                fg_color=STITCH_BG_CHROME,
                hover_color=STITCH_NAV_HOVER,
                text_color=STITCH_TEXT_MUTED,
                font=FONT_ST_BODY,
                command=lambda key=item.key: self.navigate(key),
            )
            button.pack(fill="x", pady=2)
            self._nav_buttons[item.key] = button

    # ------------------------------------------------------------------
    # Main = topbar + content
    # ------------------------------------------------------------------
    def _build_main(self) -> None:
        main = ctk.CTkFrame(self, fg_color=STITCH_BG_CANVAS, corner_radius=0)
        main.grid(row=0, column=2, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        self._build_topbar(main)
        _hline(main).grid(row=1, column=0, sticky="ew")

        self._content = ctk.CTkFrame(main, fg_color=STITCH_BG_CANVAS, corner_radius=0)
        self._content.grid(row=2, column=0, sticky="nsew")

    def _build_topbar(self, parent: Any) -> None:
        assert self._session is not None
        session = self._session
        topbar = ctk.CTkFrame(
            parent, height=STITCH_TOPBAR_HEIGHT, fg_color=STITCH_BG_CHROME, corner_radius=0
        )
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.pack_propagate(False)

        # --- Trái: chip cửa hàng + mã cửa hàng ---
        chip = ctk.CTkFrame(
            topbar,
            fg_color=STITCH_CHIP_BG,
            border_width=1,
            border_color=STITCH_CHIP_BORDER,
            corner_radius=STITCH_RADIUS,
        )
        chip.pack(side="left", padx=(20, 12))
        ctk.CTkLabel(
            chip, text="⌂", font=FONT_ST_BODY_STRONG, text_color=STITCH_CYAN, height=24
        ).pack(side="left", padx=(10, 6), pady=2)
        ctk.CTkLabel(
            chip,
            text=session.store_name,
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT,
            height=24,
        ).pack(side="left", padx=(0, 10), pady=2)
        ctk.CTkLabel(
            topbar,
            text=f"•   {session.store_code}",
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left")

        # --- Phải (pack từ phải sang trái) ---
        self._logout_button = ctk.CTkButton(
            topbar,
            text="⇥",
            width=28,
            height=28,
            corner_radius=STITCH_RADIUS,
            fg_color="transparent",
            hover_color=STITCH_DANGER_HOVER_BG,
            text_color=STITCH_TEXT_MUTED,
            font=FONT_ST_BRAND,
            command=self._on_logout_clicked,
        )
        self._logout_button.pack(side="right", padx=(10, 20))
        self._logout_button.bind(
            "<Enter>", lambda _e: self._logout_button.configure(text_color=STITCH_DANGER)
        )
        self._logout_button.bind(
            "<Leave>", lambda _e: self._logout_button.configure(text_color=STITCH_TEXT_MUTED)
        )

        ctk.CTkLabel(
            topbar,
            text=initials(session.full_name),
            width=32,
            height=32,
            corner_radius=16,
            fg_color=STITCH_AVATAR_BG,
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT,
        ).pack(side="right")

        identity = ctk.CTkFrame(topbar, fg_color="transparent")
        identity.pack(side="right", padx=(10, 10))
        ctk.CTkLabel(
            identity,
            text=session.full_name,
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT,
            height=16,
        ).pack(anchor="e")
        self._role_label = ctk.CTkLabel(
            identity, text="", font=FONT_ST_MONO_XS_STRONG, text_color=STITCH_CYAN, height=14
        )
        self._role_label.pack(anchor="e")

        _vline(topbar, height=32).pack(side="right", padx=(6, 0))

        lang_box = ctk.CTkFrame(
            topbar,
            fg_color=STITCH_INPUT_BG,
            border_width=1,
            border_color=STITCH_CHIP_BORDER,
            corner_radius=6,
        )
        lang_box.pack(side="right", padx=(14, 8))
        for code in ("vi", "en"):
            button = ctk.CTkButton(
                lang_box,
                text=code.upper(),
                width=30,
                height=22,
                corner_radius=STITCH_RADIUS,
                font=FONT_ST_MONO_SM,
                command=lambda c=code: self.set_language(c),
            )
            button.pack(side="left", padx=2, pady=2)
            self._lang_buttons[code] = button

        self._search_entry = ctk.CTkEntry(
            topbar,
            width=192,
            height=32,
            corner_radius=6,
            fg_color=STITCH_INPUT_BG,
            border_color=STITCH_INPUT_BORDER,
            border_width=1,
            text_color=STITCH_TEXT,
            placeholder_text_color=STITCH_TEXT_DIM,
            font=FONT_ST_BODY,
        )
        self._search_entry.pack(side="right")
        self._search_entry.bind("<Return>", self._on_search_submitted)
    # ------------------------------------------------------------------
    # Điều hướng
    # ------------------------------------------------------------------
    def navigate(self, key: NavKey | str) -> bool:
        """Chuyển content sang màn `key`. Trả True nếu màn đó đang được hiển thị."""
        if self._is_closed or self._session is None:
            return False
        try:
            nav_key = NavKey(key)
        except ValueError:
            logger.warning("Bỏ qua navigation key không hợp lệ: %r", key)
            return False

        # Phòng thủ 2 lớp: menu đã ẩn, nhưng gọi navigate() trực tiếp cũng bị chặn.
        if not can_access(self._session.role, nav_key):
            ToastManager.show(self, get_user_friendly_error("PERMISSION_DENIED"), kind="warning")
            return False

        if nav_key == self._current_key and self._current_view is not None:
            return True

        context = ViewContext(
            services=self._services,
            session=self._session,
            language=self._language,
            navigate=self.navigate,
        )
        factory = self._factories.get(nav_key) or placeholder_factory(nav_key)
        try:
            new_view = factory(self._content, context)
        except Exception:
            # Không crash app, không lộ traceback; giữ nguyên màn đang mở.
            logger.exception("Không tạo được view %s", nav_key)
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")
            return False

        self._dispose_current_view()
        new_view.pack(fill="both", expand=True, padx=STITCH_CONTENT_PADX, pady=STITCH_CONTENT_PADY)
        self._current_view = new_view
        self._current_key = nav_key
        self._refresh_nav_styles()
        self._refresh_search_state()
        return True

    def _dispose_current_view(self) -> None:
        """Gọi shutdown() của view (nếu có) để hủy after/refresh, rồi destroy."""
        view = self._current_view
        self._current_view = None
        self._current_key = None
        if view is None:
            return
        shutdown = getattr(view, "shutdown", None)
        if callable(shutdown):
            try:
                shutdown()
            except Exception:
                logger.exception("Lỗi khi shutdown view")
        view.destroy()

    def _refresh_nav_styles(self) -> None:
        for key, button in self._nav_buttons.items():
            active = key == self._current_key
            button.configure(
                fg_color=STITCH_NAV_ACTIVE_BG if active else STITCH_BG_CHROME,
                hover_color=STITCH_NAV_ACTIVE_BG if active else STITCH_NAV_HOVER,
                border_color=STITCH_NAV_ACTIVE_BORDER if active else STITCH_BG_CHROME,
                text_color=STITCH_CYAN if active else STITCH_TEXT_MUTED,
                font=FONT_ST_BODY_STRONG if active else FONT_ST_BODY,
            )

    # ------------------------------------------------------------------
    # Tìm kiếm trên topbar: chỉ bật khi view hiện tại có handle_search()
    # ------------------------------------------------------------------
    def _refresh_search_state(self) -> None:
        supported = callable(getattr(self._current_view, "handle_search", None))
        self._search_entry.configure(state="normal")
        self._search_entry.delete(0, "end")
        # CTkEntry chỉ tự hiện lại placeholder khi mất focus; gán lại để hiện ngay.
        self._search_entry.configure(placeholder_text=translate("header.search_placeholder", self._language))
        if not supported:
            self._search_entry.configure(state="disabled")


    def _on_search_submitted(self, _event: Any = None) -> None:
        handler = getattr(self._current_view, "handle_search", None)
        if callable(handler):
            handler(self._search_entry.get().strip())

    # ------------------------------------------------------------------
    # Phím tắt (NG-08): Ctrl+F tìm kiếm, F5 làm mới, Esc xóa ô tìm kiếm, Ctrl+1..5 chuyển menu
    # ------------------------------------------------------------------
    def _bind_shortcuts(self) -> None:
        window = self.winfo_toplevel()
        specs = [
            ("<Control-f>", self.focus_search),
            ("<Control-F>", self.focus_search),
            ("<F5>", self.refresh_current_view),
        ]
        for index in range(1, 6):
            specs.append((f"<Control-Key-{index}>", lambda _e=None, i=index: self._navigate_by_index(i)))
        for sequence, handler in specs:
            funcid = window.bind(sequence, lambda event, h=handler: h(event), add="+")
            self._shortcut_ids.append((sequence, funcid))
        self._search_entry.bind("<Escape>", self.clear_search, add="+")

    def _unbind_shortcuts(self) -> None:
        try:
            window = self.winfo_toplevel()
            for sequence, funcid in self._shortcut_ids:
                window.unbind(sequence, funcid)
        except tk.TclError:
            pass  # cửa sổ đã đóng
        self._shortcut_ids.clear()

    def focus_search(self, _event: Any = None) -> str:
        """Ctrl+F: đưa con trỏ vào ô tìm kiếm trên topbar."""
        if not self._is_closed:
            self._search_entry.focus_set()
            self._search_entry.select_range(0, "end")
        return "break"

    def clear_search(self, _event: Any = None) -> str:
        """Esc trong ô tìm kiếm: xóa từ khóa và trả màn hiện tại về danh sách đầy đủ."""
        if self._search_entry.get():
            self._search_entry.delete(0, "end")
            self._on_search_submitted()
        return "break"

    def refresh_current_view(self, _event: Any = None) -> str:
        """F5: tải lại màn hiện tại (refresh(manual=True) của dashboard hoặc reload() của các màn khác)."""
        view = self._current_view
        if self._is_closed or view is None:
            return "break"
        refresh = getattr(view, "refresh", None)
        reload = getattr(view, "reload", None)
        try:
            if callable(refresh):
                refresh(manual=True)
            elif callable(reload):
                reload()
        except Exception:  # noqa: BLE001 — không để phím tắt làm crash app
            logger.exception("Không làm mới được màn %s", self._current_key)
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")
        return "break"

    def _navigate_by_index(self, index: int) -> str:
        """Ctrl+1..5: mở mục menu thứ `index` mà vai trò hiện tại được thấy."""
        keys = self.nav_keys
        if 1 <= index <= len(keys):
            self.navigate(keys[index - 1])
        return "break"

    # ------------------------------------------------------------------
    # Ngôn ngữ
    # ------------------------------------------------------------------
    def set_language(self, language: str) -> None:
        new_language = normalize_language(language)
        if new_language == self._language:
            return
        self._language = new_language
        self._apply_language()
        # Dựng lại view hiện tại để view nhận language mới qua ViewContext.
        current = self._current_key
        if current is not None:
            self._dispose_current_view()
            self.navigate(current)

    def _apply_language(self) -> None:
        assert self._session is not None
        lang = self._language
        for key, button in self._nav_buttons.items():
            item = get_nav_item(key)
            button.configure(text=f"{item.icon}   {translate(item.i18n_key, lang)}")
        for code, button in self._lang_buttons.items():
            active = code == lang
            button.configure(
                fg_color=STITCH_CYAN if active else "transparent",
                hover_color=STITCH_CYAN if active else STITCH_NAV_HOVER,
                text_color=STITCH_TEXT_ON_CYAN if active else STITCH_TEXT_MUTED,
            )
        self._status_label.configure(text=f"● {translate('status.ready', lang)}")
        self._role_label.configure(text=role_label(self._session, lang))
        self._search_entry.configure(placeholder_text=translate("header.search_placeholder", lang))

    # ------------------------------------------------------------------
    # Đăng xuất
    # ------------------------------------------------------------------
    def _on_logout_clicked(self) -> None:
        if self._is_closed:
            return
        confirmed = ConfirmDialog.ask(
            self.winfo_toplevel(),
            title=LOGOUT_TITLE,
            message=LOGOUT_MESSAGE,
            confirm_label=LOGOUT_CONFIRM_LABEL,
            cancel_label=MSG_CANCEL,
            is_danger=True,
        )
        if confirmed:
            self.logout()

    def logout(self) -> None:
        """Dọn shell, xóa session UI, rồi trả quyền cho composition root (về Login)."""
        if self._is_closed:
            return
        callback = self._on_logout
        self.destroy()
        callback()

    def _teardown(self) -> None:
        if self._is_closed:
            return
        self._is_closed = True
        self._unbind_shortcuts()
        self._dispose_current_view()
        self._session = None
        self._nav_buttons.clear()
        self._lang_buttons.clear()

    def destroy(self) -> None:
        # Mọi đường đóng shell (logout, đóng cửa sổ) đều dọn view và session.
        self._teardown()
        super().destroy()


def _run_demo() -> None:
    """Chạy thử shell với mock, không cần MySQL/Login.

    python -m cyberhub_manager.ui.app_shell            # quản lý
    python -m cyberhub_manager.ui.app_shell nhanvien01 # nhân viên
    """
    import sys

    from ..services.mocks.factory import build_mock_services
    from ..services.mocks.fixtures import DEMO_PASSWORD
    from .theme import SHELL_HEIGHT, SHELL_WIDTH, load_stitch_fonts, setup_theme
    from .theme import SHELL_HEIGHT, SHELL_WIDTH, load_stitch_fonts, setup_theme
    from .views import default_view_factories

    username = sys.argv[1] if len(sys.argv) > 1 else "quanly01"
    setup_theme()
    services = build_mock_services()
    session = services.auth.login(username, DEMO_PASSWORD)

    root = ctk.CTk()
    load_stitch_fonts()  # sau khi có root; trước khi tạo widget
    root.title("CyberHub Manager")
    root.geometry(f"{SHELL_WIDTH}x{SHELL_HEIGHT}")
    root.minsize(SHELL_WIDTH, SHELL_HEIGHT)

    def back_to_login() -> None:
        print("Logout OK — HA-11 sẽ hiển thị LoginView tại đây.")
        root.after(300, root.destroy)

    AppShell(
        root,
        services,
        session,
        on_logout=back_to_login,
        view_factories=default_view_factories(),
    ).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    _run_demo()
