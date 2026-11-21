"""Offline revenue and customer-demand forecasting.

The package is intentionally independent from the assistant/RAG runtime.  It
uses local historical aggregates and never needs an API key.
"""

from cyberhub_manager.application.services.forecasting.dataset import DailyObservation, ForecastDataset, generate_demo_dataset
from cyberhub_manager.application.services.forecasting.dashboard import ForecastDashboardService
from cyberhub_manager.application.services.forecasting.evaluation import MetricResult, evaluate_predictions
from cyberhub_manager.application.services.forecasting.predictor import ForecastPoint, ForecastPredictor
from cyberhub_manager.application.services.forecasting.trainer import ForecastArtifact, ForecastTrainer

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
