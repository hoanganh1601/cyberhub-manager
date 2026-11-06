"""MachineDialog — Hộp thoại thêm mới hoặc chỉnh sửa cấu hình máy trạm.

Tuân thủ thiết kế Stitch:
- Tham chiếu: docs/ui-reference/th_m_m_y_cyberhub_manager_1280x720/code.html
- Kích thước chuẩn: 500x520, nền STITCH_BG_CHROME (#121824), viền #273147.
- Trường nhập: Mã máy (*), Tên máy (*), Giá theo giờ (*) kèm đơn vị VND/giờ.
- Thẻ thông tin chìm: Cửa hàng và Trạng thái ban đầu (Trống).
- 4 trạng thái: Default, Submitting (loading), Validation error, Success.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import customtkinter as ctk

from ...domain.dtos import EmployeeSession, MachineSummary
from ...domain.enums import MachineStatus
from ...domain.exceptions import ApplicationError
from ..components import ActionButton, ToastManager
from ..messages import MSG_OPERATION_FAILED, get_field_errors_safe, get_user_friendly_error
from ..theme import (
    FONT_ST_BODY,
    FONT_ST_BODY_STRONG,
    FONT_ST_MONO_BODY,
    FONT_ST_MONO_SM,
    FONT_ST_MONO_XS,
    FONT_ST_MONO_XS_STRONG,
    FONT_ST_PAGE_TITLE,
    RADIUS_DIALOG,
    STITCH_BG_CANVAS,
    STITCH_BG_CHROME,
    STITCH_BORDER,
    STITCH_CARD_BORDER,
    STITCH_CYAN,
    STITCH_DANGER,
    STITCH_EMERALD,
    STITCH_INPUT_BG,
    STITCH_INPUT_BORDER,
    STITCH_SUNKEN_BG,
    STITCH_TEXT,
    STITCH_TEXT_MUTED,
    STITCH_TEXT_ON_CYAN,
    STITCH_TEXT_STRONG,
)

logger = logging.getLogger(__name__)


class MachineDialog(ctk.CTkToplevel):
    """Hộp thoại modal thêm mới hoặc chỉnh sửa cấu hình máy trạm."""

    def __init__(
        self,
        parent: Any,
        services: Any,
        *,
        actor: EmployeeSession,
        machine: MachineSummary | None = None,
        language: str = "vi",
        on_success: Any = None,
    ) -> None:
        super().__init__(parent)
        self._services = services
        self._actor = actor
        self._machine = machine
        self._is_edit = machine is not None
        self._language = language
        self._on_success = on_success
        self._is_submitting = False

        is_vi = language == "vi"
        title_str = (
            ("Chỉnh sửa máy" if self._is_edit else "Thêm máy")
            if is_vi
            else ("Edit Machine" if self._is_edit else "Add Machine")
        )

        self.title(title_str)
        self.geometry("500x520")
        self.resizable(False, False)
        self.configure(fg_color=STITCH_BG_CANVAS)

        self.transient(parent)
        self.grab_set()

        self._build_ui(title_str)
        self.bind("<Escape>", lambda _e: self._handle_close())
        self.bind("<Return>", lambda _e: self._handle_save())
        self.after(
            50,
            lambda: (
                self._code_entry.focus_set()
                if hasattr(self, "_code_entry") and not self._is_edit
                else (self._name_entry.focus_set() if hasattr(self, "_name_entry") else None)
            ),
        )

    def _handle_close(self) -> None:
        if not self._is_submitting and self.winfo_exists():
            self.destroy()

    def _build_ui(self, title_str: str) -> None:
        is_vi = self._language == "vi"
        store_name = self._actor.store_name or "CyberHub Hà Nội"

        container = ctk.CTkFrame(
            self,
            fg_color=STITCH_BG_CHROME,
            border_width=1,
            border_color=STITCH_CARD_BORDER,
            corner_radius=RADIUS_DIALOG,
        )
        container.pack(fill="both", expand=True, padx=12, pady=12)

        # ------------------------------------------------------------------
        # Header: Title + Subtitle + Close Button
        # ------------------------------------------------------------------
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 12))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            title_box,
            text=title_str,
            font=FONT_ST_PAGE_TITLE,
            text_color=STITCH_TEXT_STRONG,
        ).pack(anchor="w")

        sub = (
            (f"Cập nhật thông tin máy {self._machine.machine_code}" if self._is_edit else f"Thêm máy mới vào cửa hàng {store_name}")
            if is_vi
            else (f"Update details for machine {self._machine.machine_code}" if self._is_edit else f"Add new workstation to {store_name}")
        )
        ctk.CTkLabel(
            title_box,
            text=sub,
            font=FONT_ST_MONO_SM,
            text_color=STITCH_TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        close_btn = ctk.CTkButton(
            header,
            text="✕",
            width=28,
            height=28,
            corner_radius=6,
            fg_color="transparent",
            hover_color=STITCH_BORDER,
            text_color=STITCH_TEXT_MUTED,
            font=FONT_ST_BODY_STRONG,
            command=self._handle_close,
        )
        close_btn.pack(side="right", anchor="n")

        # Divider
        ctk.CTkFrame(container, fg_color=STITCH_BORDER, height=1).pack(fill="x", padx=20, pady=(0, 14))

        # ------------------------------------------------------------------
        # Form Body
        # ------------------------------------------------------------------
        body = ctk.CTkFrame(container, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20)

        # FIELD 1: MÃ MÁY *
        code_lbl_row = ctk.CTkFrame(body, fg_color="transparent")
        code_lbl_row.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(
            code_lbl_row,
            text="MÃ MÁY " if is_vi else "MACHINE CODE ",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_TEXT,
        ).pack(side="left")
        ctk.CTkLabel(
            code_lbl_row,
            text="*",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_CYAN,
        ).pack(side="left")

        self._code_entry = ctk.CTkEntry(
            body,
            placeholder_text="Ví dụ: PC-21" if is_vi else "e.g. PC-21",
            font=FONT_ST_MONO_BODY,
            fg_color=STITCH_INPUT_BG,
            border_color=STITCH_INPUT_BORDER,
            border_width=1,
            text_color=STITCH_TEXT_STRONG,
            corner_radius=6,
            height=34,
        )
        self._code_entry.pack(fill="x")
        if self._is_edit and self._machine:
            self._code_entry.insert(0, self._machine.machine_code)
            self._code_entry.configure(state="disabled", fg_color=STITCH_SUNKEN_BG, text_color=STITCH_TEXT_MUTED)

        self._code_hint = ctk.CTkLabel(
            body,
            text="Mã máy phải duy nhất trong hệ thống" if is_vi else "Machine code must be unique in system",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
            anchor="w",
        )
        self._code_hint.pack(fill="x", pady=(2, 8))

        # FIELD 2: TÊN MÁY *
        name_lbl_row = ctk.CTkFrame(body, fg_color="transparent")
        name_lbl_row.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(
            name_lbl_row,
            text="TÊN MÁY " if is_vi else "MACHINE NAME ",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_TEXT,
        ).pack(side="left")
        ctk.CTkLabel(
            name_lbl_row,
            text="*",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_CYAN,
        ).pack(side="left")

        self._name_entry = ctk.CTkEntry(
            body,
            placeholder_text="Ví dụ: Máy VIP 21" if is_vi else "e.g. VIP Station 21",
            font=FONT_ST_BODY,
            fg_color=STITCH_INPUT_BG,
            border_color=STITCH_INPUT_BORDER,
            border_width=1,
            text_color=STITCH_TEXT_STRONG,
            corner_radius=6,
            height=34,
        )
        self._name_entry.pack(fill="x")
        if self._is_edit and self._machine:
            self._name_entry.insert(0, self._machine.name)

        self._name_hint = ctk.CTkLabel(
            body,
            text="",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_DANGER,
            anchor="w",
        )
        self._name_hint.pack(fill="x", pady=(2, 8))

        # FIELD 3: GIÁ THEO GIỜ *
        rate_lbl_row = ctk.CTkFrame(body, fg_color="transparent")
        rate_lbl_row.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(
            rate_lbl_row,
            text="GIÁ THEO GIỜ " if is_vi else "HOURLY RATE ",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_TEXT,
        ).pack(side="left")
        ctk.CTkLabel(
            rate_lbl_row,
            text="*",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_CYAN,
        ).pack(side="left")

        rate_input_wrap = ctk.CTkFrame(body, fg_color=STITCH_INPUT_BG, border_width=1, border_color=STITCH_INPUT_BORDER, corner_radius=6, height=34)
        rate_input_wrap.pack(fill="x")
        rate_input_wrap.pack_propagate(False)
        self._rate_wrap = rate_input_wrap

        self._rate_entry = ctk.CTkEntry(
            rate_input_wrap,
            placeholder_text="10000",
            font=FONT_ST_MONO_BODY,
            fg_color="transparent",
            border_width=0,
            text_color=STITCH_TEXT_STRONG,
        )
        self._rate_entry.pack(side="left", fill="both", expand=True, padx=(8, 0))
        if self._is_edit and self._machine:
            self._rate_entry.insert(0, str(self._machine.hourly_rate))
        else:
            self._rate_entry.insert(0, "10000")

        ctk.CTkLabel(
            rate_input_wrap,
            text="VND/giờ" if is_vi else "VND/h",
            font=FONT_ST_MONO_SM,
            text_color=STITCH_TEXT_MUTED,
        ).pack(side="right", padx=(0, 10))

        self._rate_hint = ctk.CTkLabel(
            body,
            text="",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_DANGER,
            anchor="w",
        )
        self._rate_hint.pack(fill="x", pady=(2, 10))

        # INFO CARD: Cửa hàng + Trạng thái ban đầu
        info_card = ctk.CTkFrame(
            body,
            fg_color=STITCH_SUNKEN_BG,
            border_width=1,
            border_color=STITCH_BORDER,
            corner_radius=8,
            height=54,
        )
        info_card.pack(fill="x", pady=(0, 6))
        info_card.pack_propagate(False)

        col_store = ctk.CTkFrame(info_card, fg_color="transparent")
        col_store.pack(side="left", fill="both", expand=True, padx=12, pady=6)
        ctk.CTkLabel(
            col_store,
            text="Cửa hàng" if is_vi else "Store",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        ).pack(anchor="w")

        store_val_box = ctk.CTkFrame(col_store, fg_color="transparent")
        store_val_box.pack(anchor="w")
        ctk.CTkLabel(store_val_box, text="● ", font=FONT_ST_MONO_XS, text_color=STITCH_CYAN).pack(side="left")
        ctk.CTkLabel(
            store_val_box,
            text=store_name,
            font=FONT_ST_BODY_STRONG,
            text_color=STITCH_TEXT_STRONG,
        ).pack(side="left")

        col_status = ctk.CTkFrame(info_card, fg_color="transparent")
        col_status.pack(side="right", fill="both", expand=True, padx=12, pady=6)
        status_label = "Trạng thái ban đầu" if not self._is_edit else "Trạng thái hiện tại"
        ctk.CTkLabel(
            col_status,
            text=status_label if is_vi else "Status",
            font=FONT_ST_MONO_XS,
            text_color=STITCH_TEXT_MUTED,
        ).pack(anchor="w")

        st_pill = ctk.CTkFrame(col_status, fg_color="#132E27", corner_radius=10, height=22)
        st_pill.pack(anchor="w", pady=(2, 0))
        st_txt = "Trống" if not self._is_edit or not self._machine else (
            "Trống" if self._machine.status == MachineStatus.AVAILABLE else (
                "Đang dùng" if self._machine.status == MachineStatus.IN_USE else "Bảo trì"
            )
        )
        ctk.CTkLabel(
            st_pill,
            text=f"● {st_txt}",
            font=FONT_ST_MONO_XS_STRONG,
            text_color=STITCH_EMERALD,
        ).pack(padx=8, pady=1)

        # ------------------------------------------------------------------
        # Footer Actions
        # ------------------------------------------------------------------
        ctk.CTkFrame(container, fg_color=STITCH_BORDER, height=1).pack(fill="x", padx=20, pady=(6, 12))

        footer = ctk.CTkFrame(container, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 16))

        save_label = (
            ("Lưu thay đổi" if self._is_edit else "+ Thêm máy")
            if is_vi
            else ("Save Changes" if self._is_edit else "+ Add Machine")
        )
        self._btn_save = ActionButton(
            footer,
            text=save_label,
            kind="primary",
            width=130,
            height=34,
            command=self._handle_save,
        )
        self._btn_save.pack(side="right")

        self._btn_cancel = ActionButton(
            footer,
            text="Hủy" if is_vi else "Cancel",
            kind="ghost",
            width=80,
            height=34,
            command=self._handle_close,
        )
        self._btn_cancel.pack(side="right", padx=(0, 8))

    def _reset_errors(self) -> None:
        self._code_entry.configure(border_color=STITCH_INPUT_BORDER)
        self._name_entry.configure(border_color=STITCH_INPUT_BORDER)
        self._rate_wrap.configure(border_color=STITCH_INPUT_BORDER)
        self._code_hint.configure(
            text="Mã máy phải duy nhất trong hệ thống" if self._language == "vi" else "Machine code must be unique in system",
            text_color=STITCH_TEXT_MUTED,
        )
        self._name_hint.configure(text="")
        self._rate_hint.configure(text="")

    def _handle_save(self) -> None:
        if self._is_submitting:
            return

        is_vi = self._language == "vi"
        self._reset_errors()

        code = self._code_entry.get().strip().upper()
        name = self._name_entry.get().strip()
        rate_str = self._rate_entry.get().strip().replace(".", "").replace(",", "")

        has_error = False

        if not self._is_edit:
            if not code:
                self._code_entry.configure(border_color=STITCH_DANGER)
                self._code_hint.configure(
                    text="Mã máy không được để trống" if is_vi else "Machine code cannot be empty",
                    text_color=STITCH_DANGER,
                )
                has_error = True
            elif not re.match(r"^[A-Z0-9_\-]+$", code):
                self._code_entry.configure(border_color=STITCH_DANGER)
                self._code_hint.configure(
                    text="Mã máy chỉ chứa chữ cái, số, gạch ngang" if is_vi else "Invalid code characters",
                    text_color=STITCH_DANGER,
                )
                has_error = True

        if not name:
            self._name_entry.configure(border_color=STITCH_DANGER)
            self._name_hint.configure(
                text="Tên máy không được để trống" if is_vi else "Machine name cannot be empty",
                text_color=STITCH_DANGER,
            )
            has_error = True

        rate = 0
        try:
            rate = int(rate_str)
            if rate <= 0:
                raise ValueError()
        except ValueError:
            self._rate_wrap.configure(border_color=STITCH_DANGER)
            self._rate_hint.configure(
                text="Đơn giá phải là số nguyên dương" if is_vi else "Hourly rate must be a positive integer",
                text_color=STITCH_DANGER,
            )
            has_error = True

        if has_error:
            return

        self._set_submitting(True)

        try:
            if self._is_edit:
                assert self._machine is not None
                self._services.machines.update_machine(
                    machine_id=self._machine.machine_id,
                    name=name,
                    hourly_rate=rate,
                    actor=self._actor,
                )
                msg = f"Cập nhật máy {self._machine.machine_code} thành công!" if is_vi else f"Machine {self._machine.machine_code} updated successfully!"
            else:
                self._services.machines.create_machine(
                    code=code,
                    store_id=self._actor.store_id,
                    name=name,
                    hourly_rate=rate,
                    actor=self._actor,
                )
                msg = f"Đã thêm máy {code} thành công!" if is_vi else f"Machine {code} added successfully!"

            ToastManager.show(self.master, msg, kind="success")
            if self._on_success:
                self._on_success()
            if self.winfo_exists():
                self.destroy()

        except ApplicationError as err:
            logger.warning("Lỗi lưu máy: %s", err)
            field_errors = get_field_errors_safe(err)
            if "code" in field_errors:
                self._code_entry.configure(border_color=STITCH_DANGER)
                self._code_hint.configure(text=field_errors["code"], text_color=STITCH_DANGER)
            if "name" in field_errors:
                self._name_entry.configure(border_color=STITCH_DANGER)
                self._name_hint.configure(text=field_errors["name"], text_color=STITCH_DANGER)
            if "hourly_rate" in field_errors:
                self._rate_wrap.configure(border_color=STITCH_DANGER)
                self._rate_hint.configure(text=field_errors["hourly_rate"], text_color=STITCH_DANGER)
            if not field_errors:
                ToastManager.show(self, get_user_friendly_error(err), kind="error")
        except Exception:
            logger.exception("Lỗi không mong muốn khi lưu máy")
            ToastManager.show(self, MSG_OPERATION_FAILED, kind="error")
        finally:
            if self.winfo_exists():
                self._set_submitting(False)

    def _set_submitting(self, busy: bool) -> None:
        self._is_submitting = busy
        self._btn_save.set_busy(busy)
        self._btn_cancel.set_enabled(not busy)
        if not self._is_edit:
            self._code_entry.configure(state="disabled" if busy else "normal")
        self._name_entry.configure(state="disabled" if busy else "normal")
        self._rate_entry.configure(state="disabled" if busy else "normal")
