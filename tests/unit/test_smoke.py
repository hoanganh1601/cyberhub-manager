"""Smoke tests for the project skeleton."""

from importlib import import_module

def test_package_can_be_imported() -> None:
    package = import_module('cyberhub_manager')
    assert package.__name__ == "cyberhub_manager"

def test_entry_point_is_callable() -> None:
    app = import_module("cyberhub_manager.app")

    assert callable(app.main)
    # assert: Khẳng định một điều kiện phải đũng