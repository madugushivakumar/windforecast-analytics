import sys
import json
from pathlib import Path
import pytest
import pandas as pd
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app
from app.services.pipeline import pipeline_service
from app.services.matcher import Matcher
from app.analytics.metrics import (
    calculate_mae,
    calculate_rmse,
    calculate_mean_signed_error,
    calculate_max_absolute_error,
    calculate_wape,
    calculate_conditional_mape,
)
from reproduce_analysis import run_independent_validation

client = TestClient(app)

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent.parent / "artifacts" / "january_2026"


def test_artifacts_exist_and_are_valid():
    """Verify that all required artifacts were generated and have valid formats."""
    summary_path = ARTIFACTS_DIR / "analysis_summary.json"
    csv_path = ARTIFACTS_DIR / "observations_analysis.csv"
    dq_path = ARTIFACTS_DIR / "data_quality_report.json"
    manifest_path = ARTIFACTS_DIR / "run_manifest.json"
    log_path = ARTIFACTS_DIR / "validation_log.md"

    assert summary_path.exists(), "analysis_summary.json missing"
    assert csv_path.exists(), "observations_analysis.csv missing"
    assert dq_path.exists(), "data_quality_report.json missing"
    assert manifest_path.exists(), "run_manifest.json missing"
    assert log_path.exists(), "validation_log.md missing"

    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)
    assert summary["project"] == "WindForecast Analytics"
    assert summary["target_period"] == "January 2026"
    assert summary["effective_cutoff"]["hour_utc"] == 11
    assert summary["effective_cutoff"]["minute_utc"] == 0
    assert summary["validation_status"] == "PASSED"
    assert summary["coverage"]["expected_periods"] == 744
    assert summary["coverage"]["matched_periods"] == 744


def test_independent_validation_passes():
    """Verify that independent validation of the saved observations CSV passes completely."""
    summary_path = ARTIFACTS_DIR / "analysis_summary.json"
    csv_path = ARTIFACTS_DIR / "observations_analysis.csv"

    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    val_res = run_independent_validation(csv_path, summary)
    assert val_res["all_checks_passed"] is True, f"Independent checks failed: {val_res}"
    for check in val_res["checks"]:
        assert check["status"] == "PASS", f"Check {check['description']} failed"
    for m in val_res["metrics_comparison"]:
        assert m["status"] == "PASS", f"Metric {m['metric']} mismatch: diff {m['diff']}"


def test_zero_lookahead_bias_in_saved_csv():
    """Ensure that every single selected forecast was published at or before the decision cutoff."""
    csv_path = ARTIFACTS_DIR / "observations_analysis.csv"
    df = pd.read_csv(csv_path)

    assert len(df) == 744
    df["cutoff_dt"] = pd.to_datetime(df["decision_cutoff_utc"], utc=True)
    df["pub_dt"] = pd.to_datetime(df["selected_publish_time_utc"], utc=True)

    violations = df[df["pub_dt"] > df["cutoff_dt"]]
    assert len(violations) == 0, f"Found {len(violations)} lookahead violations"


def test_february_1_deliveries_included_for_january_decisions():
    """Verify that delivery periods on 2026-02-01 resulting from 2026-01-31 decisions are included."""
    csv_path = ARTIFACTS_DIR / "observations_analysis.csv"
    df = pd.read_csv(csv_path)

    feb1_records = df[df["settlement_date"] == "2026-02-01"]
    assert len(feb1_records) == 24, "Expected 24 hourly periods on 2026-02-01"
    assert all(feb1_records["decision_date"] == "2026-01-31"), "Feb 1 deliveries must map to Jan 31 decision"


def test_api_metrics_match_saved_artifacts():
    """Verify that backend API endpoints return the exact same metrics as the saved analysis summary."""
    summary_path = ARTIFACTS_DIR / "analysis_summary.json"
    with open(summary_path, "r", encoding="utf-8") as f:
        saved_summary = json.load(f)
    saved_m = saved_summary["metrics"]

    # 1. Check /api/accuracy endpoint
    pipeline_service.run_pipeline(cutoff_hour_utc=11, cutoff_minute_utc=0, window_type="decision", resolution="hourly", force_refresh=True)
    resp = client.get("/api/accuracy?cutoff_hour=11&cutoff_minute=0&window=decision&resolution=hourly")
    assert resp.status_code == 200
    api_acc = resp.json()["metrics"]

    assert api_acc["sample_size"] == saved_m["sample_size"]
    assert pytest.approx(api_acc["mae_mw"], 0.01) == saved_m["mae_mw"]
    assert pytest.approx(api_acc["rmse_mw"], 0.01) == saved_m["rmse_mw"]
    assert pytest.approx(api_acc["mean_signed_error_mw"], 0.01) == saved_m["mean_signed_error_bias_mw"]
    assert pytest.approx(api_acc["wape_percentage"], 0.01) == saved_m["wape_percentage"]
    assert pytest.approx(api_acc["mape_percentage"], 0.01) == saved_m["conditional_mape_percentage"]

    # 2. Check /api/overview endpoint
    resp_ov = client.get("/api/overview?cutoff_hour=11&cutoff_minute=0&window=decision&resolution=hourly")
    assert resp_ov.status_code == 200
    api_ov = resp_ov.json()
    assert pytest.approx(api_ov["metrics"]["mae_mw"], 0.01) == saved_m["mae_mw"]
    assert pytest.approx(api_ov["metrics"]["rmse_mw"], 0.01) == saved_m["rmse_mw"]
    assert pytest.approx(api_ov["metrics"]["wape_percentage"], 0.01) == saved_m["wape_percentage"]
    assert api_ov["coverage_percentage"] == 100.0


def test_hand_calculated_metric_fixtures():
    """Verify accuracy metrics on deterministic, hand-calculated values."""
    # Fixture with known values:
    # Forecasts: [1000, 2000, 3000, 4000]
    # Actuals:   [1200, 1800, 3100, 3500]
    # Errors (Forecast - Actual):
    #   1000 - 1200 = -200
    #   2000 - 1800 = +200
    #   3000 - 3100 = -100
    #   4000 - 3500 = +500
    # Abs Errors: [200, 200, 100, 500] -> sum = 1000, mean (MAE) = 250.0
    # Squared Errors: [40000, 40000, 10000, 250000] -> sum = 340000, mean = 85000 -> RMSE = sqrt(85000) = 291.5476
    # Bias: (-200 + 200 - 100 + 500) / 4 = 400 / 4 = +100.0
    # Max abs: 500.0, Min signed: -200.0, Max signed: 500.0
    # Sum Actuals: 1200 + 1800 + 3100 + 3500 = 9600
    # WAPE: (1000 / 9600) * 100 = 10.416667% -> 10.42%
    # MAPE: (|e|/actual): [200/1200, 200/1800, 100/3100, 500/3500]
    #   = [0.16667, 0.11111, 0.03226, 0.14286] -> mean = 0.11322 -> 11.32%

    df_fixture = pd.DataFrame({
        "forecast_mw": [1000.0, 2000.0, 3000.0, 4000.0],
        "actual_mw": [1200.0, 1800.0, 3100.0, 3500.0],
        "signed_error_mw": [-200.0, 200.0, -100.0, 500.0],
        "abs_error_mw": [200.0, 200.0, 100.0, 500.0],
        "squared_error_mw2": [40000.0, 40000.0, 10000.0, 250000.0],
        "status": ["MATCHED", "MATCHED", "MATCHED", "MATCHED"]
    })

    metrics = pipeline_service.compute_accuracy_metrics(df_fixture)
    assert metrics.sample_size == 4
    assert pytest.approx(metrics.mae_mw, 0.01) == 250.0
    assert pytest.approx(metrics.rmse_mw, 0.01) == 291.55
    assert pytest.approx(metrics.mean_signed_error_mw, 0.01) == 100.0
    assert pytest.approx(metrics.max_abs_error_mw, 0.01) == 500.0
    assert pytest.approx(metrics.min_signed_error_mw, 0.01) == -200.0
    assert pytest.approx(metrics.max_signed_error_mw, 0.01) == 500.0
    assert pytest.approx(metrics.wape_percentage, 0.01) == 10.42
    assert pytest.approx(metrics.mape_percentage, 0.01) == 11.32


def test_partial_hour_actual_aggregation():
    """Verify that hourly actual aggregation preserves both half-hour readings."""
    matcher = Matcher()
    t1 = pd.Timestamp("2026-01-01T00:00:00Z")
    df_f = pd.DataFrame([
        {
            "startTime": t1,
            "forecast_mw": 1500.0,
            "decision_date": "2025-12-31",
            "decision_cutoff": pd.Timestamp("2025-12-31T11:00:00Z"),
            "selected_publish_time": pd.Timestamp("2025-12-31T10:00:00Z"),
            "lead_time_hours": 14.0
        }
    ])
    df_a = pd.DataFrame([
        {"startTime": pd.Timestamp("2026-01-01T00:00:00Z"), "actual_mw": 1000.0, "settlementDate": "2026-01-01", "settlementPeriod": 1},
        {"startTime": pd.Timestamp("2026-01-01T00:30:00Z"), "actual_mw": 2000.0, "settlementDate": "2026-01-01", "settlementPeriod": 2},
    ])
    df_matched, counts = matcher.match(df_f, df_a, resolution="hourly")
    assert len(df_matched) == 1
    row = df_matched.iloc[0]
    assert row["actual_mw"] == 1500.0  # mean of 1000 and 2000
    assert row["actual_hh0_mw"] == 1000.0
    assert row["actual_hh1_mw"] == 2000.0
    assert row["signed_error_mw"] == 0.0  # 1500 - 1500


def test_partial_hour_missing_half_hour_is_incomplete():
    """Verify that if one half-hour actual is missing, the hour is flagged as MISSING_ACTUAL."""
    matcher = Matcher()
    t1 = pd.Timestamp("2026-01-01T00:00:00Z")
    df_f = pd.DataFrame([
        {
            "startTime": t1,
            "forecast_mw": 1500.0,
            "decision_date": "2025-12-31",
            "decision_cutoff": pd.Timestamp("2025-12-31T11:00:00Z"),
            "selected_publish_time": pd.Timestamp("2025-12-31T10:00:00Z"),
            "lead_time_hours": 14.0
        }
    ])
    # Only period 1 exists, period 2 (:30) is missing
    df_a = pd.DataFrame([
        {"startTime": pd.Timestamp("2026-01-01T00:00:00Z"), "actual_mw": 1000.0, "settlementDate": "2026-01-01", "settlementPeriod": 1},
    ])
    df_matched, counts = matcher.match(df_f, df_a, resolution="hourly")
    assert len(df_matched) == 1
    row = df_matched.iloc[0]
    assert row["status"] == "MISSING_ACTUAL"
    assert pd.isna(row["actual_mw"])
    assert counts["matched_periods"] == 0
    assert counts["missing_actual"] == 1
