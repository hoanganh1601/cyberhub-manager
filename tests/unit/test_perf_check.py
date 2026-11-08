"""Benchmark isolation: no non-test writes and cleanup after partial failures."""

import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def script():
    path = Path(__file__).resolve().parents[2] / "scripts/perf_check.py"
    spec = importlib.util.spec_from_file_location("perf_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("scale", ["0", "-1", "nan", "inf", "11"])
def test_invalid_scale_cannot_connect(script, monkeypatch, scale):
    connect = Mock()
    monkeypatch.setattr(script.connection, "get_connection", connect)
    with pytest.raises(SystemExit):
        script.main(["--scale", scale])
    connect.assert_not_called()


def test_explicit_production_database_is_refused_before_connecting(script, monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", "cyberhub_manager")
    connect = Mock()
    monkeypatch.setattr(script.connection, "get_connection", connect)
    with pytest.raises(SystemExit):
        script.main([])
    connect.assert_not_called()


def test_wrong_actual_database_is_closed_without_cleanup(script, monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", script.TEST_DATABASE)
    conn = Mock()
    monkeypatch.setattr(script.connection, "get_connection", lambda: conn)
    monkeypatch.setattr(script, "_run", lambda *_: [("production",)])
    cleanup = Mock()
    monkeypatch.setattr(script, "cleanup", cleanup)
    with pytest.raises(SystemExit):
        script.main([])
    cleanup.assert_not_called()
    conn.close.assert_called_once()


def test_seed_failure_rolls_back_cleans_owned_data_and_closes(script, monkeypatch):
    monkeypatch.setenv("MYSQL_DATABASE", script.TEST_DATABASE)
    conn = Mock()
    monkeypatch.setattr(script.connection, "get_connection", lambda: conn)
    monkeypatch.setattr(script, "_run", lambda *_: [(script.TEST_DATABASE,)])
    monkeypatch.setattr(script, "seed", Mock(side_effect=RuntimeError("partial seed")))
    cleanup = Mock()
    monkeypatch.setattr(script, "cleanup", cleanup)
    with pytest.raises(RuntimeError, match="partial seed"):
        script.main([])
    conn.rollback.assert_called_once()
    cleanup.assert_called_once_with(conn)
    conn.close.assert_called_once()


def test_cleanup_uses_unique_run_prefix_not_generic_perf(script, monkeypatch):
    calls = []
    monkeypatch.setattr(script, "_run", lambda conn, sql, params: calls.append((sql, params)) or [])
    script.cleanup(Mock())
    assert len(script.PREFIX) == 10 and script.PREFIX.isalnum()
    assert all("PERF%" not in params for _, params in calls)
    assert calls[-1][1] == (script.PREFIX + "%",)


def test_capture_restores_driver_on_exception(script):
    original = script.py_cursor.MySQLCursor.execute
    with pytest.raises(RuntimeError):
        with script.capture_selects():
            assert script.py_cursor.MySQLCursor.execute is not original
            raise RuntimeError("benchmark failed")
    assert script.py_cursor.MySQLCursor.execute is original
