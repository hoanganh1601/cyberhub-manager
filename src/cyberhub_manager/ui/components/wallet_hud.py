"""WalletHudCard component cho CyberHub Manager theo chuẩn Google Stitch.

Hiển thị số dư ví khách hàng dạng thẻ HUD công nghệ cao (High Contrast Glowing HUD):
- Nền xanh navy sâu (#0C182B), viền cyan phát sáng (#00C6FF), bo góc 8px.
- Thanh micro-accent cyan trang trí tinh tế ở cạnh trên.
- Nhãn mô tả số dư ("SỐ DƯ HIỆN TẠI") đi kèm biểu tượng ví vector cyan.
- Badge trạng thái tài khoản ("KHẢ DỤNG" xanh lục hoặc "NỢ CẦN THU" đỏ hồng).
- Số dư là thành phần nổi bật nhất: Typography cỡ lớn (28px bold), phân tách hàng nghìn bằng dấu chấm.
- Đơn vị "VND" màu cyan đặt cạnh số dư chuẩn theo Stitch.
"""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ..formatters import format_money
from ..icons import get_icon
from ..theme import (
    FONT_FAMILY,
    FONT_ST_MONO_XS,
    FONT_ST_MONO_XS_STRONG,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_SUCCESS,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
)

FONT_HUD_NUMBER = (FONT_FAMILY, 28, "bold")
FONT_HUD_UNIT = (FONT_FAMILY, 13, "bold")


class WalletHudCard(ctk.CTkFrame):
    """Thẻ HUD hiển thị số dư ví công nghệ cao theo thiết kế Stitch."""

    def __init__(
        self,
        master: Any,
        balance: int | None = 0,
        *,
        language: str = "vi",
        status_text: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._language = language
        self._balance = balance
        self._is_empty = (balance is None)

        super().__init__(
            master=master,
            fg_color="#0C182B",
            border_width=1,
            border_color="#00C6FF",
            corner_radius=8,
            **kwargs,
        )

        self._build_ui(status_text)
        if self._is_empty:
            self.set_empty()
        else:
            self.set_balance(balance, status_text)

    def _build_ui(self, status_text: str | None) -> None:
        is_vi = self._language == "vi"

        # 1. Thanh viền trang trí micro-accent phát sáng ở mép trên (Top Glow Strip)
        self._glow_bar = ctk.CTkFrame(
            self,
            height=2,
            fg_color="#00C6FF",
            corner_radius=1,
        )
        self._glow_bar.pack(fill="x", padx=12, pady=(3, 0))

        # 2. Khung nội dung chính với padding chuẩn p-3 (12px)
        self._inner = ctk.CTkFrame(self, fg_color="transparent")
        self._inner.pack(fill="both", expand=True, padx=12, pady=(6, 10))

        # 3. Hàng tiêu đề: Icon ví + Nhãn mô tả + Badge khả dụng
        self._header_row = ctk.CTkFrame(self._inner, fg_color="transparent")
        self._header_row.pack(fill="x", pady=(0, 4))

        # Left box: Icon ví vector + Nhãn SỐ DƯ HIỆN TẠI
        title_box = ctk.CTkFrame(self._header_row, fg_color="transparent")
        title_box.pack(side="left")

        self._icon_lbl = ctk.CTkLabel(
            title_box,
            text="",
            image=get_icon("wallet", STITCH_CYAN, size=(13, 13)),
        )
        self._icon_lbl.pack(side="left", padx=(0, 5))

        self._desc_label = ctk.CTkLabel(
            title_box,
            text="SỐ DƯ HIỆN TẠI" if is_vi else "CURRENT BALANCE",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_CYAN,
        )
        self._desc_label.pack(side="left")

        # Right box: Badge trạng thái KHẢ DỤNG / NỢ CẦN THU / KHÔNG KHẢ DỤNG
        self._status_badge = ctk.CTkLabel(
            self._header_row,
            text="KHẢ DỤNG" if is_vi else "AVAILABLE",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_SUCCESS,
            fg_color="#0A2918",
            corner_radius=4,
            padx=7,
            pady=2,
        )
        self._status_badge.pack(side="right")

        # 4. Hàng số liệu chính (Metric Showcase): Số tiền lớn + Đơn vị VND cyan
        self._metric_row = ctk.CTkFrame(self._inner, fg_color="transparent")
        self._metric_row.pack(fill="x", anchor="w", pady=(2, 0))

        self._num_label = ctk.CTkLabel(
            self._metric_row,
            text="0",
            font=FONT_HUD_NUMBER,
            text_color=STITCH_TEXT_STRONG,
            anchor="w",
        )
        self._num_label.pack(side="left")

        self._unit_label = ctk.CTkLabel(
            self._metric_row,
            text="VND",
            font=FONT_HUD_UNIT,
            text_color=STITCH_CYAN,
            anchor="s",
        )
        self._unit_label.pack(side="left", padx=(6, 0), pady=(0, 3))

        # 5. Dòng cảnh báo nợ phụ (chỉ hiển thị khi số dư âm)
        self._alert_row = ctk.CTkFrame(self._inner, fg_color="transparent")
        self._alert_label = ctk.CTkLabel(
            self._alert_row,
            text="",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_DANGER,
            anchor="w",
        )
        self._alert_label.pack(side="left")

    # ------------------------------------------------------------------
    # Public Methods
    # ------------------------------------------------------------------
    def set_balance(self, amount: int | None, status: str | None = None) -> None:
        """Cập nhật số dư và giao diện thẻ HUD."""
        if amount is None:
            self.set_empty()
            return

        self._balance = amount
        self._is_empty = False
        is_vi = self._language == "vi"

        # Định dạng số tiền
        if amount < 0:
            formatted_num = f"-{abs(amount):,}".replace(",", ".")
            num_color = STITCH_DANGER
            default_badge = "NỢ CẦN THU" if is_vi else "OVERDUE"
            badge_fg = STITCH_DANGER
            badge_bg = "#331317"
            self._alert_label.configure(
                text="⚠ Tài khoản nợ cước phiên chơi" if is_vi else "⚠ Overdue account balance"
            )
            self._alert_row.pack(fill="x", pady=(2, 0))
            self._glow_bar.configure(fg_color=STITCH_DANGER)
            self.configure(border_color=STITCH_DANGER)
        else:
            formatted_num = f"{amount:,}".replace(",", ".")
            num_color = STITCH_TEXT_STRONG
            default_badge = "KHẢ DỤNG" if is_vi else "AVAILABLE"
            badge_fg = STITCH_SUCCESS
            badge_bg = "#0A2918"
            self._alert_row.pack_forget()
            self._glow_bar.configure(fg_color="#00C6FF")
            self.configure(border_color="#00C6FF")

        badge_text = status if status is not None else default_badge

        self._num_label.configure(text=formatted_num, text_color=num_color)
        self._unit_label.configure(text="VND", text_color=STITCH_CYAN)
        self._status_badge.configure(
            text=badge_text,
            text_color=badge_fg,
            fg_color=badge_bg,
        )

    def set_empty(self) -> None:
        """Chuyển thẻ sang trạng thái chưa chọn khách hàng."""
        self._balance = None
        self._is_empty = True
        is_vi = self._language == "vi"

        self._num_label.configure(text="0", text_color=STITCH_TEXT_MUTED)
        self._unit_label.configure(text="VND", text_color=STITCH_TEXT_MUTED)
        self._status_badge.configure(
            text="KHÔNG KHẢ DỤNG" if is_vi else "N/A",
            text_color=STITCH_TEXT_MUTED,
            fg_color="#171F30",
        )
        self._alert_row.pack_forget()
        self._glow_bar.configure(fg_color="#27344E")
        self.configure(border_color="#27344E")

    @property
    def balance(self) -> int | None:
        """Lấy giá trị số dư hiện tại."""
        return self._balance

    @property
    def is_empty(self) -> bool:
        """Kiểm tra thẻ có đang ở trạng thái rỗng không."""
        return self._is_empty

