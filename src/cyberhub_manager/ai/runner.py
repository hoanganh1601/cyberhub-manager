"""Bounded provider calls with a caller-visible wall-clock timeout.

Python cannot kill a running provider thread. Timed-out work retains its slot
until it finishes; excess calls fail busy instead of creating unlimited threads.
Real adapters still need native network/inference timeouts and output limits.
"""

from collections.abc import Callable
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
import math
from threading import BoundedSemaphore, Thread
from typing import TypeVar

from .errors import ProviderBusyError, ProviderTimeoutError, ProviderUnavailableError

T = TypeVar("T")


class BoundedProviderRunner:
    def __init__(self, *, max_concurrent: int = 2) -> None:
        if type(max_concurrent) is not int or max_concurrent <= 0:
            raise ValueError("max_concurrent must be a positive integer")
        self._slots = BoundedSemaphore(max_concurrent)

    def run(self, operation: Callable[[], T], *, timeout_seconds: float) -> T:
        if (
            type(timeout_seconds) not in (int, float)
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be positive and finite")
        if not self._slots.acquire(blocking=False):
            raise ProviderBusyError("provider worker capacity is exhausted")
        future: Future[T] = Future()

        def work() -> None:
            try:
                result = operation()
            except BaseException as exc:
                self._slots.release()
                future.set_exception(exc)
            else:
                self._slots.release()
                future.set_result(result)

        try:
            Thread(target=work, daemon=True, name="cyberhub-ai-provider").start()
        except Exception:
            self._slots.release()
            raise ProviderUnavailableError("provider worker could not start") from None
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError:
            raise ProviderTimeoutError("provider call exceeded the request deadline") from None
