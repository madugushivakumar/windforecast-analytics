import logging
from typing import Dict, Any, Tuple
import pandas as pd

logger = logging.getLogger("matcher")


class Matcher:
    """
    Matches selected forecasts with actual outturn generation strictly
    on the target delivery period timestamp (startTime).
    Calculates observation-level error fields.
    """
    def match(
        self,
        df_selected_forecasts: pd.DataFrame,
        df_clean_actuals: pd.DataFrame
    ) -> Tuple[pd.DataFrame, Dict[str, int]]:
        """
        Performs an outer join on startTime to retain full visibility of
        matched observations, missing actuals, and missing forecasts.
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

        actual_count = len(a_df)
        forecast_count = len(f_df)

        merged = pd.merge(
            a_df,
            f_df,
            on="startTime",
            how="outer"
        )

        merged.sort_values(by="startTime", inplace=True)

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
