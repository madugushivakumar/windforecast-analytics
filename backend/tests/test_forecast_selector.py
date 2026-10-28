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
