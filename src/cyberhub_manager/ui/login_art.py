"""Local artwork for Login: scalable circuit canvas and antialiased outline icons.

No webview, icon font, network request or external icon package is needed at runtime.
"""

from __future__ import annotations

import math
import tkinter as tk
from importlib.resources import files
from typing import Any

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from . import theme as t


def icon_image(name: str, color: str, size: int = 18, *, angle: int = 0) -> ctk.CTkImage:
    """Draw 24-unit outline icons at 4x resolution, then downsample for HiDPI."""
    image = Image.new("RGBA", (size * 4, size * 4))
    draw = ImageDraw.Draw(image)
    scale = size * 4 / 24

    def line(points: list[tuple[float, float]]) -> None:
        draw.line([(x * scale, y * scale) for x, y in points], fill=color,
                  width=max(1, round(1.7 * scale)), joint="curve")

    def oval(box: tuple[float, float, float, float]) -> None:
        draw.ellipse(tuple(v * scale for v in box), outline=color, width=max(1, round(1.7 * scale)))

    if name == "user":
        oval((8, 3, 16, 11))
        draw.arc((5 * scale, 14 * scale, 19 * scale, 28 * scale), 180, 360,
                 fill=color, width=round(1.7 * scale))
        line([(5, 21), (19, 21)])
    elif name == "lock":
        draw.rounded_rectangle(tuple(v * scale for v in (5, 10, 19, 21)), radius=2 * scale,
                               outline=color, width=round(1.7 * scale))
        draw.arc((8 * scale, 2 * scale, 16 * scale, 15 * scale), 180, 360,
                 fill=color, width=round(1.7 * scale))
        line([(8, 8), (8, 10)])
        line([(16, 8), (16, 10)])
        line([(12, 14), (12, 17)])
    elif name in ("eye", "eye-off"):
        line([(2, 12), (5, 8), (9, 6), (15, 6), (19, 8), (22, 12),
              (19, 16), (15, 18), (9, 18), (5, 16), (2, 12)])
        oval((9, 9, 15, 15))
        if name == "eye-off":
            line([(3, 3), (21, 21)])
    elif name == "arrow":
        line([(4, 12), (20, 12)])
        line([(14, 6), (20, 12), (14, 18)])
    elif name == "spinner":
        draw.arc(tuple(v * scale for v in (4, 4, 20, 20)), angle, angle + 265,
                 fill=color, width=round(2 * scale))
    elif name == "alert":
        line([(12, 3), (22, 21), (2, 21), (12, 3)])
        line([(12, 9), (12, 14)])
        oval((11.5, 17, 12.5, 18))
    else:
        raise ValueError(f"Unknown login icon: {name}")
    return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))


class BrandPanel(ctk.CTkFrame):
    """Paint the entire left panel, including its text, over one continuous backdrop."""

    def __init__(self, master: Any, language: str = "vi") -> None:
        super().__init__(master, fg_color=t.LOGIN_BG, corner_radius=0)
        self.language = language
        self.canvas = tk.Canvas(self, background=t.LOGIN_BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self._redraw_id: str | None = None
        self._photos: list[ImageTk.PhotoImage] = []
        logo = files("cyberhub_manager.ui.assets").joinpath("cyberhub_logo_dark.png")
        with logo.open("rb") as source:
            self._logo = Image.open(source).convert("RGBA")
        self.canvas.bind("<Configure>", self._queue_redraw)

    def set_language(self, language: str) -> None:
        self.language = language
        if self._redraw_id is not None:
            self.after_cancel(self._redraw_id)
        self._render_artwork()

    def _queue_redraw(self, _event: Any = None) -> None:
        if self._redraw_id is not None:
            self.after_cancel(self._redraw_id)
        self._redraw_id = self.after(35, self._render_artwork)

    def _render_artwork(self) -> None:
        self._redraw_id = None
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if width < 2 or height < 2:
            return
        cv = self.canvas
        cv.delete("all")
        self._photos.clear()
        # Render the two soft radial glows at low resolution; lines/text remain vectors.
        small = Image.new("RGB", (88, 90))
        pixels = small.load()
        assert pixels is not None
        for y in range(90):
            for x in range(88):
                cyan = math.exp(-(((x / 88 - .30) / .45) ** 2 + ((y / 90 - .40) / .5) ** 2) * 2)
                blue = math.exp(-(((x / 88 - .75) / .4) ** 2 + ((y / 90 - .70) / .45) ** 2) * 2)
                pixels[x, y] = (9, round(14 + cyan * 11 + blue * 3), round(25 + cyan * 13 + blue * 13))
        self._photos.append(ImageTk.PhotoImage(small.resize((width, height), Image.Resampling.BILINEAR)))
        cv.create_image(0, 0, image=self._photos[-1], anchor="nw")
        scale = min(width / 704, height / 720)
        ox, oy = (width - 704 * scale) / 2, (height - 720 * scale) / 2

        def coords(points: list[tuple[float, float]]) -> list[float]:
            return [v for x, y in points for v in (ox + x * scale, oy + y * scale)]

        def line(points: list[tuple[float, float]], color: str, dash: Any = None) -> None:
            cv.create_line(*coords(points), fill=color, width=max(1, scale), dash=dash)

        def text(x: float, y: float, content: str, size: int, color: str, bold: bool = False,
                 family: str = t.LOGIN_FONT_DISPLAY, **kwargs: Any) -> int:
            return cv.create_text(ox + x * scale, oy + y * scale, text=content, anchor="nw", fill=color,
                                  font=(family, -round(size * scale), "bold" if bold else "normal"), **kwargs)

        for x in range(0, width, max(1, round(40 * scale))):
            cv.create_line(x, 0, x, height, fill=t.LOGIN_GRID)
        for y in range(0, height, max(1, round(40 * scale))):
            cv.create_line(0, y, width, y, fill=t.LOGIN_GRID)
        paths = [
            ([(0, 160), (220, 160), (280, 220), (460, 220), (520, 280), (520, 420)], t.LOGIN_CIRCUIT, (4, 4)),
            ([(120, 720), (120, 540), (190, 470), (420, 470), (480, 410), (640, 410)], t.LOGIN_CIRCUIT_BLUE, (3, 3)),
            ([(600, 80), (640, 120), (640, 240), (680, 280)], t.LOGIN_CIRCUIT, None),
            ([(60, 480), (140, 480), (170, 510), (170, 620)], t.LOGIN_CIRCUIT_BLUE, None),
        ]
        for points, color, dash in paths:
            line(points, color, dash)
            for x, y in points[1:-1]:
                r = 3 * scale
                cx, cy = ox + x * scale, oy + y * scale
                cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="")
        # Float the transparent logo directly over the circuit backdrop.
        # Its larger footprint stays above the badge at every supported window size.
        logo = self._logo.copy()
        logo.thumbnail((round(344 * scale), round(144 * scale)), Image.Resampling.LANCZOS)
        self._photos.append(ImageTk.PhotoImage(logo))
        cv.create_image(ox + 48 * scale, oy + 148 * scale, image=self._photos[-1], anchor="nw")

        vi = self.language == "vi"
        badge = "PHẦN MỀM QUẢN LÝ PHÒNG MÁY" if vi else "CYBERCAFE MANAGEMENT SYSTEM"
        badge_id = text(58, 316, badge, 11, t.LOGIN_PRIMARY)
        box = cv.bbox(badge_id)
        if box:
            rect = cv.create_rectangle(box[0] - 9 * scale, box[1] - 5 * scale,
                                       box[2] + 9 * scale, box[3] + 5 * scale,
                                       fill=t.LOGIN_BADGE_BG, outline=t.LOGIN_BADGE_BORDER)
            cv.tag_lower(rect, badge_id)
        title_id = text(48, 352, "CyberHub", 36, t.LOGIN_WHITE, True)
        box = cv.bbox(title_id)
        title_width = (box[2] - box[0]) / scale if box else 176
        text(48 + title_width + 9, 352, "Manager", 36, t.LOGIN_PRIMARY, True)
        text(48, 405, "Hệ thống quản lý phòng máy chuyên nghiệp" if vi else
             "Professional cybercafe management, in one place.", 17, t.LOGIN_MUTED, family=t.LOGIN_FONT_FAMILY)
        line([(48, 461), (592, 461)], t.LOGIN_BORDER)
        features = (
            ("Kiểm soát phiên thời gian thực", "Real-time session control"),
            ("Biểu phí & Nạp tiền chuẩn xác", "Accurate tariffs & top-ups"),
            ("Đồng bộ 20 máy trạm tức thì", "Instant 20-station sync"),
            ("Độ trễ phản hồi dưới 15ms", "Sub-15ms response latency"),
        )
        for index, labels in enumerate(features):
            x, y = 48 + index % 2 * 278, 482 + index // 2 * 28
            color = t.LOGIN_PRIMARY
            if index in (0, 1):
                cx, cy = ox + (x + 7) * scale, oy + (y + 7) * scale
                r = 6 * scale
                cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=max(1, scale))
                if index == 0:
                    line([(x + 4, y + 7), (x + 6, y + 9), (x + 10, y + 5)], color)
                else:
                    text(x + 4, y, "$", 11, color)
            elif index == 2:
                cv.create_rectangle(*coords([(x + 1, y + 2), (x + 14, y + 11)]), outline=color)
                line([(x + 7, y + 11), (x + 7, y + 15)], color)
                line([(x + 4, y + 15), (x + 11, y + 15)], color)
            else:
                line([(x + 9, y), (x + 2, y + 8), (x + 7, y + 8),
                      (x + 5, y + 15), (x + 13, y + 6), (x + 8, y + 6), (x + 9, y)], color)
            text(x + 24, y, labels[0 if vi else 1], 11, t.LOGIN_MUTED)
        cv.create_text(ox + 48 * scale, height - 48 * scale, text="© 2026 CyberHub Manager",
                       anchor="sw", fill=t.LOGIN_DIM, font=(t.LOGIN_FONT_DISPLAY, -round(11 * scale)))

    def destroy(self) -> None:
        if self._redraw_id is not None:
            self.after_cancel(self._redraw_id)
        super().destroy()
