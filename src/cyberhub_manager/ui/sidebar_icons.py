"""Consistent outline navigation icons, rendered at 4x for crisp desktop scaling."""

from __future__ import annotations

import customtkinter as ctk
from PIL import Image, ImageDraw

from .theme import STITCH_NAV_ICON_SIZE


def sidebar_icon(name: str, color: str, size: int = STITCH_NAV_ICON_SIZE) -> ctk.CTkImage:
    image = Image.new("RGBA", (size * 4, size * 4))
    draw = ImageDraw.Draw(image)
    scale = size * 4 / 24
    stroke = max(1, round(1.8 * scale))

    def line(points: list[tuple[float, float]]) -> None:
        draw.line([(x * scale, y * scale) for x, y in points], fill=color,
                  width=stroke, joint="curve")

    def rect(box: tuple[float, float, float, float], radius: float = 1.5) -> None:
        draw.rounded_rectangle(tuple(v * scale for v in box), radius=radius * scale,
                               outline=color, width=stroke)

    def circle(box: tuple[float, float, float, float]) -> None:
        draw.ellipse(tuple(v * scale for v in box), outline=color, width=stroke)

    if name == "dashboard":
        for box in ((3, 3, 10, 10), (14, 3, 21, 10), (3, 14, 10, 21), (14, 14, 21, 21)):
            rect(box)
    elif name == "customers":
        circle((5, 3, 12, 10))
        draw.arc(tuple(v * scale for v in (1, 13, 16, 29)), 180, 360, fill=color, width=stroke)
        line([(1, 21), (16, 21)])
        draw.arc(tuple(v * scale for v in (14, 5, 21, 12)), 245, 460, fill=color, width=stroke)
        draw.arc(tuple(v * scale for v in (13, 14, 23, 26)), 245, 360, fill=color, width=stroke)
        line([(20, 20), (23, 20)])
    elif name == "machines":
        rect((2, 4, 22, 17), 2)
        line([(12, 17), (12, 21)])
        line([(7, 21), (17, 21)])
    elif name == "invoices":
        line([(5, 3), (19, 3), (19, 22), (16, 20), (13, 22),
              (10, 20), (7, 22), (5, 20), (5, 3)])
        line([(9, 8), (15, 8)])
        line([(9, 12), (15, 12)])
        line([(9, 16), (13, 16)])
    elif name == "reports":
        line([(2, 3), (2, 22), (22, 22)])
        rect((6, 13, 9, 18), .5)
        rect((12, 9, 15, 18), .5)
        rect((18, 4, 21, 18), .5)
    elif name == "logout":
        line([(11, 3), (4, 3), (4, 21), (11, 21)])
        line([(10, 12), (22, 12)])
        line([(17, 7), (22, 12), (17, 17)])
    elif name in ("refresh", "restore"):
        draw.arc(tuple(v * scale for v in (4, 4, 20, 20)), 40, 325, fill=color, width=stroke)
        line([(19, 3), (20, 9), (14, 8)])
    elif name == "plus":
        line([(12, 4), (12, 20)])
        line([(4, 12), (20, 12)])
    elif name == "edit":
        line([(4, 16), (16, 4), (20, 8), (8, 20), (3, 21), (4, 16)])
        line([(13, 7), (17, 11)])
    elif name == "maintenance":
        line([(5, 3), (9, 7), (7, 10), (3, 6), (3, 12), (8, 15),
              (15, 22), (19, 18), (12, 11), (13, 6), (9, 3), (5, 3)])
    elif name == "archive":
        rect((3, 4, 21, 8), 1)
        rect((5, 8, 19, 21), 1)
        line([(10, 12), (14, 12)])
    elif name == "copy":
        rect((8, 7, 21, 21), 2)
        line([(16, 7), (16, 3), (3, 3), (3, 16), (8, 16)])
    elif name == "calendar":
        rect((3, 5, 21, 21), 2)
        line([(3, 10), (21, 10)])
        line([(8, 2), (8, 7)])
        line([(16, 2), (16, 7)])
        line([(8, 14), (10, 14)])
        line([(14, 14), (16, 14)])
    elif name == "money":
        rect((2, 5, 22, 19), 2)
        circle((9, 9, 15, 15))
        line([(5, 10), (5, 14)])
        line([(19, 10), (19, 14)])
    elif name == "check":
        circle((2, 2, 22, 22))
        line([(7, 12), (10, 15), (17, 8)])
    elif name == "clock":
        circle((2, 2, 22, 22))
        line([(12, 6), (12, 12), (16, 14)])
    elif name == "search":
        circle((3, 3, 17, 17))
        line([(15, 15), (22, 22)])
    else:
        raise ValueError(f"Unknown sidebar icon: {name}")
    return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
