"""Train and compare local forecasting models with a chronological split."""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cyberhub_manager.application.services.forecasting.dataset import ForecastDataset, ROOM_TYPES
from cyberhub_manager.application.services.forecasting.evaluation import evaluate_predictions
from cyberhub_manager.application.services.forecasting.features import FEATURE_NAMES, TARGET_FIELDS, FeatureRow, build_feature_rows


ARTIFACT_VERSION = 1


class SeasonalNaiveRegressor:
    """Seven-day seasonal baseline with the same interface as sklearn models."""

    def __init__(self, feature_index: int) -> None:
        self.feature_index = feature_index

    def fit(self, _x: list[list[float]], _y: list[float]) -> "SeasonalNaiveRegressor":
        return self

    def predict(self, x: list[list[float]]) -> list[float]:
        return [float(row[self.feature_index]) for row in x]


@dataclass(slots=True)
class ForecastArtifact:
    version: int
    trained_at: datetime
    source: str
    trained_on_simulated_data: bool
    feature_names: tuple[str, ...]
    history: tuple[Any, ...]
    models: dict[str, Any]
    selected_models: dict[str, str]
    evaluation: dict[str, Any]

    def save(self, path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as stream:
            pickle.dump(self, stream, protocol=pickle.HIGHEST_PROTOCOL)
        return output

    @classmethod
    def load(cls, path: str | Path) -> "ForecastArtifact":
        # Model artifacts are pickle files: only load files produced locally by
        # this project, never an untrusted upload.
        with Path(path).open("rb") as stream:
            from cyberhub_manager.infrastructure.artifacts import ForecastUnpickler

            artifact = ForecastUnpickler(stream, module_aliases={
                "cyberhub_manager.services.forecasting":
                    "cyberhub_manager.application.services.forecasting",
            }).load()  # trusted local artifact
        if not isinstance(artifact, cls) or artifact.version != ARTIFACT_VERSION:
            raise ValueError("unsupported forecasting artifact")
        return artifact

    def save_report(self, path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "artifact_version": self.version,
            "trained_at": self.trained_at.isoformat(),
            "source": self.source,
            "is_simulated": self.trained_on_simulated_data,
            **self.evaluation,
        }
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return output


class ForecastTrainer:
    """Compare baseline and three regressors, then retain the best per target."""

    def __init__(self, *, random_state: int = 20261116) -> None:
        self.random_state = random_state

    def train(self, dataset: ForecastDataset) -> ForecastArtifact:
        active_days = sum(
            item.revenue > 0 and item.session_count > 0
            for item in dataset.observations
        )
        if active_days < 30:
            raise ValueError(
                "at least 30 days with revenue and sessions are required; "
                "use the labelled demo dataset until MySQL has enough history"
            )
        rows = build_feature_rows(dataset.observations)
        train_rows, test_rows = self._time_split(rows)
        candidates = self._candidate_models()
        selected_models: dict[str, str] = {}
        production_models: dict[str, Any] = {}
        report_targets: dict[str, Any] = {}

        train_x = [list(row.values) for row in train_rows]
        test_x = [list(row.values) for row in test_rows]
        all_x = [list(row.values) for row in rows]

        for target in TARGET_FIELDS:
            train_y = [row.targets[target] for row in train_rows]
            test_y = [row.targets[target] for row in test_rows]
            all_y = [row.targets[target] for row in rows]
            results: dict[str, Any] = {}

            for name, factory in candidates[target].items():
                model = factory()
                model.fit(train_x, train_y)
                predictions = [max(0.0, float(value)) for value in model.predict(test_x)]
                metrics = evaluate_predictions(test_y, predictions)
                results[name] = metrics.to_dict()

            winner = min(results, key=lambda name: results[name]["mae"])
            selected_models[target] = winner
            final_model = candidates[target][winner]()
            final_model.fit(all_x, all_y)
            production_models[target] = final_model
            report_targets[target] = {
                "selected_model": winner,
                "models": results,
            }

        return ForecastArtifact(
            version=ARTIFACT_VERSION,
            trained_at=datetime.now(timezone.utc),
            source=dataset.source,
            trained_on_simulated_data=dataset.is_simulated,
            feature_names=FEATURE_NAMES,
            history=dataset.observations,
            models=production_models,
            selected_models=selected_models,
            evaluation={
                "split": {
                    "strategy": "chronological_holdout",
                    "train_from": train_rows[0].day.isoformat(),
                    "train_to": train_rows[-1].day.isoformat(),
                    "test_from": test_rows[0].day.isoformat(),
                    "test_to": test_rows[-1].day.isoformat(),
                    "train_samples": len(train_rows),
                    "test_samples": len(test_rows),
                },
                "targets": report_targets,
                "room_type_summary": self._room_type_summary(dataset),
            },
        )

    @staticmethod
    def _time_split(
        rows: tuple[FeatureRow, ...],
    ) -> tuple[tuple[FeatureRow, ...], tuple[FeatureRow, ...]]:
        if len(rows) < 45:
            raise ValueError("at least 59 daily observations are required for training")
        test_size = max(14, round(len(rows) * 0.20))
        train_rows = rows[:-test_size]
        test_rows = rows[-test_size:]
        if len(train_rows) < 30:
            raise ValueError("training partition must contain at least 30 samples")
        return train_rows, test_rows

    def _candidate_models(self) -> dict[str, dict[str, Any]]:
        from cyberhub_manager.infrastructure.forecast_models import model_types

        LinearRegression, RandomForestRegressor, GradientBoostingRegressor = model_types()

        candidates: dict[str, dict[str, Any]] = {}
        for target in TARGET_FIELDS:
            lag_feature = FEATURE_NAMES.index(f"{target}_lag_7")
            candidates[target] = {
                "seasonal_naive": lambda index=lag_feature: SeasonalNaiveRegressor(index),
                "linear_regression": LinearRegression,
                "random_forest": lambda: RandomForestRegressor(
                    n_estimators=180,
                    min_samples_leaf=2,
                    random_state=self.random_state,
                    n_jobs=-1,
                ),
                "gradient_boosting": lambda: GradientBoostingRegressor(
                    n_estimators=140,
                    learning_rate=0.04,
                    max_depth=3,
                    loss="huber",
                    random_state=self.random_state,
                ),
            }
        return candidates

    @staticmethod
    def _room_type_summary(dataset: ForecastDataset) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for room_type in ROOM_TYPES:
            sessions = sum(item.room_sessions[room_type] for item in dataset.observations)
            revenue = sum(item.room_revenue[room_type] for item in dataset.observations)
            result[room_type] = {
                "sessions": sessions,
                "revenue": revenue,
                "average_revenue_per_session": revenue / sessions if sessions else 0.0,
            }
        return result
