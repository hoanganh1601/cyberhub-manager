"""DataTable component cho CyberHub Manager.

Quy định: docs/07_DTO_UI_HANDOFF.md mục 7 và docs/03_UI_THEME.md mục 3.4.
- Cấu trúc: TableColumn(key, label, align), TableRow(key, cells).
- API: set_columns(columns), set_rows(rows), set_state(state, message=None, on_retry=None), set_on_select(callback).
- Trạng thái qua ViewState: LOADING, READY, EMPTY, ERROR.
- Cột tiền căn phải; callback nhận row key (ID ổn định), không nhận vị trí dòng.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import customtkinter as ctk

from ..state import ViewState
from ..theme import (
    BG_ROW_ALT,
    BG_SURFACE,
    BG_SURFACE_HOVER,
    BG_TABLE_HEADER,
    BORDER,
    DANGER,
    FONT_BODY,
    FONT_BODY_STRONG,
    FONT_CAPTION,
    RADIUS_INPUT,
    SPACING_MD,
    SPACING_SM,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from .action_button import ActionButton


@dataclass(frozen=True)
class TableColumn:
    """Cấu trúc định nghĩa một cột của bảng."""

    key: str
    label: str
    align: str = "left"  # "left", "right", "center"
    width: int = 120


@dataclass(frozen=True)
class TableRow:
    """Cấu trúc dữ liệu hiển thị một dòng của bảng."""

    key: int | str
    cells: dict[str, str] = field(default_factory=dict)


class DataTable(ctk.CTkFrame):
    """Bảng dữ liệu chuẩn hỗ trợ phân cột, hover dòng, chọn dòng và 4 trạng thái ViewState."""

    def __init__(
        self,
        master: Any,
        columns: list[TableColumn] | None = None,
        rows: list[TableRow] | None = None,
        *,
        on_select: Callable[[int | str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master=master,
            fg_color=BG_SURFACE,
            border_width=1,
            border_color=BORDER,
            corner_radius=RADIUS_INPUT,
            **kwargs,
        )
        self._columns: list[TableColumn] = columns or []
        self._rows: list[TableRow] = rows or []
        self._state: ViewState = ViewState.READY
        self._on_select: Callable[[int | str], None] | None = on_select
        self._selected_key: int | str | None = None
        self._row_frames: dict[int | str, ctk.CTkFrame] = {}

        # 1. Header frame cố định phía trên
        self._header_frame = ctk.CTkFrame(
            self,
            fg_color=BG_TABLE_HEADER,
            corner_radius=0,
            height=40,
        )
        self._header_frame.pack(fill="x", side="top")

        # 2. Body scrollable chứa các dòng hoặc thông báo trạng thái
        self._body_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
        )
        self._body_frame.pack(fill="both", expand=True, side="top")

        # 3. Message overlay cho trạng thái LOADING / EMPTY / ERROR
        self._status_frame = ctk.CTkFrame(self._body_frame, fg_color="transparent")

        self._render_header()
        if self._rows:
            self._render_rows()
        else:
            self.set_state(ViewState.EMPTY)

    @property
    def selected_key(self) -> int | str | None:
        """Key của dòng đang được chọn."""
        return self._selected_key

    def set_columns(self, columns: list[TableColumn]) -> None:
        """Thiết lập danh sách cột và vẽ lại header."""
        self._columns = list(columns)
        self._render_header()
        if self._state == ViewState.READY:
            self._render_rows()

    def set_rows(self, rows: list[TableRow]) -> None:
        """Cập nhật dữ liệu các dòng. Tự động chuyển sang READY nếu có dữ liệu, EMPTY nếu rỗng."""
        self._rows = list(rows)
        # Nếu dòng đang chọn không còn tồn tại trong danh sách mới, hủy chọn
        if self._selected_key is not None and self._selected_key not in {r.key for r in self._rows}:
            self._selected_key = None

        if not self._rows:
            self.set_state(ViewState.EMPTY)
        else:
            self._state = ViewState.READY
            self._render_rows()

    def set_state(
        self,
        state: ViewState,
        message: str | None = None,
        on_retry: Callable[[], None] | None = None,
    ) -> None:
        """Đặt trạng thái hiển thị của bảng: LOADING, READY, EMPTY, ERROR."""
        self._state = state
        self._clear_body()

        if state == ViewState.READY:
            self._render_rows()
            return

        # Hiển thị frame thông điệp trạng thái
        self._status_frame = ctk.CTkFrame(self._body_frame, fg_color="transparent")
        self._status_frame.pack(fill="both", expand=True, pady=40)

        if state == ViewState.LOADING:
            text = message or "Loading data…"
            label = ctk.CTkLabel(
                self._status_frame,
                text=f"⏳  {text}",
                font=FONT_BODY,
                text_color=TEXT_SECONDARY,
            )
            label.pack(pady=20)

        elif state == ViewState.EMPTY:
            text = message or "No matching data found"
            label = ctk.CTkLabel(
                self._status_frame,
                text=f"📋  {text}",
                font=FONT_BODY,
                text_color=TEXT_MUTED,
            )
            label.pack(pady=20)

        elif state == ViewState.ERROR:
            text = message or "Unable to load data"
            label = ctk.CTkLabel(
                self._status_frame,
                text=f"⚠  {text}",
                font=FONT_BODY,
                text_color=DANGER,
            )
            label.pack(pady=(10, 12))

            if on_retry:
                retry_btn = ActionButton(
                    self._status_frame,
                    text="Retry",
                    kind="secondary",
                    width=100,
                    command=on_retry,
                )
                retry_btn.pack()

    def set_on_select(self, callback: Callable[[int | str], None] | None) -> None:
        """Đăng ký callback khi người dùng chọn dòng (nhận row.key)."""
        self._on_select = callback

    def _render_header(self) -> None:
        """Vẽ lại thanh tiêu đề các cột."""
        for child in self._header_frame.winfo_children():
            child.destroy()

        if not self._columns:
            return

        for idx, col in enumerate(self._columns):
            anchor = "w" if col.align == "left" else ("e" if col.align == "right" else "center")
            lbl = ctk.CTkLabel(
                self._header_frame,
                text=col.label,
                font=FONT_BODY_STRONG,
                text_color=TEXT_PRIMARY,
                anchor=anchor,
                width=col.width,
            )
            lbl.pack(side="left", padx=SPACING_SM, pady=SPACING_SM, fill="x", expand=False)

    def _clear_body(self) -> None:
        """Xóa sạch nội dung hiện tại trong body."""
        for child in self._body_frame.winfo_children():
            child.destroy()
        self._row_frames.clear()

    def _render_rows(self) -> None:
        """Hiển thị danh sách các dòng dữ liệu."""
        self._clear_body()

        for idx, row in enumerate(self._rows):
            is_selected = (row.key == self._selected_key)
            row_bg = BG_SURFACE_HOVER if is_selected else (
                BG_ROW_ALT if idx % 2 == 1 else "transparent"
            )

            row_frame = ctk.CTkFrame(
                self._body_frame,
                fg_color=row_bg,
                corner_radius=4,
                height=40,
            )
            row_frame.pack(fill="x", pady=1)
            self._row_frames[row.key] = row_frame

            # Gắn sự kiện click và hover
            self._bind_row_events(row_frame, row.key, row_bg)

            for col in self._columns:
                cell_text = row.cells.get(col.key, "")
                anchor = "w" if col.align == "left" else ("e" if col.align == "right" else "center")

                cell_lbl = ctk.CTkLabel(
                    row_frame,
                    text=cell_text,
                    font=FONT_BODY,
                    text_color=TEXT_PRIMARY,
                    anchor=anchor,
                    width=col.width,
                )
                cell_lbl.pack(side="left", padx=SPACING_SM, pady=8, fill="x", expand=False)
                self._bind_row_events(cell_lbl, row.key, row_bg)

    def _bind_row_events(self, widget: Any, row_key: int | str, original_bg: str) -> None:
        """Gắn sự kiện hover và click cho dòng và các label con."""
        def on_click(_event: Any) -> None:
            self._select_row(row_key)

        def on_enter(_event: Any) -> None:
            if row_key != self._selected_key:
                frame = self._row_frames.get(row_key)
                if frame and frame.winfo_exists():
                    frame.configure(fg_color=BG_SURFACE_HOVER)

        def on_leave(_event: Any) -> None:
            if row_key != self._selected_key:
                frame = self._row_frames.get(row_key)
                if frame and frame.winfo_exists():
                    frame.configure(fg_color=original_bg)

        widget.bind("<Button-1>", on_click)
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def _select_row(self, row_key: int | str) -> None:
        """Chọn một dòng theo row key."""
        old_key = self._selected_key
        self._selected_key = row_key

        # Đổi lại màu dòng cũ nếu có
        if old_key is not None and old_key in self._row_frames:
            old_frame = self._row_frames[old_key]
            if old_frame.winfo_exists():
                # Tìm lại màu ban đầu theo index
                old_idx = next((i for i, r in enumerate(self._rows) if r.key == old_key), 0)
                old_bg = BG_ROW_ALT if old_idx % 2 == 1 else "transparent"
                old_frame.configure(fg_color=old_bg)

        # Đổi màu dòng đang chọn
        if row_key in self._row_frames:
            new_frame = self._row_frames[row_key]
            if new_frame.winfo_exists():
                new_frame.configure(fg_color=BG_SURFACE_HOVER)

        if self._on_select:
            self._on_select(row_key)
