import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MetricCard } from "../components/MetricCard";

describe("MetricCard Component", () => {
  it("renders label, value, and subtext correctly", () => {
    render(
      <MetricCard
        label="Mean Absolute Error (MAE)"
        value="2,107 MW"
        subtext="Average expected magnitude of forecasting error"
        variant="cyan"
      />
    );

    expect(screen.getByText("Mean Absolute Error (MAE)")).toBeInTheDocument();
    expect(screen.getByText("2,107 MW")).toBeInTheDocument();
    expect(screen.getByText("Average expected magnitude of forecasting error")).toBeInTheDocument();
  });
});
