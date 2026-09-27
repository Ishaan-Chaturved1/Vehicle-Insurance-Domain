"""
Prometheus Observability Metrics for Vehicle Insurance MLOps Application.
Provides counters, histograms, and collectors following Prometheus conventions.
"""

import time
from typing import Callable
from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    REGISTRY
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# -----------------------------------------------------------------------------
# Metric Definitions
# -----------------------------------------------------------------------------

# 1. Prediction Metrics
PREDICTION_REQUESTS_TOTAL = Counter(
    "vehicle_insurance_prediction_requests_total",
    "Total number of vehicle insurance prediction requests received.",
    ["status"],  # success, failure
)

PREDICTION_ERRORS_TOTAL = Counter(
    "vehicle_insurance_prediction_errors_total",
    "Total number of vehicle insurance prediction failures.",
    ["error_type"],
)

PREDICTION_LATENCY_SECONDS = Histogram(
    "vehicle_insurance_prediction_latency_seconds",
    "Time spent processing prediction requests in seconds.",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# 2. Training Metrics
TRAINING_RUNS_TOTAL = Counter(
    "vehicle_insurance_training_runs_total",
    "Total number of model training pipeline executions.",
    ["status"],  # started, completed, failed
)

TRAINING_FAILURES_TOTAL = Counter(
    "vehicle_insurance_training_failures_total",
    "Total number of failed training pipeline executions.",
    ["stage"],  # data_ingestion, validation, transformation, training, evaluation, pusher
)

# 3. Database Metrics
MONGODB_ERRORS_TOTAL = Counter(
    "vehicle_insurance_mongodb_errors_total",
    "Total number of MongoDB database operations failures.",
    ["operation"],  # connect, ping, export, query
)

# 4. HTTP Request Metrics (Generic ASGI)
HTTP_REQUESTS_TOTAL = Counter(
    "vehicle_insurance_http_requests_total",
    "Total HTTP requests received by the FastAPI application.",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "vehicle_insurance_http_request_duration_seconds",
    "HTTP request latency across endpoints in seconds.",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Middleware to record standard HTTP request count and latency
    for every incoming request without high-cardinality labels.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Normalize endpoint to avoid high-cardinality path labels
        path = request.url.path
        if path.startswith("/static"):
            path = "/static"
        
        start_time = time.time()
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
        except Exception:
            status_code = "500"
            raise
        finally:
            duration = time.time() - start_time
            # Ignore the metrics scrape itself to prevent loop inflation
            if path != "/metrics":
                HTTP_REQUESTS_TOTAL.labels(
                    method=request.method,
                    endpoint=path,
                    status_code=status_code,
                ).inc()
                HTTP_REQUEST_DURATION_SECONDS.labels(
                    method=request.method,
                    endpoint=path,
                ).observe(duration)

        return response


def get_latest_metrics() -> Response:
    """Returns formatted Prometheus metric output."""
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST
    )
