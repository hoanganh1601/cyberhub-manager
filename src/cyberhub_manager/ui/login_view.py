"""Login View — Màn hình Đăng nhập theo chuẩn Google Stitch.

Tuân thủ thiết kế Stitch:
- Tham chiếu: docs/ui-reference/ng_nh_p_cyberhub_manager_1280x720/code.html
- Bố cục 2 cột: 55% Trái (704px) + 45% Phải (576px) trên canvas 1280x720.
- Cột trái: Nền Cyber Ops Dark với Tactical Circuit Design (đường mạch điện chiến thuật vector trên Canvas), Buffalo logo, tiêu đề CyberHub Manager, 4 thẻ tính năng nổi bật.
- Cột phải: Cổng vận hành nhân viên, bộ chuyển đổi ngôn ngữ VI/EN, form đăng nhập với icon trong ô Username (👤) và Password (🔒), nút hiện/ẩn mật khẩu (👁), banner cảnh báo lỗi xác thực và nút submit có hiệu ứng busy.
- Giữ nguyên authentication flow và session management hiện tại.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import customtkinter as ctk
from PIL import Image

from ..domain.dtos import EmployeeSession
from ..domain.exceptions import ApplicationError, AuthenticationError
from ..services.contracts import AuthServiceProtocol
from .components import ActionButton, ToastManager
from .i18n import Language, normalize_language, translate
from .messages import MSG_INVALID_CREDENTIALS, MSG_OPERATION_FAILED, get_user_friendly_error
from .theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_BRAND,
    FONT_ST_MONO_BODY,
    FONT_ST_MONO_SM,
    FONT_ST_MONO_XS,
    FONT_ST_MONO_XS_STRONG,
    FONT_ST_PAGE_TITLE,
    RADIUS_INPUT,
    STITCH_BG_CANVAS,
    STITCH_BG_CHROME,
    STITCH_BORDER,
    STITCH_CHIP_BG,
    STITCH_CHIP_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_EMERALD,
    STITCH_INPUT_BG,
    STITCH_RADIUS,
    STITCH_RADIUS_LG,
    STITCH_SUNKEN_BG,
    STITCH_TEXT,
    STITCH_TEXT_DIM,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_ON_CYAN,
    STITCH_TEXT_STRONG,
)

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_DIR / "cyberhub_logo_dark.png"


class LoginView(ctk.CTkFrame):
    """Màn hình Đăng nhập 2 cột kích thước 1280x720 chuẩn Stitch."""

    def __init__(
        self,
        master: Any,
        auth_service: AuthServiceProtocol,
        *,
        on_login_success: Callable[[EmployeeSession], None],
        language: str = "vi",
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color=STITCH_BG_CANVAS, corner_radius=0, **kwargs)
        self._auth_service = auth_service
        self._on_login_success = on_login_success
        self._language: Language = normalize_language(language)
        self._password_visible = False

        self.grid_columnconfigure(0, weight=55, uniform="login_split")
        self.grid_columnconfigure(1, weight=45, uniform="login_split")
        self.grid_rowconfigure(0, weight=1)

        self._build_left_brand_panel()
        self._build_right_form_panel()

        # Keyboard shortcuts: Enter to submit
        self._username_entry.bind("<Return>", lambda _e: self._handle_submit())
        self._password_entry.bind("<Return>", lambda _e: self._handle_submit())

        # Typing clears errors
        self._username_entry.bind("<KeyRelease>", lambda _e: self._clear_field_error("username"))
        self._password_entry.bind("<KeyRelease>", lambda _e: self._clear_field_error("password"))

    # ------------------------------------------------------------------
    # CỘT TRÁI (55%): TACTICAL CIRCUIT DESIGN & THƯƠNG HIỆU
    # ------------------------------------------------------------------
    def _build_left_brand_panel(self) -> None:
        left_panel = ctk.CTkFrame(
            self,
            fg_color="#090E19",
            corner_radius=0,
            border_width=0,
        )
        left_panel.grid(row=0, column=0, sticky="nsew")

        # 1. Canvas Tactical Circuit Layer (Đường mạch điện chiến thuật)
        self._circuit_canvas = ctk.CTkCanvas(
            left_panel,
            width=704,
            height=720,
            bg="#090E19",
            highlightthickness=0,
        )
        self._circuit_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._draw_tactical_circuits()

        # 2. Border divider at the right edge of left panel
        vline = ctk.CTkFrame(self, fg_color="#232B40", width=1, corner_radius=0)
        vline.grid(row=0, column=0, sticky="nse")

        # 3. Content Frame placed on top of Canvas
        inner = ctk.CTkFrame(left_panel, fg_color="transparent")
        inner.place(x=48, y=36, relwidth=0.88, relheight=0.92)

        # Center Brand / Identity Section
        mid_box = ctk.CTkFrame(inner, fg_color="transparent")
        mid_box.pack(fill="x", expand=True, anchor="w", pady=(10, 0))

        # Buffalo Logo Box (with glassmorphism effect)
        logo_box = ctk.CTkFrame(
            mid_box,
            fg_color="#131826",
            border_width=1,
            border_color="#232B40",
            corner_radius=12,
        )
        logo_box.pack(anchor="w", pady=(0, 16))

        if LOGO_PATH.exists():
            try:
                pil_logo = Image.open(LOGO_PATH)
                target_h = 58
                target_w = int(pil_logo.width * (target_h / pil_logo.height))
                ctk_logo = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(target_w, target_h))
                logo_lbl = ctk.CTkLabel(logo_box, image=ctk_logo, text="")
                logo_lbl.pack(padx=16, pady=10)
            except Exception as e:
                logger.warning("Không thể tải logo CyberHub: %s", e)
                ctk.CTkLabel(logo_box, text="⚡ CYBERHUB", font=FONT_ST_PAGE_TITLE, text_color=STITCH_CYAN).pack(padx=20, pady=12)
        else:
            ctk.CTkLabel(logo_box, text="⚡ CYBERHUB", font=FONT_ST_PAGE_TITLE, text_color=STITCH_CYAN).pack(padx=20, pady=12)

        # Badge: Phần mềm quản lý phòng máy
        badge_f = ctk.CTkFrame(mid_box, fg_color="#0C2433", border_width=1, border_color="#00C6FF", corner_radius=4)
        badge_f.pack(anchor="w", pady=(0, 8))
        self._lbl_badge = ctk.CTkLabel(
            badge_f,
            text="PHẦN MỀM QUẢN LÝ PHÒNG MÁY" if self._language == "vi" else "CYBERCAFE MANAGEMENT SYSTEM",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_CYAN,
        )
        self._lbl_badge.pack(padx=8, pady=2)

        # Title: CyberHub Manager
        title_row = ctk.CTkFrame(mid_box, fg_color="transparent")
        title_row.pack(anchor="w")

        ctk.CTkLabel(
            title_row,
            text="CyberHub ",
            font=(FONT_ST_PAGE_TITLE[0], 34, "bold"),
            text_color=STITCH_TEXT_STRONG,
        ).pack(side="left")

        ctk.CTkLabel(
            title_row,
            text="Manager",
            font=(FONT_ST_PAGE_TITLE[0], 34, "bold"),
            text_color=STITCH_CYAN,
        ).pack(side="left")

        # Subtitle
        is_vi = self._language == "vi"
        self._tagline_label = ctk.CTkLabel(
            mid_box,
            text="Hệ thống quản lý phòng máy chuyên nghiệp"
            if is_vi
            else "Professional Cybercafe & Esports Operations Platform",
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
        )
        self._tagline_label.pack(anchor="w", pady=(4, 20))

        # 4 Feature Tags in 2x2 Grid
        features_grid = ctk.CTkFrame(mid_box, fg_color="transparent")
        features_grid.pack(fill="x", anchor="w")
        features_grid.grid_columnconfigure(0, weight=1)
        features_grid.grid_columnconfigure(1, weight=1)

        feats = [
            ("⚡", "Kiểm soát phiên thời gian thực" if is_vi else "Real-time session control"),
            ("💎", "Biểu phí & Nạp tiền chuẩn xác" if is_vi else "Accurate tariffs & billing"),
            ("🖥", "Đồng bộ 20 máy trạm tức thì" if is_vi else "Instant 20-station sync"),
            ("⏱", "Độ trễ phản hồi dưới 15ms" if is_vi else "Sub-15ms response latency"),
        ]

        self._feat_labels: list[ctk.CTkLabel] = []
        for idx, (icon, text) in enumerate(feats):
            r = idx // 2
            c = idx % 2
            card = ctk.CTkFrame(
                features_grid,
                fg_color="#0E1424",
                border_width=1,
                border_color="#232B40",
                corner_radius=6,
                height=36,
            )
            card.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")
            card.pack_propagate(False)

            ctk.CTkLabel(card, text=icon, font=FONT_ST_MONO_SM, text_color=STITCH_CYAN).pack(side="left", padx=(10, 6))
            lbl = ctk.CTkLabel(card, text=text, font=FONT_ST_MONO_XS, text_color=STITCH_TEXT)
            lbl.pack(side="left")
            self._feat_labels.append(lbl)

        # Bottom Footer Left
        foot_left = ctk.CTkFrame(inner, fg_color="transparent")
        foot_left.pack(fill="x", side="bottom")

        ctk.CTkLabel(
            foot_left,
            text="© 2026 CyberHub Manager • All systems operational",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_DIM,
        ).pack(side="left")

    def _draw_tactical_circuits(self) -> None:
        """Vẽ các đường mạch điện chiến thuật chuẩn Stitch SVG."""
        cv = self._circuit_canvas

        # Subtle grid background
        for x in range(0, 720, 48):
            cv.create_line(x, 0, x, 720, fill="#0F1523", width=1)
        for y in range(0, 720, 48):
            cv.create_line(0, y, 720, y, fill="#0F1523", width=1)

        # Path 1: Cyan dashed line M 0 160 H 220 L 280 220 H 460 L 520 280 V 420
        p1 = [(0, 160), (220, 160), (280, 220), (460, 220), (520, 280), (520, 420)]
        for i in range(len(p1) - 1):
            cv.create_line(p1[i][0], p1[i][1], p1[i + 1][0], p1[i + 1][1], fill="#00C6FF", width=1.5, dash=(4, 4))
        for cx, cy in [(280, 220), (460, 220), (520, 280)]:
            cv.create_oval(cx - 3.5, cy - 3.5, cx + 3.5, cy + 3.5, fill="#00C6FF", outline="")

        # Path 2: Blue dashed line M 120 720 V 540 L 190 470 H 420 L 480 410 H 640
        p2 = [(120, 720), (120, 540), (190, 470), (420, 470), (480, 410), (640, 410)]
        for i in range(len(p2) - 1):
            cv.create_line(p2[i][0], p2[i][1], p2[i + 1][0], p2[i + 1][1], fill="#2563EB", width=1.5, dash=(3, 3))
        for cx, cy in [(190, 470), (420, 470), (480, 410)]:
            cv.create_oval(cx - 3.5, cy - 3.5, cx + 3.5, cy + 3.5, fill="#2563EB", outline="")

        # Path 3: Top-right cyan branch M 600 80 L 640 120 V 240 L 680 280
        p3 = [(600, 80), (640, 120), (640, 240), (680, 280)]
        for i in range(len(p3) - 1):
            cv.create_line(p3[i][0], p3[i][1], p3[i + 1][0], p3[i + 1][1], fill="#00C6FF", width=1)
        cv.create_oval(640 - 2.5, 120 - 2.5, 640 + 2.5, 120 + 2.5, fill="#00C6FF", outline="")

        # Path 4: Bottom-left blue branch M 60 480 H 140 L 170 510 V 620
        p4 = [(60, 480), (140, 480), (170, 510), (170, 620)]
        for i in range(len(p4) - 1):
            cv.create_line(p4[i][0], p4[i][1], p4[i + 1][0], p4[i + 1][1], fill="#2563EB", width=1)
        cv.create_oval(140 - 2.5, 480 - 2.5, 140 + 2.5, 480 + 2.5, fill="#2563EB", outline="")

    # ------------------------------------------------------------------
    # CỘT PHẢI (45%): FORM ĐĂNG NHẬP & CÔNG TẮC NGÔN NGỮ
    # ------------------------------------------------------------------
    def _build_right_form_panel(self) -> None:
        right_panel = ctk.CTkFrame(
            self,
            fg_color="#0E131E",
            corner_radius=0,
        )
        right_panel.grid(row=0, column=1, sticky="nsew")

        inner = ctk.CTkFrame(right_panel, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=48, pady=36)

        # Top Bar Cột phải: Role Tag + Nút chuyển ngôn ngữ VI | EN
        top_bar = ctk.CTkFrame(inner, fg_color="transparent")
        top_bar.pack(fill="x")

        is_vi = self._language == "vi"
        self._lbl_portal = ctk.CTkLabel(
            top_bar,
            text="CỔNG VẬN HÀNH NHÂN VIÊN" if is_vi else "STAFF OPERATIONS PORTAL",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        )
        self._lbl_portal.pack(side="left")

        lang_box = ctk.CTkFrame(top_bar, fg_color="#131826", border_width=1, border_color="#232B40", corner_radius=6)
        lang_box.pack(side="right")

        self._lang_btn_vi = ctk.CTkButton(
            lang_box,
            text="VI",
            width=28,
            height=22,
            corner_radius=STITCH_RADIUS,
            font=FONT_ST_MONO_SM,
            command=lambda: self._set_language("vi"),
        )
        self._lang_btn_vi.pack(side="left", padx=2, pady=2)

        self._lang_btn_en = ctk.CTkButton(
            lang_box,
            text="EN",
            width=28,
            height=22,
            corner_radius=STITCH_RADIUS,
            font=FONT_ST_MONO_SM,
            command=lambda: self._set_language("en"),
        )
        self._lang_btn_en.pack(side="left", padx=2, pady=2)

        self._update_lang_styles()

        # Center: Khung Form đăng nhập
        form_center = ctk.CTkFrame(inner, fg_color="transparent")
        form_center.pack(fill="x", expand=True, pady=(20, 20))

        self._form_title = ctk.CTkLabel(
            form_center,
            text="Đăng nhập" if is_vi else "Sign in",
            font=(FONT_ST_PAGE_TITLE[0], 28, "bold"),
            text_color=STITCH_TEXT_STRONG,
        )
        self._form_title.pack(anchor="w")

        self._form_subtitle = ctk.CTkLabel(
            form_center,
            text="Đăng nhập để tiếp tục quản lý cửa hàng"
            if is_vi
            else "Enter credentials to access manager workstation",
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
        )
        self._form_subtitle.pack(anchor="w", pady=(3, 20))

        # ---------------- TRƯỜNG TÊN ĐĂNG NHẬP (Icon 👤) ----------------
        self._lbl_user_label = ctk.CTkLabel(
            form_center,
            text="TÊN ĐĂNG NHẬP" if is_vi else "USERNAME",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_TEXT_STRONG,
        )
        self._lbl_user_label.pack(anchor="w", pady=(0, 4))

        self._box_username = ctk.CTkFrame(
            form_center,
            fg_color="#131826",
            border_width=1,
            border_color="#232B40",
            corner_radius=8,
            height=38,
        )
        self._box_username.pack(fill="x")
        self._box_username.pack_propagate(False)

        ctk.CTkLabel(
            self._box_username,
            text="👤",
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left", padx=(10, 6))

        self._username_entry = ctk.CTkEntry(
            self._box_username,
            placeholder_text="Nhập tên đăng nhập" if is_vi else "Enter username",
            fg_color="transparent",
            border_width=0,
            text_color=STITCH_TEXT_STRONG,
            font=FONT_ST_BODY,
        )
        self._username_entry.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._username_entry.insert(0, "quanly01")

        self._err_username = ctk.CTkLabel(
            form_center,
            text="",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_DANGER,
            height=16,
        )
        self._err_username.pack(anchor="w", pady=(1, 4))

        # ---------------- TRƯỜNG MẬT KHẨU (Icon 🔒 + Toggle 👁) ----------------
        self._lbl_pass_label = ctk.CTkLabel(
            form_center,
            text="MẬT KHẨU" if is_vi else "PASSWORD",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_TEXT_STRONG,
        )
        self._lbl_pass_label.pack(anchor="w", pady=(0, 4))

        self._box_password = ctk.CTkFrame(
            form_center,
            fg_color="#131826",
            border_width=1,
            border_color="#232B40",
            corner_radius=8,
            height=38,
        )
        self._box_password.pack(fill="x")
        self._box_password.pack_propagate(False)

        ctk.CTkLabel(
            self._box_password,
            text="🔒",
            font=FONT_ST_BODY,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="left", padx=(10, 6))

        self._password_entry = ctk.CTkEntry(
            self._box_password,
            placeholder_text="Nhập mật khẩu" if is_vi else "Enter password",
            show="*",
            fg_color="transparent",
            border_width=0,
            text_color=STITCH_TEXT_STRONG,
            font=FONT_ST_BODY,
        )
        self._password_entry.pack(side="left", fill="both", expand=True)
        self._password_entry.insert(0, "demo123")

        self._btn_toggle_pass = ctk.CTkButton(
            self._box_password,
            text="👁",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color="#1E273A",
            text_color=STITCH_TEXT_MUTED,
            font=FONT_ST_BODY,
            command=self._toggle_password_visibility,
        )
        self._btn_toggle_pass.pack(side="right", padx=4)

        self._err_password = ctk.CTkLabel(
            form_center,
            text="",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_DANGER,
            height=16,
        )
        self._err_password.pack(anchor="w", pady=(1, 6))

        # ---------------- AUTH ALERT BANNER ----------------
        self._auth_alert = ctk.CTkFrame(
            form_center,
            fg_color="#2D151F",
            border_width=1,
            border_color="#FF4D6D",
            corner_radius=8,
        )
        al_inner = ctk.CTkFrame(self._auth_alert, fg_color="transparent")
        al_inner.pack(fill="both", expand=True, padx=10, pady=8)

        self._lbl_auth_alert = ctk.CTkLabel(
            al_inner,
            text="⚠ Tên đăng nhập hoặc mật khẩu không đúng." if is_vi else "⚠ Invalid username or password.",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_DANGER,
        )
        self._lbl_auth_alert.pack(side="left")

        # Nút Đăng nhập
        self._btn_login = ActionButton(
            form_center,
            text="Đăng nhập hệ thống" if is_vi else "Sign In",
            kind="primary",
            height=42,
            command=self._handle_submit,
        )
        self._btn_login.pack(fill="x", pady=(8, 0))

        # Hint tài khoản demo
        hint_box = ctk.CTkFrame(form_center, fg_color="#121824", border_width=1, border_color=STITCH_BORDER, corner_radius=6)
        hint_box.pack(fill="x", pady=(16, 0))
        ctk.CTkLabel(
            hint_box,
            text="Tài khoản demo: quanly01 (Quản lý) | nhanvien01 (Nhân viên) • Pass: demo123"
            if is_vi
            else "Demo accounts: quanly01 (Manager) | nhanvien01 (Staff) • Pass: demo123",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        ).pack(padx=8, pady=6)

    def _toggle_password_visibility(self) -> None:
        self._password_visible = not self._password_visible
        self._password_entry.configure(show="" if self._password_visible else "*")
        self._btn_toggle_pass.configure(text="👁‍🗨" if self._password_visible else "👁")

    def _clear_field_error(self, field: str) -> None:
        if field == "username":
            self._box_username.configure(border_color="#232B40")
            self._err_username.configure(text="")
        elif field == "password":
            self._box_password.configure(border_color="#232B40")
            self._err_password.configure(text="")
        if self._auth_alert.winfo_ismapped():
            self._auth_alert.pack_forget()

    def _set_language(self, language: Language) -> None:
        if language == self._language:
            return
        self._language = language
        self._update_lang_styles()
        is_vi = language == "vi"

        self._lbl_badge.configure(
            text="PHẦN MỀM QUẢN LÝ PHÒNG MÁY" if is_vi else "CYBERCAFE MANAGEMENT SYSTEM"
        )
        self._tagline_label.configure(
            text="Hệ thống quản lý phòng máy chuyên nghiệp"
            if is_vi
            else "Professional Cybercafe & Esports Operations Platform"
        )
        self._lbl_portal.configure(
            text="CỔNG VẬN HÀNH NHÂN VIÊN" if is_vi else "STAFF OPERATIONS PORTAL"
        )
        self._form_title.configure(text="Đăng nhập" if is_vi else "Sign in")
        self._form_subtitle.configure(
            text="Đăng nhập để tiếp tục quản lý cửa hàng"
            if is_vi
            else "Enter credentials to access manager workstation"
        )
        self._lbl_user_label.configure(text="TÊN ĐĂNG NHẬP" if is_vi else "USERNAME")
        self._lbl_pass_label.configure(text="MẬT KHẨU" if is_vi else "PASSWORD")
        self._username_entry.configure(placeholder_text="Nhập tên đăng nhập" if is_vi else "Enter username")
        self._password_entry.configure(placeholder_text="Nhập mật khẩu" if is_vi else "Enter password")
        self._btn_login.configure(text="Đăng nhập hệ thống" if is_vi else "Sign In")

    def _update_lang_styles(self) -> None:
        vi_active = self._language == "vi"
        self._lang_btn_vi.configure(
            fg_color=STITCH_CYAN if vi_active else "transparent",
            hover_color=STITCH_CYAN if vi_active else STITCH_CHIP_BG,
            text_color=STITCH_TEXT_ON_CYAN if vi_active else STITCH_TEXT_MUTED,
            font=FONT_ST_BODY_STRONG if vi_active else FONT_ST_BODY,
        )
        self._lang_btn_en.configure(
            fg_color=STITCH_CYAN if not vi_active else "transparent",
            hover_color=STITCH_CYAN if not vi_active else STITCH_CHIP_BG,
            text_color=STITCH_TEXT_ON_CYAN if not vi_active else STITCH_TEXT_MUTED,
            font=FONT_ST_BODY_STRONG if not vi_active else FONT_ST_BODY,
        )

    # ------------------------------------------------------------------
    # Form Submission
    # ------------------------------------------------------------------
    def _handle_submit(self) -> None:
        username = self._username_entry.get().strip()
        password = self._password_entry.get()

        self._clear_field_error("username")
        self._clear_field_error("password")

        has_error = False
        if not username:
            self._box_username.configure(border_color=STITCH_DANGER)
            self._err_username.configure(
                text="Vui lòng nhập tên đăng nhập" if self._language == "vi" else "Please enter username"
            )
            has_error = True

        if not password:
            self._box_password.configure(border_color=STITCH_DANGER)
            self._err_password.configure(
                text="Vui lòng nhập mật khẩu" if self._language == "vi" else "Please enter password"
            )
            has_error = True

        if has_error:
            return

        self._btn_login.set_busy(True)
        try:
            session = self._auth_service.login(username, password)
            self._on_login_success(session)
        except AuthenticationError:
            err_msg = (
                "Tên đăng nhập hoặc mật khẩu không đúng."
                if self._language == "vi"
                else "Invalid username or password."
            )
            self._box_username.configure(border_color=STITCH_DANGER)
            self._box_password.configure(border_color=STITCH_DANGER)
            self._lbl_auth_alert.configure(text=f"⚠ {err_msg}")
            self._auth_alert.pack(fill="x", pady=(0, 8), before=self._btn_login)
            ToastManager.show(self, err_msg, kind="error")
        except ApplicationError as err:
            logger.warning("Lỗi đăng nhập: %s", err)
            ToastManager.show(self, get_user_friendly_error(err), kind="error")
        except Exception:
            logger.exception("Lỗi không mong muốn khi đăng nhập")
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")
        finally:
            self._btn_login.set_busy(False)
