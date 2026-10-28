import logging
from datetime import datetime, timedelta, timezone, time
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd

logger = logging.getLogger("forecast_selector")


def get_market_cutoff_info(cutoff_hour: int, cutoff_minute: int = 0) -> Dict[str, Any]:
    """
    Returns explicit metadata regarding the meaning of the configured decision cutoff:
    whether it matches an official exchange auction order book closure or is an operational modelling assumption.
    """
    time_str = f"{cutoff_hour:02d}:{cutoff_minute:02d} UTC"
    if cutoff_hour == 9 and cutoff_minute == 20:
        return {
            "time_utc": time_str,
            "market_name": "EPEX SPOT Great Britain 60-Minute Day-Ahead Auction",
            "is_official_exchange_closure": True,
            "rule_description": "Official EPEX SPOT GB 60min Day-Ahead Auction order book closure at 09:20 GMT/UTC on Day D-1.",
            "source_url": "https://www.epexspot.com/en/market-data",
            "type": "official_exchange_auction"
        }
    elif cutoff_hour == 9 and cutoff_minute == 50:
        return {
            "time_utc": time_str,
            "market_name": "Nord Pool GB Day-Ahead Auction (N2EX)",
            "is_official_exchange_closure": True,
            "rule_description": "Official Nord Pool GB Day-Ahead Auction order book closure at 09:50 GMT/UTC on Day D-1.",
            "source_url": "https://www.nordpoolgroup.com/trading/Day-ahead-trading/Auction-GB/",
            "type": "official_exchange_auction"
        }
    elif cutoff_hour == 15 and cutoff_minute == 30:
        return {
            "time_utc": time_str,
            "market_name": "EPEX SPOT Great Britain 30-Minute Day-Ahead Auction",
            "is_official_exchange_closure": True,
            "rule_description": "Official EPEX SPOT GB 30min Day-Ahead Auction order book closure at 15:30 GMT/UTC on Day D-1.",
            "source_url": "https://www.epexspot.com/en/market-data",
            "type": "official_exchange_auction"
        }
    elif cutoff_hour == 11 and cutoff_minute == 0:
        return {
            "time_utc": time_str,
            "market_name": "Utility Operational Day-Ahead Decision Window",
            "is_official_exchange_closure": False,
            "rule_description": "Configurable operational modelling assumption (11:00 UTC on Day D-1) representing a utility's late-morning procurement decision window (aligned with European SDAC reference; enables evaluating latest 10:30 UTC NESO forecast update). Note: Not an official GB exchange order book closure.",
            "source_url": "Configurable internal trading model",
            "type": "operational_modelling_assumption"
        }
    else:
        return {
            "time_utc": time_str,
            "market_name": f"Custom Operational Decision Cutoff ({time_str})",
            "is_official_exchange_closure": False,
            "rule_description": f"User-configured operational decision cutoff at {time_str} on Day D-1.",
            "source_url": "User-defined",
            "type": "custom_cutoff"
        }


def compute_day_ahead_cutoff(
    delivery_dt: datetime,
    cutoff_hour_utc: int = 11,
    cutoff_minute_utc: int = 0
) -> Tuple[datetime, str, datetime]:
    """
    Computes the Day-Ahead auction decision cutoff for a given delivery period.
    For delivery on Day D:
      Decision Date = D - 1 day
      Decision Cutoff = (D - 1) at cutoff_hour_utc:cutoff_minute_utc:00 UTC
    All timestamps are normalized to timezone-aware UTC.
    """
    if not (0 <= cutoff_hour_utc <= 23):
        raise ValueError(f"cutoff_hour_utc must be between 0 and 23, got {cutoff_hour_utc}")
    if not (0 <= cutoff_minute_utc <= 59):
        raise ValueError(f"cutoff_minute_utc must be between 0 and 59, got {cutoff_minute_utc}")

    if delivery_dt.tzinfo is None:
        delivery_dt = delivery_dt.replace(tzinfo=timezone.utc)
    else:
        delivery_dt = delivery_dt.astimezone(timezone.utc)
        
    delivery_date = delivery_dt.date()
    decision_date = delivery_date - timedelta(days=1)
    decision_cutoff = datetime.combine(
        decision_date,
        time(hour=cutoff_hour_utc, minute=cutoff_minute_utc, second=0),
        tzinfo=timezone.utc
    )
    return decision_cutoff, str(decision_date), delivery_dt


def is_decision_in_window(
    delivery_dt: datetime,
    window_start: datetime,
    window_end: datetime,
    cutoff_hour_utc: int = 11,
    cutoff_minute_utc: int = 0
) -> bool:
    """
    Determines if the day-ahead purchasing decision for a given delivery timestamp
    falls strictly within [window_start, window_end).
    """
    cutoff_dt, _, _ = compute_day_ahead_cutoff(delivery_dt, cutoff_hour_utc, cutoff_minute_utc)
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=timezone.utc)
    else:
        window_start = window_start.astimezone(timezone.utc)
    if window_end.tzinfo is None:
        window_end = window_end.replace(tzinfo=timezone.utc)
    else:
        window_end = window_end.astimezone(timezone.utc)
    return window_start <= cutoff_dt < window_end


class ForecastSelector:
    """
    Applies Day-Ahead market gate closure rules to select the latest eligible
    wind forecast published strictly prior to or at the decision cutoff.
    """
    def __init__(self, cutoff_hour_utc: int = 11, cutoff_minute_utc: int = 0):
        if not (0 <= cutoff_hour_utc <= 23):
            raise ValueError(f"cutoff_hour_utc must be between 0 and 23, got {cutoff_hour_utc}")
        if not (0 <= cutoff_minute_utc <= 59):
            raise ValueError(f"cutoff_minute_utc must be between 0 and 59, got {cutoff_minute_utc}")
        self.cutoff_hour_utc = cutoff_hour_utc
        self.cutoff_minute_utc = cutoff_minute_utc

    def select_day_ahead_forecasts(
        self,
        df_forecasts: pd.DataFrame,
        cutoff_hour_utc: Optional[int] = None,
        cutoff_minute_utc: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Filters forecasts to only those published before the day-ahead cutoff
        and selects the latest published forecast for each delivery period (startTime).
        """
        hour = cutoff_hour_utc if cutoff_hour_utc is not None else self.cutoff_hour_utc
        minute = cutoff_minute_utc if cutoff_minute_utc is not None else self.cutoff_minute_utc
        
        if not (0 <= hour <= 23):
            raise ValueError(f"cutoff_hour_utc must be between 0 and 23, got {hour}")
        if not (0 <= minute <= 59):
            raise ValueError(f"cutoff_minute_utc must be between 0 and 59, got {minute}")

        if df_forecasts.empty:
            return pd.DataFrame(columns=[
                "startTime", "decision_date", "decision_cutoff",
                "selected_publish_time", "forecast_mw", "lead_time_hours"
            ])

        df_f = df_forecasts.copy()
        if not pd.api.types.is_datetime64_any_dtype(df_f["publishTime"]):
            df_f["publishTime"] = pd.to_datetime(df_f["publishTime"], utc=True)
        elif df_f["publishTime"].dt.tz is None:
            df_f["publishTime"] = df_f["publishTime"].dt.tz_localize(timezone.utc)
        else:
            df_f["publishTime"] = df_f["publishTime"].dt.tz_convert(timezone.utc)

        if not pd.api.types.is_datetime64_any_dtype(df_f["startTime"]):
            df_f["startTime"] = pd.to_datetime(df_f["startTime"], utc=True)
        elif df_f["startTime"].dt.tz is None:
            df_f["startTime"] = df_f["startTime"].dt.tz_localize(timezone.utc)
        else:
            df_f["startTime"] = df_f["startTime"].dt.tz_convert(timezone.utc)
            
        rows = []
        # Group forecasts by delivery period startTime
        for start_time, group in df_f.groupby("startTime"):
            start_dt = start_time.to_pydatetime() if isinstance(start_time, pd.Timestamp) else start_time
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            else:
                start_dt = start_dt.astimezone(timezone.utc)
                
            cutoff_dt, decision_date_str, _ = compute_day_ahead_cutoff(start_dt, hour, minute)
            
            # Filter strictly: publishTime <= cutoff_dt (inclusive of exact cutoff second)
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
            else:
                pub_dt = pub_dt.astimezone(timezone.utc)
                
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
        delivery_dt: datetime,
        cutoff_hour_utc: Optional[int] = None,
        cutoff_minute_utc: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Returns all forecast vintages published for a specific delivery period,
        tagged with their eligibility under the decision cutoff.
        """
        if df_forecasts.empty:
            return []

        df_f = df_forecasts.copy()
        if not pd.api.types.is_datetime64_any_dtype(df_f["publishTime"]):
            df_f["publishTime"] = pd.to_datetime(df_f["publishTime"], utc=True)
        elif df_f["publishTime"].dt.tz is None:
            df_f["publishTime"] = df_f["publishTime"].dt.tz_localize(timezone.utc)
        else:
            df_f["publishTime"] = df_f["publishTime"].dt.tz_convert(timezone.utc)

        if not pd.api.types.is_datetime64_any_dtype(df_f["startTime"]):
            df_f["startTime"] = pd.to_datetime(df_f["startTime"], utc=True)
        elif df_f["startTime"].dt.tz is None:
            df_f["startTime"] = df_f["startTime"].dt.tz_localize(timezone.utc)
        else:
            df_f["startTime"] = df_f["startTime"].dt.tz_convert(timezone.utc)
            
        hour = cutoff_hour_utc if cutoff_hour_utc is not None else self.cutoff_hour_utc
        minute = cutoff_minute_utc if cutoff_minute_utc is not None else self.cutoff_minute_utc

        if delivery_dt.tzinfo is None:
            delivery_dt = delivery_dt.replace(tzinfo=timezone.utc)
        else:
            delivery_dt = delivery_dt.astimezone(timezone.utc)
            
        cutoff_dt, dec_date_str, _ = compute_day_ahead_cutoff(delivery_dt, hour, minute)
        
        # Match startTime
        matching = df_f[df_f["startTime"] == delivery_dt].copy()
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
            else:
                pub_dt = pub_dt.astimezone(timezone.utc)
                
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
