"""Hiển thị lỗi nghiệp vụ thống nhất cho mọi view/dialog.

Quy định: docs/07_DTO_UI_HANDOFF.md mục 6.
- Không bao giờ hiện traceback/SQL; chỉ dùng câu tiếng Anh trong ui.messages.
- ConflictError của tranh chấp máy/phiên -> ConfirmDialog.alert (không Toast trùng nội dung).
- Lỗi không phải ApplicationError -> ghi log, hiện thông báo chung.
"""

from __future__ import annotations

import logging
from typing import Any

from ..domain.exceptions import ApplicationError, ConflictError
from .components import ConfirmDialog, ToastManager
from .messages import MSG_OPERATION_FAILED, get_user_friendly_error

logger = logging.getLogger(__name__)

CONFLICT_TITLE = "Operation conflict"


def notify_error(parent: Any, error: Exception, *, conflict_as_alert: bool = False) -> None:
    """Báo lỗi cho người dùng theo loại exception."""
    if not isinstance(error, ApplicationError):
        logger.error("Lỗi không mong đợi", exc_info=error)
        ToastManager.show(parent, MSG_OPERATION_FAILED, kind="error")
        return

    message = get_user_friendly_error(error)
    if conflict_as_alert and isinstance(error, ConflictError):
        ConfirmDialog.alert(parent.winfo_toplevel(), CONFLICT_TITLE, message)
        return
    ToastManager.show(parent, message, kind="error")


def notify_success(parent: Any, message: str) -> None:
    ToastManager.show(parent, message, kind="success")
