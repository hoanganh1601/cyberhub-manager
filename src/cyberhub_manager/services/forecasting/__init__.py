"""Offline revenue and customer-demand forecasting.

The package is intentionally independent from the assistant/RAG runtime.  It
uses local historical aggregates and never needs an API key.
"""

from .dataset import DailyObservation, ForecastDataset, generate_demo_dataset
from .dashboard import ForecastDashboardService
from .evaluation import MetricResult, evaluate_predictions
from .predictor import ForecastPoint, ForecastPredictor
from .trainer import ForecastArtifact, ForecastTrainer

__all__ = [
    "DailyObservation",
    "ForecastArtifact",
    "ForecastDataset",
    "ForecastDashboardService",
    "ForecastPoint",
    "ForecastPredictor",
    "ForecastTrainer",
    "MetricResult",
    "evaluate_predictions",
    "generate_demo_dataset",
]
