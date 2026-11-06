"""Vector Icon provider cho CyberHub Manager (chuẩn hóa theo Google Stitch SVG icons).

Sử dụng Pillow vẽ icon vector sắc nét (antialiased bằng supersampling) thành CTkImage.
Hỗ trợ đầy đủ các trạng thái active (Cyan #00C6FF), default (Slate-400 #94A3B8), và màu sắc thái.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

import customtkinter as ctk
from PIL import Image, ImageDraw

from .theme import (
    STITCH_AMBER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_SUCCESS,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
)

_CANVAS_SIZE = 64  # Vẽ ở độ phân giải 64x64 rồi resize supersample


def _new_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (_CANVAS_SIZE, _CANVAS_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    return img, draw


@lru_cache(maxsize=128)
def _get_pil_icon(name: str, color_hex: str, size: tuple[int, int]) -> Image.Image:
    img, draw = _new_canvas()

    if name == "dashboard":
        # 4 ô vuông góc tròn 2x2 grid
        draw.rounded_rectangle([8, 8, 28, 28], radius=4, outline=color_hex, width=5)
        draw.rounded_rectangle([36, 8, 56, 28], radius=4, outline=color_hex, width=5)
        draw.rounded_rectangle([8, 36, 28, 56], radius=4, outline=color_hex, width=5)
        draw.rounded_rectangle([36, 36, 56, 56], radius=4, outline=color_hex, width=5)

    elif name == "customers":
        # Người dùng silhouette đôi
        # Người chính
        draw.ellipse([22, 10, 42, 30], outline=color_hex, width=5)
        draw.arc([10, 34, 54, 70], start=190, end=350, fill=color_hex, width=5)
        # Người phụ phía sau
        draw.ellipse([38, 14, 52, 28], outline=color_hex, width=4)
        draw.arc([30, 36, 62, 64], start=210, end=330, fill=color_hex, width=4)

    elif name == "machines":
        # Màn hình máy tính + chân đế
        draw.rounded_rectangle([8, 10, 56, 44], radius=4, outline=color_hex, width=5)
        # Chân đế
        draw.line([32, 44, 32, 54], fill=color_hex, width=5)
        draw.line([20, 54, 44, 54], fill=color_hex, width=5)

    elif name == "invoices":
        # Tờ hóa đơn với các đường ngang
        draw.rounded_rectangle([12, 8, 52, 56], radius=4, outline=color_hex, width=5)
        draw.line([20, 22, 44, 22], fill=color_hex, width=4)
        draw.line([20, 32, 44, 32], fill=color_hex, width=4)
        draw.line([20, 42, 36, 42], fill=color_hex, width=4)

    elif name == "reports":
        # Biểu đồ cột / đường xu hướng tăng
        draw.line([10, 54, 54, 54], fill=color_hex, width=4)
        draw.line([10, 10, 10, 54], fill=color_hex, width=4)
        draw.rectangle([16, 34, 24, 52], fill=color_hex)
        draw.rectangle([28, 24, 36, 52], fill=color_hex)
        draw.rectangle([40, 14, 48, 52], fill=color_hex)

    elif name == "refresh":
        # Hai mũi tên xoay tròn
        draw.arc([12, 12, 52, 52], start=45, end=270, fill=color_hex, width=5)
        draw.polygon([(46, 20), (56, 32), (38, 34)], fill=color_hex)

    elif name == "search":
        # Kính lúp
        draw.ellipse([12, 12, 40, 40], outline=color_hex, width=5)
        draw.line([34, 34, 54, 54], fill=color_hex, width=6)

    elif name == "store":
        # Biểu tượng cửa hàng / chi nhánh
        draw.polygon([(8, 24), (32, 10), (56, 24)], outline=color_hex, fill=None)
        draw.rectangle([12, 24, 52, 52], outline=color_hex, width=4)
        draw.rectangle([26, 34, 38, 52], outline=color_hex, width=4)

    elif name == "logout":
        # Cửa và mũi tên thoát ra
        draw.rectangle([12, 10, 38, 54], outline=color_hex, width=5)
        draw.line([28, 32, 54, 32], fill=color_hex, width=5)
        draw.polygon([(46, 24), (56, 32), (46, 40)], fill=color_hex)

    elif name == "check":
        # Dấu tick hoàn thành
        draw.line([14, 34, 26, 46], fill=color_hex, width=6)
        draw.line([26, 46, 50, 18], fill=color_hex, width=6)

    elif name == "clock":
        # Đồng hồ
        draw.ellipse([10, 10, 54, 54], outline=color_hex, width=5)
        draw.line([32, 32, 32, 18], fill=color_hex, width=5)
        draw.line([32, 32, 44, 32], fill=color_hex, width=5)

    elif name == "history":
        # Đồng hồ lịch sử có mũi tên xoay tròn ngược chiều kim đồng hồ (Stitch history)
        draw.arc([10, 10, 54, 54], start=45, end=330, fill=color_hex, width=5)
        draw.polygon([(46, 16), (56, 26), (42, 30)], fill=color_hex)
        draw.line([32, 32, 32, 20], fill=color_hex, width=5)
        draw.line([32, 32, 42, 32], fill=color_hex, width=5)

    elif name == "wrench" or name == "build":
        # Cờ lê bảo trì
        draw.line([18, 46, 44, 20], fill=color_hex, width=8)
        draw.ellipse([36, 12, 54, 30], outline=color_hex, width=5)

    elif name == "users":
        # Nhóm người dùng online
        draw.ellipse([18, 14, 32, 28], fill=color_hex)
        draw.arc([10, 32, 40, 58], start=180, end=360, fill=color_hex, width=5)
        draw.ellipse([36, 18, 48, 30], fill=color_hex)
        draw.arc([28, 34, 56, 56], start=200, end=340, fill=color_hex, width=4)

    elif name == "play":
        # Mũi tên tam giác mở phiên
        draw.polygon([(20, 14), (50, 32), (20, 50)], fill=color_hex)

    elif name == "lock":
        # Ổ khóa đóng
        draw.arc([20, 12, 44, 36], start=180, end=360, fill=color_hex, width=5)
        draw.rounded_rectangle([14, 28, 50, 54], radius=4, fill=color_hex)

    elif name == "unlock":
        # Ổ khóa mở
        draw.arc([26, 10, 50, 34], start=160, end=340, fill=color_hex, width=5)
        draw.rounded_rectangle([14, 28, 50, 54], radius=4, fill=color_hex)

    elif name == "edit":
        # Bút chì chỉnh sửa
        draw.line([16, 48, 44, 20], fill=color_hex, width=6)
        draw.polygon([(12, 52), (16, 42), (22, 48)], fill=color_hex)
        draw.line([42, 18, 48, 24], fill=color_hex, width=6)

    elif name == "wallet":
        # Ví tiền
        draw.rounded_rectangle([10, 16, 54, 50], radius=5, outline=color_hex, width=5)
        draw.rounded_rectangle([34, 26, 54, 40], radius=3, fill=color_hex)
        draw.ellipse([38, 31, 42, 35], fill="#0E131E")

    elif name == "close":
        # Dấu X
        draw.line([16, 16, 48, 48], fill=color_hex, width=5)
        draw.line([48, 16, 16, 48], fill=color_hex, width=5)

    elif name == "add":
        # Dấu cộng
        draw.line([32, 16, 32, 48], fill=color_hex, width=6)
        draw.line([16, 32, 48, 32], fill=color_hex, width=6)

    elif name == "add_circle":
        # Dấu cộng nằm trong vòng tròn (Stitch add_circle)
        draw.ellipse([8, 8, 56, 56], outline=color_hex, width=5)
        draw.line([32, 20, 32, 44], fill=color_hex, width=5)
        draw.line([20, 32, 44, 32], fill=color_hex, width=5)

    elif name == "alert":
        # Tam giác cảnh báo
        draw.polygon([(32, 12), (10, 52), (54, 52)], outline=color_hex)
        draw.line([(32, 12), (10, 52)], fill=color_hex, width=5)
        draw.line([(10, 52), (54, 52)], fill=color_hex, width=5)
        draw.line([(54, 52), (32, 12)], fill=color_hex, width=5)
        draw.line([32, 24, 32, 38], fill=color_hex, width=4)
        draw.ellipse([30, 42, 34, 46], fill=color_hex)

    elif name == "user":
        # Một người dùng silhouette
        draw.ellipse([20, 10, 44, 34], outline=color_hex, width=5)
        draw.arc([10, 36, 54, 76], start=190, end=350, fill=color_hex, width=5)

    else:
        # Chấm tròn mặc định
        draw.ellipse([22, 22, 42, 42], fill=color_hex)

    # Downsample về kích thước mong muốn với chất lượng cao
    return img.resize(size, Image.Resampling.LANCZOS)


def get_icon(
    name: str,
    color: str | None = None,
    size: tuple[int, int] = (16, 16),
) -> ctk.CTkImage:
    """Lấy icon vector theo tên và màu chỉ định."""
    pil_img = _get_pil_icon(name, color or STITCH_CYAN, size)
    return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)


def get_nav_icon(key: str, active: bool = False, size: tuple[int, int] = (16, 16)) -> ctk.CTkImage:
    """Lấy icon tương ứng cho 5 mục menu điều hướng Stitch."""
    color = STITCH_CYAN if active else STITCH_TEXT_MUTED
    mapping = {
        "dashboard": "dashboard",
        "customers": "customers",
        "machines": "machines",
        "invoices": "invoices",
        "reports": "reports",
    }
    icon_name = mapping.get(key, "dashboard")
    pil_img = _get_pil_icon(icon_name, color, size)
    return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)

