"""Chạy lệnh gọi service ngoài Tk main thread rồi trả kết quả về main thread.

Quy định: docs/07_DTO_UI_HANDOFF.md mục 8 — không chạy service/DB call có thể chặn lâu
trên Tk main thread; worker không được chạm widget; kết quả chuyển về bằng `after`.

- ThreadTaskRunner: dùng khi chạy app thật (1 worker -> các lệnh chạy lần lượt).
- ImmediateTaskRunner: chạy ngay trên main thread, dùng trong unit test.
"""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Protocol, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_POLL_MS = 30


class TaskRunner(Protocol):
    def submit(
        self,
        widget: Any,
        func: Callable[[], T],
        on_success: Callable[[T], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        """Chạy `func`; gọi on_success/on_error trên main thread nếu widget còn tồn tại."""
        ...


def _widget_alive(widget: Any) -> bool:
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False


class ThreadTaskRunner:
    """Chạy func trên một worker thread; poll kết quả bằng widget.after()."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cyberhub-ui")

    def submit(
        self,
        widget: Any,
        func: Callable[[], T],
        on_success: Callable[[T], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        future: Future[T] = self._executor.submit(func)

        def poll() -> None:
            if not _widget_alive(widget):
                return  # View đã đóng: bỏ kết quả, không chạm widget đã hủy.
            if not future.done():
                widget.after(_POLL_MS, poll)
                return
            error = future.exception()
            if error is None:
                on_success(future.result())
            elif isinstance(error, Exception):
                on_error(error)
            else:  # BaseException (KeyboardInterrupt...) — không nuốt.
                raise error

        widget.after(_POLL_MS, poll)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


class ImmediateTaskRunner:
    """Chạy đồng bộ — dùng cho unit test để không phải chờ vòng lặp sự kiện."""

    def submit(
        self,
        widget: Any,
        func: Callable[[], T],
        on_success: Callable[[T], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        try:
            result = func()
        except Exception as error:  # noqa: BLE001 — chuyển cho on_error xử lý
            on_error(error)
        else:
            on_success(result)


_default_runner: ThreadTaskRunner | None = None


def default_runner() -> ThreadTaskRunner:
    """Một runner dùng chung cho toàn app (tạo lần đầu khi cần)."""
    global _default_runner
    if _default_runner is None:
        _default_runner = ThreadTaskRunner()
    return _default_runner
