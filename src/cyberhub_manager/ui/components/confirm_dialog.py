"""ConfirmDialog component cho CyberHub Manager.

Quy định: docs/07_DTO_UI_HANDOFF.md mục 7 và docs/03_UI_THEME.md mục 3.4.
- API: ConfirmDialog.ask(parent, title: str, message: str, ...) -> bool.
- Gọi từ UI thread, modal chặn tương tác cửa sổ cha, không trực tiếp thực hiện nghiệp vụ.
"""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ..theme import (
    BG_APP,
    BG_SURFACE,
    BORDER,
    FONT_BODY,
    FONT_BODY_STRONG,
    FONT_TITLE_MD,
    HEIGHT_BUTTON,
    PADDING_CONTENT,
    RADIUS_DIALOG,
    SPACING_MD,
    SPACING_SM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from .action_button import ActionButton


class ConfirmDialog(ctk.CTkToplevel):
    """Hộp thoại modal: xác nhận thao tác (ConfirmDialog) hoặc cảnh báo lỗi (AlertDialog)."""

    def __init__(
        self,
        parent: Any,
        title: str,
        message: str,
        *,
        confirm_label: str = "Confirm",
        cancel_label: str | None = "Cancel",
        is_danger: bool = False,
    ) -> None:
        super().__init__(parent)
        self._result = False

        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=BG_APP)

        # Cài đặt modal
        self.transient(parent)
        self.grab_set()

        # Frame chứa nội dung
        container = ctk.CTkFrame(
            self,
            fg_color=BG_SURFACE,
            corner_radius=RADIUS_DIALOG,
            border_width=1,
            border_color=BORDER,
        )
        container.pack(fill="both", expand=True, padx=SPACING_SM, pady=SPACING_SM)

        # Tiêu đề
        title_label = ctk.CTkLabel(
            container,
            text=title,
            font=FONT_TITLE_MD,
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        title_label.pack(fill="x", padx=PADDING_CONTENT, pady=(PADDING_CONTENT, SPACING_SM))

        # Nội dung thông điệp
        message_label = ctk.CTkLabel(
            container,
            text=message,
            font=FONT_BODY,
            text_color=TEXT_SECONDARY,
            anchor="w",
            justify="left",
            wraplength=400,
        )
        message_label.pack(fill="x", padx=PADDING_CONTENT, pady=(0, PADDING_CONTENT))

        # Hàng nút bấm ở dưới
        button_row = ctk.CTkFrame(container, fg_color="transparent")
        button_row.pack(fill="x", padx=PADDING_CONTENT, pady=(0, PADDING_CONTENT))

        if cancel_label is not None:
            self._cancel_btn = ActionButton(
                button_row,
                text=cancel_label,
                kind="secondary",
                width=100,
                command=self._on_cancel,
            )
            self._cancel_btn.pack(side="right", padx=(SPACING_SM, 0))
        else:
            self._cancel_btn = None

        confirm_kind = "danger" if is_danger else "primary"
        self._confirm_btn = ActionButton(
            button_row,
            text=confirm_label,
            kind=confirm_kind,
            width=110,
            command=self._on_confirm,
        )
        self._confirm_btn.pack(side="right")

        # Định vị giữa cửa sổ cha
        self.update_idletasks()
        self._center_window(parent)

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _center_window(self, parent: Any) -> None:
        """Căn giữa dialog so với cửa sổ cha."""
        width = 460
        height = self.winfo_reqheight()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    def _on_confirm(self) -> None:
        self._result = True
        self.grab_release()
        self.destroy()

    def _on_cancel(self) -> None:
        self._result = False
        self.grab_release()
        self.destroy()

    @classmethod
    def ask(
        cls,
        parent: Any,
        title: str,
        message: str,
        *,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        is_danger: bool = False,
    ) -> bool:
        """Hiển thị hộp thoại modal và chặn cho tới khi người dùng phản hồi.

        Returns:
            True nếu người dùng chọn Xác nhận; False nếu chọn Hủy hoặc đóng hộp thoại.
        """
        dialog = cls(
            parent,
            title=title,
            message=message,
            confirm_label=confirm_label,
            cancel_label=cancel_label,
            is_danger=is_danger,
        )
        if hasattr(parent, "wait_window"):
            try:
                parent.wait_window(dialog)
            except Exception:
                pass
        return dialog._result

    @classmethod
    def alert(
        cls,
        parent: Any,
        title: str,
        message: str,
        *,
        button_label: str = "Close",
        is_danger: bool = True,
    ) -> None:
        """Hiển thị hộp thoại cảnh báo / báo lỗi modal (1 nút đóng).

        Dùng cho business conflict hoặc lỗi nghiêm trọng theo quy chuẩn docs/03_UI_THEME.md mục 3.4.
        """
        # Nếu parent là Mock hoặc không có Tkinter runtime thật, bỏ qua để không lỗi trong unit test
        if getattr(parent, "tk", None) is None:
            return

        dialog = cls(
            parent,
            title=title,
            message=message,
            confirm_label=button_label,
            cancel_label=None,
            is_danger=is_danger,
        )
        if hasattr(parent, "wait_window"):
            try:
                parent.wait_window(dialog)
            except Exception:
                pass
