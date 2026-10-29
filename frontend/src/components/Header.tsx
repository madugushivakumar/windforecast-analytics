import React from "react";
import { Wind, BarChart3, GitCompare, Compass, Database, RefreshCw } from "lucide-react";

interface HeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  dataSource: string;
  coverage: number;
  lastUpdated: string;
  onRefresh: () => void;
  isRefreshing: boolean;
  cutoffHour: number;
  setCutoffHour: (h: number) => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  dataSource,
  coverage,
  lastUpdated,
  onRefresh,
  isRefreshing,
  cutoffHour,
  setCutoffHour,
}) => {
  return (
    <header className="nav-header">
      <div className="nav-container">
        <div className="nav-logo-group">
          <div className="nav-logo-icon">
            <Wind size={22} />
          </div>
          <div>
            <h1 className="nav-title">WindForecast Analytics</h1>
            <p className="nav-subtitle">GB National Wind Generation Day-Ahead Accuracy | Elexon BMRS | Jan 2026</p>
          </div>
        </div>

        <nav className="nav-tabs" aria-label="Main Navigation">
          <button
            id="tab-overview"
            className={`nav-tab-btn ${activeTab === "overview" ? "active" : ""}`}
            onClick={() => setActiveTab("overview")}
          >
            <BarChart3 size={16} /> Overview
          </button>
          <button
            id="tab-comparison"
            className={`nav-tab-btn ${activeTab === "comparison" ? "active" : ""}`}
            onClick={() => setActiveTab("comparison")}
          >
            <GitCompare size={16} /> Forecast Comparison
          </button>
          <button
            id="tab-accuracy"
            className={`nav-tab-btn ${activeTab === "accuracy" ? "active" : ""}`}
            onClick={() => setActiveTab("accuracy")}
          >
            <Compass size={16} /> Accuracy Metrics
          </button>
          <button
            id="tab-explorer"
            className={`nav-tab-btn ${activeTab === "explorer" ? "active" : ""}`}
            onClick={() => setActiveTab("explorer")}
          >
            <Database size={16} /> Data Explorer
          </button>
        </nav>

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <label htmlFor="cutoff-select" style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              Decision Cutoff:
            </label>
            <select
              id="cutoff-select"
              value={cutoffHour}
              onChange={(e) => setCutoffHour(Number(e.target.value))}
              className="select-input"
              style={{ fontSize: "0.75rem", padding: "0.25rem 0.5rem" }}
            >
              <option value={11}>11:00 UTC (Utility Operational DA)</option>
              <option value={12}>12:00 UTC (Midday Cutoff)</option>
              <option value={9}>09:00 UTC (Early DA Cutoff)</option>
              <option value={14}>14:00 UTC (Afternoon Cutoff)</option>
            </select>
          </div>

          <span className={`badge ${coverage >= 80 ? "badge-healthy" : "badge-info"}`}>
            {coverage}% Coverage
          </span>

          <button
            id="btn-refresh-pipeline"
            onClick={onRefresh}
            disabled={isRefreshing}
            className="btn btn-secondary"
            style={{ padding: "0.35rem 0.75rem", fontSize: "0.75rem" }}
            title={`Source: ${dataSource} | Updated: ${lastUpdated}`}
          >
            <RefreshCw size={14} className={isRefreshing ? "animate-spin" : ""} />
            {isRefreshing ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>
    </header>
  );
};
