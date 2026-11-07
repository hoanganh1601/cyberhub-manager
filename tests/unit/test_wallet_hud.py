"""Unit tests cho WalletHudCard component — Mục B: Wallet HUD.

Kiểm tra:
- Cấu trúc thẻ HUD: Nền #0C182B, viền cyan #00C6FF, bo góc 8px.
- Thanh micro-accent cyan phát sáng ở mép trên.
- Nhãn mô tả số dư ("SỐ DƯ HIỆN TẠI") kèm icon vector ví cyan.
- Typography số dư lớn (28px bold), định dạng dấu chấm phân tách hàng nghìn nhất quán.
- Đơn vị tiền tệ "VND" màu cyan đặt cạnh số dư.
- Badge trạng thái tài khoản: "KHẢ DỤNG" (xanh lục) / "NỢ CẦN THU" (đỏ hồng).
- Xử lý số dư âm, số dư 0 và trạng thái empty khi chưa chọn khách hàng.
"""

from __future__ import annotations

import customtkinter as ctk
import pytest

from cyberhub_manager.ui.components.wallet_hud import FONT_HUD_NUMBER, FONT_HUD_UNIT, WalletHudCard
from cyberhub_manager.ui.theme import (
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_SUCCESS,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
)




def test_wallet_hud_initial_structure_and_styling(tk_root) -> None:
    """Kiểm tra cấu trúc và style của thẻ HUD đúng chuẩn Stitch."""
    card = WalletHudCard(tk_root, balance=50000, language="vi")

    # 1. Thẻ container: Nền navy sâu #0C182B, viền cyan #00C6FF, bo góc 8
    assert card.cget("fg_color") == "#0C182B"
    assert card.cget("border_color") == "#00C6FF"
    assert card.cget("border_width") == 1
    assert card.cget("corner_radius") == 8

    # 2. Thanh viền phát sáng mép trên (Top Glow Bar)
    assert card._glow_bar.cget("fg_color") == "#00C6FF"
    assert card._glow_bar.cget("height") == 2

    # 3. Nhãn mô tả số dư kèm icon ví cyan
    assert card._desc_label.cget("text") == "SỐ DƯ HIỆN TẠI"
    assert card._desc_label.cget("text_color") == STITCH_CYAN

    # 4. Badge trạng thái khả dụng
    assert card._status_badge.cget("text") == "KHẢ DỤNG"
    assert card._status_badge.cget("text_color") == STITCH_SUCCESS
    assert card._status_badge.cget("fg_color") == "#0A2918"

    # 5. Typography số dư lớn và đơn vị VND cyan
    assert card._num_label.cget("font") == FONT_HUD_NUMBER
    assert card._num_label.cget("text") == "50.000"
    assert card._num_label.cget("text_color") == STITCH_TEXT_STRONG

    assert card._unit_label.cget("font") == FONT_HUD_UNIT
    assert card._unit_label.cget("text") == "VND"
    assert card._unit_label.cget("text_color") == STITCH_CYAN

    card.destroy()


def test_wallet_hud_money_formatting(tk_root) -> None:
    """Kiểm tra định dạng tiền tệ với các giá trị khác nhau."""
    card = WalletHudCard(tk_root, balance=0, language="vi")

    # Số 0
    assert card._num_label.cget("text") == "0"
    assert card.balance == 0

    # Số lớn
    card.set_balance(1250000)
    assert card._num_label.cget("text") == "1.250.000"
    assert card.balance == 1250000

    # Số lẻ hàng trăm
    card.set_balance(25500)
    assert card._num_label.cget("text") == "25.500"

    card.destroy()


def test_wallet_hud_negative_balance_alert(tk_root) -> None:
    """Khi số dư âm (nợ), thẻ chuyển phong cách cảnh báo đỏ hồng."""
    card = WalletHudCard(tk_root, balance=-5000, language="vi")

    # 1. Số tiền âm có dấu trừ và màu đỏ rose
    assert card._num_label.cget("text") == "-5.000"
    assert card._num_label.cget("text_color") == STITCH_DANGER

    # 2. Badge đổi sang "NỢ CẦN THU" với màu đỏ rose
    assert card._status_badge.cget("text") == "NỢ CẦN THU"
    assert card._status_badge.cget("text_color") == STITCH_DANGER
    assert card._status_badge.cget("fg_color") == "#331317"

    # 3. Viền và thanh glow đổi sang màu đỏ rose cảnh báo
    assert card.cget("border_color") == STITCH_DANGER
    assert card._glow_bar.cget("fg_color") == STITCH_DANGER

    # 4. Dòng cảnh báo nợ phụ hiển thị
    assert "⚠" in card._alert_label.cget("text")

    card.destroy()


def test_wallet_hud_empty_state(tk_root) -> None:
    """Khi chưa chọn khách hàng (empty state), thẻ chuyển sang muted."""
    card = WalletHudCard(tk_root, balance=None, language="vi")

    assert card.is_empty is True
    assert card.balance is None

    # Số tiền hiển thị 0 mờ
    assert card._num_label.cget("text") == "0"
    assert card._num_label.cget("text_color") == STITCH_TEXT_MUTED
    assert card._unit_label.cget("text_color") == STITCH_TEXT_MUTED

    # Badge chuyển sang "KHÔNG KHẢ DỤNG"
    assert card._status_badge.cget("text") == "KHÔNG KHẢ DỤNG"
    assert card._status_badge.cget("text_color") == STITCH_TEXT_MUTED

    # Viền và thanh glow chuyển sang màu xám mờ #27344E
    assert card.cget("border_color") == "#27344E"
    assert card._glow_bar.cget("fg_color") == "#27344E"

    card.destroy()


def test_wallet_hud_dynamic_state_transitions(tk_root) -> None:
    """Kiểm tra chuyển đổi trạng thái liên tục: Empty -> Dương -> Âm -> Empty."""
    card = WalletHudCard(tk_root, balance=None, language="vi")
    assert card.is_empty is True

    # 1. Chuyển sang có số dư dương
    card.set_balance(100000)
    assert card.is_empty is False
    assert card.balance == 100000
    assert card._num_label.cget("text") == "100.000"
    assert card._num_label.cget("text_color") == STITCH_TEXT_STRONG
    assert card._status_badge.cget("text") == "KHẢ DỤNG"
    assert card.cget("border_color") == "#00C6FF"

    # 2. Chuyển sang số dư âm
    card.set_balance(-20000)
    assert card.is_empty is False
    assert card.balance == -20000
    assert card._num_label.cget("text") == "-20.000"
    assert card._num_label.cget("text_color") == STITCH_DANGER
    assert card._status_badge.cget("text") == "NỢ CẦN THU"
    assert card.cget("border_color") == STITCH_DANGER

    # 3. Chuyển về empty
    card.set_empty()
    assert card.is_empty is True
    assert card._num_label.cget("text") == "0"
    assert card._num_label.cget("text_color") == STITCH_TEXT_MUTED
    assert card.cget("border_color") == "#27344E"

    card.destroy()

