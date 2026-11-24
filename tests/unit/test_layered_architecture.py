"""Architectural fitness rules: inspect lazy imports too, without importing GUI/DB."""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "src" / "cyberhub_manager"
ALLOWED = {
    "presentation": {"presentation", "application", "domain"},
    "application": {"application", "infrastructure", "domain"},
    "infrastructure": {"infrastructure", "domain"},
    "domain": {"domain"},
}


def violations(root):
    errors = []
    for layer, allowed in ALLOWED.items():
        for path in (root / layer).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        errors.append(f"{path}:{node.lineno}: use absolute imports")
                    names = [node.module or ""]
                for name in names:
                    if name.startswith("cyberhub_manager."):
                        target = name.split(".")[1]
                        if target not in allowed:
                            errors.append(f"{path}:{node.lineno}: {layer} -> {name}")
                    if layer in {"domain", "presentation", "application"} and name.split('.')[0] in {
                        "mysql", "sqlite3", "sklearn", "bcrypt",
                    }:
                        errors.append(f"{path}:{node.lineno}: vendor {name} belongs in infrastructure")
                    if layer in {"domain", "infrastructure", "application"} and name.split('.')[0] in {
                        "flask", "customtkinter", "tkinter", "werkzeug",
                    }:
                        errors.append(f"{path}:{node.lineno}: UI framework {name} in {layer}")
                if layer in {"application", "presentation"} and isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute) and node.func.attr in {"cursor", "execute", "executemany"}:
                        errors.append(f"{path}:{node.lineno}: SQL belongs in infrastructure")
    return errors


def test_layer_dependencies_are_enforced():
    assert violations(ROOT) == []


@pytest.mark.parametrize("source,target", [
    ("presentation", "infrastructure.repositories"),
    ("infrastructure", "application.services"),
    ("domain", "presentation.web"),
])
def test_architecture_check_detects_forbidden_dependencies(tmp_path, source, target):
    folder = tmp_path / source
    folder.mkdir()
    (folder / "example.py").write_text(f"def lazy():\n    import cyberhub_manager.{target}\n")
    assert violations(tmp_path)


def test_web_legacy_entrypoint_and_packaged_assets():
    from importlib.resources import files
    from cyberhub_manager.web import create_app as legacy
    from cyberhub_manager.presentation.web import create_app

    assert legacy is create_app
    assert files("cyberhub_manager.presentation.web").joinpath("templates/index.html").is_file()
    assert files("cyberhub_manager.presentation.desktop.assets").joinpath("cyberhub_logo_dark.png").is_file()


def test_desktop_compatibility_retains_module_identity():
    from cyberhub_manager import app
    from cyberhub_manager.presentation import desktop_app

    assert app is desktop_app


def test_forecast_unpickler_resolves_legacy_module_names():
    from io import BytesIO
    from cyberhub_manager.infrastructure.artifacts import ForecastUnpickler
    from cyberhub_manager.application.services.forecasting.trainer import ForecastArtifact

    payload = b"ccyberhub_manager.services.forecasting.trainer\nForecastArtifact\n."
    result = ForecastUnpickler(BytesIO(payload), module_aliases={
        "cyberhub_manager.services.forecasting":
            "cyberhub_manager.application.services.forecasting",
    }).load()
    assert result is ForecastArtifact
