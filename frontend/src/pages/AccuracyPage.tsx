import React, { useState, useEffect } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { Compass, AlertTriangle, Target, Info, ShieldAlert } from "lucide-react";
import { api } from "../services/api";
import { AccuracyResponse } from "../types";
import { MetricCard } from "../components/MetricCard";

interface AccuracyPageProps {
  cutoffHour: number;
}

export const AccuracyPage: React.FC<AccuracyPageProps> = ({ cutoffHour }) => {
  const [data, setData] = useState<AccuracyResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAccuracy();
  }, [cutoffHour]);

  const loadAccuracy = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getAccuracy(undefined, undefined, cutoffHour);
      setData(res);
    } catch (err: any) {
      setError(err.message || "Failed to load accuracy analytics.");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: "4rem 2rem", textAlign: "center" }}>
        <div style={{ display: "inline-block", width: 40, height: 40, border: "3px solid rgba(56, 189, 248, 0.2)", borderTopColor: "#38bdf8", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
        <p style={{ marginTop: "1rem", color: "var(--text-muted)" }}>Computing quantitative accuracy metrics and distributions...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="glass-card" style={{ padding: "2rem", margin: "2rem auto", maxWidth: 700, borderColor: "var(--accent-rose)" }}>
        <AlertTriangle color="var(--accent-rose)" size={28} />
        <p style={{ color: "var(--text-muted)", marginTop: "0.5rem" }}>{error || "Unable to load accuracy metrics."}</p>
      </div>
    );
  }

  const { metrics, error_distribution, largest_error_periods } = data;

  return (
    <div className="animate-fade-in" style={{ padding: "1.5rem" }}>
      {/* Metric Cards Row */}
      <div className="kpi-grid">
        <MetricCard
          label="Mean Absolute Error (MAE)"
          value={`${metrics.mae_mw.toLocaleString()} MW`}
          subtext="Typical expected forecasting error magnitude"
          variant="cyan"
          icon={<Compass size={18} color="var(--accent-cyan)" />}
        />
        <MetricCard
          label="Root Mean Squared Error (RMSE)"
          value={`${metrics.rmse_mw.toLocaleString()} MW`}
          subtext="Heavily penalizes volatile or large misses"
          variant="indigo"
          icon={<Target size={18} color="var(--accent-indigo)" />}
        />
        <MetricCard
          label="Mean Signed Error / Bias"
          value={`${metrics.mean_signed_error_mw > 0 ? "+" : ""}${metrics.mean_signed_error_mw.toLocaleString()} MW`}
          subtext={metrics.mean_signed_error_mw > 0 ? "Systematic Over-forecast (F > A)" : "Systematic Under-forecast (F < A)"}
          variant={metrics.mean_signed_error_mw > 0 ? "amber" : "emerald"}
          icon={<AlertTriangle size={18} color="var(--accent-amber)" />}
        />
        <MetricCard
          label="Maximum Observed Error"
          value={`${metrics.max_abs_error_mw.toLocaleString()} MW`}
          subtext="Single largest dispatch discrepancy"
          variant="amber"
          icon={<ShieldAlert size={18} color="var(--accent-rose)" />}
        />
      </div>

      {/* Grid of Distribution and Percentage Handling */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(450px, 1fr))", gap: "1.5rem", marginBottom: "1.5rem" }}>
        {/* Error Distribution Histogram */}
        <div className="glass-card" style={{ padding: "1.5rem" }}>
          <h3 style={{ fontSize: "1.125rem", marginBottom: "0.25rem" }}>Forecast Signed Error Distribution (Histogram)</h3>
          <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginBottom: "1rem" }}>
            Frequency of signed error buckets ($F_t - A_t$ in MW). Positive = Over-forecast; Negative = Under-forecast.
          </p>

          <div style={{ width: "100%", height: 300 }}>
            <ResponsiveContainer>
              <BarChart data={error_distribution} margin={{ top: 10, right: 10, left: -10, bottom: 25 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" />
                <XAxis dataKey="range_label" stroke="#64748b" tick={{ fontSize: 10 }} angle={-25} textAnchor="end" />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "#0f172a", border: "1px solid rgba(148,163,184,0.2)", borderRadius: "8px" }}
                  formatter={(val: any) => [`${val} periods`, "Count"]}
                />
                <Bar dataKey="count" fill="#38bdf8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Statistical Rigor & MAPE Policy Explanation */}
        <div className="glass-card" style={{ padding: "1.5rem", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div>
            <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "1.125rem", color: "var(--accent-cyan)", marginBottom: "0.75rem" }}>
              <Info size={18} /> Percentage Metrics & Low-Generation Handling
            </h3>
            <p style={{ fontSize: "0.875rem", color: "var(--text-muted)", lineHeight: 1.6, marginBottom: "1rem" }}>
              Commercial electricity trading requires absolute capacity metrics (<strong>MW</strong>) because power imbalance settlement is penalized in MWh cash-out prices.
            </p>
            <div style={{ background: "rgba(15, 23, 42, 0.9)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "1rem", marginBottom: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                <span style={{ fontSize: "0.85rem", color: "var(--text-dim)" }}>Weighted Absolute Percentage Error (WAPE):</span>
                <span style={{ fontWeight: 700, color: "var(--text-main)" }}>{metrics.wape_percentage !== null ? `${metrics.wape_percentage}%` : "N/A"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                <span style={{ fontSize: "0.85rem", color: "var(--text-dim)" }}>Conditional MAPE (Actuals &ge; 100 MW):</span>
                <span style={{ fontWeight: 700, color: "var(--text-main)" }}>{metrics.mape_percentage !== null ? `${metrics.mape_percentage}%` : "N/A"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: "0.85rem", color: "var(--text-dim)" }}>Error Standard Deviation (&sigma;):</span>
                <span style={{ fontWeight: 700, color: "var(--text-main)" }}>{metrics.error_std_mw.toLocaleString()} MW</span>
              </div>
            </div>
            <p style={{ fontSize: "0.8rem", color: "var(--text-dim)", lineHeight: 1.5 }}>
              <strong>Zero-Actual Policy:</strong> {metrics.mape_note}
            </p>
          </div>
          <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "0.75rem", marginTop: "1rem", fontSize: "0.75rem", color: "var(--text-dim)" }}>
            Mathematical formulas: MAE = (1/N) * &Sigma;|e_t|, RMSE = &radic;((1/N) * &Sigma;e_t&sup2;), Bias = (1/N) * &Sigma;e_t.
          </div>
        </div>
      </div>

      {/* Extreme Error Discrepancy Periods Table */}
      <div className="glass-card" style={{ padding: "1.5rem" }}>
        <h3 style={{ fontSize: "1.125rem", marginBottom: "0.25rem" }}>Top 10 Largest Absolute Forecast Error Discrepancies</h3>
        <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginBottom: "1rem" }}>
          Periods in January 2026 where the Day-Ahead model deviated most sharply from delivered wind outturn
        </p>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Delivery Start Time (UTC)</th>
                <th>Day-Ahead Forecast (MW)</th>
                <th>Actual Delivered (MW)</th>
                <th>Signed Error (F - A)</th>
                <th>Absolute Error</th>
                <th>Discrepancy Category</th>
              </tr>
            </thead>
            <tbody>
              {largest_error_periods.map((item, idx) => (
                <tr key={idx}>
                  <td style={{ fontWeight: 600 }}>{new Date(item.startTime).toUTCString()}</td>
                  <td style={{ color: "var(--accent-cyan)", fontWeight: 600 }}>{item.forecast_mw.toLocaleString()} MW</td>
                  <td style={{ color: "var(--accent-emerald)", fontWeight: 600 }}>{item.actual_mw.toLocaleString()} MW</td>
                  <td style={{ fontWeight: 700, color: item.signed_error_mw > 0 ? "var(--accent-amber)" : "var(--accent-rose)" }}>
                    {item.signed_error_mw > 0 ? `+${item.signed_error_mw.toLocaleString()}` : item.signed_error_mw.toLocaleString()} MW
                  </td>
                  <td style={{ fontWeight: 700 }}>{item.abs_error_mw.toLocaleString()} MW</td>
                  <td>
                    {item.error_type === "OVER_FORECAST" ? (
                      <span className="badge badge-warning">Over-Forecast (Shortage)</span>
                    ) : (
                      <span className="badge badge-healthy">Under-Forecast (Excess)</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
