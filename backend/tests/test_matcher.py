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

    df_matched, counts = matcher.match(df_f, df_a)

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
