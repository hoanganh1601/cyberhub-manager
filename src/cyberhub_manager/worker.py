"""Vòng lặp chung cho worker nền: ghi log từng lượt, thử lại có backoff, dừng êm khi nhận tín hiệu."""

from __future__ import annotations

import logging
import signal
import threading
from collections.abc import Callable, Mapping

logger = logging.getLogger(__name__)

MAX_BACKOFF_SECONDS = 300


def backoff_delay(interval: float, failures: int, cap: float = MAX_BACKOFF_SECONDS) -> float:
    """Sau n lần lỗi liên tiếp chờ interval·2^n, không vượt max(interval, cap)."""
    return min(interval * 2 ** failures, max(interval, cap))


def run_worker(
    name: str,
    job: Callable[[], Mapping[str, int] | None],
    *,
    interval: float,
    once: bool = False,
    stop: threading.Event | None = None,
    wait: Callable[[float], bool] | None = None,
    install_signals: bool = False,
) -> int:
    """Chạy `job` lặp lại; trả về mã thoát (0 thành công, 1 nếu `--once` bị lỗi).

    Lỗi của một lượt chỉ được ghi log rồi thử lại sau thời gian chờ tăng dần; không bao giờ làm chết worker.
    `wait(seconds)` trả True khi có yêu cầu dừng (mặc định dùng `stop.wait`; test truyền bản giả).
    """
    stop = stop or threading.Event()
    wait = wait or stop.wait
    if install_signals:
        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, lambda *_: stop.set())
    failures = 0
    logger.info("%s started (interval=%ss, once=%s)", name, interval, once)
    while not stop.is_set():
        try:
            result = job() or {}
        except Exception:
            failures += 1
            logger.exception("%s failed (%s in a row); will retry", name, failures)
            if once:
                return 1
        else:
            failures = 0
            summary = " ".join(f"{key}={value}" for key, value in result.items())
            logger.log(logging.INFO if any(result.values()) else logging.DEBUG, "%s: %s", name, summary or "ok")
            if once:
                return 0
        if wait(backoff_delay(interval, failures)):
            break
    logger.info("%s stopped", name)
    return 0
