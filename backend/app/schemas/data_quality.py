from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class DataQualitySummary(BaseModel):
    actual_records_fetched: int = Field(..., description="Total FUELHH raw records fetched across all fuel types")
    wind_actual_records_retained: int = Field(..., description="FUELHH records retained with fuelType == 'WIND'")
    forecast_records_fetched: int = Field(..., description="Total WINDFOR raw forecast records fetched")
    invalid_generation_records: int = Field(..., description="Records with negative or unparseable generation values")
    duplicate_records_resolved: int = Field(..., description="Conflicting or duplicate records detected and resolved")
    missing_actual_periods: int = Field(..., description="Expected delivery periods with no actual outturn record")
    missing_forecast_periods: int = Field(..., description="Delivery periods with no eligible forecast prior to cutoff")
    matched_periods_count: int = Field(..., description="Delivery periods with both valid forecast and actual")
    total_expected_periods: int = Field(..., description="Total delivery half-hours expected in the evaluation window")
    data_coverage_percentage: float = Field(..., description="Percentage of delivery periods successfully matched")
    last_updated_utc: str = Field(..., description="Timestamp of the data ingestion / pipeline execution")
    data_source: str = Field(..., description="LIVE_API, DISK_CACHE, or LOCAL_FIXTURE")
    notes: List[str] = Field(default_factory=list, description="Audit observations or data anomalies")
