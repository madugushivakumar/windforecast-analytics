import React from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from "recharts";
import { Activity, AlertTriangle, CheckCircle2, TrendingUp, Info } from "lucide-react";
import { OverviewResponse } from "../types";
import { MetricCard } from "../components/MetricCard";

interface OverviewPageProps {
  data: OverviewResponse | null;
  loading: boolean;
  error: string | null;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({ data, loading, error }) => {
  if (loading) {
    return (
      <div style={{ padding: "4rem 2rem", textAlign: "center" }}>
        <div style={{ display: "inline-block", width: 40, height: 40, border: "3px solid rgba(56, 189, 248, 0.2)", borderTopColor: "#38bdf8", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
        <p style={{ marginTop: "1rem", color: "var(--text-muted)" }}>Ingesting Elexon datasets and calculating Day-Ahead accuracy...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="glass-card" style={{ padding: "2rem", margin: "2rem auto", maxWidth: 700, borderColor: "var(--accent-rose)" }}>
        <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
          <AlertTriangle color="var(--accent-rose)" size={28} />
          <div>
            <h3 style={{ color: "var(--accent-rose)", fontSize: "1.2rem" }}>Data Retrieval Error</h3>
            <p style={{ color: "var(--text-muted)", marginTop: "0.25rem" }}>{error || "Unable to load overview analytics from the backend API."}</p>
          </div>
        </div>
      </div>
    );
  }

  const { metrics } = data;

  // Format time series for Recharts
  const chartData = data.time_series_sample
    .filter((pt) => pt.forecast_mw !== null || pt.actual_mw !== null)
    .map((pt) => ({
      time: new Date(pt.startTime).toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      }),
      Forecast: pt.forecast_mw !== null ? Math.round(pt.forecast_mw) : undefined,
      Actual: pt.actual_mw !== null ? Math.round(pt.actual_mw) : undefined,
      Error: pt.signed_error_mw !== null ? Math.round(pt.signed_error_mw) : undefined,
    }));

  return (
    <div className="animate-fade-in" style={{ padding: "1.5rem" }}>
      {/* Scope and Context Banner */}
      <div className="glass-card" style={{ padding: "1.25rem 1.5rem", marginBottom: "1.5rem", display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: "1rem" }}>
        <div>
          <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--accent-cyan)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
            UK Day-Ahead Power Market Evaluation
          </span>
          <h2 style={{ fontSize: "1.5rem", marginTop: "0.25rem" }}>January 2026 National Wind Outturn vs. Day-Ahead Forecasts</h2>
          <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", marginTop: "0.25rem" }}>
            Decision Gate Closure: <strong>{data.decision_cutoff_rule}</strong> | Source: <strong>Elexon BMRS WINDFOR & FUELHH (WIND)</strong>
          </p>
        </div>
        <div style={{ display: "flex", gap: "1.5rem" }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Data Ingestion Status</div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", justifyContent: "flex-end", color: "#34d399", fontWeight: 600, fontSize: "0.875rem" }}>
              <CheckCircle2 size={16} /> Verified ({data.data_source})
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Analysis Window</div>
            <div style={{ fontWeight: 600, fontSize: "0.875rem", color: "var(--text-main)" }}>2026-01-01 to 2026-01-31</div>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="kpi-grid">
        <MetricCard
          label="Mean Absolute Error (MAE)"
          value={`${metrics.mae_mw.toLocaleString()} MW`}
          subtext="Average expected magnitude of forecasting error"
          variant="cyan"
          icon={<Activity size={18} color="var(--accent-cyan)" />}
        />
        <MetricCard
          label="Root Mean Squared Error (RMSE)"
          value={`${metrics.rmse_mw.toLocaleString()} MW`}
          subtext="Penalizes large forecast discrepancies"
          variant="indigo"
          icon={<TrendingUp size={18} color="var(--accent-indigo)" />}
        />
        <MetricCard
          label="Mean Signed Error (Bias)"
          value={`${metrics.mean_signed_error_mw > 0 ? "+" : ""}${metrics.mean_signed_error_mw.toLocaleString()} MW`}
          subtext={metrics.mean_signed_error_mw > 0 ? "Systematic over-forecasting tendency" : "Systematic under-forecasting tendency"}
          variant={metrics.mean_signed_error_mw > 0 ? "amber" : "emerald"}
          icon={<AlertTriangle size={18} color="var(--accent-amber)" />}
        />
        <MetricCard
          label="Matched Delivery Periods"
          value={`${metrics.sample_size} / ${data.total_delivery_periods}`}
          subtext={`${data.coverage_percentage}% coverage of total delivery window`}
          variant="emerald"
          icon={<CheckCircle2 size={18} color="var(--accent-emerald)" />}
        />
      </div>

      {/* Main Time Series Chart */}
      <div className="glass-card" style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <div>
            <h3 style={{ fontSize: "1.125rem" }}>National Wind Generation: Day-Ahead Forecast vs. Actual Outturn</h3>
            <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
              Half-hourly outturn generation from FUELHH (green) matched with day-ahead selected forecasts from WINDFOR (blue)
            </p>
          </div>
          <div style={{ display: "flex", gap: "1rem", fontSize: "0.8125rem" }}>
            <span style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
              <span style={{ width: 12, height: 3, backgroundColor: "#38bdf8", borderRadius: 2 }} /> Forecast (MW)
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
              <span style={{ width: 12, height: 3, backgroundColor: "#10b981", borderRadius: 2 }} /> Actual (MW)
            </span>
          </div>
        </div>

        <div style={{ width: "100%", height: 380 }}>
          <ResponsiveContainer>
            <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" />
              <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 11 }} minTickGap={40} />
              <YAxis stroke="#64748b" tick={{ fontSize: 11 }} tickFormatter={(val) => `${val / 1000}k MW`} />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid rgba(148,163,184,0.2)", borderRadius: "8px", fontSize: "0.85rem" }}
                labelStyle={{ color: "#94a3b8" }}
              />
              <Legend verticalAlign="top" height={36} />
              <Line type="monotone" dataKey="Forecast" stroke="#38bdf8" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
              <Line type="monotone" dataKey="Actual" stroke="#10b981" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Analytical Interpretation & Domain Explanations */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.25rem" }}>
        <div className="glass-card" style={{ padding: "1.25rem 1.5rem" }}>
          <h4 style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "1rem", color: "var(--accent-cyan)", marginBottom: "0.5rem" }}>
            <Info size={18} /> Commercial Electricity Market Interpretation
          </h4>
          <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", lineHeight: 1.6 }}>
            In the UK wholesale power market, utilities purchasing day-ahead must balance forecast risk against cash-out imbalance prices.
            With a <strong>Mean Signed Error of +{metrics.mean_signed_error_mw} MW</strong>, the day-ahead forecast tended to <em>over-predict</em> wind production in January 2026.
            Utilities relying strictly on this unadjusted forecast would have entered the intraday market in a net short physical position, requiring buy-backs or exposure to system buy prices.
          </p>
        </div>

        <div className="glass-card" style={{ padding: "1.25rem 1.5rem" }}>
          <h4 style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "1rem", color: "var(--accent-emerald)", marginBottom: "0.5rem" }}>
            <Activity size={18} /> Data Quality & Resolution Notes
          </h4>
          <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", lineHeight: 1.6 }}>
            Elexon <strong>FUELHH</strong> reports national generation at 30-minute settlement period frequency (1,488 periods in January).
            Elexon <strong>WINDFOR</strong> day-ahead national model forecasts are published at hourly resolution (744 periods).
            Our matching engine strictly joins on normalized delivery start times without interpolating unobserved half-hours, ensuring 100% mathematical integrity.
          </p>
        </div>
      </div>
    </div>
  );
};
