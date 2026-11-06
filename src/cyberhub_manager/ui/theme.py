"""Cyber Ops Dark design system tokens cho CyberHub Manager.

Toàn bộ view và component phải tham chiếu token tại đây; không hard-code màu hoặc font.
Nguồn quy chuẩn: docs/03_UI_THEME.md
"""

from __future__ import annotations

import customtkinter as ctk

# ==============================================================================
# 1. BẢNG MÀU (COLOR PALETTE)
# ==============================================================================

# Background colors
BG_APP = "#0B1120"            # Nền toàn ứng dụng
BG_SIDEBAR = "#111827"        # Nền sidebar menu
BG_SURFACE = "#172033"        # Nền card, panel, dialog
BG_SURFACE_HOVER = "#22304A"  # Nền hover/selected surface
BG_TABLE_HEADER = "#1E293B"   # Nền header bảng dữ liệu
BG_ALERT_DANGER = "#3B1822"   # Nền cảnh báo đỏ nhạt (cho số dư âm)
BG_ROW_ALT = "#151D2E"        # Nền xen kẽ (sọc) dòng bảng dữ liệu

# App Shell backgrounds — CyberHub Stitch reference
BG_TOPBAR = "#0D1626"
BG_CONTENT = "#080F1E"
BG_CARD = "#111B2C"
BG_CARD_HOVER = "#162238"
BG_INPUT = "#0E1728"
BG_OVERLAY = "#050A14"

# Navigation backgrounds
BG_NAV_ACTIVE = "#083344"
BG_NAV_HOVER = "#12233A"
BG_NAV_IDLE = "transparent"

# Subtle badge, toast & status background tokens
BG_SUCCESS_SUBTLE = "#0A2918" # Nền xanh nhạt cho badge/toast thành công
BG_DANGER_SUBTLE = "#331317"  # Nền đỏ nhạt cho badge/toast lỗi
BG_WARNING_SUBTLE = "#352309" # Nền cam/vàng nhạt cho badge/toast cảnh báo
BG_INFO_SUBTLE = "#0C2A38"    # Nền xanh cyan nhạt cho badge/toast thông tin
BG_MUTED_SUBTLE = "#1E293B"   # Nền xám nhạt cho badge/toast trung tính, inactive

# Border & divider
BORDER = "#334155"            # Viền input, card divider, table divider
BORDER_SUBTLE = "#1E293B"
BORDER_STRONG = "#475569"
BORDER_FOCUS = "#06B6D4"

# Text colors
TEXT_PRIMARY = "#F8FAFC"      # Tiêu đề, nội dung chính
TEXT_SECONDARY = "#94A3B8"    # Mô tả, nhãn phụ, metadata
TEXT_MUTED = "#64748B"        # Chữ mờ, placeholder

# Accent & actions
ACCENT = "#3B82F6"            # Nút primary, link, focus
ACCENT_HOVER = "#2563EB"      # Hover primary
# CyberHub brand colors used by the unified App Shell.
BRAND_PRIMARY = "#06B6D4"
BRAND_PRIMARY_HOVER = "#0891B2"
BRAND_SECONDARY = "#3B82F6"
BRAND_GLOW = "#22D3EE"

NAV_TEXT = "#94A3B8"
NAV_TEXT_ACTIVE = "#67E8F9"

# Status & semantic colors
SUCCESS = "#22C55E"           # Máy trống, thao tác thành công
SUCCESS_HOVER = "#16A34A"     # Hover nút success
DANGER = "#EF4444"            # Máy đang dùng, cảnh báo âm, lỗi, hủy
DANGER_HOVER = "#DC2626"      # Hover nút danger
WARNING = "#F59E0B"           # Máy bảo trì, cảnh báo chưa chặn
WARNING_HOVER = "#D97706"     # Hover nút warning
INFO = "#06B6D4"              # Thông tin, badge phụ
DISABLED = "#64748B"          # Control/nút bị khóa, trạng thái ngừng hoạt động

# ==============================================================================
# 2. TYPOGRAPHY (FONT TOKENS)
# ==============================================================================
# Tkinter / CustomTkinter font tuple: (Family, Size, Weight)
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_FALLBACK = "Arial"

FONT_TITLE_XL = (FONT_FAMILY, 28, "bold")     # Tên màn hình login
FONT_TITLE_LG = (FONT_FAMILY, 22, "bold")     # Tiêu đề trang
FONT_TITLE_MD = (FONT_FAMILY, 18, "bold")     # Dialog / Card section
FONT_BODY = (FONT_FAMILY, 14, "normal")       # Nội dung, form, table
FONT_BODY_STRONG = (FONT_FAMILY, 14, "bold")  # Nút, số liệu chính
FONT_CAPTION = (FONT_FAMILY, 12, "normal")    # Hint, thời gian, metadata, nhãn lỗi
FONT_MONEY = (FONT_FAMILY, 16, "bold")        # Số dư và tổng tiền

# Compact typography for the 1280x720 desktop App Shell.
FONT_SHELL_BRAND = (FONT_FAMILY, 14, "bold")
FONT_SHELL_TITLE = (FONT_FAMILY, 20, "bold")
FONT_SHELL_SECTION = (FONT_FAMILY, 15, "bold")
FONT_SHELL_BODY = (FONT_FAMILY, 12, "normal")
FONT_SHELL_BODY_STRONG = (FONT_FAMILY, 12, "bold")
FONT_SHELL_CAPTION = (FONT_FAMILY, 10, "normal")
FONT_SHELL_METRIC = (FONT_FAMILY, 18, "bold")

# ==============================================================================
# 3. SPACING & SIZING (KÍCH THƯỚC VÀ KHOẢNG CÁCH)
# ==============================================================================
# Grid cơ sở: 4 px
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24
SPACING_2XL = 32

# Border radius
RADIUS_INPUT = 8
RADIUS_BUTTON = 8
RADIUS_CARD = 12
RADIUS_DIALOG = 16
RADIUS_BADGE = 6

# Heights & Widths
HEIGHT_INPUT = 40
HEIGHT_BUTTON = 40
HEIGHT_PRIMARY_ACTION = 44
HEIGHT_HEADER = 64
WIDTH_SIDEBAR = 224
PADDING_CONTENT = 24
GAP_CARD = 16

# Unified App Shell geometry.
SHELL_WIDTH = 1280
SHELL_HEIGHT = 720
SHELL_MIN_WIDTH = 1100
SHELL_MIN_HEIGHT = 650

SHELL_TOPBAR_HEIGHT = 56
SHELL_SIDEBAR_WIDTH = 208
SHELL_CONTENT_PADDING = 16
SHELL_NAV_ITEM_HEIGHT = 40
SHELL_STATUSBAR_HEIGHT = 28
SHELL_CARD_GAP = 12

# Cửa sổ ứng dụng
APP_MIN_WIDTH = 1280
APP_MIN_HEIGHT = 720
DIALOG_WIDTH_MIN = 480
DIALOG_WIDTH_MAX = 560


def setup_theme() -> None:
    """Khởi tạo theme Cyber Ops Dark cho CustomTkinter."""
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

# ==============================================================================
# 4. APP SHELL THEO STITCH EXPORT (code.html + DESIGN.md "Cyber Defense Operations")
# ==============================================================================
# Token mới, không sửa token cũ ở trên để không ảnh hưởng component NG-01.
# Tkinter không hỗ trợ alpha: màu dạng "cyan 15%" đã được trộn sẵn trên nền chrome.

STITCH_BG_CANVAS = "#0B101B"          # nền vùng nội dung
STITCH_BG_CHROME = "#0E131E"          # nền sidebar + topbar
STITCH_BG_CHROME_FOOT = "#0A0E17"     # khối trạng thái đáy sidebar
STITCH_BORDER = "#222A3D"             # đường kẻ 1px giữa các vùng
STITCH_CHIP_BG = "#171F30"            # chip cửa hàng, nút phụ
STITCH_CHIP_BORDER = "#27344E"
STITCH_INPUT_BG = "#131926"           # ô tìm kiếm, công tắc VI/EN
STITCH_INPUT_BORDER = "#263147"
STITCH_AVATAR_BG = "#1E273A"
STITCH_CARD_BG = "#121824"            # dùng cho view NG-03 trở đi
STITCH_CARD_BORDER = "#212B3E"

STITCH_CYAN = "#00C6FF"               # màu nhấn chính
STITCH_NAV_ACTIVE_BG = "#0C2E40"      # cyan 15% trên STITCH_BG_CHROME
STITCH_NAV_ACTIVE_BORDER = "#085B78"  # cyan 40% trên STITCH_BG_CHROME
STITCH_NAV_HOVER = "#161D2D"
STITCH_DANGER_HOVER_BG = "#251724"    # rose 10% trên STITCH_BG_CHROME

STITCH_TEXT_STRONG = "#FFFFFF"
STITCH_TEXT = "#E2E8F0"               # slate-200
STITCH_TEXT_MUTED = "#94A3B8"         # slate-400
STITCH_TEXT_DIM = "#64748B"           # slate-500
STITCH_TEXT_ON_CYAN = "#020617"       # slate-950
STITCH_SUCCESS = "#34D399"            # emerald-400
STITCH_DANGER = "#FB7185"             # rose-400
STITCH_WARNING = "#FBBF24"            # amber-400

STITCH_SIDEBAR_WIDTH = 220
STITCH_BRAND_HEIGHT = 60
STITCH_TOPBAR_HEIGHT = 52
STITCH_NAV_ITEM_HEIGHT = 36
STITCH_CONTENT_PADX = 20
STITCH_CONTENT_PADY = 14
STITCH_RADIUS = 4
STITCH_RADIUS_LG = 8

# Font: cần cài Space Grotesk + JetBrains Mono (hoặc nạp bằng load_stitch_fonts()).
# Thiếu font thì Tk tự dùng font mặc định, app vẫn chạy.
STITCH_FONT = "Space Grotesk"
STITCH_FONT_MONO = "JetBrains Mono"

FONT_ST_BRAND = (STITCH_FONT, 14, "bold")
FONT_ST_PAGE_TITLE = (STITCH_FONT, 18, "bold")
FONT_ST_BODY = (STITCH_FONT, 12, "normal")
FONT_ST_BODY_STRONG = (STITCH_FONT, 12, "bold")
FONT_ST_MONO_XS = (STITCH_FONT_MONO, 10, "normal")
FONT_ST_MONO_XS_STRONG = (STITCH_FONT_MONO, 10, "bold")
FONT_ST_MONO_SM = (STITCH_FONT_MONO, 11, "bold")
FONT_ST_MONO_BODY = (STITCH_FONT_MONO, 12, "normal")


def load_stitch_fonts() -> None:
    """Nạp mọi file .ttf trong ui/assets/fonts (nếu có) cho phiên chạy hiện tại."""
    from importlib.resources import as_file, files

    fonts_dir = files("cyberhub_manager.ui.assets").joinpath("fonts")
    if not fonts_dir.is_dir():
        return
    for entry in fonts_dir.iterdir():
        if entry.name.lower().endswith(".ttf"):
            with as_file(entry) as path:
                ctk.FontManager.load_font(str(path))

