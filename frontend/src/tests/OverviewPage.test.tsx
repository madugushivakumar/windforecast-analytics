import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { OverviewPage } from "../pages/OverviewPage";
import { OverviewResponse } from "../types";

// Mock Recharts ResponsiveContainer to avoid JSDOM zero-width/height issues
vi.mock("recharts", async () => {
  const original = await vi.importActual<any>("recharts");
  return {
    ...original,
    ResponsiveContainer: ({ children }: any) => (
      <div style={{ width: 800, height: 400 }}>{children}</div>
    ),
  };
});

describe("OverviewPage Component", () => {
  it("renders loading state correctly", () => {
    render(<OverviewPage data={null} loading={true} error={null} />);
    expect(screen.getByText(/Ingesting Elexon datasets/i)).toBeInTheDocument();
  });

  it("renders error state correctly", () => {
    render(<OverviewPage data={null} loading={false} error="Upstream service unavailable" />);
    expect(screen.getByText("Data Retrieval Error")).toBeInTheDocument();
    expect(screen.getByText("Upstream service unavailable")).toBeInTheDocument();
  });

  it("renders metrics and KPIs with valid data", () => {
    const mockData: OverviewResponse = {
      title: "WindForecast Analytics",
      analysis_window: "January 2026 Day-Ahead Market",
      decision_cutoff_rule: "Day D-1 at 11:00 UTC",
      metrics: {
        sample_size: 744,
        mae_mw: 2107.18,
        rmse_mw: 2611.24,
        mean_signed_error_mw: 1839.92,
        max_abs_error_mw: 6500.0,
        min_signed_error_mw: -1200.0,
        max_signed_error_mw: 6500.0,
        error_std_mw: 1850.5,
        wape_percentage: 16.4,
        mape_percentage: 18.2,
        mape_note: "Computed safely",
        unit: "MW",
      },
      coverage_percentage: 50.0,
      total_delivery_periods: 1488,
      matched_delivery_periods: 744,
      missing_forecast_periods: 744,
      missing_actual_periods: 0,
      last_updated_utc: "2026-10-28T04:30:00Z",
      data_source: "LIVE_API",
      time_series_sample: [
        {
          startTime: "2026-01-01T12:00:00Z",
          forecast_mw: 15000,
          actual_mw: 13000,
          signed_error_mw: 2000,
          abs_error_mw: 2000,
          status: "MATCHED",
        },
      ],
    };

    render(<OverviewPage data={mockData} loading={false} error={null} />);

    expect(screen.getByText(/January 2026 National Wind Outturn/i)).toBeInTheDocument();
    expect(screen.getByText("2,107.18 MW")).toBeInTheDocument();
    expect(screen.getByText("2,611.24 MW")).toBeInTheDocument();
    expect(screen.getByText("+1,839.92 MW")).toBeInTheDocument();
    expect(screen.getByText("744 / 1488")).toBeInTheDocument();
  });
});
