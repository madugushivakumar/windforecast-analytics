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
    pipeline_service.current_window_type = "decision"
    pipeline_service.current_resolution = "hourly"
    pipeline_service.selector.cutoff_hour_utc = 11
    pipeline_service.target_year = 2026
    pipeline_service.target_month = 1
    pipeline_service.df_clean_forecasts = pd.DataFrame([
        {"startTime": t1, "publishTime": datetime(2025, 12, 31, 10, 30, tzinfo=timezone.utc), "forecast_mw": 12500.0},
        {"startTime": t1, "publishTime": datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc), "forecast_mw": 12800.0},
    ])
    pipeline_service.data_source = "MOCK_TEST_FIXTURE"
    yield
    pipeline_service.df_matched = pd.DataFrame()
    pipeline_service.df_clean_forecasts = pd.DataFrame()
    pipeline_service.data_source = "UNINITIALIZED"


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


def test_forecasts_hourly_string_settlement_period_and_cors():
    """Verify that hourly range settlement periods like 'P1-P2' do not crash the endpoint, and CORS headers are returned for origin 3000."""
    t1 = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    pipeline_service.df_matched = pd.DataFrame([
        {
            "startTime": t1,
            "settlementDate": "2026-01-02",
            "settlementPeriod": "P1-P2",
            "decision_date": "2026-01-01",
            "decision_cutoff": datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc),
            "selected_publish_time": datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc),
            "forecast_mw": 18699.0,
            "actual_mw": 15366.5,
            "signed_error_mw": 3332.5,
            "abs_error_mw": 3332.5,
            "squared_error_mw2": 11105556.25,
            "lead_time_hours": 14.5,
            "status": "MATCHED"
        }
    ])
    resp = client.get(
        "/api/forecasts?start_date=2026-01-01&end_date=2026-01-07&cutoff_hour=11",
        headers={"Origin": "http://localhost:3000"}
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
    data = resp.json()
    assert data["count"] == 1
    assert data["data"][0]["settlementPeriod"] == "P1-P2"


def test_forecasts_origin_localhost_3001():
    """Verify that http://localhost:3001 is explicitly allowed by CORS."""
    t1 = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    pipeline_service.df_matched = pd.DataFrame([
        {
            "startTime": t1,
            "settlementDate": "2026-01-02",
            "settlementPeriod": "P1-P2",
            "decision_date": "2026-01-01",
            "decision_cutoff": datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc),
            "selected_publish_time": datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc),
            "forecast_mw": 18699.0,
            "actual_mw": 15366.5,
            "signed_error_mw": 3332.5,
            "abs_error_mw": 3332.5,
            "squared_error_mw2": 11105556.25,
            "lead_time_hours": 14.5,
            "status": "MATCHED"
        }
    ])
    resp = client.get(
        "/api/forecasts?start_date=2026-01-01&end_date=2026-01-07&cutoff_hour=11",
        headers={"Origin": "http://localhost:3001"}
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3001"
    assert resp.headers.get("access-control-allow-credentials") == "true"
    data = resp.json()
    assert data["count"] == 1
    assert data["data"][0]["settlementPeriod"] == "P1-P2"


def test_cors_preflight_options():
    """Verify CORS preflight OPTIONS request returns correct headers for port 3001."""
    resp = client.options(
        "/api/forecasts",
        headers={
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        }
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3001"
    assert "GET" in resp.headers.get("access-control-allow-methods", "")


def test_unapproved_origin_rejected_by_cors():
    """Verify that unapproved origins are not granted Access-Control-Allow-Origin headers."""
    resp = client.get(
        "/api/forecasts?start_date=2026-01-01&end_date=2026-01-07&cutoff_hour=11",
        headers={"Origin": "http://unapproved-origin.com"}
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") is None


def test_settlement_period_handling_numeric_and_range():
    """Verify that both numeric and string ranges (and missing) are handled cleanly without ValueError."""
    t1 = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 2, 1, 0, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 1, 2, 2, 0, 0, tzinfo=timezone.utc)
    pipeline_service.df_matched = pd.DataFrame([
        {
            "startTime": t1,
            "settlementDate": "2026-01-02",
            "settlementPeriod": "P1-P2",
            "decision_date": "2026-01-01",
            "decision_cutoff": datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc),
            "selected_publish_time": datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc),
            "forecast_mw": 18699.0,
            "actual_mw": 15366.5,
            "signed_error_mw": 3332.5,
            "abs_error_mw": 3332.5,
            "status": "MATCHED"
        },
        {
            "startTime": t2,
            "settlementDate": "2026-01-02",
            "settlementPeriod": 3,
            "decision_date": "2026-01-01",
            "decision_cutoff": datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc),
            "selected_publish_time": datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc),
            "forecast_mw": 18000.0,
            "actual_mw": 15000.0,
            "signed_error_mw": 3000.0,
            "abs_error_mw": 3000.0,
            "status": "MATCHED"
        },
        {
            "startTime": t3,
            "settlementDate": "2026-01-02",
            "settlementPeriod": None,
            "decision_date": "2026-01-01",
            "decision_cutoff": datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc),
            "selected_publish_time": None,
            "forecast_mw": None,
            "actual_mw": 14000.0,
            "status": "MISSING_FORECAST"
        }
    ])
    resp = client.get("/api/forecasts?start_date=2026-01-01&end_date=2026-01-07&cutoff_hour=11")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 3
    assert data[0]["settlementPeriod"] == "P1-P2"
    assert data[1]["settlementPeriod"] == 3
    assert data[2]["settlementPeriod"] is None
