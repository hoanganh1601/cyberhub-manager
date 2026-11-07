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
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_MONO_SM,
    FONT_ST_MONO_XS,
    FONT_ST_MONO_XS_STRONG,
    RADIUS_INPUT,
    SPACING_MD,
    SPACING_SM,
    STITCH_CARD_BG,
    STITCH_CARD_BORDER,
    STITCH_CYAN,
    STITCH_NAV_ACTIVE_BG,
    STITCH_NAV_ACTIVE_BORDER,
    STITCH_SUNKEN_BG,
    STITCH_TEXT,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_STRONG,
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
    cell_colors: dict[str, str] = field(default_factory=dict)
    cell_subtexts: dict[str, str] = field(default_factory=dict)
    badges: dict[str, tuple[str, str, str]] = field(default_factory=dict)  # (text, text_color, bg_color)
    action_buttons: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    ratio_bars: dict[str, tuple[float, str]] = field(default_factory=dict)  # (pct 0-100, label)
    inline_tags: dict[str, tuple[str, str, str]] = field(default_factory=dict)  # (tag_text, tag_fg, tag_bg)
    dimmed: bool = False


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
        self._row_indicators: dict[int | str, ctk.CTkFrame] = {}

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

        self._header_frame.configure(fg_color=STITCH_SUNKEN_BG)

        for idx, col in enumerate(self._columns):
            anchor = "w" if col.align == "left" else ("e" if col.align == "right" else "center")
            lbl = ctk.CTkLabel(
                self._header_frame,
                text=col.label,
                font=FONT_ST_MONO_XS_STRONG,
                text_color=STITCH_TEXT_MUTED,
                anchor=anchor,
                width=col.width,
            )
            lbl.pack(side="left", padx=4, pady=6, fill="x", expand=False)

    def _clear_body(self) -> None:
        """Xóa sạch nội dung hiện tại trong body."""
        for child in self._body_frame.winfo_children():
            child.destroy()
        self._row_frames.clear()
        self._row_indicators.clear()

    def _render_rows(self) -> None:
        """Hiển thị danh sách các dòng dữ liệu."""
        self._clear_body()

        for idx, row in enumerate(self._rows):
            is_selected = (row.key == self._selected_key)
            if row.dimmed:
                row_bg = "#0B0F17" if not is_selected else STITCH_NAV_ACTIVE_BG
            else:
                row_bg = STITCH_NAV_ACTIVE_BG if is_selected else (
                    "#121824" if idx % 2 == 1 else "transparent"
                )
            border_w = 1 if is_selected else 0
            border_c = STITCH_NAV_ACTIVE_BORDER if is_selected else None

            row_frame = ctk.CTkFrame(
                self._body_frame,
                fg_color=row_bg,
                corner_radius=4,
                border_width=border_w,
                border_color=border_c,
                height=48,
            )
            row_frame.pack(fill="x", pady=1)
            row_frame.pack_propagate(False)
            self._row_frames[row.key] = row_frame

            # Dải viền cyan rộng 4px ở cạnh trái của dòng được chọn theo chuẩn Stitch
            indicator = ctk.CTkFrame(
                row_frame,
                width=4,
                fg_color=STITCH_CYAN if is_selected else "transparent",
                corner_radius=2,
            )
            indicator.pack(side="left", fill="y", padx=(1, 3))
            self._row_indicators[row.key] = indicator

            # Gắn sự kiện click và hover
            self._bind_row_events(row_frame, row.key, row_bg)

            for col in self._columns:
                cell_text = row.cells.get(col.key, "")
                anchor = "w" if col.align == "left" else ("e" if col.align == "right" else "center")
                text_col = row.cell_colors.get(col.key, STITCH_TEXT)

                # 1. Trường hợp có Badge
                if col.key in row.badges:
                    badge_text, b_fg, b_bg = row.badges[col.key]
                    badge_wrap = ctk.CTkFrame(row_frame, fg_color="transparent", width=col.width, height=48)
                    badge_wrap.pack(side="left", padx=4, fill="y", expand=False)
                    badge_wrap.pack_propagate(False)

                    b_chip = ctk.CTkLabel(
                        badge_wrap,
                        text=badge_text,
                        font=FONT_ST_MONO_XS_STRONG,
                        text_color=b_fg,
                        fg_color=b_bg,
                        corner_radius=4,
                        padx=6,
                        pady=2,
                    )
                    b_chip.pack(expand=True)
                    self._bind_row_events(badge_wrap, row.key, row_bg)
                    self._bind_row_events(b_chip, row.key, row_bg)
                    continue

                # 2. Trường hợp có subtext (ví dụ Tên + Ngày đăng ký)
                if col.key in row.cell_subtexts:
                    sub_text = row.cell_subtexts[col.key]
                    cell_wrap = ctk.CTkFrame(row_frame, fg_color="transparent", width=col.width, height=48)
                    cell_wrap.pack(side="left", padx=4, fill="y", expand=False)
                    cell_wrap.pack_propagate(False)

                    inner_txt = ctk.CTkFrame(cell_wrap, fg_color="transparent")
                    inner_txt.pack(expand=True, fill="x")

                    main_lbl = ctk.CTkLabel(
                        inner_txt,
                        text=cell_text,
                        font=FONT_ST_BODY_STRONG,
                        text_color=text_col,
                        anchor=anchor,
                    )
                    main_lbl.pack(anchor=anchor, fill="x")

                    sub_lbl = ctk.CTkLabel(
                        inner_txt,
                        text=sub_text,
                        font=FONT_ST_MONO_XS,
                        text_color=STITCH_TEXT_MUTED,
                        anchor=anchor,
                    )
                    sub_lbl.pack(anchor=anchor, fill="x")

                    self._bind_row_events(cell_wrap, row.key, row_bg)
                    self._bind_row_events(inner_txt, row.key, row_bg)
                    self._bind_row_events(main_lbl, row.key, row_bg)
                    self._bind_row_events(sub_lbl, row.key, row_bg)
                    continue

                # 3. Trường hợp có action buttons
                if col.key in row.action_buttons:
                    actions = row.action_buttons[col.key]
                    btn_wrap = ctk.CTkFrame(row_frame, fg_color="transparent", width=col.width, height=48)
                    btn_wrap.pack(side="left", padx=4, fill="y", expand=False)
                    btn_wrap.pack_propagate(False)

                    inner_btns = ctk.CTkFrame(btn_wrap, fg_color="transparent")
                    pack_side = "right" if col.align == "right" else "left"
                    inner_btns.pack(side=pack_side, expand=True)

                    for b_def in actions:
                        btn_txt = b_def.get("text", "")
                        btn_cmd = b_def.get("command")
                        btn_enabled = b_def.get("enabled", True)
                        btn_fg = b_def.get("fg_color", "#1E273A")
                        btn_hover = b_def.get("hover_color", "#27344E")
                        btn_tc = b_def.get("text_color", STITCH_CYAN)
                        btn_w = b_def.get("width", 26)
                        btn_h = b_def.get("height", 26)
                        btn_corner = b_def.get("corner_radius", 6)

                        if not btn_enabled:
                            btn_fg = "#141A26"
                            btn_tc = "#475569"
                            btn_hover = "#141A26"

                        btn_wgt = ctk.CTkButton(
                            inner_btns,
                            text=btn_txt,
                            width=btn_w,
                            height=btn_h,
                            corner_radius=btn_corner,
                            fg_color=btn_fg,
                            hover_color=btn_hover,
                            text_color=btn_tc,
                            font=FONT_ST_MONO_XS_STRONG,
                            state="normal" if btn_enabled else "disabled",
                            command=btn_cmd if btn_enabled else None,
                        )
                        btn_wgt.pack(side="left", padx=2)

                    self._bind_row_events(btn_wrap, row.key, row_bg)
                    self._bind_row_events(inner_btns, row.key, row_bg)
                    continue

                # 4. Trường hợp có Ratio Bar trực quan
                if col.key in row.ratio_bars:
                    pct, pct_label = row.ratio_bars[col.key]
                    bar_wrap = ctk.CTkFrame(row_frame, fg_color="transparent", width=col.width, height=48)
                    bar_wrap.pack(side="left", padx=4, fill="y", expand=False)
                    bar_wrap.pack_propagate(False)

                    inner = ctk.CTkFrame(bar_wrap, fg_color="transparent")
                    pack_side = "right" if col.align == "right" else "left"
                    inner.pack(side=pack_side, expand=True, padx=4)

                    track = ctk.CTkFrame(inner, width=64, height=6, fg_color="#171F30", corner_radius=3)
                    track.pack(side="left", padx=(0, 6))
                    track.pack_propagate(False)

                    fill_w = max(2, min(64, int(64 * (pct / 100.0)))) if pct > 0 else 0
                    if fill_w > 0:
                        fill_b = ctk.CTkFrame(track, width=fill_w, height=6, fg_color=STITCH_CYAN, corner_radius=3)
                        fill_b.pack(side="left")
                        self._bind_row_events(fill_b, row.key, row_bg)

                    pct_lbl = ctk.CTkLabel(inner, text=pct_label, font=FONT_ST_MONO_SM, text_color=text_col)
                    pct_lbl.pack(side="left")

                    self._bind_row_events(bar_wrap, row.key, row_bg)
                    self._bind_row_events(inner, row.key, row_bg)
                    self._bind_row_events(track, row.key, row_bg)
                    self._bind_row_events(pct_lbl, row.key, row_bg)
                    continue

                # 5. Trường hợp có Inline Tag (ví dụ Ngày + Badge HÔM NAY)
                if col.key in row.inline_tags:
                    tag_txt, tag_fg, tag_bg = row.inline_tags[col.key]
                    tag_wrap = ctk.CTkFrame(row_frame, fg_color="transparent", width=col.width, height=48)
                    tag_wrap.pack(side="left", padx=4, fill="y", expand=False)
                    tag_wrap.pack_propagate(False)

                    inner = ctk.CTkFrame(tag_wrap, fg_color="transparent")
                    pack_side = "left" if col.align == "left" else "right"
                    inner.pack(side=pack_side, expand=True)

                    main_lbl = ctk.CTkLabel(inner, text=cell_text, font=FONT_ST_BODY_STRONG, text_color=text_col)
                    main_lbl.pack(side="left", padx=(0, 6))

                    chip = ctk.CTkLabel(
                        inner,
                        text=tag_txt,
                        font=FONT_ST_MONO_XS_STRONG,
                        text_color=tag_fg,
                        fg_color=tag_bg,
                        corner_radius=4,
                        padx=4,
                        pady=1,
                    )
                    chip.pack(side="left")

                    self._bind_row_events(tag_wrap, row.key, row_bg)
                    self._bind_row_events(inner, row.key, row_bg)
                    self._bind_row_events(main_lbl, row.key, row_bg)
                    self._bind_row_events(chip, row.key, row_bg)
                    continue

                # 6. Text đơn thông thường
                cell_font = FONT_ST_BODY_STRONG if col.key in ("code", "balance") else FONT_ST_BODY
                cell_lbl = ctk.CTkLabel(
                    row_frame,
                    text=cell_text,
                    font=cell_font,
                    text_color=text_col,
                    anchor=anchor,
                    width=col.width,
                )
                cell_lbl.pack(side="left", padx=4, pady=4, fill="y", expand=False)
                self._bind_row_events(cell_lbl, row.key, row_bg)

    def _bind_row_events(self, widget: Any, row_key: int | str, original_bg: str) -> None:
        """Gắn sự kiện hover và click cho dòng và các widget con."""
        def on_click(_event: Any) -> None:
            self._select_row(row_key)

        def on_enter(_event: Any) -> None:
            if row_key != self._selected_key:
                frame = self._row_frames.get(row_key)
                if frame and frame.winfo_exists():
                    frame.configure(fg_color="#161D2D")

        def on_leave(_event: Any) -> None:
            if row_key != self._selected_key:
                frame = self._row_frames.get(row_key)
                if frame and frame.winfo_exists():
                    # Tìm lại màu ban đầu theo index
                    idx = next((i for i, r in enumerate(self._rows) if r.key == row_key), 0)
                    bg = "#121824" if idx % 2 == 1 else "transparent"
                    frame.configure(fg_color=bg)

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
                old_idx = next((i for i, r in enumerate(self._rows) if r.key == old_key), 0)
                old_bg = "#121824" if old_idx % 2 == 1 else "transparent"
                old_frame.configure(fg_color=old_bg, border_width=0)
            if old_key in self._row_indicators:
                old_ind = self._row_indicators[old_key]
                if old_ind.winfo_exists():
                    old_ind.configure(fg_color="transparent")

        # Đổi màu dòng đang chọn
        if row_key in self._row_frames:
            new_frame = self._row_frames[row_key]
            if new_frame.winfo_exists():
                new_frame.configure(
                    fg_color=STITCH_NAV_ACTIVE_BG,
                    border_width=1,
                    border_color=STITCH_NAV_ACTIVE_BORDER,
                )
            if row_key in self._row_indicators:
                new_ind = self._row_indicators[row_key]
                if new_ind.winfo_exists():
                    new_ind.configure(fg_color=STITCH_CYAN)

        if self._on_select:
            self._on_select(row_key)

    def select_row(self, row_key: int | str, *, trigger_callback: bool = False) -> None:
        """Chọn và highlight một dòng theo key từ bên ngoài."""
        old_key = self._selected_key
        self._selected_key = row_key

        if old_key is not None and old_key in self._row_frames:
            old_frame = self._row_frames[old_key]
            if old_frame.winfo_exists():
                old_idx = next((i for i, r in enumerate(self._rows) if r.key == old_key), 0)
                old_bg = "#121824" if old_idx % 2 == 1 else "transparent"
                old_frame.configure(fg_color=old_bg, border_width=0)
            if old_key in self._row_indicators:
                old_ind = self._row_indicators[old_key]
                if old_ind.winfo_exists():
                    old_ind.configure(fg_color="transparent")

        if row_key in self._row_frames:
            new_frame = self._row_frames[row_key]
            if new_frame.winfo_exists():
                new_frame.configure(
                    fg_color=STITCH_NAV_ACTIVE_BG,
                    border_width=1,
                    border_color=STITCH_NAV_ACTIVE_BORDER,
                )
            if row_key in self._row_indicators:
                new_ind = self._row_indicators[row_key]
                if new_ind.winfo_exists():
                    new_ind.configure(fg_color=STITCH_CYAN)

        if trigger_callback and self._on_select:
            self._on_select(row_key)
