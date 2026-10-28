import {
  OverviewResponse,
  AccuracyResponse,
  ForecastRecord,
  ForecastHistoryResponse,
  DataQualitySummary,
  ObservationsResponse
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request<T>(endpoint: string, params: Record<string, any> = {}): Promise<T> {
  const url = new URL(`${API_BASE}${endpoint}`);
  Object.keys(params).forEach((key) => {
    if (params[key] !== undefined && params[key] !== null && params[key] !== "") {
      url.searchParams.append(key, String(params[key]));
    }
  });

  const response = await fetch(url.toString(), {
    headers: {
      "Accept": "application/json",
    },
  });

  if (!response.ok) {
    const errorBody = await response.text();
    let detail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const parsed = JSON.parse(errorBody);
      if (parsed.detail) detail = parsed.detail;
    } catch (_) {
      if (errorBody) detail = errorBody;
    }
    throw new Error(detail);
  }

  return response.json();
}

export const api = {
  getOverview: (cutoffHour = 11, forceRefresh = false): Promise<OverviewResponse> =>
    request<OverviewResponse>("/api/overview", { cutoff_hour: cutoffHour, force_refresh: forceRefresh }),

  getForecasts: (startDate?: string, endDate?: string, cutoffHour = 11): Promise<{ data: ForecastRecord[]; count: number }> =>
    request("/api/forecasts", { start_date: startDate, end_date: endDate, cutoff_hour: cutoffHour }),

  getAccuracy: (startDate?: string, endDate?: string, cutoffHour = 11): Promise<AccuracyResponse> =>
    request<AccuracyResponse>("/api/accuracy", { start_date: startDate, end_date: endDate, cutoff_hour: cutoffHour }),

  getForecastHistory: (startTime: string): Promise<ForecastHistoryResponse> =>
    request<ForecastHistoryResponse>("/api/forecast-history", { start_time: startTime }),

  getDataQuality: (): Promise<DataQualitySummary> =>
    request<DataQualitySummary>("/api/data-quality"),

  getObservations: (
    page = 1,
    pageSize = 50,
    sortBy = "startTime",
    sortOrder = "asc",
    status?: string,
    minError?: number,
    maxError?: number,
    cutoffHour = 11
  ): Promise<ObservationsResponse> =>
    request<ObservationsResponse>("/api/observations", {
      page,
      page_size: pageSize,
      sort_by: sortBy,
      sort_order: sortOrder,
      status,
      min_error: minError,
      max_error: maxError,
      cutoff_hour: cutoffHour,
    }),

  getCsvExportUrl: (cutoffHour = 11): string =>
    `${API_BASE}/api/observations/export/csv?cutoff_hour=${cutoffHour}`,
};
