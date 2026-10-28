import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd

from app.schemas.data_quality import DataQualitySummary

logger = logging.getLogger("data_cleaner")


def parse_utc_timestamp(ts_str: Any) -> Optional[datetime]:
    """
    Parses an ISO 8601 string or existing datetime into a timezone-aware UTC datetime.
    Returns None if unparseable.
    """
    if ts_str is None:
        return None
    if isinstance(ts_str, datetime):
        if ts_str.tzinfo is None:
            return ts_str.replace(tzinfo=timezone.utc)
        return ts_str.astimezone(timezone.utc)
    
    if not isinstance(ts_str, str):
        return None

    clean_str = ts_str.strip()
    try:
        # Standard ISO format with Z
        if clean_str.endswith("Z"):
            dt = datetime.fromisoformat(clean_str[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        # Fallback via pandas to_datetime
        try:
            pdt = pd.to_datetime(clean_str, utc=True)
            return pdt.to_pydatetime()
        except Exception:
            return None


class DataCleaner:
    """
    Cleans, validates, and standardizes FUELHH and WINDFOR records.
    Produces clean DataFrames and an audit-trail DataQualitySummary.
    """
    def __init__(self):
        self.invalid_records_count = 0
        self.duplicate_records_count = 0
        self.notes: List[str] = []

    def clean_fuelhh_actuals(
        self,
        raw_records: List[Dict[str, Any]]
    ) -> Tuple[pd.DataFrame, Dict[str, int]]:
        """
        Cleans FUELHH records:
        1. Filters strictly to fuelType == 'WIND'
        2. Normalizes startTime and publishTime to UTC
        3. Validates generation (>= 0.0)
        4. Resolves duplicate startTimes deterministically (keeps latest publishTime)
        """
        total_fetched = len(raw_records)
        wind_records = []
        invalid_count = 0
        
        for r in raw_records:
            if r.get("fuelType") != "WIND":
                continue
            
            gen_val = r.get("generation")
            try:
                gen_float = float(gen_val)
                if gen_float < 0.0:
                    invalid_count += 1
                    continue
            except (ValueError, TypeError):
                invalid_count += 1
                continue
                
            start_dt = parse_utc_timestamp(r.get("startTime"))
            pub_dt = parse_utc_timestamp(r.get("publishTime"))
            
            if not start_dt:
                invalid_count += 1
                continue
            if not pub_dt:
                pub_dt = start_dt  # fallback if publishTime missing
                
            wind_records.append({
                "startTime": start_dt,
                "publishTime": pub_dt,
                "settlementDate": r.get("settlementDate"),
                "settlementPeriod": r.get("settlementPeriod"),
                "actual_mw": gen_float,
                "dataset": "FUELHH"
            })
            
        wind_retained = len(wind_records)
        if not wind_records:
            df_empty = pd.DataFrame(columns=["startTime", "publishTime", "settlementDate", "settlementPeriod", "actual_mw"])
            return df_empty, {
                "fetched": total_fetched,
                "retained": 0,
                "invalid": invalid_count,
                "duplicates": 0
            }
            
        df = pd.DataFrame(wind_records)
        
        # Deduplication: sort by startTime asc, publishTime desc -> keep first (latest publish)
        initial_len = len(df)
        df.sort_values(by=["startTime", "publishTime"], ascending=[True, False], inplace=True)
        df.drop_duplicates(subset=["startTime"], keep="first", inplace=True)
        duplicates_removed = initial_len - len(df)
        
        self.invalid_records_count += invalid_count
        self.duplicate_records_count += duplicates_removed
        
        stats = {
            "fetched": total_fetched,
            "retained": wind_retained,
            "invalid": invalid_count,
            "duplicates": duplicates_removed
        }
        return df, stats

    def clean_windfor_forecasts(
        self,
        raw_records: List[Dict[str, Any]]
    ) -> Tuple[pd.DataFrame, Dict[str, int]]:
        """
        Cleans WINDFOR records:
        1. Normalizes startTime and publishTime to UTC
        2. Validates generation (>= 0.0)
        3. Deduplicates identical (startTime, publishTime) observations
        """
        total_fetched = len(raw_records)
        cleaned_records = []
        invalid_count = 0
        
        for r in raw_records:
            gen_val = r.get("generation")
            try:
                gen_float = float(gen_val)
                if gen_float < 0.0:
                    invalid_count += 1
                    continue
            except (ValueError, TypeError):
                invalid_count += 1
                continue
                
            start_dt = parse_utc_timestamp(r.get("startTime"))
            pub_dt = parse_utc_timestamp(r.get("publishTime"))
            
            if not start_dt or not pub_dt:
                invalid_count += 1
                continue
                
            cleaned_records.append({
                "startTime": start_dt,
                "publishTime": pub_dt,
                "forecast_mw": gen_float,
                "dataset": "WINDFOR"
            })
            
        if not cleaned_records:
            df_empty = pd.DataFrame(columns=["startTime", "publishTime", "forecast_mw"])
            return df_empty, {
                "fetched": total_fetched,
                "retained": 0,
                "invalid": invalid_count,
                "duplicates": 0
            }
            
        df = pd.DataFrame(cleaned_records)
        initial_len = len(df)
        df.drop_duplicates(subset=["startTime", "publishTime"], keep="last", inplace=True)
        duplicates_removed = initial_len - len(df)
        
        self.invalid_records_count += invalid_count
        self.duplicate_records_count += duplicates_removed
        
        stats = {
            "fetched": total_fetched,
            "retained": len(df),
            "invalid": invalid_count,
            "duplicates": duplicates_removed
        }
        return df, stats
