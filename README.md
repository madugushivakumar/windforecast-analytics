# WindForecast Analytics: UK National Wind Generation Day-Ahead Forecast Accuracy (January 2026)

[![Backend Tests](https://img.shields.io/badge/Pytest-43%20passed-success)](./backend/tests)
[![Frontend Tests](https://img.shields.io/badge/Vitest-5%20passed-success)](./frontend/src/tests)
[![TypeScript](https://img.shields.io/badge/TypeScript-Verified-blue)](./frontend)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](./backend)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green)](./backend)
[![React](https://img.shields.io/badge/React-18-cyan)](./frontend)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED)](./docker-compose.yml)

---

## 1. Project Overview & Business Problem

In the United Kingdom wholesale electricity market, energy utilities purchase power on day-ahead wholesale power exchanges (e.g., EPEX SPOT and Nord Pool GB). Energy traders and commercial dispatchers place binding volume and price bids on day $D-1$ for physical delivery of electricity across settlement periods 1 to 48 on day $D$.

Because wind generation is weather-dependent and highly intermittent, commercial utilities face substantial volume risk and cash-out imbalance penalties when generation diverges from forecast. Energy procurement desks require an authoritative analytics system to answer two fundamental commercial questions:
1. **What was the latest authoritative wind forecast available when purchasing decisions were executed at Day-Ahead gate closure?**
2. **What was the quantitative accuracy of those forecasts when evaluated against delivered transmission outturn in January 2026?**

**WindForecast Analytics** is a production-quality, mathematically rigorous full-stack analytics platform built to ingest official Elexon Insights Solution (BMRS) data, enforce day-ahead auction decision cutoffs with zero lookahead bias, match forecasts and actuals strictly on delivery period timestamps, compute quantitative error metrics (MAE, RMSE, Mean Signed Error / Bias, WAPE), and present insights through a responsive enterprise dashboard.

---

## 2. Main Features

- **Authoritative Elexon BMRS Ingestion**: Connects directly to official Elexon Insights Solution stream endpoints for `FUELHH` (outturn generation) and `WINDFOR` (day-ahead national wind forecasts) with bounded 7-day chunking, exponential backoff retries, and local disk cache fallback.
- **Strict Fuel Filtering**: Filters `FUELHH` generation strictly to `fuelType == 'WIND'`, discarding all conventional, nuclear, and interconnection flows.
- **Day-Ahead Decision Cutoff Enforcement**: Enforces market gate closure rules with minute-level precision (default: 11:00 UTC on day $D-1$ as an operational utility purchasing assumption; fully configurable to official exchange deadlines like 09:20 UTC for EPEX SPOT GB). Only forecasts published strictly prior to or at gate closure (`publishTime <= cutoffTime`) are eligible. The latest eligible vintage is selected with zero future lookahead.
- **January 2026 Decision-Date Window Filtering**: Evaluates all purchasing decisions made between `2026-01-01 00:00:00 UTC` and `2026-02-01 00:00:00 UTC` (exclusive), corresponding to deliveries from `2026-01-02 00:00:00 UTC` through `2026-02-01 23:00:00 UTC` (or `23:30:00 UTC` half-hourly).
- **Dual Resolution Alignment**:
  - **Hourly Aggregated Evaluation (Primary / Evaluated)**: Pairs hourly WINDFOR forecasts with arithmetic-mean actual generation across the two half-hours in that hour: $A_H = \frac{A_{H:00} + A_{H:30}}{2} \text{ MW}$, yielding 100.0% coverage across all 744 hours in the 31-day delivery span.
  - **Half-Hourly Granular Evaluation (Transparency Mode)**: Evaluates forecasts strictly against the matching `:00` half-hour, transparently reporting the 744 `:30` periods as `MISSING_FORECAST` (50.0% coverage) with zero artificial interpolation.
- **Pure Mathematical Metric Calculations**: Hand-calculated and automated unit tests for:
  - **Mean Absolute Error (MAE)**: Measures average expected forecast error magnitude in MW.
  - **Root Mean Squared Error (RMSE)**: Penalizes severe forecasting misses in MW.
  - **Mean Signed Error (Bias)**: Quantifies systematic over- or under-forecasting tendency in MW.
  - **Weighted Absolute Percentage Error (WAPE)**: Safe aggregate percentage error without division-by-zero singularities.
  - **Conditional MAPE**: Explicitly documents and filters near-zero actual generation lulls ($A_t < 100 \text{ MW}$) to prevent infinite percentage distortions.
- **Interactive Enterprise React Frontend**:
  - **Page A (Overview Dashboard)**: Executive KPIs, full-month forecast vs. actual outturn time-series chart, data coverage health indicator, resolution mode toggle, and commercial market interpretations.
  - **Page B (Forecast Comparison)**: Delivery window date filter, week presets, interactive time-series zoom, and a **Forecast Vintage History Inspector** revealing all published forecast runs and gate closure eligibility.
  - **Page C (Accuracy Analysis)**: Error distribution histogram, residual error trends, and top 10 largest absolute error discrepancy periods.
  - **Page D (Data Explorer)**: Paginated, multi-column sortable, filterable table of delivery periods, cutoffs, forecasts, actuals, signed errors, and direct CSV export of verified analyzed records.
- **Data Quality Audit Trail & Provenance**: Full accounting of records fetched, wind records retained, duplicates resolved, missing actuals, missing forecasts, and explicit data source provenance (`DISK_CACHE`, `LIVE_API`, `MIXED_CACHE_API`).

---

## 3. Technology Stack

| Layer | Technologies | Rationale |
|---|---|---|
| **Frontend** | React 18, TypeScript, Vite, Recharts, Lucide Icons | High-performance SPA with modern dark glassmorphism design, responsive layouts, and interactive time-series visualizations. |
| **Backend** | Python 3.11, FastAPI, Pandas, HTTPX, Pydantic v2 | Authoritative analytics engine, robust async HTTP client, and automatic OpenAPI documentation. |
| **Data Cleaning** | Pandas, Timezone-aware UTC datetimes | Efficient vector joins, deterministic duplicate resolution, and strict data quality auditing. |
| **Testing** | Pytest, Vitest, React Testing Library, JSDOM | 31 backend Pytest tests, 1 opt-in live integration test, and 5 frontend Vitest tests. |
| **Containerization** | Docker, Docker Compose, Nginx Alpine | Multi-stage reproducible container builds with health checks and corrected cache volume mounts. |
| **Deployment** | Vercel (Frontend), Heroku / Render (Backend) | Production-ready with SPA client-side routing and CORS configuration. |

---

## 4. Architecture Diagram

```mermaid
graph TD
    subgraph External Sources
        Elexon["Elexon BMRS API (Insights Solution)"]
    end

    subgraph Python Backend (FastAPI :8000)
        Client["ElexonApiClient (HTTPX with chunking & backoff)"]
        Cache["Disk & In-Memory Pipeline Cache (data/cache/)"]
        Cleaner["DataCleaner (Fuel filtering, deduplication, DQ audit)"]
        Selector["ForecastSelector (Day-Ahead Cutoff D-1 11:00 UTC)"]
        Matcher["Matcher (Delivery period startTime alignment & hourly aggregation)"]
        Analytics["AnalyticsEngine (MAE, RMSE, Bias, distributions)"]
        FastAPI["FastAPI REST Endpoints (/api/*, /health)"]
    end

    subgraph React Frontend (Vite :3000)
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

## 5. Official Data Sources & Schema

WindForecast Analytics queries the live official Elexon Insights Solution (BMRS) APIs:
1. **FUELHH Dataset** (`https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream`):
   - `startTime`: Start of 30-minute settlement period in ISO 8601 UTC.
   - `publishTime`: Timestamp when outturn reading was released.
   - `fuelType`: Categorical fuel identifier. **Filtered exclusively to `fuelType == 'WIND'`**.
   - `generation`: Delivered generation in Megawatts (MW).
   - `settlementDate`: Calendar delivery date.
   - `settlementPeriod`: Half-hour period index (1 to 48).
2. **WINDFOR Dataset** (`https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream`):
   - `startTime`: Target delivery period timestamp in ISO 8601 UTC.
   - `publishTime`: Vintage timestamp when forecast was generated by National Grid ESO.
   - `generation`: Forecasted wind generation in Megawatts (MW).

---

## 6. January 2026 Scope & Decision Cutoff Rules

- **Decision-Date Window (Primary Focus)**: Purchasing decisions executed in January 2026 (`2026-01-01 00:00:00 UTC` through `2026-02-01 00:00:00 UTC` exclusive). Under the Day-Ahead rule, decisions made on January 1 deliver on January 2; decisions made on January 31 deliver on February 1 (all 24 hours of February 1 are included). Decisions executed on December 31, 2025 (delivering January 1, 2026) belong to December 2025 commercial decisions and are excluded.
- **Delivery Window (Alternative Toggle)**: Delivery periods occurring strictly within January 2026 (`2026-01-01 00:00:00 UTC` through `2026-01-31 23:00:00 UTC` hourly or `23:30:00 UTC` half-hourly).
- **Gate Closure Cutoff Logic & Market Rules**:
  - For delivery on Day $D$, day-ahead wholesale auction orders close on Day $D-1$.
  - **Verified Official Market Closures**:
    - **EPEX SPOT GB 60min Day-Ahead Auction**: Order book closes at **09:20 GMT/UTC** daily on Day $D-1$ ([EPEX SPOT Market Data](https://www.epexspot.com/en/market-data)).
    - **Nord Pool GB Day-Ahead Auction (N2EX)**: Order book closes at **09:50 GMT/UTC** (10:50 CET) daily on Day $D-1$ ([Nord Pool GB Auction](https://www.nordpoolgroup.com/trading/Day-ahead-trading/Auction-GB/)).
    - **EPEX SPOT GB 30min Day-Ahead Auction**: Order book closes at **15:30 GMT/UTC** daily on Day $D-1$.
  - **Default Project Cutoff (11:00 UTC)**: Configured as an **operational utility purchasing decision assumption** (aligned with the European SDAC 12:00 CET/11:00 UTC reference). This enables commercial utilities to incorporate National Grid ESO's **10:30 UTC WINDFOR forecast release** prior to midday operations.
  - **Configurability**: Minute-level precision is supported via `--cutoff-hour` and `--cutoff-minute` (e.g. `09:20` for official EPEX SPOT GB or `11:00` for operational utility baseline).
  - **Eligibility Rule**: A forecast vintage is eligible if and only if `publishTime <= decisionCutoff`. Forecast revisions published strictly after the cutoff are excluded to prevent future lookahead bias.
  - **Selection Rule**: The system selects the forecast with $\max(\text{publishTime})$ among all eligible records, preserving its original publication timestamp for auditing.

---

## 7. Data Cleaning & Resolution Alignment Methodology

1. **Timezone Normalization**: All incoming timestamps are parsed and converted to timezone-aware UTC datetime objects (`datetime.timezone.utc`).
2. **Negative & Malformed Record Detection**: Records with negative generation or unparseable values are audited and dropped.
3. **Deterministic Duplicate Resolution**: If multiple records exist for identical delivery `startTime`, the record with the latest `publishTime` is retained, and a duplicate event is logged in the Data Quality report.
4. **Resolution Finding & Alignment**:
   - In January 2026, `FUELHH` reports 30-minute settlement periods (1,488 half-hours), while `WINDFOR` national forecasts are published at hourly resolution (`:00`). Both streams report power in **Megawatts (MW)**.
   - **Hourly Aggregated Evaluation (Primary / Evaluated)**: Pairs each hourly forecast with the arithmetic-mean actual generation across the two half-hours in that hour: $A_H = \frac{A_{H:00} + A_{H:30}}{2} \text{ MW}$. This achieves **100.0% coverage across all 744 hours** in the 31-day delivery span without making unsupported assumptions. The underlying `:00` and `:30` half-hour actuals are preserved for full auditability.
   - **Half-Hourly Granular Mode (Transparency Mode)**: Evaluates forecasts strictly against the matching `:00` half-hour, transparently reporting the 744 `:30` periods as `MISSING_FORECAST` (50.0% coverage) with zero artificial interpolation.

---

## 8. Forecast Accuracy Metric Definitions

Let $F_t$ = Day-Ahead forecast generation for delivery period $t$, $A_t$ = Actual wind generation for delivery period $t$, and $e_t = F_t - A_t$:
- **Signed Error ($e_t$)**: $e_t = F_t - A_t$ (Positive indicates over-forecasting; negative indicates under-forecasting).
- **Mean Absolute Error (MAE)**:
  $$\text{MAE} = \frac{1}{N} \sum_{t=1}^N |F_t - A_t| \quad [\text{MW}]$$
- **Root Mean Squared Error (RMSE)**:
  $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{t=1}^N (F_t - A_t)^2} \quad [\text{MW}]$$
- **Mean Signed Error / Bias**:
  $$\text{Bias} = \frac{1}{N} \sum_{t=1}^N (F_t - A_t) \quad [\text{MW}]$$
- **Weighted Absolute Percentage Error (WAPE)**:
  $$\text{WAPE} = \frac{\sum_{t=1}^N |F_t - A_t|}{\sum_{t=1}^N A_t} \times 100\%$$
- **Conditional MAPE**: Evaluated strictly on periods where $A_t \ge 100 \text{ MW}$ to avoid dividing by near-zero wind lull observations.

### Verified January 2026 Results (Day-Ahead 11:00 UTC D-1 Cutoff, Decision Window)

#### Primary Evaluated Mode: Hourly Aggregation
- **Decision Window**: `2026-01-01 00:00:00 UTC` to `2026-02-01 00:00:00 UTC` (exclusive)
- **Delivery Span**: `2026-01-02 00:00:00 UTC` to `2026-02-01 23:00:00 UTC`
- **Sample Size ($N$)**: **744 matched hourly delivery periods** (100.0% coverage of 744 expected hours)
- **Mean Absolute Error (MAE)**: **2,013.01 MW**
- **Root Mean Squared Error (RMSE)**: **2,505.94 MW**
- **Mean Signed Error (Bias)**: **+1,729.93 MW** (Systematic over-forecasting)
- **Maximum Absolute Error**: **6,833.00 MW**
- **Minimum Signed Error**: **-4,128.00 MW**
- **Maximum Signed Error**: **+6,833.00 MW**
- **Error Standard Deviation**: **1,814.25 MW**
- **WAPE**: **17.84%** (Total Absolute Error: 1,497,682 MW / Total Generation: 8,396,971 MW)
- **Conditional MAPE**: **21.61%** (744/744 periods with $A_t \ge 100 \text{ MW}$)
- **Data Source**: Elexon BMRS API (`DISK_CACHE` / `LIVE_API`)

#### Transparency Mode: Half-Hourly Granular
- **Sample Size ($N$)**: 744 matched half-hours (50.0% coverage of 1,488 expected periods; 744 unforecasted `:30` periods)
- **MAE**: **1,995.57 MW**
- **RMSE**: **2,498.82 MW**
- **Bias**: **+1,727.98 MW**
- **Maximum Absolute Error**: **6,857.00 MW**
- **WAPE**: **17.68%**

---

## 9. Project Directory Structure

```text
windforecast-analytics/
├── .env.example                     # Example environment variables
├── .gitignore                       # Git exclusions for Python, Node, and secrets
├── docker-compose.yml               # Docker Compose orchestration
├── README.md                        # Master project documentation
├── PROJECT_PLAN.md                  # Comprehensive engineering plan
├── REQUIREMENTS_TRACEABILITY.md     # Traceability matrix mapping requirements to tests
├── IMPLEMENTATION_STATUS.md         # Phase-by-phase implementation tracker
├── docs/
│   ├── ARCHITECTURE.md              # System design, data flows, and trade-offs
│   ├── DATA_DICTIONARY.md           # Schema, types, units, and transformation rules
│   ├── DATA_ASSUMPTIONS.md          # Market rules, cutoffs, and edge-case handling
│   ├── TESTING.md                   # Automated test commands, results, acceptance checklist
│   ├── DEPLOYMENT.md                # Vercel, Heroku, and Docker deployment guide
│   ├── VIDEO_SCRIPT.md              # 10-minute demo script (Part 1 Customer + Part 2 Technical)
│   └── SUBMISSION_CHECKLIST.md      # Final submission and incognito verification checklist
├── backend/
│   ├── Dockerfile                   # Python 3.11 container definition
│   ├── Procfile                     # Heroku process startup file
│   ├── requirements.txt             # Python dependencies (FastAPI, Pandas, HTTPX, Pytest)
│   ├── app/
│   │   ├── main.py                  # FastAPI application entrypoint and healthcheck
│   │   ├── core/
│   │   │   └── config.py            # Pydantic BaseSettings environment configuration
│   │   ├── schemas/
│   │   │   ├── observation.py       # Pydantic schemas for observations
│   │   │   ├── metrics.py           # Pydantic schemas for accuracy metrics
│   │   │   └── data_quality.py      # Pydantic schemas for data quality summaries
│   │   ├── services/
│   │   │   ├── elexon_client.py     # Elexon API client with bounded chunking & retries
│   │   │   ├── data_cleaner.py      # Fuel filtering, timestamp parsing, deduplication
│   │   │   ├── forecast_selector.py # Day-Ahead decision cutoff logic
│   │   │   ├── matcher.py           # Delivery startTime matching & error calculations
│   │   │   └── pipeline.py          # Central pipeline orchestration & in-memory caching
│   │   ├── analytics/
│   │   │   └── metrics.py           # Pure mathematical functions (MAE, RMSE, Bias, distributions)
│   │   └── api/
│   │       └── endpoints.py         # REST routes (/overview, /forecasts, /accuracy, /observations)
│   └── tests/
│       ├── test_metrics.py          # Unit tests with hand-calculated examples
│       ├── test_data_cleaner.py     # Cleaning, fuel filtering, and deduplication tests
│       ├── test_forecast_selector.py# Decision cutoff enforcement & eligibility tests
│       ├── test_matcher.py          # Forecast-actual matching tests
│       └── test_api.py              # Integration tests for FastAPI endpoints
└── frontend/
    ├── Dockerfile                   # Multi-stage build with Nginx Alpine
    ├── nginx.conf                   # Nginx reverse proxy & SPA fallback configuration
    ├── package.json                 # Node dependencies (React 18, Vite, Recharts, Vitest)
    ├── tsconfig.json                # TypeScript compiler configuration
    ├── vite.config.ts               # Vite configuration with Vitest setup
    ├── vercel.json                  # Vercel client-side routing rewrites
    ├── public/
    │   └── favicon.svg              # Wind energy favicon
    └── src/
        ├── index.css                # Modern dark glassmorphic design system
        ├── main.tsx                 # React DOM mount point
        ├── App.tsx                  # Root navigation and view coordinator
        ├── types/
        │   └── index.ts             # TypeScript interfaces for API models
        ├── services/
        │   └── api.ts               # Type-safe centralized REST client
        ├── components/
        │   ├── Header.tsx           # Navigation header, tabs, and cutoff selector
        │   └── MetricCard.tsx       # Reusable KPI card with status variants
        ├── pages/
        │   ├── OverviewPage.tsx     # Page A: Executive overview & time-series
        │   ├── ForecastComparisonPage.tsx # Page B: Comparison & Vintage Inspector
        │   ├── AccuracyPage.tsx     # Page C: Statistical accuracy & distributions
        │   └── DataExplorerPage.tsx # Page D: Paginated table & CSV export
        └── tests/
            ├── setup.ts             # Testing Library JSDOM setup
            ├── MetricCard.test.tsx  # MetricCard component tests
            ├── Header.test.tsx      # Header & navigation tests
            └── OverviewPage.test.tsx# Overview page rendering & KPI tests
```

---

## 10. Prerequisites

- **Python**: Version 3.11 or higher
- **Node.js**: Version 18.0 or higher (v20+ recommended)
- **Git**: For version control
- **Docker & Docker Compose**: Optional for containerized local execution

---

## 11. Local Setup Instructions

### Step 1: Clone Repository
```bash
git clone <repository-url>
cd windforecast-analytics
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

---

## 12. Backend Startup Instructions

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The backend will start at:
- **API Base**: `http://localhost:8000`
- **Health Check**: `http://localhost:8000/health`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`

---

## 13. Frontend Startup Instructions

```bash
cd frontend
npm install
npm run dev
```
The frontend will start at `http://localhost:3000` (or `http://localhost:5173`).

---

## 14. Docker Containerization Instructions

Ensure Docker Desktop daemon is running, then run:
```bash
docker compose up --build
```
- **Frontend**: `http://localhost:3000`
- **Backend API**: `http://localhost:8000`
- **Stop Containers**: `docker compose down`

---

## 15. Automated Test Commands

### Run Backend Tests (Pytest)
```bash
python -m pytest backend/tests -v
```
*Expected: 43 passed, 1 skipped (100% of deterministic suite). Live API integration test can be run with `$env:RUN_LIVE_TESTS="1"`.*

### Run Reproducible Analysis & Audit Verification Pipeline
```bash
python backend/reproduce_analysis.py --cutoff-hour 11 --cutoff-minute 0 --window decision --resolution hourly
```
*Generates and validates all 5 audit artifacts into `artifacts/january_2026/`:*
1. `analysis_summary.json` (Configuration, effective cutoff metadata, final metrics, independent validation status)
2. `observations_analysis.csv` (744 rows of evaluated hourly observations with decision cutoff and selected publish timestamps)
3. `data_quality_report.json` (Record counts, duplicates resolved, missing actuals, 100% data coverage)
4. `run_manifest.json` (SHA-256 hashes of input caches and output artifacts, git commit, python version)
5. `validation_log.md` (Table comparing primary pipeline against independent recomputations with diff < 0.003)

### Run Frontend Tests (Vitest)
```bash
cd frontend
npm run test
```
*Expected: 5 passed (100%).*

### Run Frontend Production Typecheck & Build
```bash
cd frontend
npm run build
```
*Expected: Built in ~6s with zero TypeScript errors.*

---

## 16. Production Deployment Instructions

See [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) for full instructions:
- **Frontend (Vercel)**: Connect repository or run `cd frontend && vercel --prod`. Set `VITE_API_BASE_URL` to the deployed backend URL.
- **Backend (Heroku / Render / Container Host)**: Uses `backend/Procfile` or `backend/Dockerfile`. Set `ENVIRONMENT=production`, `CORS_ORIGINS`, and verify `GET /health`.

---

## 17. Disclosure of AI Tools Used

In accordance with assignment requirements:
- **AI Tools Used**: Google Gemini / Antigravity Agentic Coding Assistant.
- **Scope of Assistance**: Assisted with project planning documentation, initial boilerplate code structure, data dictionary compilation, mathematical metric unit test fixtures, TypeScript interfaces, and video presentation scripting.
- **Verification**: All mathematical logic, Elexon API requests, timestamp conversions, cutoff comparisons, and test suites were independently implemented, executed, and verified against real Elexon BMRS January 2026 data.

---

## 18. Known Limitations & Future Improvements

1. **Forecast Horizon Resolution**: Elexon `WINDFOR` national forecasts for January 2026 are published at hourly resolution, while `FUELHH` actuals are recorded at 30-minute settlement period frequency. The platform matches all 744 hourly periods strictly without fabricating unobserved half-hours. Future enhancements could implement configurable half-hour spline interpolation if requested by commercial desks.
2. **Additional Market Cutoffs**: The default cutoff is 11:00 UTC D-1 (EPEX SPOT Day-Ahead Auction). Users can toggle alternative cutoffs (12:00 UTC, 09:00 UTC, or custom lead times). Future versions could support Intraday 1-hour gate closure rolling horizons.
3. **Regional Disaggregation**: Current analysis evaluates national transmission-level wind generation. Integration of embedded wind generation (PV & distributed wind) would provide further insights into localized grid congestion.
