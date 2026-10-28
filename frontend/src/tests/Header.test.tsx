import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Header } from "../components/Header";

describe("Header Component", () => {
  it("renders branding and navigation tabs", () => {
    const setActiveTab = vi.fn();
    const onRefresh = vi.fn();
    const setCutoffHour = vi.fn();

    render(
      <Header
        activeTab="overview"
        setActiveTab={setActiveTab}
        dataSource="LIVE_API"
        coverage={50}
        lastUpdated="2026-10-28T04:30:00Z"
        onRefresh={onRefresh}
        isRefreshing={false}
        cutoffHour={11}
        setCutoffHour={setCutoffHour}
      />
    );

    expect(screen.getByText("WindForecast Analytics")).toBeInTheDocument();
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Forecast Comparison")).toBeInTheDocument();
    expect(screen.getByText("Accuracy Metrics")).toBeInTheDocument();
    expect(screen.getByText("Data Explorer")).toBeInTheDocument();
    expect(screen.getByText("50% Coverage")).toBeInTheDocument();

    const comparisonTab = screen.getByRole("button", { name: /Forecast Comparison/i });
    fireEvent.click(comparisonTab);
    expect(setActiveTab).toHaveBeenCalledWith("comparison");
  });
});
