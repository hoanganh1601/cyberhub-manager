"""Offline forecasting contracts: chronology, provenance and safe planning output."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from cyberhub_manager.domain.exceptions import NotFoundError, ValidationError
from cyberhub_manager.services.forecasting.dashboard import ForecastDashboardService
from cyberhub_manager.services.forecasting.dataset import (
    DailyObservation,
    ForecastDataset,
    generate_demo_dataset,
)
from cyberhub_manager.services.forecasting.evaluation import evaluate_predictions
from cyberhub_manager.services.forecasting.features import build_feature_rows
from cyberhub_manager.services.forecasting.predictor import ForecastPredictor
from cyberhub_manager.services.forecasting.trainer import ForecastTrainer


def test_demo_dataset_is_deterministic_contiguous_and_explicitly_simulated():
    end = date(2026, 11, 16)
    first = generate_demo_dataset(days=90, end_day=end, seed=42)
    second = generate_demo_dataset(days=90, end_day=end, seed=42)

    assert first.source == "simulated:90-days:seed-42"
    assert first.is_simulated is True
    assert first.observations[0].day == end - timedelta(days=89)
    assert first.observations[-1].day == end
    assert [item.to_dict() for item in first.observations] == [
        item.to_dict() for item in second.observations
    ]
    assert all(
        sum(item.room_sessions.values()) == item.session_count
        for item in first.observations
    )


def test_dataset_rejects_gaps_mixed_provenance_and_invalid_room_totals():
    base = generate_demo_dataset(days=90, end_day=date(2026, 11, 16), seed=7)
    with pytest.raises(ValueError, match="every calendar day"):
        ForecastDataset(
            observations=base.observations[:10] + base.observations[11:],
            source=base.source,
            generated_at=base.generated_at,
        )

    real = DailyObservation(
        day=base.observations[-1].day + timedelta(days=1),
        revenue=0,
        customer_count=0,
        session_count=0,
        is_simulated=False,
    )
    with pytest.raises(ValueError, match="must not be mixed"):
        ForecastDataset(
            observations=base.observations + (real,),
            source="invalid",
            generated_at=base.generated_at,
        )

    with pytest.raises(ValueError, match="must equal session_count"):
        DailyObservation(
            day=date(2026, 1, 1),
            revenue=10_000,
            customer_count=1,
            session_count=1,
            is_simulated=True,
        )


def test_feature_rows_only_use_prior_days_and_time_order():
    dataset = generate_demo_dataset(days=90, end_day=date(2026, 11, 16), seed=11)
    rows = build_feature_rows(dataset.observations)

    assert rows[0].day == dataset.observations[14].day
    assert rows[-1].day == dataset.observations[-1].day
    assert [row.day for row in rows] == sorted(row.day for row in rows)
    # Lag 1 revenue is the prior observation, never the target day's revenue.
    assert rows[0].values[7] == dataset.observations[13].revenue


def test_evaluation_keeps_zero_actuals_in_mae_but_not_mape():
    result = evaluate_predictions([0, 100, 200], [30, 110, 180])
    assert result.mae == 20
    assert result.mape == pytest.approx(10)
    assert result.sample_count == 3


@pytest.fixture(scope="module")
def trained_forecast():
    dataset = generate_demo_dataset(
        days=90, end_day=date(2026, 11, 16), seed=20261116
    )
    artifact = ForecastTrainer(random_state=20261116).train(dataset)
    return dataset, artifact


def test_training_uses_chronological_holdout_and_compares_all_models(trained_forecast):
    dataset, artifact = trained_forecast
    split = artifact.evaluation["split"]

    assert split["strategy"] == "chronological_holdout"
    assert split["train_to"] < split["test_from"]
    assert artifact.trained_on_simulated_data is True
    assert artifact.source == dataset.source
    for target in ("revenue", "customer_count", "session_count"):
        result = artifact.evaluation["targets"][target]
        assert set(result["models"]) == {
            "seasonal_naive",
            "linear_regression",
            "random_forest",
            "gradient_boosting",
        }
        assert result["selected_model"] in result["models"]


def test_recursive_predictions_preserve_totals_and_provenance(trained_forecast):
    _, artifact = trained_forecast
    points = ForecastPredictor(artifact).predict(30)

    assert len(points) == 30
    assert points[0].day == artifact.history[-1].day + timedelta(days=1)
    assert all(right.day - left.day == timedelta(days=1) for left, right in zip(points, points[1:]))
    assert all(sum(point.room_sessions.values()) == point.predicted_sessions for point in points)
    assert all(sum(point.room_revenue.values()) == pytest.approx(point.predicted_revenue) for point in points)
    assert all(point.trained_on_simulated_data for point in points)


def test_dashboard_builds_management_summary_from_valid_artifacts(tmp_path, trained_forecast):
    _, artifact = trained_forecast
    artifact.save_report(tmp_path / "evaluation.json")
    predictor = ForecastPredictor(artifact)
    predictor.save_predictions(tmp_path / "forecast_7_days.json", 7)

    result = ForecastDashboardService(tmp_path).dashboard(horizon_days=7, store_id=1)

    assert result["is_simulated"] is True
    assert result["horizon_days"] == 7
    assert len(result["predictions"]) == 7
    assert result["summary"]["total_revenue"] > 0
    assert result["planning"]["revenue_target"] > result["summary"]["total_revenue"]
    assert {item["room_type"] for item in result["room_types"]} == {
        "STANDARD",
        "VIP",
        "COUPLE",
        "SUPER_VIP",
    }


def test_dashboard_fails_closed_for_missing_mismatched_or_cross_store_files(tmp_path):
    service = ForecastDashboardService(tmp_path)
    with pytest.raises(NotFoundError):
        service.dashboard(horizon_days=7, store_id=1)
    with pytest.raises(ValidationError):
        service.dashboard(horizon_days=14, store_id=1)

    report = {"source": "mysql:store-2", "targets": {}}
    forecast = {
        "schema_version": 1,
        "horizon_days": 7,
        "source": "mysql:store-2",
        "is_simulated": False,
        "predictions": [
            {
                "day": (date(2026, 11, 17) + timedelta(days=index)).isoformat(),
                "predicted_revenue": 100_000,
                "predicted_customers": 10,
                "predicted_sessions": 11,
                "room_sessions": {},
                "room_revenue": {},
            }
            for index in range(7)
        ],
    }
    (tmp_path / "evaluation.json").write_text(json.dumps(report), encoding="utf-8")
    (tmp_path / "forecast_7_days.json").write_text(json.dumps(forecast), encoding="utf-8")
    with pytest.raises(NotFoundError, match="cơ sở hiện tại"):
        service.dashboard(horizon_days=7, store_id=1)
