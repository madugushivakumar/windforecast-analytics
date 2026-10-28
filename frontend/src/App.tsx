import React, { useState, useEffect } from "react";
import { Header } from "./components/Header";
import { OverviewPage } from "./pages/OverviewPage";
import { ForecastComparisonPage } from "./pages/ForecastComparisonPage";
import { AccuracyPage } from "./pages/AccuracyPage";
import { DataExplorerPage } from "./pages/DataExplorerPage";
import { api } from "./services/api";
import { OverviewResponse } from "./types";

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [cutoffHour, setCutoffHour] = useState<number>(11);
  const [overviewData, setOverviewData] = useState<OverviewResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchOverview();
  }, [cutoffHour]);

  const fetchOverview = async (forceRefresh = false) => {
    try {
      if (forceRefresh) setRefreshing(true);
      else setLoading(true);
      setError(null);
      const res = await api.getOverview(cutoffHour, forceRefresh);
      setOverviewData(res);
    } catch (err: any) {
      setError(err.message || "Failed to connect to backend analytics API.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        dataSource={overviewData?.data_source || "Elexon BMRS API"}
        coverage={overviewData?.coverage_percentage || 0}
        lastUpdated={overviewData?.last_updated_utc || new Date().toISOString()}
        onRefresh={() => fetchOverview(true)}
        isRefreshing={refreshing}
        cutoffHour={cutoffHour}
        setCutoffHour={setCutoffHour}
      />

      <main style={{ flex: 1, maxWidth: 1400, margin: "0 auto", width: "100%" }}>
        {activeTab === "overview" && (
          <OverviewPage data={overviewData} loading={loading} error={error} />
        )}
        {activeTab === "comparison" && (
          <ForecastComparisonPage cutoffHour={cutoffHour} />
        )}
        {activeTab === "accuracy" && (
          <AccuracyPage cutoffHour={cutoffHour} />
        )}
        {activeTab === "explorer" && (
          <DataExplorerPage cutoffHour={cutoffHour} />
        )}
      </main>

      <footer style={{
        marginTop: "auto",
        borderTop: "1px solid var(--border-subtle)",
        background: "var(--bg-secondary)",
        padding: "1.5rem",
        fontSize: "0.8125rem",
        color: "var(--text-dim)",
        textAlign: "center"
      }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: "1rem" }}>
          <div>
            <strong>WindForecast Analytics</strong> &copy; 2026 | UK Day-Ahead Electricity Market Forecasting
          </div>
          <div>
            Data Provider: <strong>Elexon Insights Solution (BMRS)</strong> | Datasets: <strong>WINDFOR</strong> & <strong>FUELHH (WIND)</strong>
          </div>
          <div>
            Stack: <strong>React 18</strong> &bull; <strong>FastAPI</strong> &bull; <strong>Pandas</strong> &bull; <strong>Docker</strong>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
