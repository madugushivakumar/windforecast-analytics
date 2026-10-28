from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class ErrorDecile(BaseModel):
    percentile: str
    error_mw: float


class ErrorDistributionBucket(BaseModel):
    range_label: str
    min_val: float
    max_val: float
    count: int
    percentage: float


class AccuracyMetrics(BaseModel):
    sample_size: int = Field(..., description="Number of matched delivery periods evaluated (N)")
    mae_mw: float = Field(..., description="Mean Absolute Error in MW")
    rmse_mw: float = Field(..., description="Root Mean Squared Error in MW")
    mean_signed_error_mw: float = Field(..., description="Mean Signed Error (Bias) F - A in MW")
    max_abs_error_mw: float = Field(..., description="Maximum Absolute Error in MW")
    min_signed_error_mw: float = Field(..., description="Minimum (largest negative) Signed Error in MW")
    max_signed_error_mw: float = Field(..., description="Maximum (largest positive) Signed Error in MW")
    error_std_mw: float = Field(..., description="Standard deviation of signed forecast error in MW")
    wape_percentage: Optional[float] = Field(None, description="Weighted Absolute Percentage Error (Sum|e| / Sum A) %")
    mape_percentage: Optional[float] = Field(None, description="Conditional MAPE on periods where actual >= 100 MW")
    mape_note: str = Field(..., description="Explanation of zero-handling and percentage limitations")
    unit: str = "MW"


class OverviewResponse(BaseModel):
    title: str = "WindForecast Analytics"
    analysis_window: str = "January 2026 Day-Ahead Market"
    decision_cutoff_rule: str
    metrics: AccuracyMetrics
    coverage_percentage: float
    total_delivery_periods: int
    matched_delivery_periods: int
    missing_forecast_periods: int
    missing_actual_periods: int
    last_updated_utc: str
    data_source: str
    time_series_sample: List[dict]
