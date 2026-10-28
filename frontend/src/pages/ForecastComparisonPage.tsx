import React, { useState, useEffect } from "react";
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
import { Calendar, History, ShieldCheck, Clock } from "lucide-react";
import { api } from "../services/api";
import { ForecastRecord, ForecastVintage } from "../types";

interface ForecastComparisonPageProps {
  cutoffHour: number;
}

export const ForecastComparisonPage: React.FC<ForecastComparisonPageProps> = ({ cutoffHour }) => {
  const [records, setRecords] = useState<ForecastRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [startDate, setStartDate] = useState<string>("2026-01-01");
  const [endDate, setEndDate] = useState<string>("2026-01-07");
  const [selectedPeriod, setSelectedPeriod] = useState<string | null>(null);
  const [vintages, setVintages] = useState<ForecastVintage[]>([]);
  const [vintagesLoading, setVintagesLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadForecasts();
  }, [startDate, endDate, cutoffHour]);

  const loadForecasts = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getForecasts(startDate, endDate, cutoffHour);
      setRecords(res.data);
      if (res.data.length > 0 && !selectedPeriod) {
        setSelectedPeriod(res.data[0].startTime);
        loadVintages(res.data[0].startTime);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load forecast data.");
    } finally {
      setLoading(false);
    }
  };

  const loadVintages = async (startTime: string) => {
    try {
      setVintagesLoading(true);
      setSelectedPeriod(startTime);
      const res = await api.getForecastHistory(startTime);
      setVintages(res.vintages);
    } catch (err) {
      console.error("Failed to load vintages:", err);
    } finally {
      setVintagesLoading(false);
    }
  };

  const chartData = records.map((r) => ({
    time: new Date(r.startTime).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    }),
    rawStartTime: r.startTime,
    Forecast: r.forecast_mw !== null ? Math.round(r.forecast_mw) : undefined,
    Actual: r.actual_mw !== null ? Math.round(r.actual_mw) : undefined,
    LeadTime: r.leadTimeHours,
  }));

  return (
    <div className="animate-fade-in" style={{ padding: "1.5rem" }}>
      {/* Filter and Range Selection Bar */}
      <div className="filter-bar">
        <div className="filter-group">
          <Calendar size={18} color="var(--accent-cyan)" />
          <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>Delivery Date Window:</span>
          <input
            id="input-start-date"
            type="date"
            value={startDate}
            min="2026-01-01"
            max="2026-01-31"
            onChange={(e) => setStartDate(e.target.value)}
            className="text-input"
          />
          <span style={{ color: "var(--text-dim)" }}>to</span>
          <input
            id="input-end-date"
            type="date"
            value={endDate}
            min="2026-01-01"
            max="2026-01-31"
            onChange={(e) => setEndDate(e.target.value)}
            className="text-input"
          />
        </div>

        {/* Preset quick buttons */}
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            className="btn btn-secondary"
            style={{ fontSize: "0.75rem", padding: "0.3rem 0.6rem" }}
            onClick={() => { setStartDate("2026-01-01"); setEndDate("2026-01-07"); }}
          >
            Week 1
          </button>
          <button
            className="btn btn-secondary"
            style={{ fontSize: "0.75rem", padding: "0.3rem 0.6rem" }}
            onClick={() => { setStartDate("2026-01-08"); setEndDate("2026-01-14"); }}
          >
            Week 2
          </button>
          <button
            className="btn btn-secondary"
            style={{ fontSize: "0.75rem", padding: "0.3rem 0.6rem" }}
            onClick={() => { setStartDate("2026-01-15"); setEndDate("2026-01-21"); }}
          >
            Week 3
          </button>
          <button
            className="btn btn-secondary"
            style={{ fontSize: "0.75rem", padding: "0.3rem 0.6rem" }}
            onClick={() => { setStartDate("2026-01-22"); setEndDate("2026-01-31"); }}
          >
            Week 4 & End
          </button>
          <button
            className="btn btn-secondary"
            style={{ fontSize: "0.75rem", padding: "0.3rem 0.6rem" }}
            onClick={() => { setStartDate("2026-01-01"); setEndDate("2026-01-31"); }}
          >
            Full Month
          </button>
        </div>
      </div>

      {error && (
        <div className="glass-card" style={{ padding: "1rem", marginBottom: "1rem", borderColor: "var(--accent-rose)", color: "var(--accent-rose)" }}>
          {error}
        </div>
      )}

      {/* Forecast Chart */}
      <div className="glass-card" style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <div>
            <h3 style={{ fontSize: "1.125rem" }}>Filtered Delivery Horizon ({records.length} observations) {loading && <span style={{ fontSize: "0.8rem", color: "var(--accent-cyan)" }}>(Loading...)</span>}</h3>
            <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
              Click any point on the chart or select below to inspect all forecast publication vintages
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.75rem", color: "var(--text-dim)" }}>
            <ShieldCheck size={14} color="#34d399" />
            <span>Cutoff Enforced: D-1 at {cutoffHour}:00 UTC</span>
          </div>
        </div>

        <div style={{ width: "100%", height: 350 }}>
          <ResponsiveContainer>
            <LineChart
              data={chartData}
              onClick={(e) => {
                if (e && e.activePayload && e.activePayload.length > 0) {
                  const pt = e.activePayload[0].payload;
                  loadVintages(pt.rawStartTime);
                }
              }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" />
              <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 11 }} minTickGap={30} />
              <YAxis stroke="#64748b" tick={{ fontSize: 11 }} tickFormatter={(val) => `${val / 1000}k MW`} />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid rgba(148,163,184,0.2)", borderRadius: "8px" }}
              />
              <Legend verticalAlign="top" height={36} />
              <Line type="monotone" dataKey="Forecast" stroke="#38bdf8" strokeWidth={2} dot={{ r: 2 }} activeDot={{ r: 6 }} />
              <Line type="monotone" dataKey="Actual" stroke="#10b981" strokeWidth={2} dot={{ r: 2 }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Forecast Vintage Inspector Section */}
      <div className="glass-card" style={{ padding: "1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <div>
            <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "1.125rem" }}>
              <History size={18} color="var(--accent-indigo)" />
              Forecast Publication Vintage History Inspector
            </h3>
            <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
              Selected Delivery Period: <strong>{selectedPeriod ? new Date(selectedPeriod).toUTCString() : "Select a period"}</strong>
            </p>
          </div>
          {selectedPeriod && (
            <span className="badge badge-info">
              {vintages.length} Forecast Runs Available
            </span>
          )}
        </div>

        {vintagesLoading ? (
          <p style={{ padding: "1rem", color: "var(--text-dim)" }}>Loading historical vintages...</p>
        ) : vintages.length === 0 ? (
          <p style={{ padding: "1rem", color: "var(--text-dim)" }}>No historical forecast runs found for the selected period.</p>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Publication Timestamp (publishTime)</th>
                  <th>Forecast Generation (MW)</th>
                  <th>Lead Time Before Delivery</th>
                  <th>Decision Gate Status</th>
                  <th>Selection Outcome</th>
                </tr>
              </thead>
              <tbody>
                {vintages.map((v, i) => {
                  const isLatestEligible = v.is_eligible && (i === vintages.filter(x => x.is_eligible).length - 1);
                  return (
                    <tr key={i} style={{ background: isLatestEligible ? "rgba(56, 189, 248, 0.08)" : undefined }}>
                      <td style={{ fontWeight: 600 }}>{new Date(v.publishTime).toUTCString()}</td>
                      <td style={{ color: "var(--accent-cyan)", fontWeight: 700 }}>{v.forecast_mw.toLocaleString()} MW</td>
                      <td>
                        <span style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                          <Clock size={14} color="var(--text-dim)" /> {v.lead_time_hours} hours
                        </span>
                      </td>
                      <td>
                        {v.is_eligible ? (
                          <span className="badge badge-healthy">Pre-Cutoff (Eligible)</span>
                        ) : (
                          <span className="badge badge-warning">Post-Cutoff (Future Info)</span>
                        )}
                      </td>
                      <td>
                        {isLatestEligible ? (
                          <strong style={{ color: "var(--accent-cyan)" }}>★ Selected for Day-Ahead</strong>
                        ) : v.is_eligible ? (
                          <span style={{ color: "var(--text-dim)" }}>Superseded by later run</span>
                        ) : (
                          <span style={{ color: "var(--accent-rose)" }}>Excluded (Past Cutoff)</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
