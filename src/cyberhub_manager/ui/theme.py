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

# Border & divider
BORDER = "#334155"            # Viền input, card divider, table divider

# Text colors
TEXT_PRIMARY = "#F8FAFC"      # Tiêu đề, nội dung chính
TEXT_SECONDARY = "#94A3B8"    # Mô tả, nhãn phụ, metadata
TEXT_MUTED = "#64748B"        # Chữ mờ, placeholder

# Accent & actions
ACCENT = "#3B82F6"            # Nút primary, link, focus
ACCENT_HOVER = "#2563EB"      # Hover primary

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

# Cửa sổ ứng dụng
APP_MIN_WIDTH = 1280
APP_MIN_HEIGHT = 720
DIALOG_WIDTH_MIN = 480
DIALOG_WIDTH_MAX = 560


def setup_theme() -> None:
    """Khởi tạo theme Cyber Ops Dark cho CustomTkinter."""
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
