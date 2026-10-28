import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import numpy as np
import pandas as pd

from app.core.config import settings
from app.services.elexon_client import ElexonApiClient
from app.services.data_cleaner import DataCleaner
from app.services.forecast_selector import ForecastSelector, get_market_cutoff_info
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
    Supports both decision-date window (primary) and delivery-date window,
    as well as hourly aggregation (primary) and half-hourly resolution.
    """
    def __init__(self, elexon_client: Optional[ElexonApiClient] = None):
        self.client = elexon_client or ElexonApiClient()
        self.cleaner = DataCleaner()
        self.selector = ForecastSelector(
            cutoff_hour_utc=settings.DEFAULT_CUTOFF_HOUR_UTC,
            cutoff_minute_utc=settings.DEFAULT_CUTOFF_MINUTE_UTC
        )
        self.matcher = Matcher()
        
        # In-memory cached artifacts and state
        self.raw_actuals: List[Dict[str, Any]] = []
        self.raw_forecasts: List[Dict[str, Any]] = []
        self.df_clean_actuals: pd.DataFrame = pd.DataFrame()
        self.df_clean_forecasts: pd.DataFrame = pd.DataFrame()
        self.df_matched: pd.DataFrame = pd.DataFrame()
        self.dq_summary: Optional[DataQualitySummary] = None
        self.last_run_utc: Optional[str] = None
        self.data_source: str = "UNINITIALIZED"
        self.current_window_type: str = "decision"
        self.current_resolution: str = "hourly"
        self.target_year: int = 2026
        self.target_month: int = 1

    def run_pipeline(
        self,
        target_year: int = 2026,
        target_month: int = 1,
        cutoff_hour_utc: int = 11,
        cutoff_minute_utc: int = 0,
        window_type: str = "decision",
        resolution: str = "hourly",
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Executes the full analytics pipeline for the specified parameters.
        - window_type: 'decision' (January 2026 purchasing decisions, delivering Jan 2 to Feb 1)
                       or 'delivery' (January 2026 delivery periods, Jan 1 to Jan 31)
        - resolution: 'hourly' (mean actual MW of the two half-hours vs 1-hour forecast)
                      or 'half-hourly' (raw :00 join with :30 marked MISSING_FORECAST)
        """
        # Check if already loaded for same parameters
        if (
            not force_refresh
            and not self.df_matched.empty
            and self.selector.cutoff_hour_utc == cutoff_hour_utc
            and self.selector.cutoff_minute_utc == cutoff_minute_utc
            and self.current_window_type == window_type
            and self.current_resolution == resolution
            and self.target_year == target_year
            and self.target_month == target_month
        ):
            logger.info("Returning cached in-memory analysis dataset.")
            return self.df_matched

        self.selector.cutoff_hour_utc = cutoff_hour_utc
        self.selector.cutoff_minute_utc = cutoff_minute_utc
        self.current_window_type = window_type
        self.current_resolution = resolution
        self.target_year = target_year
        self.target_month = target_month

        # Define delivery date range covering both decision window and delivery window:
        # For January decisions (Jan 1 to Jan 31), delivery spans Jan 2 00:00 UTC to Feb 1 23:30 UTC.
        # For January deliveries, delivery spans Jan 1 00:00 UTC to Jan 31 23:30 UTC.
        # Ingesting from Jan 1 00:00:00Z to Feb 1 23:59:59Z covers all required periods.
        delivery_start = datetime(target_year, target_month, 1, 0, 0, 0, tzinfo=timezone.utc)
        delivery_end = datetime(target_year, target_month + 1, 1, 23, 59, 59, tzinfo=timezone.utc) if target_month < 12 else datetime(target_year + 1, 1, 1, 23, 59, 59, tzinfo=timezone.utc)

        # Forecast ingest window: begins 2 days prior to delivery_start to capture all D-1 Day-Ahead forecasts
        forecast_ingest_start = delivery_start - timedelta(days=2)
        forecast_ingest_end = delivery_end

        logger.info(f"Ingesting FUELHH actuals for delivery {delivery_start.isoformat()} to {delivery_end.isoformat()}")
        actuals_raw = self.client.fetch_fuelhh(delivery_start, delivery_end, use_cache=not force_refresh)
        self.raw_actuals = actuals_raw

        logger.info(f"Ingesting WINDFOR forecasts from {forecast_ingest_start.isoformat()} to {forecast_ingest_end.isoformat()}")
        forecasts_raw = self.client.fetch_windfor(forecast_ingest_start, forecast_ingest_end, use_cache=not force_refresh)
        self.raw_forecasts = forecasts_raw

        # Step 2: Clean and validate
        df_act, act_stats = self.cleaner.clean_fuelhh_actuals(actuals_raw)
        df_for, for_stats = self.cleaner.clean_windfor_forecasts(forecasts_raw)
        
        self.df_clean_actuals = df_act
        self.df_clean_forecasts = df_for

        # Step 3: Select Day-Ahead forecasts published <= cutoff
        df_selected_forecasts = self.selector.select_day_ahead_forecasts(
            df_for,
            cutoff_hour_utc=cutoff_hour_utc,
            cutoff_minute_utc=cutoff_minute_utc
        )

        # Step 4: Match on startTime with specified resolution
        df_matched, match_counts = self.matcher.match(df_selected_forecasts, df_act, resolution=resolution)

        # Step 5: Filter strictly according to requested window_type
        if window_type == "decision":
            # Purchasing decisions made in target month: 2026-01-01 <= decision_date <= 2026-01-31
            # Delivering from 2026-01-02 00:00:00Z through 2026-02-01 23:59:59Z
            start_dec_str = f"{target_year}-{target_month:02d}-01"
            if target_month == 12:
                end_dec_str = f"{target_year + 1}-01-01"
            else:
                end_dec_str = f"{target_year}-{target_month + 1:02d}-01"
            
            mask_window = (df_matched["decision_date"] >= start_dec_str) & (df_matched["decision_date"] < end_dec_str)
            self.df_matched = df_matched.loc[mask_window].copy()
        else:
            # Delivery window: delivery periods delivered in target month (Jan 1 00:00:00Z to Jan 31 23:59:59Z)
            month_end = datetime(target_year, target_month + 1, 1, 0, 0, 0, tzinfo=timezone.utc) if target_month < 12 else datetime(target_year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            mask_window = (df_matched["startTime"] >= delivery_start) & (df_matched["startTime"] < month_end)
            self.df_matched = df_matched.loc[mask_window].copy()

        # Step 6: Build Data Quality Summary
        days_in_month = 31  # January
        if resolution == "hourly":
            total_expected_periods = days_in_month * 24  # 744 hours
        else:
            total_expected_periods = days_in_month * 48  # 1,488 half-hours

        matched_in_window = int((self.df_matched["status"] == "MATCHED").sum())
        missing_act = int((self.df_matched["status"] == "MISSING_ACTUAL").sum())
        missing_fc = int((self.df_matched["status"] == "MISSING_FORECAST").sum())
        
        coverage_pct = round((matched_in_window / total_expected_periods) * 100.0, 2)

        self.last_run_utc = datetime.now(timezone.utc).isoformat()
        
        # Real provenance tracking: check cache vs live API from client
        fuel_prov = self.client.get_dataset_provenance("FUELHH")
        wind_prov = self.client.get_dataset_provenance("WINDFOR")
        if fuel_prov == "DISK_CACHE" and wind_prov == "DISK_CACHE":
            self.data_source = "DISK_CACHE"
        elif fuel_prov == "LIVE_API" and wind_prov == "LIVE_API":
            self.data_source = "LIVE_API"
        else:
            self.data_source = f"{fuel_prov}/{wind_prov}"

        cutoff_meta = get_market_cutoff_info(cutoff_hour_utc, cutoff_minute_utc)
        notes = [
            f"Analysis Window: {window_type.capitalize()} Window ({'Decisions Jan 1-31 delivering Jan 2-Feb 1' if window_type == 'decision' else 'Delivery Jan 1-31'}).",
            f"Resolution: {resolution.capitalize()} ({'Mean actual MW of two half-hours vs 1-hour forecast' if resolution == 'hourly' else 'Exact half-hourly join'}).",
            f"Decision Cutoff: {cutoff_meta['rule_description']} [Type: {cutoff_meta['type']}, Official Exchange Closure: {cutoff_meta['is_official_exchange_closure']}].",
            f"Selected latest eligible WINDFOR vintage where publishTime <= cutoff timestamp.",
            f"Data Source Provenance: FUELHH={fuel_prov}, WINDFOR={wind_prov}."
        ]

        self.dq_summary = DataQualitySummary(
            actual_records_fetched=act_stats["fetched"],
            wind_actual_records_retained=act_stats["retained"],
            forecast_records_fetched=for_stats["fetched"],
            invalid_generation_records=act_stats["invalid"] + for_stats["invalid"],
            duplicate_records_resolved=act_stats["duplicates"] + for_stats["duplicates"],
            missing_actual_periods=missing_act,
            missing_forecast_periods=missing_fc,
            matched_periods_count=matched_in_window,
            total_expected_periods=total_expected_periods,
            data_coverage_percentage=coverage_pct,
            last_updated_utc=self.last_run_utc,
            data_source=self.data_source,
            notes=notes
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
            total_expected_periods=744,
            data_coverage_percentage=0.0,
            last_updated_utc=datetime.now(timezone.utc).isoformat(),
            data_source=self.data_source,
            notes=[]
        )

        # Time series preview
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

        window_desc = "January 2026 Day-Ahead Market (Decision Window: Jan 1 - Jan 31)" if self.current_window_type == "decision" else "January 2026 Delivery Window (Jan 1 - Jan 31)"

        cutoff_meta = get_market_cutoff_info(self.selector.cutoff_hour_utc, self.selector.cutoff_minute_utc)
        cutoff_rule_str = f"Day D-1 at {self.selector.cutoff_hour_utc:02d}:{self.selector.cutoff_minute_utc:02d} UTC ({cutoff_meta['market_name']})"

        return OverviewResponse(
            title="WindForecast Analytics",
            analysis_window=window_desc,
            decision_cutoff_rule=cutoff_rule_str,
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
