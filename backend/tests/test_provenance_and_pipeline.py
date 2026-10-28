import json
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone
import pytest
import pandas as pd

from app.services.elexon_client import ElexonApiClient
from app.services.pipeline import AnalyticsPipeline
from app.services.forecast_selector import is_decision_in_window


def test_provenance_labeling_disk_cache():
    """
    Verifies that when data is loaded from local disk cache, the provenance
    is labeled as 'DISK_CACHE' and NOT falsely claimed as 'LIVE_API'.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_path = Path(tmp_dir)
        client = ElexonApiClient(cache_dir=cache_path)

        # Pre-seed cache with sample records
        start_iso = "2026-01-01T00:00:00Z"
        end_iso = "2026-01-08T00:00:00Z"
        c_file = client._get_cache_path("FUELHH", start_iso, end_iso)
        with open(c_file, "w") as f:
            json.dump([{"dataset": "FUELHH", "startTime": start_iso, "generation": 1000}], f)

        start_dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(2026, 1, 8, 0, 0, 0, tzinfo=timezone.utc)
        records = client.fetch_stream_chunked("FUELHH", start_dt, end_dt, chunk_days=7, use_cache=True)

        assert len(records) == 1
        assert client.get_dataset_provenance("FUELHH") == "DISK_CACHE"


def test_corrupted_cache_fallback(monkeypatch):
    """
    Ensures that if a disk cache file is corrupted (e.g. invalid JSON),
    the client handles it safely and falls back to live fetch instead of crashing.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_path = Path(tmp_dir)
        client = ElexonApiClient(cache_dir=cache_path)

        start_iso = "2026-01-01T00:00:00Z"
        end_iso = "2026-01-08T00:00:00Z"
        c_file = client._get_cache_path("FUELHH", start_iso, end_iso)
        # Write corrupted content
        with open(c_file, "w") as f:
            f.write("{ INVALID JSON NOT A LIST")

        # Mock _request_with_retry to simulate live API returning valid data
        def mock_retry(url, params):
            return [{"dataset": "FUELHH", "startTime": start_iso, "generation": 2500}]

        monkeypatch.setattr(client, "_request_with_retry", mock_retry)

        start_dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(2026, 1, 8, 0, 0, 0, tzinfo=timezone.utc)
        records = client.fetch_stream_chunked("FUELHH", start_dt, end_dt, chunk_days=7, use_cache=True)

        assert len(records) == 1
        assert records[0]["generation"] == 2500
        assert client.get_dataset_provenance("FUELHH") == "LIVE_API"


def test_pipeline_decision_date_window_selection():
    """
    Verifies that the AnalyticsPipeline filters strictly by January 2026 decision dates:
    - Dec 31, 2025 decision (delivering Jan 1, 2026) is EXCLUDED.
    - Jan 1, 2026 decision (delivering Jan 2, 2026) is INCLUDED.
    - Jan 31, 2026 decision (delivering Feb 1, 2026) is INCLUDED.
    - Feb 1, 2026 decision (delivering Feb 2, 2026) is EXCLUDED.
    """
    pipeline = AnalyticsPipeline()
    # Run against real bundled cache
    df = pipeline.run_pipeline(target_year=2026, target_month=1, cutoff_hour_utc=11, window_type="decision", resolution="hourly")

    assert not df.empty
    # Must have exactly 744 matched hours (31 days * 24 hours)
    assert len(df) == 744

    # Earliest delivery date in Jan decision window is 2026-01-02 00:00:00Z (decided Jan 1)
    min_start = pd.to_datetime(df["startTime"]).min()
    assert min_start == pd.Timestamp("2026-01-02 00:00:00+0000", tz="UTC")

    # Latest delivery date in Jan decision window is 2026-02-01 23:00:00Z (decided Jan 31)
    max_start = pd.to_datetime(df["startTime"]).max()
    assert max_start == pd.Timestamp("2026-02-01 23:00:00+0000", tz="UTC")

    # Verify decision dates in matched set are all within 2026-01-01 and 2026-01-31
    dec_dates = sorted(df["decision_date"].unique())
    assert dec_dates[0] == "2026-01-01"
    assert dec_dates[-1] == "2026-01-31"
    assert len(dec_dates) == 31

    # Verify data source provenance is DISK_CACHE (not falsely LIVE_API)
    assert pipeline.data_source == "DISK_CACHE"
    assert pipeline.dq_summary.data_source == "DISK_CACHE"
    assert pipeline.dq_summary.data_coverage_percentage == 100.0


def test_pipeline_half_hourly_resolution_transparency():
    """
    Verifies that when half-hourly resolution is requested, missing forecasts on :30
    are preserved transparently without interpolation (resulting in 50% coverage).
    """
    pipeline = AnalyticsPipeline()
    df = pipeline.run_pipeline(target_year=2026, target_month=1, cutoff_hour_utc=11, window_type="decision", resolution="half-hourly")

    assert not df.empty
    # Total periods: 31 days * 48 half-hours = 1,488
    assert pipeline.dq_summary.total_expected_periods == 1488
    # 744 matched, 744 missing forecasts
    assert pipeline.dq_summary.matched_periods_count == 744
    assert pipeline.dq_summary.missing_forecast_periods == 744
    assert pipeline.dq_summary.data_coverage_percentage == 50.0


@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason="Opt-in live integration test. Set RUN_LIVE_TESTS=1 to run.")
def test_live_elexon_api_integration():
    """
    Opt-in live test verifying real Elexon Insights Solution REST endpoints.
    Only runs when network access is authorized and RUN_LIVE_TESTS=1 is set.
    """
    client = ElexonApiClient()
    start_dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 1, 1, 2, 0, 0, tzinfo=timezone.utc)

    # Live query without cache
    records = client.fetch_fuelhh(start_dt, end_dt, use_cache=False)
    assert len(records) > 0
    assert any(r.get("fuelType") == "WIND" for r in records)
