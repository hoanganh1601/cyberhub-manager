"""Time-series evaluation metrics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import fmean
from typing import Iterable


@dataclass(frozen=True, slots=True)
class MetricResult:
    mae: float
    mape: float | None
    sample_count: int

    def to_dict(self) -> dict[str, float | int | None]:
        return asdict(self)


def evaluate_predictions(
    actual: Iterable[float],
    predicted: Iterable[float],
) -> MetricResult:
    actual_values = [float(value) for value in actual]
    predicted_values = [float(value) for value in predicted]
    if not actual_values or len(actual_values) != len(predicted_values):
        raise ValueError("actual and predicted must have the same non-zero length")

    absolute_errors = [
        abs(actual_value - predicted_value)
        for actual_value, predicted_value in zip(
            actual_values, predicted_values, strict=True
        )
    ]
    percentage_errors = [
        error / abs(actual_value) * 100
        for actual_value, error in zip(actual_values, absolute_errors, strict=True)
        if actual_value != 0
    ]
    return MetricResult(
        mae=fmean(absolute_errors),
        mape=fmean(percentage_errors) if percentage_errors else None,
        sample_count=len(actual_values),
    )
