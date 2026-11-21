"""Recursive 7/30-day prediction from a trained local artifact."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from cyberhub_manager.application.services.forecasting.dataset import DailyObservation, ROOM_TYPES, is_vietnam_public_holiday
from cyberhub_manager.application.services.forecasting.features import build_feature_vector
from cyberhub_manager.application.services.forecasting.trainer import ForecastArtifact


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    day: date
    predicted_revenue: float
    predicted_customers: int
    predicted_sessions: int
    room_sessions: dict[str, int]
    room_revenue: dict[str, float]
    is_holiday: bool
    trained_on_simulated_data: bool

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["day"] = self.day.isoformat()
        payload["is_simulated"] = self.trained_on_simulated_data
        return payload


class ForecastPredictor:
    def __init__(self, artifact: ForecastArtifact) -> None:
        if not artifact.history:
            raise ValueError("forecast artifact has no history")
        self.artifact = artifact

    @classmethod
    def load(cls, path: str | Path) -> "ForecastPredictor":
        return cls(ForecastArtifact.load(path))

    def predict(self, days: int) -> tuple[ForecastPoint, ...]:
        if not 1 <= days <= 90:
            raise ValueError("forecast horizon must be between 1 and 90 days")

        history = list(self.artifact.history)
        points: list[ForecastPoint] = []
        for _ in range(days):
            target_day = history[-1].day + timedelta(days=1)
            vector = [list(build_feature_vector(history, target_day))]
            revenue = max(
                0.0, float(self.artifact.models["revenue"].predict(vector)[0])
            )
            customers = max(
                0,
                round(
                    float(
                        self.artifact.models["customer_count"].predict(vector)[0]
                    )
                ),
            )
            sessions = max(
                customers,
                round(
                    float(self.artifact.models["session_count"].predict(vector)[0])
                ),
            )
            room_sessions = self._allocate_room_sessions(history, target_day, sessions)
            room_revenue = self._allocate_room_revenue(history, room_sessions, revenue)
            point = ForecastPoint(
                day=target_day,
                predicted_revenue=round(revenue, 2),
                predicted_customers=customers,
                predicted_sessions=sessions,
                room_sessions=room_sessions,
                room_revenue=room_revenue,
                is_holiday=is_vietnam_public_holiday(target_day),
                trained_on_simulated_data=self.artifact.trained_on_simulated_data,
            )
            points.append(point)
            history.append(
                DailyObservation(
                    day=target_day,
                    revenue=point.predicted_revenue,
                    customer_count=customers,
                    session_count=sessions,
                    standard_sessions=room_sessions["STANDARD"],
                    vip_sessions=room_sessions["VIP"],
                    couple_sessions=room_sessions["COUPLE"],
                    super_vip_sessions=room_sessions["SUPER_VIP"],
                    standard_revenue=room_revenue["STANDARD"],
                    vip_revenue=room_revenue["VIP"],
                    couple_revenue=room_revenue["COUPLE"],
                    super_vip_revenue=room_revenue["SUPER_VIP"],
                    is_holiday=point.is_holiday,
                    is_simulated=self.artifact.trained_on_simulated_data,
                )
            )
        return tuple(points)

    def save_predictions(self, path: str | Path, days: int) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        points = self.predict(days)
        payload = {
            "schema_version": 1,
            "horizon_days": days,
            "source": self.artifact.source,
            "is_simulated": self.artifact.trained_on_simulated_data,
            "selected_models": self.artifact.selected_models,
            "predictions": [point.to_dict() for point in points],
        }
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return output

    @staticmethod
    def _shares(history: list[DailyObservation], day: date, field: str) -> list[float]:
        comparable = [item for item in history[-84:] if item.day.weekday() == day.weekday()]
        sample = comparable or history[-28:]
        totals = [
            sum(
                (item.room_sessions if field == "sessions" else item.room_revenue)[room]
                for item in sample
            )
            for room in ROOM_TYPES
        ]
        total = sum(totals)
        return [value / total for value in totals] if total else [0.57, 0.24, 0.12, 0.07]

    def _allocate_room_sessions(
        self, history: list[DailyObservation], day: date, total: int
    ) -> dict[str, int]:
        shares = self._shares(history, day, "sessions")
        raw = [total * share for share in shares]
        values = [math.floor(value) for value in raw]
        for index in sorted(
            range(len(raw)), key=lambda item: raw[item] % 1, reverse=True
        )[: total - sum(values)]:
            values[index] += 1
        return dict(zip(ROOM_TYPES, values, strict=True))

    def _allocate_room_revenue(
        self,
        history: list[DailyObservation],
        room_sessions: dict[str, int],
        total: float,
    ) -> dict[str, float]:
        historical = self._shares(history, history[-1].day + timedelta(days=1), "revenue")
        # Blend historical revenue share with the predicted room demand share.
        session_total = max(1, sum(room_sessions.values()))
        weights = [
            (historical[index] + room_sessions[room] / session_total) / 2
            for index, room in enumerate(ROOM_TYPES)
        ]
        weight_total = sum(weights) or 1.0
        allocated = {
            room: round(total * weights[index] / weight_total, 2)
            for index, room in enumerate(ROOM_TYPES)
        }
        difference = round(total - sum(allocated.values()), 2)
        allocated[ROOM_TYPES[0]] = round(allocated[ROOM_TYPES[0]] + difference, 2)
        return allocated
