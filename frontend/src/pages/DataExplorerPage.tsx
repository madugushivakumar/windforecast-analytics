import React, { useState, useEffect } from "react";
import { Download, Filter, ChevronLeft, ChevronRight, ArrowUpDown } from "lucide-react";
import { api } from "../services/api";
import { ForecastRecord } from "../types";

interface DataExplorerPageProps {
  cutoffHour: number;
}

export const DataExplorerPage: React.FC<DataExplorerPageProps> = ({ cutoffHour }) => {
  const [records, setRecords] = useState<ForecastRecord[]>([]);
  const [totalRecords, setTotalRecords] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(50);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [sortBy, setSortBy] = useState<string>("startTime");
  const [sortOrder, setSortOrder] = useState<string>("asc");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadObservations();
  }, [page, pageSize, statusFilter, sortBy, sortOrder, cutoffHour]);

  const loadObservations = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getObservations(
        page,
        pageSize,
        sortBy,
        sortOrder,
        statusFilter || undefined,
        undefined,
        undefined,
        cutoffHour
      );
      setRecords(res.records);
      setTotalRecords(res.total_records);
      setTotalPages(res.total_pages);
    } catch (err: any) {
      setError(err.message || "Failed to load observations.");
    } finally {
      setLoading(false);
    }
  };

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      setSortOrder("asc");
    }
    setPage(1);
  };

  const handleDownloadCsv = () => {
    const url = api.getCsvExportUrl(cutoffHour);
    window.open(url, "_blank");
  };

  return (
    <div className="animate-fade-in" style={{ padding: "1.5rem" }}>
      {/* Controls & Export Header */}
      <div className="filter-bar">
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "1rem" }}>
          <div className="filter-group">
            <Filter size={16} color="var(--accent-cyan)" />
            <label htmlFor="select-status" style={{ fontSize: "0.875rem", fontWeight: 600 }}>Status Filter:</label>
            <select
              id="select-status"
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              className="select-input"
            >
              <option value="">All Records</option>
              <option value="MATCHED">Matched (Forecast & Actual)</option>
              <option value="MISSING_FORECAST">Missing Forecast</option>
              <option value="MISSING_ACTUAL">Missing Actual</option>
            </select>
          </div>

          <div className="filter-group">
            <label htmlFor="select-page-size" style={{ fontSize: "0.875rem", color: "var(--text-dim)" }}>Rows:</label>
            <select
              id="select-page-size"
              value={pageSize}
              onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
              className="select-input"
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>
        </div>

        <button
          id="btn-export-csv"
          onClick={handleDownloadCsv}
          className="btn btn-primary"
          title="Download verified analyzed observations in CSV format"
        >
          <Download size={16} /> Export Analyzed Dataset (CSV)
        </button>
      </div>

      {error && (
        <div className="glass-card" style={{ padding: "1rem", marginBottom: "1rem", borderColor: "var(--accent-rose)", color: "var(--accent-rose)" }}>
          {error}
        </div>
      )}

      {/* Observation Table */}
      <div className="glass-card" style={{ padding: "1.25rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
          <div style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>
            Showing <strong>{records.length}</strong> of <strong>{totalRecords}</strong> delivery periods
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <button
              className="btn btn-secondary"
              style={{ padding: "0.3rem 0.6rem" }}
              disabled={page <= 1 || loading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft size={16} /> Previous
            </button>
            <span style={{ fontSize: "0.85rem", color: "var(--text-dim)" }}>
              Page {page} of {totalPages}
            </span>
            <button
              className="btn btn-secondary"
              style={{ padding: "0.3rem 0.6rem" }}
              disabled={page >= totalPages || loading}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Next <ChevronRight size={16} />
            </button>
          </div>
        </div>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th onClick={() => toggleSort("startTime")} style={{ cursor: "pointer" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                    Delivery Start Time (UTC) <ArrowUpDown size={12} />
                  </div>
                </th>
                <th>Settlement</th>
                <th>Day-Ahead Cutoff</th>
                <th>Selected Publish Time</th>
                <th onClick={() => toggleSort("forecast_mw")} style={{ cursor: "pointer" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                    Forecast (MW) <ArrowUpDown size={12} />
                  </div>
                </th>
                <th onClick={() => toggleSort("actual_mw")} style={{ cursor: "pointer" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                    Actual (MW) <ArrowUpDown size={12} />
                  </div>
                </th>
                <th onClick={() => toggleSort("signed_error_mw")} style={{ cursor: "pointer" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                    Signed Error (MW) <ArrowUpDown size={12} />
                  </div>
                </th>
                <th onClick={() => toggleSort("abs_error_mw")} style={{ cursor: "pointer" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                    Abs Error (MW) <ArrowUpDown size={12} />
                  </div>
                </th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={9} style={{ textAlign: "center", padding: "2rem", color: "var(--text-dim)" }}>
                    Loading observation records...
                  </td>
                </tr>
              ) : records.length === 0 ? (
                <tr>
                  <td colSpan={9} style={{ textAlign: "center", padding: "2rem", color: "var(--text-dim)" }}>
                    No observations found matching the selected filters.
                  </td>
                </tr>
              ) : (
                records.map((r, idx) => (
                  <tr key={idx}>
                    <td style={{ fontWeight: 600 }}>{new Date(r.startTime).toUTCString()}</td>
                    <td>{r.settlementDate ? `${r.settlementDate} (P${r.settlementPeriod})` : "-"}</td>
                    <td style={{ color: "var(--text-dim)", fontSize: "0.8rem" }}>
                      {r.decisionCutoff ? new Date(r.decisionCutoff).toUTCString() : "-"}
                    </td>
                    <td style={{ color: "var(--text-dim)", fontSize: "0.8rem" }}>
                      {r.selectedPublishTime ? new Date(r.selectedPublishTime).toUTCString() : "-"}
                    </td>
                    <td style={{ color: "var(--accent-cyan)", fontWeight: 600 }}>
                      {r.forecast_mw !== null ? `${r.forecast_mw.toLocaleString()} MW` : "-"}
                    </td>
                    <td style={{ color: "var(--accent-emerald)", fontWeight: 600 }}>
                      {r.actual_mw !== null ? `${r.actual_mw.toLocaleString()} MW` : "-"}
                    </td>
                    <td style={{
                      fontWeight: 700,
                      color: r.signed_error_mw === null ? "inherit" : r.signed_error_mw > 0 ? "var(--accent-amber)" : "var(--accent-rose)"
                    }}>
                      {r.signed_error_mw !== null ? `${r.signed_error_mw > 0 ? "+" : ""}${r.signed_error_mw.toLocaleString()} MW` : "-"}
                    </td>
                    <td style={{ fontWeight: 700 }}>
                      {r.abs_error_mw !== null ? `${r.abs_error_mw.toLocaleString()} MW` : "-"}
                    </td>
                    <td>
                      {r.status === "MATCHED" && <span className="badge badge-healthy">Matched</span>}
                      {r.status === "MISSING_FORECAST" && <span className="badge badge-warning">Missing Forecast</span>}
                      {r.status === "MISSING_ACTUAL" && <span className="badge badge-warning">Missing Actual</span>}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
