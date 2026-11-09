"""Actual timeout/capacity behavior without network, sleeps or unbounded workers."""

from threading import Event
import time

import pytest

from cyberhub_manager.ai.errors import ProviderBusyError, ProviderTimeoutError, ProviderUnavailableError
from cyberhub_manager.ai.runner import BoundedProviderRunner


def test_runner_returns_value_and_releases_single_worker_slot():
    runner = BoundedProviderRunner(max_concurrent=1)
    assert runner.run(lambda: 42, timeout_seconds=1) == 42
    assert runner.run(lambda: "next", timeout_seconds=1) == "next"


def test_runner_propagates_error_and_releases_slot():
    runner = BoundedProviderRunner(max_concurrent=1)
    def fail():
        raise ValueError("operation failed")
    with pytest.raises(ValueError, match="operation failed"):
        runner.run(fail, timeout_seconds=1)
    assert runner.run(lambda: 42, timeout_seconds=1) == 42


def test_timed_out_work_holds_capacity_and_cannot_spawn_unbounded_workers():
    runner = BoundedProviderRunner(max_concurrent=1)
    release, entered, completed = Event(), Event(), Event()
    calls = []
    def blocked():
        calls.append("entered")
        entered.set()
        try:
            if not release.wait(timeout=5):
                raise AssertionError("test did not release provider")
            return "late result"
        finally:
            completed.set()
    started = time.monotonic()
    try:
        with pytest.raises(ProviderTimeoutError):
            runner.run(blocked, timeout_seconds=0.02)
        assert entered.is_set()
        assert time.monotonic() - started < 2
        for _ in range(5):
            with pytest.raises(ProviderBusyError):
                runner.run(lambda: calls.append("unexpected"), timeout_seconds=1)
        assert calls == ["entered"]
    finally:
        release.set()
        assert completed.wait(timeout=5)


@pytest.mark.parametrize("value", [0, -1, True, float("nan"), float("inf")])
def test_runner_rejects_invalid_timeouts(value):
    with pytest.raises(ValueError):
        BoundedProviderRunner().run(lambda: 1, timeout_seconds=value)


@pytest.mark.parametrize("value", [0, -1, True])
def test_runner_rejects_invalid_capacity(value):
    with pytest.raises(ValueError):
        BoundedProviderRunner(max_concurrent=value)


def test_worker_start_failure_releases_capacity_and_uses_safe_error(monkeypatch):
    import cyberhub_manager.ai.runner as module
    runner = BoundedProviderRunner(max_concurrent=1)
    original = module.Thread
    class BrokenThread:
        def __init__(self, **kwargs):
            pass

        def start(self):
            raise RuntimeError("private implementation detail")
    monkeypatch.setattr(module, "Thread", BrokenThread)
    with pytest.raises(ProviderUnavailableError) as error:
        runner.run(lambda: 1, timeout_seconds=1)
    assert "private implementation detail" not in str(error.value)
    monkeypatch.setattr(module, "Thread", original)
    assert runner.run(lambda: 2, timeout_seconds=1) == 2
