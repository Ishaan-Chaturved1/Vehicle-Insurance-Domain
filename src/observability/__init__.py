"""
Observability package for Vehicle Insurance MLOps Application.
"""
from src.observability.metrics import (
    PREDICTION_REQUESTS_TOTAL,
    PREDICTION_ERRORS_TOTAL,
    PREDICTION_LATENCY_SECONDS,
    TRAINING_RUNS_TOTAL,
    TRAINING_FAILURES_TOTAL,
    MONGODB_ERRORS_TOTAL,
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    PrometheusMiddleware,
    get_latest_metrics,
)

__all__ = [
    "PREDICTION_REQUESTS_TOTAL",
    "PREDICTION_ERRORS_TOTAL",
    "PREDICTION_LATENCY_SECONDS",
    "TRAINING_RUNS_TOTAL",
    "TRAINING_FAILURES_TOTAL",
    "MONGODB_ERRORS_TOTAL",
    "HTTP_REQUESTS_TOTAL",
    "HTTP_REQUEST_DURATION_SECONDS",
    "PrometheusMiddleware",
    "get_latest_metrics",
]
