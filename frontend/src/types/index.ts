export interface AccuracyMetrics {
  sample_size: number;
  mae_mw: number;
  rmse_mw: number;
  mean_signed_error_mw: number;
  max_abs_error_mw: number;
  min_signed_error_mw: number;
  max_signed_error_mw: number;
  error_std_mw: number;
  wape_percentage: number | null;
  mape_percentage: number | null;
  mape_note: string;
  unit: string;
}

export interface TimeSeriesPoint {
  startTime: string;
  forecast_mw: number | null;
  actual_mw: number | null;
  signed_error_mw: number | null;
  abs_error_mw: number | null;
  status: string;
}

export interface OverviewResponse {
  title: string;
  analysis_window: string;
  decision_cutoff_rule: string;
  metrics: AccuracyMetrics;
  coverage_percentage: number;
  total_delivery_periods: number;
  matched_delivery_periods: number;
  missing_forecast_periods: number;
  missing_actual_periods: number;
  last_updated_utc: string;
  data_source: string;
  time_series_sample: TimeSeriesPoint[];
}

export interface ForecastRecord {
  startTime: string;
  settlementDate?: string;
  settlementPeriod?: number;
  decisionCutoff: string;
  selectedPublishTime: string;
  leadTimeHours?: number;
  forecast_mw: number | null;
  actual_mw: number | null;
  signed_error_mw: number | null;
  abs_error_mw: number | null;
  status: string;
}

export interface ErrorBucket {
  range_label: string;
  min_val: number;
  max_val: number;
  count: number;
  percentage: number;
}

export interface ExtremeErrorPeriod {
  startTime: string;
  forecast_mw: number;
  actual_mw: number;
  signed_error_mw: number;
  abs_error_mw: number;
  error_type: "OVER_FORECAST" | "UNDER_FORECAST";
}

export interface AccuracyResponse {
  metrics: AccuracyMetrics;
  error_distribution: ErrorBucket[];
  largest_error_periods: ExtremeErrorPeriod[];
}

export interface ForecastVintage {
  publishTime: string;
  forecast_mw: number;
  is_eligible: boolean;
  decision_cutoff: string;
  lead_time_hours: number;
}

export interface ForecastHistoryResponse {
  delivery_start_time: string;
  vintages_count: number;
  vintages: ForecastVintage[];
}

export interface DataQualitySummary {
  actual_records_fetched: number;
  wind_actual_records_retained: number;
  forecast_records_fetched: number;
  invalid_generation_records: number;
  duplicate_records_resolved: number;
  missing_actual_periods: number;
  missing_forecast_periods: number;
  matched_periods_count: number;
  total_expected_periods: number;
  data_coverage_percentage: number;
  last_updated_utc: string;
  data_source: string;
  notes: string[];
}

export interface ObservationsResponse {
  page: number;
  page_size: number;
  total_records: number;
  total_pages: number;
  records: ForecastRecord[];
}
