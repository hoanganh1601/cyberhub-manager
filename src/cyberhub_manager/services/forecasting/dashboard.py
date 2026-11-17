"""Read validated forecast artifacts and build management planning summaries."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cyberhub_manager.domain.exceptions import NotFoundError, ValidationError

from .dataset import ROOM_TYPES


VN_TZ = timezone(timedelta(hours=7))


class ForecastDashboardService:
    """Expose trusted local forecast output without running training in a request."""

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)

    def dashboard(self, *, horizon_days: int, store_id: int) -> dict[str, Any]:
        if horizon_days not in (7, 30):
            raise ValidationError(
                field_errors={"days": "Chỉ hỗ trợ dự báo 7 hoặc 30 ngày"}
            )
        store_dir = self.output_dir / f"store-{store_id}"
        source_dir = store_dir if store_dir.is_dir() else self.output_dir
        report = self._read_json(source_dir, "evaluation.json")
        forecast = self._read_json(
            source_dir, f"forecast_{horizon_days}_days.json"
        )
        self._validate_payloads(report, forecast, horizon_days, store_id)

        predictions = forecast["predictions"]
        summary = self._summary(predictions)
        room_types = self._room_summary(predictions)
        first_day = date.fromisoformat(predictions[0]["day"])
        last_day = date.fromisoformat(predictions[-1]["day"])
        today = datetime.now(VN_TZ).date()

        targets = report.get("targets", {})
        metrics = {
            target: {
                "selected_model": details.get("selected_model"),
                **details.get("models", {}).get(details.get("selected_model"), {}),
            }
            for target, details in targets.items()
            if isinstance(details, dict)
        }
        return {
            "horizon_days": horizon_days,
            "source": forecast["source"],
            "is_simulated": bool(forecast.get("is_simulated")),
            "trained_at": report.get("trained_at"),
            "forecast_from": first_day,
            "forecast_to": last_day,
            "is_stale": last_day < today or first_day > today + timedelta(days=1),
            "selected_models": forecast.get("selected_models", {}),
            "metrics": metrics,
            "split": report.get("split", {}),
            "predictions": predictions,
            "summary": summary,
            "room_types": room_types,
            "planning": self._planning(summary, room_types, predictions),
        }

    def _read_json(self, directory: Path, name: str) -> dict[str, Any]:
        path = directory / name
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise NotFoundError(
                "Chưa có dữ liệu dự báo. Hãy chạy scripts.run_forecasting trước."
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ValidationError(
                "Tệp dự báo không hợp lệ. Hãy huấn luyện và xuất lại dữ liệu."
            ) from exc
        if not isinstance(payload, dict):
            raise ValidationError("Tệp dự báo phải chứa JSON object")
        return payload

    @staticmethod
    def _validate_payloads(
        report: dict[str, Any],
        forecast: dict[str, Any],
        horizon_days: int,
        store_id: int,
    ) -> None:
        if forecast.get("schema_version") != 1:
            raise ValidationError("Phiên bản dữ liệu dự báo không được hỗ trợ")
        if forecast.get("horizon_days") != horizon_days:
            raise ValidationError("Khoảng dự báo không khớp với tệp dữ liệu")
        if report.get("source") != forecast.get("source"):
            raise ValidationError("Báo cáo đánh giá và dự báo không cùng nguồn dữ liệu")
        source = str(forecast.get("source", ""))
        if source.startswith("mysql:store-") and source != f"mysql:store-{store_id}":
            raise NotFoundError("Chưa có dự báo cho cơ sở hiện tại")
        predictions = forecast.get("predictions")
        if not isinstance(predictions, list) or len(predictions) != horizon_days:
            raise ValidationError("Danh sách dự báo không đầy đủ")
        try:
            days = [date.fromisoformat(str(item["day"])) for item in predictions]
            for item in predictions:
                float(item["predicted_revenue"])
                int(item["predicted_customers"])
                int(item["predicted_sessions"])
                if not isinstance(item["room_sessions"], dict):
                    raise TypeError
                if not isinstance(item["room_revenue"], dict):
                    raise TypeError
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError("Một bản ghi dự báo không hợp lệ") from exc
        if days != sorted(days) or len(days) != len(set(days)):
            raise ValidationError("Ngày dự báo phải duy nhất và tăng dần")

    @staticmethod
    def _summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
        total_revenue = sum(float(item["predicted_revenue"]) for item in predictions)
        total_customers = sum(int(item["predicted_customers"]) for item in predictions)
        total_sessions = sum(int(item["predicted_sessions"]) for item in predictions)
        peak_customers = max(
            predictions, key=lambda item: int(item["predicted_customers"])
        )
        peak_revenue = max(
            predictions, key=lambda item: float(item["predicted_revenue"])
        )
        return {
            "total_revenue": round(total_revenue, 2),
            "average_daily_revenue": round(total_revenue / len(predictions), 2),
            "total_customers": total_customers,
            "average_daily_customers": round(total_customers / len(predictions), 1),
            "total_sessions": total_sessions,
            "average_daily_sessions": round(total_sessions / len(predictions), 1),
            "peak_customer_day": peak_customers["day"],
            "peak_customer_count": int(peak_customers["predicted_customers"]),
            "peak_revenue_day": peak_revenue["day"],
            "peak_revenue": round(float(peak_revenue["predicted_revenue"]), 2),
        }

    @staticmethod
    def _room_summary(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for room_type in ROOM_TYPES:
            sessions = sum(
                int(item["room_sessions"].get(room_type, 0)) for item in predictions
            )
            revenue = sum(
                float(item["room_revenue"].get(room_type, 0)) for item in predictions
            )
            result.append(
                {
                    "room_type": room_type,
                    "sessions": sessions,
                    "revenue": round(revenue, 2),
                    "average_revenue_per_session": round(
                        revenue / sessions if sessions else 0, 2
                    ),
                }
            )
        return result

    @staticmethod
    def _planning(
        summary: dict[str, Any],
        room_types: list[dict[str, Any]],
        predictions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        average = float(summary["average_daily_customers"])
        busy_days = [
            item["day"]
            for item in predictions
            if int(item["predicted_customers"]) >= average * 1.15
        ]
        room_focus = max(room_types, key=lambda item: item["revenue"])
        return {
            "revenue_target": round(float(summary["total_revenue"]) * 1.05, 2),
            "busy_days": busy_days,
            "suggested_extra_staff": 2 if summary["peak_customer_count"] >= average * 1.35 else 1,
            "estimated_drinks": round(int(summary["total_customers"]) * 0.65),
            "estimated_meals": round(int(summary["total_customers"]) * 0.35),
            "room_focus": room_focus["room_type"],
            "room_focus_revenue": room_focus["revenue"],
            "note": "Operational estimates only; validate against staffing and recipe data.",
        }
