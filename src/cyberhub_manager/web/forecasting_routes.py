"""Management-only forecasting dashboard routes."""

from __future__ import annotations

import os
from pathlib import Path

from flask import g, request

from cyberhub_manager.domain.exceptions import ValidationError
from cyberhub_manager.services.forecasting.dashboard import ForecastDashboardService


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def register_forecasting_routes(app, *, reply, manager_only) -> None:
    output_dir = Path(
        os.getenv(
            "CYBERHUB_FORECAST_DIR",
            str(PROJECT_ROOT / "runtime" / "forecasting"),
        )
    )
    service = ForecastDashboardService(output_dir)

    @app.get("/api/forecasting")
    @manager_only
    def forecasting_dashboard():
        try:
            horizon_days = int(request.args.get("days", "7"))
        except ValueError as exc:
            raise ValidationError(
                field_errors={"days": "Chỉ hỗ trợ dự báo 7 hoặc 30 ngày"}
            ) from exc
        return reply(
            service.dashboard(
                horizon_days=horizon_days,
                store_id=g.actor.store_id,
            )
        )
