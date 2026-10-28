from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class RawFuelRecord(BaseModel):
    dataset: str = "FUELHH"
    publishTime: str
    startTime: str
    settlementDate: Optional[str] = None
    settlementPeriod: Optional[int] = None
    fuelType: str
    generation: float


class RawWindForecastRecord(BaseModel):
    dataset: str = "WINDFOR"
    publishTime: str
    startTime: str
    generation: float


class CleanFuelObservation(BaseModel):
    start_time: datetime
    publish_time: datetime
    settlement_date: Optional[str] = None
    settlement_period: Optional[int] = None
    actual_mw: float


class CleanForecastObservation(BaseModel):
    start_time: datetime
    publish_time: datetime
    forecast_mw: float


class MatchedObservation(BaseModel):
    start_time: str = Field(..., description="Start of delivery period in ISO 8601 UTC")
    settlement_date: Optional[str] = Field(None, description="Delivery date (YYYY-MM-DD)")
    settlement_period: Optional[int] = Field(None, description="Settlement period number (1-48)")
    decision_date: str = Field(..., description="Date purchasing decision was made (YYYY-MM-DD)")
    decision_cutoff: str = Field(..., description="Day-ahead auction cutoff timestamp (ISO 8601 UTC)")
    selected_publish_time: Optional[str] = Field(None, description="Timestamp of the selected forecast run")
    forecast_mw: Optional[float] = Field(None, description="Day-ahead forecast wind generation in MW")
    actual_mw: Optional[float] = Field(None, description="Actual wind outturn generation in MW")
    signed_error_mw: Optional[float] = Field(None, description="Signed error F - A in MW")
    abs_error_mw: Optional[float] = Field(None, description="Absolute error |F - A| in MW")
    lead_time_hours: Optional[float] = Field(None, description="Forecast publication lead time before delivery (hours)")
    status: str = Field(..., description="MATCHED, MISSING_FORECAST, MISSING_ACTUAL, or INVALID_VALUE")
