import logging
from datetime import datetime, timedelta, timezone, time
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd

logger = logging.getLogger("forecast_selector")


def compute_day_ahead_cutoff(delivery_dt: datetime, cutoff_hour_utc: int = 11) -> Tuple[datetime, str, datetime]:
    """
    Computes the Day-Ahead auction decision cutoff for a given delivery period.
    For delivery on Day D:
      Decision Date = D - 1 day
      Decision Cutoff = (D - 1) at cutoff_hour_utc:00:00 UTC
    All timestamps are normalized to timezone-aware UTC.
    """
    if delivery_dt.tzinfo is None:
        delivery_dt = delivery_dt.replace(tzinfo=timezone.utc)
    else:
        delivery_dt = delivery_dt.astimezone(timezone.utc)
        
    delivery_date = delivery_dt.date()
    decision_date = delivery_date - timedelta(days=1)
    decision_cutoff = datetime.combine(
        decision_date,
        time(hour=cutoff_hour_utc, minute=0, second=0),
        tzinfo=timezone.utc
    )
    return decision_cutoff, str(decision_date), delivery_dt


def is_decision_in_window(
    delivery_dt: datetime,
    window_start: datetime,
    window_end: datetime,
    cutoff_hour_utc: int = 11
) -> bool:
    """
    Determines if the day-ahead purchasing decision for a given delivery timestamp
    falls strictly within [window_start, window_end).
    """
    cutoff_dt, _, _ = compute_day_ahead_cutoff(delivery_dt, cutoff_hour_utc)
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=timezone.utc)
    if window_end.tzinfo is None:
        window_end = window_end.replace(tzinfo=timezone.utc)
    return window_start <= cutoff_dt < window_end


class ForecastSelector:
    """
    Applies Day-Ahead market gate closure rules to select the latest eligible
    wind forecast published strictly prior to or at the decision cutoff.
    """
    def __init__(self, cutoff_hour_utc: int = 11):
        self.cutoff_hour_utc = cutoff_hour_utc

    def select_day_ahead_forecasts(
        self,
        df_forecasts: pd.DataFrame,
        cutoff_hour_utc: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Filters forecasts to only those published before the day-ahead cutoff
        and selects the latest published forecast for each delivery period (startTime).
        """
        hour = cutoff_hour_utc if cutoff_hour_utc is not None else self.cutoff_hour_utc
        
        if df_forecasts.empty:
            return pd.DataFrame(columns=[
                "startTime", "decision_date", "decision_cutoff",
                "selected_publish_time", "forecast_mw", "lead_time_hours"
            ])
            
        rows = []
        # Group forecasts by delivery period startTime
        for start_time, group in df_forecasts.groupby("startTime"):
            start_dt = start_time.to_pydatetime() if isinstance(start_time, pd.Timestamp) else start_time
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
                
            cutoff_dt, decision_date_str, _ = compute_day_ahead_cutoff(start_dt, hour)
            
            # Filter strictly: publishTime <= cutoff_dt
            eligible = group[group["publishTime"] <= cutoff_dt]
            
            if eligible.empty:
                continue
                
            # Take latest eligible vintage
            latest_idx = eligible["publishTime"].idxmax()
            best_row = eligible.loc[latest_idx]
            
            pub_dt = best_row["publishTime"]
            if isinstance(pub_dt, pd.Timestamp):
                pub_dt = pub_dt.to_pydatetime()
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                
            lead_time = (start_dt - pub_dt).total_seconds() / 3600.0
            
            rows.append({
                "startTime": start_dt,
                "decision_date": decision_date_str,
                "decision_cutoff": cutoff_dt,
                "selected_publish_time": pub_dt,
                "forecast_mw": float(best_row["forecast_mw"]),
                "lead_time_hours": round(lead_time, 2)
            })
            
        if not rows:
            return pd.DataFrame(columns=[
                "startTime", "decision_date", "decision_cutoff",
                "selected_publish_time", "forecast_mw", "lead_time_hours"
            ])
            
        df_selected = pd.DataFrame(rows)
        df_selected.sort_values(by="startTime", inplace=True)
        return df_selected

    def get_forecast_history_for_period(
        self,
        df_forecasts: pd.DataFrame,
        delivery_dt: datetime
    ) -> List[Dict[str, Any]]:
        """
        Returns all forecast vintages published for a specific delivery period,
        tagged with their eligibility under the decision cutoff.
        """
        if df_forecasts.empty:
            return []
            
        if delivery_dt.tzinfo is None:
            delivery_dt = delivery_dt.replace(tzinfo=timezone.utc)
            
        cutoff_dt, dec_date_str, _ = compute_day_ahead_cutoff(delivery_dt, self.cutoff_hour_utc)
        
        # Match startTime
        matching = df_forecasts[df_forecasts["startTime"] == delivery_dt].copy()
        if matching.empty:
            return []
            
        matching.sort_values(by="publishTime", ascending=True, inplace=True)
        
        vintages = []
        for _, row in matching.iterrows():
            pub_dt = row["publishTime"]
            if isinstance(pub_dt, pd.Timestamp):
                pub_dt = pub_dt.to_pydatetime()
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                
            is_eligible = pub_dt <= cutoff_dt
            lead_time = (delivery_dt - pub_dt).total_seconds() / 3600.0
            
            vintages.append({
                "publishTime": pub_dt.isoformat(),
                "forecast_mw": float(row["forecast_mw"]),
                "is_eligible": bool(is_eligible),
                "decision_cutoff": cutoff_dt.isoformat(),
                "lead_time_hours": round(lead_time, 2)
            })
            
        return vintages
