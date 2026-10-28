import pytest
from datetime import datetime, timezone
from app.services.data_cleaner import DataCleaner, parse_utc_timestamp


def test_parse_utc_timestamp():
    dt1 = parse_utc_timestamp("2026-01-01T12:00:00Z")
    assert dt1 == datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    dt2 = parse_utc_timestamp("2026-01-01T12:00:00+00:00")
    assert dt2 == datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    dt3 = parse_utc_timestamp("invalid-date")
    assert dt3 is None


def test_clean_fuelhh_actuals_filters_to_wind():
    cleaner = DataCleaner()
    raw = [
        {"dataset": "FUELHH", "fuelType": "BIOMASS", "generation": 1200, "startTime": "2026-01-01T00:00:00Z", "publishTime": "2026-01-01T00:30:00Z"},
        {"dataset": "FUELHH", "fuelType": "NUCLEAR", "generation": 5000, "startTime": "2026-01-01T00:00:00Z", "publishTime": "2026-01-01T00:30:00Z"},
        {"dataset": "FUELHH", "fuelType": "WIND", "generation": 14500.5, "startTime": "2026-01-01T00:00:00Z", "publishTime": "2026-01-01T00:30:00Z"},
        {"dataset": "FUELHH", "fuelType": "CCGT", "generation": 11000, "startTime": "2026-01-01T00:00:00Z", "publishTime": "2026-01-01T00:30:00Z"},
    ]

    df, stats = cleaner.clean_fuelhh_actuals(raw)
    assert len(df) == 1
    assert stats["fetched"] == 4
    assert stats["retained"] == 1
    assert df.iloc[0]["actual_mw"] == 14500.5


def test_clean_fuelhh_actuals_discards_negative_and_invalid():
    cleaner = DataCleaner()
    raw = [
        {"dataset": "FUELHH", "fuelType": "WIND", "generation": -10.0, "startTime": "2026-01-01T00:00:00Z", "publishTime": "2026-01-01T00:30:00Z"},
        {"dataset": "FUELHH", "fuelType": "WIND", "generation": "not-a-number", "startTime": "2026-01-01T00:30:00Z", "publishTime": "2026-01-01T01:00:00Z"},
        {"dataset": "FUELHH", "fuelType": "WIND", "generation": 8000.0, "startTime": "2026-01-01T01:00:00Z", "publishTime": "2026-01-01T01:30:00Z"},
    ]

    df, stats = cleaner.clean_fuelhh_actuals(raw)
    assert len(df) == 1
    assert stats["invalid"] == 2
    assert df.iloc[0]["actual_mw"] == 8000.0


def test_clean_fuelhh_resolves_duplicates_keeping_latest_publish():
    cleaner = DataCleaner()
    # Same startTime, different publishTimes and values
    raw = [
        {"dataset": "FUELHH", "fuelType": "WIND", "generation": 10000.0, "startTime": "2026-01-01T12:00:00Z", "publishTime": "2026-01-01T12:30:00Z"},
        {"dataset": "FUELHH", "fuelType": "WIND", "generation": 10250.0, "startTime": "2026-01-01T12:00:00Z", "publishTime": "2026-01-01T13:00:00Z"},
    ]

    df, stats = cleaner.clean_fuelhh_actuals(raw)
    assert len(df) == 1
    assert stats["duplicates"] == 1
    # Latest publishTime (13:00:00Z) should be kept with 10250.0
    assert df.iloc[0]["actual_mw"] == 10250.0
    assert df.iloc[0]["publishTime"] == datetime(2026, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
