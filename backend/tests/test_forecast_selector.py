import pytest
from datetime import datetime, timezone
import pandas as pd
from app.services.forecast_selector import (
    ForecastSelector,
    compute_day_ahead_cutoff,
    is_decision_in_window,
    get_market_cutoff_info
)


def test_compute_day_ahead_cutoff():
    # Delivery on 2026-01-02 14:00:00Z
    delivery_dt = datetime(2026, 1, 2, 14, 0, 0, tzinfo=timezone.utc)
    cutoff_dt, dec_date, _ = compute_day_ahead_cutoff(delivery_dt, cutoff_hour_utc=11, cutoff_minute_utc=0)

    # Cutoff must be 2026-01-01 at 11:00:00Z
    assert cutoff_dt == datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
    assert dec_date == "2026-01-01"


def test_compute_day_ahead_cutoff_with_minutes():
    # EPEX SPOT GB 60min auction: 09:20 UTC
    delivery_dt = datetime(2026, 1, 10, 8, 0, 0, tzinfo=timezone.utc)
    cutoff_dt, dec_date, _ = compute_day_ahead_cutoff(delivery_dt, cutoff_hour_utc=9, cutoff_minute_utc=20)

    assert cutoff_dt == datetime(2026, 1, 9, 9, 20, 0, tzinfo=timezone.utc)
    assert dec_date == "2026-01-09"


def test_compute_day_ahead_cutoff_invalid_configuration():
    delivery_dt = datetime(2026, 1, 2, 14, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="cutoff_hour_utc must be between 0 and 23"):
        compute_day_ahead_cutoff(delivery_dt, cutoff_hour_utc=24)
    with pytest.raises(ValueError, match="cutoff_minute_utc must be between 0 and 59"):
        compute_day_ahead_cutoff(delivery_dt, cutoff_hour_utc=11, cutoff_minute_utc=60)


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
    selector = ForecastSelector(cutoff_hour_utc=11, cutoff_minute_utc=0)
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


def test_timezone_naive_and_aware_normalization():
    """
    Ensures that timezone-naive datetimes are normalized to UTC safely without crashing
    or misaligning timestamps.
    """
    selector = ForecastSelector(cutoff_hour_utc=11)
    naive_delivery = datetime(2026, 1, 5, 10, 0, 0)  # Naive
    naive_publish = datetime(2026, 1, 4, 10, 30, 0)   # Naive

    df_for = pd.DataFrame([
        {"startTime": naive_delivery, "publishTime": naive_publish, "forecast_mw": 4500.0}
    ])
    df_sel = selector.select_day_ahead_forecasts(df_for)

    assert len(df_sel) == 1
    assert df_sel.iloc[0]["startTime"].tzinfo == timezone.utc
    assert df_sel.iloc[0]["selected_publish_time"].tzinfo == timezone.utc
    assert df_sel.iloc[0]["decision_cutoff"].tzinfo == timezone.utc


def test_cutoff_override_epex_spot_0920():
    """
    Tests dynamic cutoff override to 09:20 UTC (EPEX SPOT GB 60min auction).
    At 09:20, a forecast published at 08:30 is eligible, while one at 09:21 or 10:30 is excluded.
    """
    selector = ForecastSelector(cutoff_hour_utc=11, cutoff_minute_utc=0)
    deliv_time = datetime(2026, 1, 10, 15, 0, 0, tzinfo=timezone.utc)

    # Vintages on D-1 (2026-01-09):
    # 1. 08:30:00Z (Eligible before 09:20) -> 6000 MW
    # 2. 09:20:00Z (Eligible exactly at 09:20) -> 6200 MW
    # 3. 09:20:01Z (Ineligible post-cutoff) -> 9999 MW
    # 4. 10:30:00Z (Ineligible post-cutoff) -> 8888 MW
    df_for = pd.DataFrame([
        {"startTime": deliv_time, "publishTime": datetime(2026, 1, 9, 8, 30, 0, tzinfo=timezone.utc), "forecast_mw": 6000.0},
        {"startTime": deliv_time, "publishTime": datetime(2026, 1, 9, 9, 20, 0, tzinfo=timezone.utc), "forecast_mw": 6200.0},
        {"startTime": deliv_time, "publishTime": datetime(2026, 1, 9, 9, 20, 1, tzinfo=timezone.utc), "forecast_mw": 9999.0},
        {"startTime": deliv_time, "publishTime": datetime(2026, 1, 9, 10, 30, 0, tzinfo=timezone.utc), "forecast_mw": 8888.0},
    ])

    # Override selector to 09:20 UTC
    df_sel = selector.select_day_ahead_forecasts(df_for, cutoff_hour_utc=9, cutoff_minute_utc=20)
    assert len(df_sel) == 1
    assert df_sel.iloc[0]["forecast_mw"] == 6200.0
    assert df_sel.iloc[0]["selected_publish_time"] == datetime(2026, 1, 9, 9, 20, 0, tzinfo=timezone.utc)


def test_market_cutoff_info_metadata():
    """
    Verifies that get_market_cutoff_info returns truthful, authoritative metadata
    distinguishing official exchange closures from operational assumptions.
    """
    info_epex_60 = get_market_cutoff_info(9, 20)
    assert info_epex_60["is_official_exchange_closure"] is True
    assert "EPEX SPOT" in info_epex_60["market_name"]
    assert info_epex_60["type"] == "official_exchange_auction"

    info_nordpool = get_market_cutoff_info(9, 50)
    assert info_nordpool["is_official_exchange_closure"] is True
    assert "Nord Pool" in info_nordpool["market_name"]

    info_1100 = get_market_cutoff_info(11, 0)
    assert info_1100["is_official_exchange_closure"] is False
    assert info_1100["type"] == "operational_modelling_assumption"
    assert "operational modelling assumption" in info_1100["rule_description"]
