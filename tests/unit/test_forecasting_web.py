"""Management-only HTTP boundary for offline forecasting artifacts."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest

pytest.importorskip("flask")

from cyberhub_manager.web import create_app


def _write_forecast(directory, days: int) -> None:
    source = "simulated:90-days:seed-7"
    report = {
        "artifact_version": 1,
        "trained_at": datetime(2026, 11, 16, tzinfo=timezone.utc).isoformat(),
        "source": source,
        "is_simulated": True,
        "split": {
            "strategy": "chronological_holdout",
            "test_from": "2026-11-01",
            "test_to": "2026-11-16",
        },
        "targets": {
            target: {
                "selected_model": "seasonal_naive",
                "models": {
                    "seasonal_naive": {
                        "mae": 10,
                        "mape": 5,
                        "sample_count": 14,
                    }
                },
            }
            for target in ("revenue", "customer_count", "session_count")
        },
    }
    forecast = {
        "schema_version": 1,
        "horizon_days": days,
        "source": source,
        "is_simulated": True,
        "selected_models": {
            "revenue": "seasonal_naive",
            "customer_count": "seasonal_naive",
            "session_count": "seasonal_naive",
        },
        "predictions": [
            {
                "day": (date(2026, 11, 17) + timedelta(days=index)).isoformat(),
                "predicted_revenue": 1_000_000 + index * 10_000,
                "predicted_customers": 40 + index,
                "predicted_sessions": 45 + index,
                "room_sessions": {
                    "STANDARD": 25 + index,
                    "VIP": 10,
                    "COUPLE": 6,
                    "SUPER_VIP": 4,
                },
                "room_revenue": {
                    "STANDARD": 500_000 + index * 10_000,
                    "VIP": 250_000,
                    "COUPLE": 150_000,
                    "SUPER_VIP": 100_000,
                },
                "is_holiday": False,
                "is_simulated": True,
            }
            for index in range(days)
        ],
    }
    (directory / "evaluation.json").write_text(json.dumps(report), encoding="utf-8")
    (directory / f"forecast_{days}_days.json").write_text(
        json.dumps(forecast), encoding="utf-8"
    )


@pytest.fixture
def app(tmp_path, monkeypatch):
    _write_forecast(tmp_path, 7)
    _write_forecast(tmp_path, 30)
    monkeypatch.setenv("CYBERHUB_FORECAST_DIR", str(tmp_path))
    return create_app(
        {
            "TESTING": True,
            "WEB_MODE": "demo",
            "SECRET_KEY": "forecast-web-test-secret",
            "ASSISTANT_ENABLED": False,
        }
    )


def _login(client, username: str) -> None:
    csrf = client.get("/api/session").json["csrf_token"]
    response = client.post(
        "/api/login",
        json={"username": username, "password": "demo123"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200


@pytest.mark.parametrize("username", ["quanly01", "admin01"])
def test_manager_and_admin_can_read_forecast(app, username):
    client = app.test_client()
    _login(client, username)

    response = client.get("/api/forecasting?days=7")

    assert response.status_code == 200
    assert response.json["horizon_days"] == 7
    assert response.json["is_simulated"] is True
    assert len(response.json["predictions"]) == 7


@pytest.mark.parametrize("username", ["nhanvien01", "bep01", "thukho01"])
def test_non_management_roles_cannot_read_forecast(app, username):
    client = app.test_client()
    _login(client, username)

    response = client.get("/api/forecasting?days=7")

    assert response.status_code == 403


@pytest.mark.parametrize("days", ["14", "invalid"])
def test_forecast_route_rejects_unsupported_horizon(app, days):
    client = app.test_client()
    _login(client, "quanly01")

    response = client.get(f"/api/forecasting?days={days}")

    assert response.status_code == 422
    assert response.json["error"]["code"] == "VALIDATION_ERROR"
