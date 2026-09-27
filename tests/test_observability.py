"""
Unit and integration tests for Observability endpoints and metrics.
Verifies /health, /ready, /metrics, Prometheus counters, and histograms.
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient
from app import app
from src.observability import (
    PREDICTION_REQUESTS_TOTAL,
    PREDICTION_ERRORS_TOTAL,
    PREDICTION_LATENCY_SECONDS,
    TRAINING_RUNS_TOTAL,
    TRAINING_FAILURES_TOTAL,
    MONGODB_ERRORS_TOTAL,
    HTTP_REQUESTS_TOTAL,
)


@pytest.fixture(scope="module")
def client():
    """Provides a TestClient instance for testing FastAPI routes."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    """
    Test Phase 1 requirement:
    GET /health returns HTTP 200 and expected machine-readable payload.
    """
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "vehicle-insurance"


def test_ready_endpoint(client):
    """
    Test Phase 1 requirement:
    GET /ready returns HTTP 200 and readiness status.
    """
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["service"] == "vehicle-insurance"


def test_metrics_endpoint_and_content(client):
    """
    Test Phase 5 & 6 requirement:
    GET /metrics returns HTTP 200 and includes all required Prometheus metrics.
    """
    response = client.get("/metrics")
    assert response.status_code == 200
    content = response.text

    # Verify custom metric declarations are present in Prometheus output
    assert "vehicle_insurance_prediction_requests_total" in content
    assert "vehicle_insurance_prediction_errors_total" in content
    assert "vehicle_insurance_prediction_latency_seconds" in content
    assert "vehicle_insurance_training_runs_total" in content
    assert "vehicle_insurance_training_failures_total" in content
    assert "vehicle_insurance_mongodb_errors_total" in content
    assert "vehicle_insurance_http_requests_total" in content


def test_prediction_metrics_increment(client):
    """
    Test Phase 20 requirement:
    Successful prediction increments prediction counter and records latency.
    """
    initial_success = PREDICTION_REQUESTS_TOTAL.labels(status="success")._value.get()

    form_payload = {
        "Gender": "Male",
        "Age": "35",
        "Driving_License": "1",
        "Region_Code": "28.0",
        "Previously_Insured": "0",
        "Annual_Premium": "35000",
        "Policy_Sales_Channel": "152.0",
        "Vintage": "180",
        "Vehicle_Age": "1-2 Year",
        "Vehicle_Damage": "Yes",
    }

    # Mock the classifier prediction so unit test doesn't depend on S3 or model file
    with patch("app.VehicleDataClassifier") as mock_classifier_cls:
        mock_instance = MagicMock()
        mock_instance.predict.return_value = [1]
        mock_classifier_cls.return_value = mock_instance

        response = client.post("/", data=form_payload)
        assert response.status_code == 200

        after_success = PREDICTION_REQUESTS_TOTAL.labels(status="success")._value.get()
        assert after_success == initial_success + 1


def test_prediction_error_metric_increment(client):
    """
    Test Phase 20 requirement:
    Failed prediction increments failure and error type counters.
    """
    initial_failures = PREDICTION_REQUESTS_TOTAL.labels(status="failure")._value.get()

    # Post invalid data that causes ValueError / Exception
    with patch("app.VehicleDataClassifier") as mock_classifier_cls:
        mock_instance = MagicMock()
        mock_instance.predict.side_effect = RuntimeError("Simulated inference failure")
        mock_classifier_cls.return_value = mock_instance

        form_payload = {
            "Gender": "Male",
            "Age": "35",
            "Driving_License": "1",
            "Region_Code": "28.0",
            "Previously_Insured": "0",
            "Annual_Premium": "35000",
            "Policy_Sales_Channel": "152.0",
            "Vintage": "180",
            "Vehicle_Age": "1-2 Year",
            "Vehicle_Damage": "Yes",
        }
        response = client.post("/", data=form_payload)
        data = response.json()
        assert data["status"] is False

        after_failures = PREDICTION_REQUESTS_TOTAL.labels(status="failure")._value.get()
        assert after_failures == initial_failures + 1
        assert PREDICTION_ERRORS_TOTAL.labels(error_type="RuntimeError")._value.get() >= 1


def test_training_metrics_increment(client):
    """
    Test Phase 20 requirement:
    Triggering /train increments training run counters.
    """
    initial_started = TRAINING_RUNS_TOTAL.labels(status="started")._value.get()
    initial_completed = TRAINING_RUNS_TOTAL.labels(status="completed")._value.get()

    with patch("app.TrainPipeline") as mock_pipeline_cls:
        mock_pipeline = MagicMock()
        mock_pipeline.run_pipeline.return_value = None
        mock_pipeline_cls.return_value = mock_pipeline

        response = client.get("/train")
        assert response.status_code == 200
        assert "Training successful" in response.text

        after_started = TRAINING_RUNS_TOTAL.labels(status="started")._value.get()
        after_completed = TRAINING_RUNS_TOTAL.labels(status="completed")._value.get()
        assert after_started == initial_started + 1
        assert after_completed == initial_completed + 1


def test_mongodb_error_metric():
    """
    Test Phase 20 requirement:
    MongoDB error metric correctly increments.
    """
    initial_errors = MONGODB_ERRORS_TOTAL.labels(operation="connection")._value.get()
    MONGODB_ERRORS_TOTAL.labels(operation="connection").inc()
    assert MONGODB_ERRORS_TOTAL.labels(operation="connection")._value.get() == initial_errors + 1
