import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import numpy as np
import pandas as pd

from app.core.config import settings
from app.services.elexon_client import ElexonApiClient
from app.services.data_cleaner import DataCleaner
from app.services.forecast_selector import ForecastSelector
from app.services.matcher import Matcher
from app.analytics.metrics import (
    calculate_mae,
    calculate_rmse,
    calculate_mean_signed_error,
    calculate_max_absolute_error,
    calculate_wape,
    calculate_conditional_mape,
    compute_error_distribution,
)
from app.schemas.data_quality import DataQualitySummary
from app.schemas.metrics import AccuracyMetrics, OverviewResponse

logger = logging.getLogger("analytics_pipeline")


class AnalyticsPipeline:
    """
    Central orchestration engine for WindForecast Analytics.
    Coordinates data ingestion, cleaning, cutoff selection, matching,
    and metrics computation with in-memory caching.
    """
    def __init__(self, elexon_client: Optional[ElexonApiClient] = None):
        self.client = elexon_client or ElexonApiClient()
        self.cleaner = DataCleaner()
        self.selector = ForecastSelector(cutoff_hour_utc=settings.DEFAULT_CUTOFF_HOUR_UTC)
        self.matcher = Matcher()
        
        # In-memory cached artifacts
        self.raw_actuals: List[Dict[str, Any]] = []
        self.raw_forecasts: List[Dict[str, Any]] = []
        self.df_clean_actuals: pd.DataFrame = pd.DataFrame()
        self.df_clean_forecasts: pd.DataFrame = pd.DataFrame()
        self.df_matched: pd.DataFrame = pd.DataFrame()
        self.dq_summary: Optional[DataQualitySummary] = None
        self.last_run_utc: Optional[str] = None
        self.data_source: str = "UNINITIALIZED"

    def run_pipeline(
        self,
        target_year: int = 2026,
        target_month: int = 1,
        cutoff_hour_utc: int = 11,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Executes the full analytics pipeline for the specified target month.
        """
        # Check if already loaded for same parameters
        if not force_refresh and not self.df_matched.empty and self.selector.cutoff_hour_utc == cutoff_hour_utc:
            logger.info("Returning cached in-memory analysis dataset.")
            return self.df_matched

        self.selector.cutoff_hour_utc = cutoff_hour_utc

        # Define time windows
        # Delivery starts 2026-01-01 00:00:00Z and runs to 2026-02-01 23:30:00Z
        delivery_start = datetime(target_year, target_month, 1, 0, 0, 0, tzinfo=timezone.utc)
        # Next month boundary
        if target_month == 12:
            delivery_end = datetime(target_year + 1, 1, 1, 23, 59, 59, tzinfo=timezone.utc)
        else:
            delivery_end = datetime(target_year, target_month + 1, 1, 23, 59, 59, tzinfo=timezone.utc)
            
        # Ingest forecasts starting 2 days prior to capture day-ahead forecasts for Jan 1
        forecast_ingest_start = delivery_start - timedelta(days=2)
        forecast_ingest_end = delivery_end

        logger.info(f"Ingesting FUELHH actuals from {delivery_start.isoformat()} to {delivery_end.isoformat()}")
        actuals_raw = self.client.fetch_fuelhh(delivery_start, delivery_end)
        self.raw_actuals = actuals_raw

        logger.info(f"Ingesting WINDFOR forecasts from {forecast_ingest_start.isoformat()} to {forecast_ingest_end.isoformat()}")
        forecasts_raw = self.client.fetch_windfor(forecast_ingest_start, forecast_ingest_end)
        self.raw_forecasts = forecasts_raw

        # Step 2: Clean and validate
        df_act, act_stats = self.cleaner.clean_fuelhh_actuals(actuals_raw)
        df_for, for_stats = self.cleaner.clean_windfor_forecasts(forecasts_raw)
        
        self.df_clean_actuals = df_act
        self.df_clean_forecasts = df_for

        # Step 3: Select Day-Ahead forecasts published <= cutoff
        df_selected_forecasts = self.selector.select_day_ahead_forecasts(df_for, cutoff_hour_utc=cutoff_hour_utc)

        # Step 4: Match on startTime
        df_matched, match_counts = self.matcher.match(df_selected_forecasts, df_act)

        # Filter matched view strictly to target month delivery periods (Jan 1 00:00 to Jan 31 23:30)
        month_end = datetime(target_year, target_month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        mask_month = (df_matched["startTime"] >= delivery_start) & (df_matched["startTime"] < month_end)
        self.df_matched = df_matched.loc[mask_month].copy()

        # Step 5: Build Data Quality Summary
        total_expected_half_hours = 31 * 48  # 1,488 half-hours in January (non-clock-change)
        matched_in_month = int((self.df_matched["status"] == "MATCHED").sum())
        missing_act = int((self.df_matched["status"] == "MISSING_ACTUAL").sum())
        missing_fc = int((self.df_matched["status"] == "MISSING_FORECAST").sum())
        
        coverage_pct = round((matched_in_month / total_expected_half_hours) * 100.0, 2)

        self.last_run_utc = datetime.now(timezone.utc).isoformat()
        self.data_source = "LIVE_API" if settings.ENABLE_CACHE else "LIVE_API_STREAM"

        self.dq_summary = DataQualitySummary(
            actual_records_fetched=act_stats["fetched"],
            wind_actual_records_retained=act_stats["retained"],
            forecast_records_fetched=for_stats["fetched"],
            invalid_generation_records=act_stats["invalid"] + for_stats["invalid"],
            duplicate_records_resolved=act_stats["duplicates"] + for_stats["duplicates"],
            missing_actual_periods=missing_act,
            missing_forecast_periods=missing_fc,
            matched_periods_count=matched_in_month,
            total_expected_periods=total_expected_half_hours,
            data_coverage_percentage=coverage_pct,
            last_updated_utc=self.last_run_utc,
            data_source=self.data_source,
            notes=[
                f"Evaluated Day-Ahead gate closure cutoff at {cutoff_hour_utc}:00 UTC (D-1).",
                f"Selected latest eligible WINDFOR vintage where publishTime <= cutoff.",
                f"Strictly matched on delivery period startTime with FUELHH fuelType == 'WIND'."
            ]
        )

        return self.df_matched

    def compute_accuracy_metrics(self, df_sample: Optional[pd.DataFrame] = None) -> AccuracyMetrics:
        """
        Computes pure mathematical metrics on the matched sample.
        """
        target_df = df_sample if df_sample is not None else self.df_matched
        matched_rows = target_df[target_df["status"] == "MATCHED"]

        if matched_rows.empty:
            return AccuracyMetrics(
                sample_size=0,
                mae_mw=0.0,
                rmse_mw=0.0,
                mean_signed_error_mw=0.0,
                max_abs_error_mw=0.0,
                min_signed_error_mw=0.0,
                max_signed_error_mw=0.0,
                error_std_mw=0.0,
                wape_percentage=None,
                mape_percentage=None,
                mape_note="No matched observations available for calculation.",
                unit="MW"
            )

        f_list = matched_rows["forecast_mw"].astype(float).tolist()
        a_list = matched_rows["actual_mw"].astype(float).tolist()
        e_list = (matched_rows["signed_error_mw"].astype(float)).tolist()

        mae = calculate_mae(f_list, a_list)
        rmse = calculate_rmse(f_list, a_list)
        bias = calculate_mean_signed_error(f_list, a_list)
        max_abs = calculate_max_absolute_error(f_list, a_list)
        wape = calculate_wape(f_list, a_list)
        mape, valid_count = calculate_conditional_mape(f_list, a_list, min_actual_threshold=100.0)

        std_err = float(np.std(e_list, ddof=1)) if len(e_list) > 1 else 0.0

        return AccuracyMetrics(
            sample_size=len(f_list),
            mae_mw=round(mae, 2),
            rmse_mw=round(rmse, 2),
            mean_signed_error_mw=round(bias, 2),
            max_abs_error_mw=round(max_abs, 2),
            min_signed_error_mw=round(min(e_list), 2),
            max_signed_error_mw=round(max(e_list), 2),
            error_std_mw=round(std_err, 2),
            wape_percentage=round(wape, 2) if wape is not None else None,
            mape_percentage=round(mape, 2) if mape is not None else None,
            mape_note=(
                f"Conditional MAPE computed on {valid_count}/{len(a_list)} periods where actual >= 100 MW "
                "to avoid division by zero or near-zero distortion."
            ),
            unit="MW"
        )

    def get_overview(self) -> OverviewResponse:
        """Builds high-level dashboard response."""
        if self.df_matched.empty:
            self.run_pipeline()

        metrics = self.compute_accuracy_metrics()
        dq = self.dq_summary or DataQualitySummary(
            actual_records_fetched=0,
            wind_actual_records_retained=0,
            forecast_records_fetched=0,
            invalid_generation_records=0,
            duplicate_records_resolved=0,
            missing_actual_periods=0,
            missing_forecast_periods=0,
            matched_periods_count=0,
            total_expected_periods=1488,
            data_coverage_percentage=0.0,
            last_updated_utc=datetime.now(timezone.utc).isoformat(),
            data_source=self.data_source,
            notes=[]
        )

        # Time series preview (every period or resampled for overview)
        ts_sample = []
        for _, row in self.df_matched.iterrows():
            ts_sample.append({
                "startTime": row["startTime"].isoformat() if hasattr(row["startTime"], "isoformat") else str(row["startTime"]),
                "forecast_mw": row["forecast_mw"] if pd.notna(row["forecast_mw"]) else None,
                "actual_mw": row["actual_mw"] if pd.notna(row["actual_mw"]) else None,
                "signed_error_mw": row["signed_error_mw"] if pd.notna(row["signed_error_mw"]) else None,
                "abs_error_mw": row["abs_error_mw"] if pd.notna(row["abs_error_mw"]) else None,
                "status": row["status"]
            })

        return OverviewResponse(
            title="WindForecast Analytics",
            analysis_window="January 2026 Day-Ahead Market",
            decision_cutoff_rule=f"Day D-1 at {self.selector.cutoff_hour_utc}:00 UTC",
            metrics=metrics,
            coverage_percentage=dq.data_coverage_percentage,
            total_delivery_periods=dq.total_expected_periods,
            matched_delivery_periods=dq.matched_periods_count,
            missing_forecast_periods=dq.missing_forecast_periods,
            missing_actual_periods=dq.missing_actual_periods,
            last_updated_utc=dq.last_updated_utc,
            data_source=dq.data_source,
            time_series_sample=ts_sample
        )


pipeline_service = AnalyticsPipeline()
