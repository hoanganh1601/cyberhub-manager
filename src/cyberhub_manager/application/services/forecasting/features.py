"""Leakage-safe feature engineering for daily time series."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from statistics import fmean

from cyberhub_manager.application.services.forecasting.dataset import DailyObservation, is_vietnam_public_holiday


TARGET_FIELDS = ("revenue", "customer_count", "session_count")
MINIMUM_HISTORY_DAYS = 14
FEATURE_NAMES = (
    "trend_days",
    "day_of_week_sin",
    "day_of_week_cos",
    "month_sin",
    "month_cos",
    "is_weekend",
    "is_holiday",
    "revenue_lag_1",
    "revenue_lag_7",
    "revenue_mean_7",
    "revenue_mean_14",
    "customer_count_lag_1",
    "customer_count_lag_7",
    "customer_count_mean_7",
    "customer_count_mean_14",
    "session_count_lag_1",
    "session_count_lag_7",
    "session_count_mean_7",
    "session_count_mean_14",
)


@dataclass(frozen=True, slots=True)
class FeatureRow:
    day: date
    values: tuple[float, ...]
    targets: dict[str, float]


def _mean(history: list[DailyObservation], field: str, days: int) -> float:
    return fmean(float(getattr(item, field)) for item in history[-days:])


def build_feature_vector(
    history: list[DailyObservation],
    target_day: date,
) -> tuple[float, ...]:
    """Build features using only observations before ``target_day``."""

    if len(history) < MINIMUM_HISTORY_DAYS:
        raise ValueError(f"at least {MINIMUM_HISTORY_DAYS} history days are required")
    if history[-1].day >= target_day:
        raise ValueError("feature history must end before target_day")

    dow_angle = 2 * math.pi * target_day.weekday() / 7
    month_angle = 2 * math.pi * (target_day.month - 1) / 12
    values: list[float] = [
        float((target_day - history[0].day).days),
        math.sin(dow_angle),
        math.cos(dow_angle),
        math.sin(month_angle),
        math.cos(month_angle),
        float(target_day.weekday() >= 5),
        float(is_vietnam_public_holiday(target_day)),
    ]
    for field in TARGET_FIELDS:
        values.extend(
            (
                float(getattr(history[-1], field)),
                float(getattr(history[-7], field)),
                _mean(history, field, 7),
                _mean(history, field, 14),
            )
        )
    return tuple(values)


def build_feature_rows(
    observations: tuple[DailyObservation, ...],
) -> tuple[FeatureRow, ...]:
    if len(observations) <= MINIMUM_HISTORY_DAYS:
        raise ValueError("dataset does not contain enough history")

    rows: list[FeatureRow] = []
    for index in range(MINIMUM_HISTORY_DAYS, len(observations)):
        observation = observations[index]
        history = list(observations[:index])
        rows.append(
            FeatureRow(
                day=observation.day,
                values=build_feature_vector(history, observation.day),
                targets={
                    field: float(getattr(observation, field))
                    for field in TARGET_FIELDS
                },
            )
        )
    return tuple(rows)
