"""Build data, train local models and export 7/30-day forecasts."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

from cyberhub_manager.infrastructure.database.transaction import transaction
from cyberhub_manager.application.services.forecasting.dataset import (
    ForecastDataset,
    generate_demo_dataset,
    load_mysql_dataset,
)
from cyberhub_manager.application.services.forecasting.predictor import ForecastPredictor
from cyberhub_manager.application.services.forecasting.trainer import ForecastTrainer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "runtime" / "forecasting"


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use date format YYYY-MM-DD") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train offline CyberHub revenue and demand forecasting models."
    )
    parser.add_argument("--source", choices=("demo", "mysql"), default="demo")
    parser.add_argument("--history-days", type=int, default=180)
    parser.add_argument("--end-date", type=_parse_date)
    parser.add_argument("--store-id", type=int)
    parser.add_argument("--seed", type=int, default=20261116)
    parser.add_argument("--output-dir", type=Path)
    return parser


def _build_dataset(args: argparse.Namespace) -> ForecastDataset:
    end_day = args.end_date or (date.today() - timedelta(days=1))
    if args.source == "demo":
        return generate_demo_dataset(
            days=args.history_days,
            end_day=end_day,
            seed=args.seed,
        )
    if args.store_id is None or args.store_id <= 0:
        raise SystemExit("--store-id is required and must be positive for MySQL")
    start_day = end_day - timedelta(days=args.history_days - 1)
    with transaction() as conn:
        return load_mysql_dataset(
            conn,
            store_id=args.store_id,
            start_day=start_day,
            end_day=end_day,
        )


def main() -> None:
    args = build_parser().parse_args()
    if not 90 <= args.history_days <= 365:
        raise SystemExit("--history-days must be between 90 and 365")

    output_dir: Path = (
        args.output_dir
        if args.output_dir is not None
        else DEFAULT_OUTPUT
        / (f"store-{args.store_id}" if args.source == "mysql" else "")
    ).resolve()
    dataset = _build_dataset(args)
    dataset_path = dataset.save(output_dir / "dataset.json")

    artifact = ForecastTrainer(random_state=args.seed).train(dataset)
    model_path = artifact.save(output_dir / "forecast_model.pkl")
    report_path = artifact.save_report(output_dir / "evaluation.json")
    predictor = ForecastPredictor(artifact)
    forecast_7_path = predictor.save_predictions(output_dir / "forecast_7_days.json", 7)
    forecast_30_path = predictor.save_predictions(
        output_dir / "forecast_30_days.json", 30
    )

    print("Forecasting completed successfully.")
    print(f"Source: {dataset.source}")
    print(f"Simulated data: {str(dataset.is_simulated).lower()}")
    print(f"Selected models: {artifact.selected_models}")
    print(f"Dataset: {dataset_path}")
    print(f"Model: {model_path}")
    print(f"Evaluation: {report_path}")
    print(f"7-day forecast: {forecast_7_path}")
    print(f"30-day forecast: {forecast_30_path}")


if __name__ == "__main__":
    main()
