# Architecture Documentation: WindForecast Analytics

## 1. System Overview
WindForecast Analytics is a production-quality full-stack energy analytics system designed to evaluate the quantitative accuracy of UK Day-Ahead wind generation forecasts against outturn generation for energy purchasing decisions in January 2026.

```mermaid
graph TD
    subgraph External Sources
        Elexon["Elexon BMRS API (Insights Solution)"]
    end

    subgraph Python Backend (FastAPI)
        Client["ElexonApiClient (HTTPX with chunking & backoff)"]
        Cache["Disk & In-Memory Pipeline Cache"]
        Cleaner["DataCleaner (Fuel filtering, deduplication, DQ audit)"]
        Selector["ForecastSelector (Decision cutoff enforcement)"]
        Matcher["Matcher (Delivery period startTime alignment)"]
        Analytics["AnalyticsEngine (MAE, RMSE, Bias, distributions)"]
        FastAPI["FastAPI REST API (/api/*, /health)"]
    end

    subgraph Frontend (React + Vite + TypeScript)
        UIStore["React State & API Client"]
        Dashboard["Overview Dashboard"]
        Comparison["Forecast Comparison & Vintages"]
        Accuracy["Accuracy & Error Analysis"]
        Explorer["Data Explorer & CSV Exporter"]
    end

    Elexon --> Client
    Client --> Cache
    Cache --> Cleaner
    Cleaner --> Selector
    Selector --> Matcher
    Matcher --> Analytics
    Analytics --> FastAPI
    FastAPI --> UIStore
    UIStore --> Dashboard
    UIStore --> Comparison
    UIStore --> Accuracy
    UIStore --> Explorer
```

---

## 2. Component Responsibilities

### 2.1 Backend (`backend/app/`)
- **`core/config.py`**: Pydantic-based configuration management loading environment variables (API base URLs, timeouts, default decision cutoffs, CORS origins).
- **`services/elexon_client.py`**: Robust HTTP client for Elexon BMRS Stream API with automatic time-window chunking (to prevent timeout on large ranges), bounded retries with exponential backoff, and transparent upstream error classification.
- **`services/data_cleaner.py`**: Validates timestamps into UTC, filters `FUELHH` strictly to `fuelType == "WIND"`, identifies duplicates, enforces generation constraints ($\ge 0$), and compiles a comprehensive Data Quality (DQ) report.
- **`services/forecast_selector.py`**: Applies market decision cutoff rules (default 11:00 UTC day-ahead). Selects the latest available forecast vintage published prior to or at gate closure ($publishTime \le cutoffTime$).
- **`services/matcher.py`**: Joins forecast and actual observations exclusively on target delivery period timestamp (`startTime`). Emits signed errors, absolute errors, squared errors, and lead times.
- **`analytics/metrics.py`**: Pure, deterministic mathematical functions for MAE, RMSE, Mean Signed Error (Bias), Maximum Absolute Error, error deciles, and safe zero-handling policies.
- **`api/endpoints.py`**: High-performance FastAPI routes exposing overview KPIs, time-series arrays, vintage histories, data-quality summaries, and observation tables.
- **`main.py`**: Application factory, CORS middleware, startup pipeline pre-warming, and health/readiness endpoints.

### 2.2 Frontend (`frontend/src/`)
- **`services/api.ts`**: Strongly typed REST API client using Axios/Fetch with error interceptors and configurable base URL (`VITE_API_BASE_URL`).
- **`pages/OverviewPage.tsx`**: Executive overview displaying high-level accuracy KPIs (MAE, RMSE, Bias), observation counts, data health status, and full-month forecast vs. actual trend.
- **`pages/ForecastComparisonPage.tsx`**: Deep-dive comparison allowing day/week filtering, zooming, and inspecting alternative forecast vintages.
- **`pages/AccuracyPage.tsx`**: Error distribution histogram, residual scatter plots, error-over-time trends, and largest over/under-forecast events.
- **`pages/DataExplorerPage.tsx`**: Interactive data grid with search, multi-column sorting, pagination, and direct CSV download of actual analyzed data.
- **`components/`**: Reusable modern UI components (MetricCard, Header, Navbar, StatusBadge, LoadingSpinner, ErrorAlert).

---

## 3. Data & API Flow

```
1. Client Request ──► FastAPI Router (/api/overview?cutoff_hour=11)
2. Router ──────────► Analytics Pipeline Manager
3. Pipeline ────────► Checks In-Memory Cache (Hit? Return immediately)
4. Cache Miss ──────► ElexonApiClient:
                      - Fetch FUELHH (2026-01-01 to 2026-02-01) in 7-day chunks
                      - Fetch WINDFOR (2025-12-30 to 2026-02-01) in 7-day chunks
5. Pipeline ────────► DataCleaner: Filter fuelType='WIND', deduplicate, log DQ counts
6. Pipeline ────────► ForecastSelector: Filter publishTime <= DayAhead Cutoff (11:00 D-1), take latest
7. Pipeline ────────► Matcher: Inner & Left joins on startTime
8. Pipeline ────────► AnalyticsEngine: Compute MAE, RMSE, MSE, Bias, Error Distribution
9. Pipeline ────────► Store clean dataset in cache & return typed Pydantic response
10. FastAPI ────────► Return HTTP 200 JSON to React Frontend
```

---

## 4. Error-Handling Strategy
1. **Upstream API Failures**:
   - If the live Elexon API is unreachable (502/503/timeout), the client attempts bounded retries (3 attempts with exponential backoff).
   - If upstream remains down, the backend falls back to local disk-cached verified data fixtures and flags `data_source: "LOCAL_CACHE_FALLBACK"` in the response header and body.
2. **Missing Observations**:
   - Gaps in actual generation or forecasts are never filled with dummy zeros. Gaps are explicitly tagged as `MISSING_ACTUAL` or `MISSING_FORECAST` and excluded from calculation denominators ($N$).
3. **Frontend Resilience**:
   - Comprehensive error boundaries, inline retry buttons, empty state illustrations, and descriptive banners prevent UI crashes.

---

## 5. Deployment Topology
- **Local Development**: Docker Compose running `backend` (FastAPI on `:8000`) and `frontend` (Vite dev or Nginx preview on `:3000` / `:5173`).
- **Production Cloud Architecture**:
  - **Frontend**: Deployed to Vercel (or static hosting) with custom routing rewrites and environment variable `VITE_API_BASE_URL`.
  - **Backend**: Containerized FastAPI service deployed to a Python-capable host (e.g., Heroku, Render, AWS ECS, or Fly.io) with CORS configured to allow the frontend origin.

---

## 6. Key Technical Trade-offs
| Decision | Alternative Considered | Rationale |
|---|---|---|
| In-Memory & File Cache over PostgreSQL | Full relational database (Postgres/Timescale) | For a focused single-month MVP (~1,488 half-hour settlement periods), in-memory Pandas indexing delivers sub-millisecond query latency with zero database maintenance overhead or credential requirements. |
| Time-Window Chunking (7 days) | Single 31-day request | Elexon stream API can time out or drop connections when transferring tens of thousands of raw multi-fuel records; 7-day chunks are fast and reliable. |
| Strict Day-Ahead 11:00 UTC D-1 Cutoff | Intraday or Rolling 4-Hour Horizon | Matches the actual commercial Day-Ahead auction gate closure in Great Britain power trading. Configurable parameters enable evaluating alternative horizons. |
