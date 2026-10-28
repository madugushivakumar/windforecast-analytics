from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
import pandas as pd

from app.main import app
from app.services.pipeline import pipeline_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_pipeline_data():
    """Populates pipeline_service with deterministic test observations."""
    t1 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
    
    test_df = pd.DataFrame([
        {
            "startTime": t1,
            "settlementDate": "2026-01-01",
            "settlementPeriod": 25,
            "decision_date": "2025-12-31",
            "decision_cutoff": datetime(2025, 12, 31, 11, 0, tzinfo=timezone.utc),
            "selected_publish_time": datetime(2025, 12, 31, 10, 30, tzinfo=timezone.utc),
            "forecast_mw": 12500.0,
            "actual_mw": 11000.0,
            "signed_error_mw": 1500.0,
            "abs_error_mw": 1500.0,
            "squared_error_mw2": 2250000.0,
            "lead_time_hours": 25.5,
            "status": "MATCHED"
        },
        {
            "startTime": t2,
            "settlementDate": "2026-01-01",
            "settlementPeriod": 26,
            "decision_date": "2025-12-31",
            "decision_cutoff": datetime(2025, 12, 31, 11, 0, tzinfo=timezone.utc),
            "selected_publish_time": datetime(2025, 12, 31, 10, 30, tzinfo=timezone.utc),
            "forecast_mw": 13000.0,
            "actual_mw": 13500.0,
            "signed_error_mw": -500.0,
            "abs_error_mw": 500.0,
            "squared_error_mw2": 250000.0,
            "lead_time_hours": 26.0,
            "status": "MATCHED"
        }
    ])
    pipeline_service.df_matched = test_df
    pipeline_service.df_clean_forecasts = pd.DataFrame([
        {"startTime": t1, "publishTime": datetime(2025, 12, 31, 10, 30, tzinfo=timezone.utc), "forecast_mw": 12500.0},
        {"startTime": t1, "publishTime": datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc), "forecast_mw": 12800.0},
    ])
    pipeline_service.data_source = "MOCK_TEST_FIXTURE"
    yield


def test_root_endpoint():
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"
    assert "WindForecast" in data["service"]


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"
    assert "upstream_elexon_api" in data
    assert "pipeline" in data


def test_overview_endpoint():
    resp = client.get("/api/overview?cutoff_hour=11")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "WindForecast Analytics"
    assert "metrics" in data
    metrics = data["metrics"]
    assert metrics["sample_size"] == 2
    # MAE = (1500 + 500) / 2 = 1000.0
    assert metrics["mae_mw"] == 1000.0
    # Mean signed error = (1500 - 500) / 2 = 500.0
    assert metrics["mean_signed_error_mw"] == 500.0


def test_forecasts_endpoint():
    resp = client.get("/api/forecasts?cutoff_hour=11")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert len(data["data"]) == 2
    assert data["data"][0]["status"] == "MATCHED"


def test_accuracy_endpoint():
    resp = client.get("/api/accuracy?cutoff_hour=11")
    assert resp.status_code == 200
    data = resp.json()
    assert "metrics" in data
    assert "error_distribution" in data
    assert "largest_error_periods" in data
    assert len(data["largest_error_periods"]) == 2
    assert data["largest_error_periods"][0]["abs_error_mw"] == 1500.0


def test_forecast_history_endpoint():
    resp = client.get("/api/forecast-history?start_time=2026-01-01T12:00:00Z")
    assert resp.status_code == 200
    data = resp.json()
    assert data["vintages_count"] == 2
    assert len(data["vintages"]) == 2


def test_data_quality_endpoint():
    resp = client.get("/api/data-quality")
    assert resp.status_code == 200
    data = resp.json()
    assert "actual_records_fetched" in data
    assert "data_coverage_percentage" in data


def test_observations_pagination_and_csv():
    # Test JSON pagination
    resp_json = client.get("/api/observations?page=1&page_size=10")
    assert resp_json.status_code == 200
    data = resp_json.json()
    assert data["total_records"] == 2
    assert len(data["records"]) == 2

    # Test CSV export
    resp_csv = client.get("/api/observations/export/csv?cutoff_hour=11")
    assert resp_csv.status_code == 200
    assert resp_csv.headers["content-type"].startswith("text/csv")
    csv_text = resp_csv.text
    assert "Delivery_Start_Time_UTC" in csv_text
    assert "12500.0" in csv_text
    assert "11000.0" in csv_text
