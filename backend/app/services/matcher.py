import logging
from typing import Dict, Any, Tuple
import pandas as pd

logger = logging.getLogger("matcher")


class Matcher:
    """
    Matches selected forecasts with actual outturn generation.
    Supports two defensible evaluation resolutions:
    1. 'hourly' (default): Aggregates half-hourly actuals to mean hourly power (MW)
       to compare against the 1-hour WINDFOR product across the exact same 1-hour window.
       Preserves individual half-hour outturn readings for full traceability.
    2. 'half-hourly': Strictly matches on exact startTime without interpolation,
       transparently preserving missing forecast periods on half-hours.
    """
    def match(
        self,
        df_selected_forecasts: pd.DataFrame,
        df_clean_actuals: pd.DataFrame,
        resolution: str = "hourly"
    ) -> Tuple[pd.DataFrame, Dict[str, int]]:
        """
        Performs matching between selected forecasts and actuals.
        """
        if df_selected_forecasts.empty and df_clean_actuals.empty:
            empty_df = pd.DataFrame(columns=[
                "startTime", "settlementDate", "settlementPeriod",
                "decision_date", "decision_cutoff", "selected_publish_time",
                "forecast_mw", "actual_mw", "signed_error_mw", "abs_error_mw",
                "lead_time_hours", "status"
            ])
            return empty_df, {
                "actual_periods": 0,
                "forecast_periods": 0,
                "matched_periods": 0,
                "missing_forecast": 0,
                "missing_actual": 0
            }

        f_df = df_selected_forecasts.copy()
        a_df = df_clean_actuals.copy()

        # Ensure unique index per startTime
        f_df.drop_duplicates(subset=["startTime"], keep="first", inplace=True)
        a_df.drop_duplicates(subset=["startTime"], keep="first", inplace=True)

        if resolution == "hourly" and not a_df.empty:
            # Group half-hourly actuals by 1-hour window
            a_df["hour_start"] = pd.to_datetime(a_df["startTime"]).dt.floor("h")
            
            # Aggregate: arithmetic mean of the two half-hour MW generation readings
            # Power in MW averaged over two 30-min intervals gives the mean hourly MW
            grouped = a_df.groupby("hour_start")
            agg_rows = []
            for hour_dt, grp in grouped:
                s_dates = grp["settlementDate"].dropna().tolist()
                s_periods = grp["settlementPeriod"].dropna().tolist()
                gens = grp["actual_mw"].tolist()
                
                period_str = f"P{min(s_periods)}-P{max(s_periods)}" if s_periods else None
                s_date = s_dates[0] if s_dates else None
                
                # Hourly power is only valid if both half-hourly intervals exist
                if len(gens) == 2:
                    mean_mw = float((gens[0] + gens[1]) / 2.0)
                    actual_mw_val = round(mean_mw, 2)
                else:
                    # Partial or incomplete hour: do not silently average or complete
                    actual_mw_val = None
                
                agg_rows.append({
                    "startTime": hour_dt,
                    "settlementDate": s_date,
                    "settlementPeriod": period_str,
                    "actual_mw": actual_mw_val,
                    "actual_hh0_mw": gens[0] if len(gens) > 0 else None,
                    "actual_hh1_mw": gens[1] if len(gens) > 1 else None,
                    "hh_count": len(gens)
                })
            a_df = pd.DataFrame(agg_rows)

        actual_count = len(a_df)
        forecast_count = len(f_df)

        merged = pd.merge(
            a_df,
            f_df,
            on="startTime",
            how="outer",
            suffixes=("_actual", "_forecast")
        )

        # Consolidate settlement date and period if present in both
        if "settlementDate_actual" in merged.columns:
            merged["settlementDate"] = merged["settlementDate_actual"].combine_first(merged.get("settlementDate_forecast", pd.Series()))
        if "settlementPeriod_actual" in merged.columns:
            merged["settlementPeriod"] = merged["settlementPeriod_actual"].combine_first(merged.get("settlementPeriod_forecast", pd.Series()))

        merged.sort_values(by="startTime", inplace=True)

        # Ensure decision_date and decision_cutoff are populated for all rows
        if not merged.empty:
            start_times = pd.to_datetime(merged["startTime"])
            deliv_dates = start_times.dt.date
            derived_decision_dates = (deliv_dates - pd.Timedelta(days=1)).astype(str)
            if "decision_date" not in merged.columns or merged["decision_date"].isna().any():
                merged["decision_date"] = merged.get("decision_date", pd.Series(index=merged.index)).fillna(derived_decision_dates)
            if "decision_cutoff" not in merged.columns or merged["decision_cutoff"].isna().any():
                derived_cutoffs = pd.to_datetime(merged["decision_date"], utc=True) + pd.Timedelta(hours=11)
                merged["decision_cutoff"] = merged.get("decision_cutoff", pd.Series(index=merged.index)).fillna(derived_cutoffs)

        # Classify status
        has_forecast = merged["forecast_mw"].notna()
        has_actual = merged["actual_mw"].notna()

        conditions = [
            (has_forecast & has_actual),
            (~has_forecast & has_actual),
            (has_forecast & ~has_actual)
        ]
        choices = ["MATCHED", "MISSING_FORECAST", "MISSING_ACTUAL"]
        merged["status"] = "INVALID"
        for cond, choice in zip(conditions, choices):
            merged.loc[cond, "status"] = choice

        # Calculate error metrics for matched observations
        matched_mask = merged["status"] == "MATCHED"
        merged["signed_error_mw"] = None
        merged["abs_error_mw"] = None
        merged["squared_error_mw2"] = None

        if matched_mask.any():
            f_vals = merged.loc[matched_mask, "forecast_mw"].astype(float)
            a_vals = merged.loc[matched_mask, "actual_mw"].astype(float)
            
            signed_err = f_vals - a_vals
            merged.loc[matched_mask, "signed_error_mw"] = signed_err.round(2)
            merged.loc[matched_mask, "abs_error_mw"] = signed_err.abs().round(2)
            merged.loc[matched_mask, "squared_error_mw2"] = (signed_err ** 2).round(2)

        matched_count = int(matched_mask.sum())
        missing_forecast_count = int((merged["status"] == "MISSING_FORECAST").sum())
        missing_actual_count = int((merged["status"] == "MISSING_ACTUAL").sum())

        counts = {
            "actual_periods": actual_count,
            "forecast_periods": forecast_count,
            "matched_periods": matched_count,
            "missing_forecast": missing_forecast_count,
            "missing_actual": missing_actual_count
        }

        return merged, counts
