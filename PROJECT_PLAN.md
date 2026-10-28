# Project Plan: WindForecast Analytics

## 1. Executive Summary & Business Requirements
The client is a United Kingdom electricity energy utility purchasing power in the UK day-ahead wholesale electricity market. Because wind generation is intermittent and weather-dependent, power traders and dispatchers must evaluate wind-generation forecasts against actual delivered generation to manage volume risk, forecast error imbalances, and day-ahead auction bidding strategies.

The primary objective of **WindForecast Analytics** is to provide an authoritative, automated, and mathematically rigorous analytics platform that:
1. Ingests official Elexon Insights Solution datasets:
   - `FUELHH` (Half-hourly generation outturn by fuel type, filtered strictly to `fuelType = 'WIND'`)
   - `WINDFOR` (Day-ahead wind generation forecasts published at varying vintages)
2. Implements a transparent, deterministic Day-Ahead decision cutoff rule for January 2026 purchasing decisions (e.g., standard UK Day-Ahead auction gate closure at 11:00 / 12:00 UTC day-ahead, with configurable decision cutoffs).
3. Matches delivery periods (`startTime`) with the latest eligible forecast published prior to the decision cutoff (`publishTime <= cutoffTime`).
4. Computes quantitative forecast accuracy metrics (Mean Absolute Error [MAE], Root Mean Squared Error [RMSE], Mean Signed Error / Bias [MSE], maximum error, error distributions).
5. Provides a clean, modern, responsive enterprise React dashboard with interactive time-series visualizations, forecast vintage comparisons, accuracy distributions, and filtered record explorer with export capabilities.

---

## 2. Technical Requirements
- **Backend**: Python 3.11+, FastAPI, Pandas, HTTPX, Pydantic v2, Pytest.
- **Frontend**: React 18 / 19, TypeScript, Vite, Recharts, Lucide Icons, clean modern CSS design system.
- **Data Engineering**: Elexon BMRS Insights Solution REST/Stream API client with bounded chunking, robust retry/backoff, timezone normalization (UTC ISO 8601), and deterministic duplicate resolution.
- **Containerization**: Multi-stage Dockerfiles for frontend and backend, orchestrated with `docker-compose.yml`.
- **Testing**:
  - Backend: Pytest unit tests for pure metric functions, cleaning pipeline, cutoff selection, and integration tests with mocked HTTP fixtures.
  - Frontend: Vitest + React Testing Library for components, metric cards, charts, error states, and filters.
- **Deployment**: Ready for Vercel (frontend) + container/cloud platform (Heroku/Render/Docker host) with documented environment variables and health/readiness endpoints.

---

## 3. Functional Requirements
1. **Data Ingestion & Bounded Retrieval**:
   - Query Elexon stream API for `FUELHH` and `WINDFOR` over the January 2026 delivery window.
   - Extract `startTime`, `publishTime`, `fuelType`, `generation`, `settlementDate`, `settlementPeriod`.
   - Filter `FUELHH` exclusively to `fuelType = WIND`.
2. **Data Cleaning & Quality Tracking**:
   - Parse all timestamps into UTC-aware datetime objects.
   - Enforce non-negative generation values; detect missing intervals, duplicate records, and conflicting readings.
   - Retain complete data-quality audit counts (records fetched, wind retained, duplicates resolved, missing values, coverage %).
3. **Decision-Time Forecast Selection**:
   - For each delivery period ($t$), determine the day-ahead purchasing decision cutoff ($T_{\text{cutoff}}(t)$). Default: 11:00 UTC on day $D-1$ for delivery on day $D$.
   - Select the latest forecast vintage where $publishTime \le T_{\text{cutoff}}(t)$.
   - Transparently flag delivery periods with missing or post-cutoff-only forecasts without fabricating values.
4. **Matched Sample & Accuracy Metrics**:
   - Align forecasts and actuals strictly on normalized delivery-period timestamp (`startTime`).
   - Signed Error: $e_t = F_t - A_t$ (positive indicates over-forecasting, negative indicates under-forecasting).
   - MAE: $\frac{1}{N} \sum_{t=1}^N |F_t - A_t|$ (MW).
   - RMSE: $\sqrt{\frac{1}{N} \sum_{t=1}^N (F_t - A_t)^2}$ (MW).
   - Mean Signed Error (Bias): $\frac{1}{N} \sum_{t=1}^N (F_t - A_t)$ (MW).
   - Maximum Absolute Error and Error Distribution deciles/histogram.
   - Handled zero actual generation safely without misleading MAPE infinities.
5. **Interactive UI Views**:
   - **Overview Dashboard**: High-level KPIs (MAE, RMSE, Bias, Matched Periods), forecast vs actual time-series chart, health/coverage indicator.
   - **Forecast Comparison**: Detailed time-series inspection, date range filter, forecast vintage lead-time exploration.
   - **Accuracy Analysis**: Error distribution histogram, error over time, largest over/under-forecast periods table.
   - **Data Explorer**: Paginated, sortable, searchable table of matched observations, cutoff details, error metrics, and raw CSV export.

---

## 4. Non-Functional Requirements
- **Performance**: Response times < 500ms for analytical API queries via in-memory caching and indexed Pandas datasets.
- **Data Integrity**: Zero fabricated data points; clear visual badges for missing or excluded periods.
- **Maintainability**: Strict separation of concerns (API client, pipeline, analytics, router, presentation).
- **Security**: No secrets or API keys stored in client bundles or public repositories.
- **Reliability**: Graceful degradation when external Elexon API is unreachable, utilizing local cached historical fixtures with clear indicators.

---

## 5. Scope Exclusions
- Execution of actual power trades or automated algorithmic bidding.
- Regional or distribution-network-level wind forecasts (national transmission level only).
- Non-wind generation fuels in core analytics (biomass, nuclear, solar, gas retained only for raw ingestion auditing if necessary).
- Third-party weather provider data (strictly Elexon BMRS WINDFOR and FUELHH).
- Unnecessary billing, authentication, or payment systems.

---

## 6. Architecture & Data Flow Overview
```
[Elexon BMRS API]
   │
   ├─► FUELHH (Stream API) ──► Filter 'WIND' ──┐
   │                                            ▼
   └─► WINDFOR (Stream API) ─► Cutoff Filter ─► Data Cleaner ─► Matcher ─► Analytics Engine
                                                                                │
                                                                                ▼
[React Enterprise Frontend] ◄── REST API (JSON) ◄────────────── [FastAPI Backend]
  - Overview Dashboard
  - Forecast Comparison
  - Accuracy Analysis
  - Data Explorer & CSV Export
```

---

## 7. Key Assumptions
1. **Day-Ahead Market Cutoff**: The UK Day-Ahead wholesale power market auction (e.g., EPEX SPOT / Nord Pool) typically closes at 11:00 UTC (12:00 CET/BST) on day $D-1$ for electricity delivered across settlement periods 1 to 48 on day $D$. We implement 11:00 UTC D-1 as the primary default decision cutoff, with API/UI configurability for alternative horizons (e.g. 12:00 UTC D-1 or Intraday rolling horizons).
2. **Timestamp Semantics**:
   - `startTime`: Start of the 30-minute settlement period in UTC.
   - `publishTime`: Exact UTC timestamp when the National Grid ESO / Elexon model forecast was released.
3. **January 2026 Scope**: Refers to purchasing decisions executed in January 2026, delivering power from 2026-01-01 00:00 UTC through 2026-01-31 23:30 UTC (and 2026-02-01 morning if evaluated under January 31 decisions).

---

## 8. Known Risks & Mitigations
| Risk | Impact | Mitigation Strategy |
|---|---|---|
| Elexon API rate limiting or temporary downtime | Analysis fails or server hangs | Implement HTTPX client with retries, timeout bounds, and local disk cache fallback of fetched real records |
| Missing or unannounced settlement periods | Gaps in time series, skewed metrics | Timestamp continuum analysis; flag missing timestamps explicitly in Data Quality audit |
| Large data payload in single request | Stream connection timeout | Bounded time-window chunking (e.g., 3-day or 7-day windows) assembled into full month |
| Ambiguity in Day-Ahead market cutoff | Biased forecast vintage selection | Configurable cutoff parameter, explicit display of selected `publishTime` vs `cutoffTime` |

---

## 9. Implementation Phases
- **Phase 1**: Inspection, Environment Verification, and Planning (Current)
- **Phase 2**: Elexon API Exploration & Data Profiling
- **Phase 3**: Architecture & Data Dictionary Documentation
- **Phase 4**: Project Structure & Tooling Initialization
- **Phase 5**: Elexon API Client Implementation
- **Phase 6**: Data Cleaning & Quality Audit Module
- **Phase 7**: Decision-Time Forecast Selection Engine
- **Phase 8**: Matching Engine (Forecast-to-Actual by Delivery Period)
- **Phase 9**: Pure Forecast Accuracy Analytics Engine & Unit Tests
- **Phase 10**: FastAPI Backend Services & Endpoints
- **Phase 11**: React Enterprise Frontend Dashboard & Charts
- **Phase 12**: Frontend-Backend API Integration & End-to-End Validation
- **Phase 13**: Automated Testing Suite (Pytest + Vitest)
- **Phase 14**: Docker & Docker Compose Containerization
- **Phase 15**: Deployment Configuration & Scripts
- **Phase 16**: Documentation, Traceability, & Anonymous GitHub Preparation
- **Phase 17**: Video Demonstration Script & Presentation Checklist
- **Phase 18**: Final Submission Verification

---

## 10. External Actions Requiring Credentials / Authorization
- Live push to a remote anonymous GitHub repository (`git push`).
- Deployment to cloud hosting providers requiring authenticated API tokens or CLI logins (e.g., Vercel account, Heroku API key).
- Recording and uploading video to YouTube.
- Submitting the final Microsoft Form.
All local application builds, automated test suites, Docker containers, and documentation will be fully developed and verified locally.
