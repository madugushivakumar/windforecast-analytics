import pytest
from datetime import datetime, timezone
import pandas as pd
from app.services.matcher import Matcher


def test_matcher_exact_join_and_errors():
    matcher = Matcher()
    t1 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 1, 1, 13, 0, 0, tzinfo=timezone.utc)

    # Forecasts for t1 and t2
    df_f = pd.DataFrame([
        {"startTime": t1, "forecast_mw": 12000.0, "decision_date": "2025-12-31", "decision_cutoff": datetime(2025, 12, 31, 11, 0, tzinfo=timezone.utc), "selected_publish_time": datetime(2025, 12, 31, 10, 0, tzinfo=timezone.utc), "lead_time_hours": 26.0},
        {"startTime": t2, "forecast_mw": 14000.0, "decision_date": "2025-12-31", "decision_cutoff": datetime(2025, 12, 31, 11, 0, tzinfo=timezone.utc), "selected_publish_time": datetime(2025, 12, 31, 10, 0, tzinfo=timezone.utc), "lead_time_hours": 26.5},
    ])

    # Actuals for t1 and t3 (t2 has missing actual, t3 has missing forecast)
    df_a = pd.DataFrame([
        {"startTime": t1, "actual_mw": 10000.0, "settlementDate": "2026-01-01", "settlementPeriod": 25},
        {"startTime": t3, "actual_mw": 11500.0, "settlementDate": "2026-01-01", "settlementPeriod": 27},
    ])

    df_matched, counts = matcher.match(df_f, df_a, resolution="half-hourly")

    assert counts["actual_periods"] == 2
    assert counts["forecast_periods"] == 2
    assert counts["matched_periods"] == 1
    assert counts["missing_actual"] == 1  # t2 has forecast but no actual
    assert counts["missing_forecast"] == 1  # t3 has actual but no forecast

    # Verify t1 is matched
    row_t1 = df_matched[df_matched["startTime"] == t1].iloc[0]
    assert row_t1["status"] == "MATCHED"
    assert row_t1["signed_error_mw"] == 2000.0  # 12000 - 10000
    assert row_t1["abs_error_mw"] == 2000.0
    assert row_t1["squared_error_mw2"] == 4000000.0


def test_matcher_hourly_aggregation():
    """
    Validates hourly aggregation:
    Two half-hourly actuals (10,000 MW and 12,000 MW) in the same hour
    must aggregate to arithmetic mean 11,000 MW.
    Forecast of 11,500 MW should yield signed_error = +500 MW.
    """
    matcher = Matcher()
    h_start = datetime(2026, 1, 5, 14, 0, 0, tzinfo=timezone.utc)
    hh_1 = datetime(2026, 1, 5, 14, 0, 0, tzinfo=timezone.utc)
    hh_2 = datetime(2026, 1, 5, 14, 30, 0, tzinfo=timezone.utc)

    df_f = pd.DataFrame([
        {
            "startTime": h_start,
            "forecast_mw": 11500.0,
            "decision_date": "2026-01-04",
            "decision_cutoff": datetime(2026, 1, 4, 11, 0, tzinfo=timezone.utc),
            "selected_publish_time": datetime(2026, 1, 4, 10, 30, tzinfo=timezone.utc),
            "lead_time_hours": 27.5
        }
    ])

    df_a = pd.DataFrame([
        {"startTime": hh_1, "actual_mw": 10000.0, "settlementDate": "2026-01-05", "settlementPeriod": 29},
        {"startTime": hh_2, "actual_mw": 12000.0, "settlementDate": "2026-01-05", "settlementPeriod": 30},
    ])

    df_matched, counts = matcher.match(df_f, df_a, resolution="hourly")

    assert counts["actual_periods"] == 1
    assert counts["forecast_periods"] == 1
    assert counts["matched_periods"] == 1

    row = df_matched.iloc[0]
    assert row["status"] == "MATCHED"
    assert row["actual_mw"] == 11000.0
    assert row["forecast_mw"] == 11500.0
    assert row["signed_error_mw"] == 500.0
    assert row["abs_error_mw"] == 500.0
    # Audit traceability fields
    assert row["actual_hh0_mw"] == 10000.0
    assert row["actual_hh1_mw"] == 12000.0
    assert row["hh_count"] == 2


def test_matcher_first_interval_missing_becomes_missing_actual():
    """Verify that if the first half-hour (:00) is missing, the hour becomes MISSING_ACTUAL."""
    matcher = Matcher()
    h_start = datetime(2026, 1, 5, 14, 0, 0, tzinfo=timezone.utc)
    hh_2 = datetime(2026, 1, 5, 14, 30, 0, tzinfo=timezone.utc)

    df_f = pd.DataFrame([{"startTime": h_start, "forecast_mw": 11500.0}])
    # Only :30 exists
    df_a = pd.DataFrame([{"startTime": hh_2, "actual_mw": 12000.0, "settlementDate": "2026-01-05", "settlementPeriod": 30}])

    df_matched, counts = matcher.match(df_f, df_a, resolution="hourly")
    row = df_matched.iloc[0]
    assert row["status"] == "MISSING_ACTUAL"
    assert pd.isna(row["actual_mw"])
    assert counts["matched_periods"] == 0
    assert counts["missing_actual"] == 1


def test_matcher_second_interval_missing_becomes_missing_actual():
    """Verify that if the second half-hour (:30) is missing, the hour becomes MISSING_ACTUAL."""
    matcher = Matcher()
    h_start = datetime(2026, 1, 5, 14, 0, 0, tzinfo=timezone.utc)
    hh_1 = datetime(2026, 1, 5, 14, 0, 0, tzinfo=timezone.utc)

    df_f = pd.DataFrame([{"startTime": h_start, "forecast_mw": 11500.0}])
    # Only :00 exists
    df_a = pd.DataFrame([{"startTime": hh_1, "actual_mw": 10000.0, "settlementDate": "2026-01-05", "settlementPeriod": 29}])

    df_matched, counts = matcher.match(df_f, df_a, resolution="hourly")
    row = df_matched.iloc[0]
    assert row["status"] == "MISSING_ACTUAL"
    assert pd.isna(row["actual_mw"])
    assert counts["matched_periods"] == 0
    assert counts["missing_actual"] == 1


def test_matcher_duplicate_intervals_handled_strictly():
    """Verify that duplicate intervals on the same startTime are deduplicated and don't count as two periods."""
    matcher = Matcher()
    h_start = datetime(2026, 1, 5, 14, 0, 0, tzinfo=timezone.utc)
    hh_1 = datetime(2026, 1, 5, 14, 0, 0, tzinfo=timezone.utc)

    df_f = pd.DataFrame([{"startTime": h_start, "forecast_mw": 11500.0}])
    # Two records but both for :00 (duplicate timestamp)
    df_a = pd.DataFrame([
        {"startTime": hh_1, "actual_mw": 10000.0, "settlementDate": "2026-01-05", "settlementPeriod": 29},
        {"startTime": hh_1, "actual_mw": 10500.0, "settlementDate": "2026-01-05", "settlementPeriod": 29},
    ])

    df_matched, counts = matcher.match(df_f, df_a, resolution="hourly")
    row = df_matched.iloc[0]
    # After deduplication, only 1 interval exists (:00), so the hour is incomplete
    assert row["status"] == "MISSING_ACTUAL"
    assert pd.isna(row["actual_mw"])
    assert counts["matched_periods"] == 0


def test_matcher_non_finite_interval_value_becomes_missing_actual():
    """Verify that if an interval has NaN or infinite generation, the hour is not aggregated."""
    import numpy as np
    matcher = Matcher()
    h_start = datetime(2026, 1, 5, 14, 0, 0, tzinfo=timezone.utc)
    hh_1 = datetime(2026, 1, 5, 14, 0, 0, tzinfo=timezone.utc)
    hh_2 = datetime(2026, 1, 5, 14, 30, 0, tzinfo=timezone.utc)

    df_f = pd.DataFrame([{"startTime": h_start, "forecast_mw": 11500.0}])
    df_a = pd.DataFrame([
        {"startTime": hh_1, "actual_mw": np.nan, "settlementDate": "2026-01-05", "settlementPeriod": 29},
        {"startTime": hh_2, "actual_mw": 12000.0, "settlementDate": "2026-01-05", "settlementPeriod": 30},
    ])

    df_matched, counts = matcher.match(df_f, df_a, resolution="hourly")
    row = df_matched.iloc[0]
    assert row["status"] == "MISSING_ACTUAL"
    assert pd.isna(row["actual_mw"])
    assert counts["matched_periods"] == 0


def test_matcher_misaligned_timestamp_becomes_missing_actual():
    """Verify that if an interval has a misaligned timestamp (e.g. :15 instead of :30), it is rejected."""
    matcher = Matcher()
    h_start = datetime(2026, 1, 5, 14, 0, 0, tzinfo=timezone.utc)
    hh_1 = datetime(2026, 1, 5, 14, 0, 0, tzinfo=timezone.utc)
    hh_misaligned = datetime(2026, 1, 5, 14, 15, 0, tzinfo=timezone.utc)

    df_f = pd.DataFrame([{"startTime": h_start, "forecast_mw": 11500.0}])
    df_a = pd.DataFrame([
        {"startTime": hh_1, "actual_mw": 10000.0, "settlementDate": "2026-01-05", "settlementPeriod": 29},
        {"startTime": hh_misaligned, "actual_mw": 12000.0, "settlementDate": "2026-01-05", "settlementPeriod": 29},
    ])

    df_matched, counts = matcher.match(df_f, df_a, resolution="hourly")
    row = df_matched.iloc[0]
    assert row["status"] == "MISSING_ACTUAL"
    assert pd.isna(row["actual_mw"])
    assert counts["matched_periods"] == 0

