"""UI state cho view và form trong CyberHub Manager.

Quy định: docs/07_DTO_UI_HANDOFF.md mục 7.
- ViewState gồm: LOADING, READY, EMPTY, ERROR.
- Trạng thái submit form là cờ is_submitting: bool riêng của form,
  không trộn với ViewState hoặc enum MachineStatus / AccountStatus.
- Sau cả thành công và thất bại phải thoát trạng thái submitting.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ViewState(StrEnum):
    """Trạng thái hiển thị của một màn hình hoặc bảng dữ liệu."""

    LOADING = "LOADING"  # Đang tải dữ liệu… (disable action phụ thuộc dữ liệu)
    READY = "READY"      # Dữ liệu thật hoặc mock hợp lệ (enable action theo quyền)
    EMPTY = "EMPTY"      # Chưa có dữ liệu phù hợp (cho đổi bộ lọc hoặc tạo mới nếu có quyền)
    ERROR = "ERROR"      # Thông báo thân thiện + nút Thử lại (retry cùng operation)


@dataclass
class FormState:
    """Trạng thái thao tác submit của form.

    Tách biệt cờ is_submitting khỏi ViewState để quản lý riêng:
    - Khi is_submitting=True: nút submit hiển thị 'Đang xử lý…', bị disable để chặn double click.
    - Dữ liệu trên form vẫn được giữ nguyên.
    - Sau cả khi thành công hoặc thất bại, form bắt buộc phải đặt lại is_submitting=False.
    """

    is_submitting: bool = False
    error_message: str | None = None

    def start_submitting(self) -> None:
        """Bắt đầu submit: kích hoạt cờ is_submitting và xóa thông báo lỗi cũ."""
        self.is_submitting = True
        self.error_message = None

    def finish_submitting(self, error: str | None = None) -> None:
        """Kết thúc submit: luôn trả cờ is_submitting về False và cập nhật lỗi nếu có."""
        self.is_submitting = False
        self.error_message = error
