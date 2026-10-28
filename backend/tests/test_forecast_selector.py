import pytest
from datetime import datetime, timezone
import pandas as pd
from app.services.forecast_selector import ForecastSelector, compute_day_ahead_cutoff


def test_compute_day_ahead_cutoff():
    # Delivery on 2026-01-02 14:00:00Z
    delivery_dt = datetime(2026, 1, 2, 14, 0, 0, tzinfo=timezone.utc)
    cutoff_dt, dec_date, _ = compute_day_ahead_cutoff(delivery_dt, cutoff_hour_utc=11)

    # Cutoff must be 2026-01-01 at 11:00:00Z
    assert cutoff_dt == datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
    assert dec_date == "2026-01-01"


def test_forecast_selector_excludes_post_cutoff_forecasts():
    selector = ForecastSelector(cutoff_hour_utc=11)
    
    # Delivery target: 2026-01-02 12:00:00Z -> Cutoff is 2026-01-01 11:00:00Z
    delivery_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

    # Three vintages:
    # 1. 2025-12-31 22:00:00Z (Eligible, older)
    # 2. 2026-01-01 10:30:00Z (Eligible, latest pre-cutoff)
    # 3. 2026-01-01 14:00:00Z (Post-cutoff! INELIGIBLE)
    data = [
        {"startTime": delivery_time, "publishTime": datetime(2025, 12, 31, 22, 0, 0, tzinfo=timezone.utc), "forecast_mw": 8000.0},
        {"startTime": delivery_time, "publishTime": datetime(2026, 1, 1, 10, 30, 0, tzinfo=timezone.utc), "forecast_mw": 8500.0},
        {"startTime": delivery_time, "publishTime": datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc), "forecast_mw": 9999.0},
    ]
    df_for = pd.DataFrame(data)

    df_selected = selector.select_day_ahead_forecasts(df_for)

    assert len(df_selected) == 1
    selected_row = df_selected.iloc[0]
    # Selected must be vintage 2 (8500 MW), NOT the post-cutoff vintage 3 (9999 MW)
    assert selected_row["forecast_mw"] == 8500.0
    assert selected_row["selected_publish_time"] == datetime(2026, 1, 1, 10, 30, 0, tzinfo=timezone.utc)


def test_forecast_selector_empty_when_no_eligible_forecast():
    selector = ForecastSelector(cutoff_hour_utc=11)
    delivery_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

    # Only post-cutoff forecasts available
    data = [
        {"startTime": delivery_time, "publishTime": datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc), "forecast_mw": 9000.0},
    ]
    df_for = pd.DataFrame(data)
    df_selected = selector.select_day_ahead_forecasts(df_for)

    assert df_selected.empty


def test_forecast_history_vintages_auditing():
    selector = ForecastSelector(cutoff_hour_utc=11)
    delivery_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

    data = [
        {"startTime": delivery_time, "publishTime": datetime(2025, 12, 31, 22, 0, 0, tzinfo=timezone.utc), "forecast_mw": 8000.0},
        {"startTime": delivery_time, "publishTime": datetime(2026, 1, 1, 10, 30, 0, tzinfo=timezone.utc), "forecast_mw": 8500.0},
        {"startTime": delivery_time, "publishTime": datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc), "forecast_mw": 9999.0},
    ]
    df_for = pd.DataFrame(data)

    vintages = selector.get_forecast_history_for_period(df_for, delivery_time)
    assert len(vintages) == 3
    # First two eligible, third not eligible
    assert vintages[0]["is_eligible"] is True
    assert vintages[1]["is_eligible"] is True
    assert vintages[2]["is_eligible"] is False


def test_january_decision_window_boundaries():
    """
    Validates the January 2026 decision window boundaries:
    - Decision window: 2026-01-01 00:00:00Z to 2026-02-01 00:00:00Z (exclusive)
    - Delivery on 2026-01-01 -> decided 2025-12-31 (EXCLUDED from Jan decision analysis)
    - Delivery on 2026-01-02 -> decided 2026-01-01 (INCLUDED)
    - Delivery on 2026-02-01 -> decided 2026-01-31 (INCLUDED)
    - Delivery on 2026-02-02 -> decided 2026-02-01 (EXCLUDED from Jan decision analysis)
    """
    from app.services.forecast_selector import is_decision_in_window
    
    win_start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    win_end = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)

    # 1. Delivery on 2026-01-01 (decided 2025-12-31 11:00 UTC) -> False
    deliv_jan1 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert is_decision_in_window(deliv_jan1, win_start, win_end) is False

    # 2. Delivery on 2026-01-02 (decided 2026-01-01 11:00 UTC) -> True
    deliv_jan2 = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    assert is_decision_in_window(deliv_jan2, win_start, win_end) is True

    # 3. Delivery on 2026-02-01 (decided 2026-01-31 11:00 UTC) -> True
    deliv_feb1 = datetime(2026, 2, 1, 23, 30, 0, tzinfo=timezone.utc)
    assert is_decision_in_window(deliv_feb1, win_start, win_end) is True

    # 4. Delivery on 2026-02-02 (decided 2026-02-01 11:00 UTC) -> False
    deliv_feb2 = datetime(2026, 2, 2, 0, 0, 0, tzinfo=timezone.utc)
    assert is_decision_in_window(deliv_feb2, win_start, win_end) is False


def test_gate_closure_second_level_precision_and_lookahead_bias():
    """
    Ensures forecasts published strictly at or before cutoff (11:00:00) are eligible,
    and any forecast published at 11:00:01 or later is excluded.
    """
    selector = ForecastSelector(cutoff_hour_utc=11)
    deliv_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Cutoff is 2026-01-14 11:00:00Z
    data = [
        {"startTime": deliv_time, "publishTime": datetime(2026, 1, 14, 10, 59, 59, tzinfo=timezone.utc), "forecast_mw": 5000.0},
        {"startTime": deliv_time, "publishTime": datetime(2026, 1, 14, 11, 0, 0, tzinfo=timezone.utc), "forecast_mw": 5100.0},
        {"startTime": deliv_time, "publishTime": datetime(2026, 1, 14, 11, 0, 1, tzinfo=timezone.utc), "forecast_mw": 9999.0},
    ]
    df_for = pd.DataFrame(data)
    df_sel = selector.select_day_ahead_forecasts(df_for)

    assert len(df_sel) == 1
    # Latest eligible must be 11:00:00 (5100 MW), rejecting 11:00:01 (9999 MW)
    assert df_sel.iloc[0]["forecast_mw"] == 5100.0
    assert df_sel.iloc[0]["selected_publish_time"] == datetime(2026, 1, 14, 11, 0, 0, tzinfo=timezone.utc)
