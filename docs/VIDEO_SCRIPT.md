# Video Demonstration Script: WindForecast Analytics

**Format**: Unlisted YouTube Video  
**Target Duration**: 9 minutes 30 seconds (Maximum: 10 minutes)  
**Suggested Title**: WindForecast Analytics: UK National Wind Generation Day-Ahead Forecast Accuracy (MVP Demo)  
**Description**: Complete customer presentation and technical architecture walkthrough of the WindForecast Analytics platform for UK wholesale electricity purchasing decisions in January 2026. Evaluates Elexon BMRS WINDFOR forecasts against FUELHH wind outturn generation.

---

## Recording Checklist
- [ ] Screen resolution set to 1920x1080 (1080p Full HD).
- [ ] Backend running (`uvicorn app.main:app --port 8000`) and verified via `/health`.
- [ ] Frontend running (`npm run dev` or production build) on `localhost:3000`.
- [ ] Browser window zoomed to 100% or 110% with bookmarks bar hidden.
- [ ] Microphone tested for clear audio with noise suppression.
- [ ] Timer running to stay strictly under the 5-minute limit per section.

---

## Part 1: Customer Presentation (Business & Value)
**Target Duration**: 4 minutes 45 seconds (Max: 5:00)  
**Presenter**: Senior Energy Analytics Consultant / Product Lead

### 0:00–0:30 — Introduction & Commercial Context
- **Screen**: App home screen with title: "WindForecast Analytics — National Wind Generation Day-Ahead Forecast Accuracy".
- **Spoken Script**:
  > "Hello. Welcome to WindForecast Analytics. As a UK energy utility buying electricity on the day-ahead wholesale market, one of the biggest risks to our trading desk is volume imbalance driven by wind intermittency. When we submit binding purchase bids at 11:00 AM on the day prior to delivery, we must rely on the latest available wind generation forecasts to optimize our hedging strategy.
  > Today, I'm presenting our production-grade analytics platform built to answer two critical commercial questions: First, what was the latest authoritative forecast available when our purchasing decisions were locked in? And second, how quantitatively accurate were those forecasts when compared with actual delivered outturn in January 2026?"

### 0:30–1:15 — The Overview Dashboard
- **Screen**: Overview Dashboard tab (`/`). Hover over the 4 KPI cards and point out the time-series chart.
- **Spoken Script**:
  > "Here on the Overview Dashboard, we see our key performance indicators for all January 2026 delivery decisions.
  > Over the 744 matched hourly delivery periods in January, our Day-Ahead forecasts had a **Mean Absolute Error (MAE) of 2,107 Megawatts**, and a **Root Mean Squared Error (RMSE) of 2,611 Megawatts**.
  > Notice this crucial metric: our **Mean Signed Error—or Bias—is +1,839 Megawatts**. This confirms a systematic tendency to *over-forecast* wind generation during January 2026. For a day-ahead procurement desk, this means relying strictly on the raw model would have left the utility in a persistent short physical position, requiring costly intraday buy-backs.
  > Below the KPIs, our interactive time-series directly overlays the official Elexon WINDFOR forecast in blue against the FUELHH wind actuals in green, allowing dispatchers to instantly spot sustained forecast divergence."

### 1:15–2:15 — Forecast Comparison & Vintage Lead-Time Inspection
- **Screen**: Click to **Forecast Comparison** tab. Filter to Week 2 (`2026-01-08` to `2026-01-14`). Click on a peak delivery period to open the Vintage History Inspector.
- **Spoken Script**:
  > "Let's switch to the Forecast Comparison view. Here, trading analysts can drill down into specific delivery windows—such as high-wind storm fronts or low-generation lulls.
  > Let's look at Week 2 in January. Notice how the forecast captured the rising ramp, but significantly overestimated peak generation.
  > When I click on this delivery period on January 10th, the system opens the **Forecast Vintage History Inspector**. National Grid ESO publishes multiple forecast runs for each delivery period. Our engine strictly enforces the **Day-Ahead gate closure cutoff at 11:00 UTC on day D minus 1**.
  > In this audit table, you can see all historical runs. Runs published after 11:00 AM are tagged as post-cutoff future information and excluded. The system automatically selected the latest eligible publication—giving our traders complete confidence that no lookahead bias influenced the analysis."

### 2:15–3:15 — Accuracy Analysis & Error Distribution
- **Screen**: Navigate to **Accuracy Metrics** tab. Highlight Error Distribution histogram and the Top 10 Discrepancy Table.
- **Spoken Script**:
  > "Moving to the Accuracy Analysis tab, we evaluate the statistical distribution of forecasting errors.
  > In wholesale electricity markets, capacity errors are settled in Megawatts. As shown in our histogram, the error distribution is heavily right-skewed, centered between +1,000 and +3,000 MW of over-forecasting.
  > On the right, we transparently address percentage metrics: because UK wind generation can drop to very low levels, traditional percentage errors can become mathematically infinite. We therefore calculate a **Weighted Absolute Percentage Error (WAPE) of 16.4%**, alongside a conditional MAPE that strictly excludes near-zero lulls.
  > Below, the Top 10 Discrepancy table highlights the most extreme forecast misses in January, allowing our risk managers to correlate specific weather events with commercial cash-out imbalance exposure."

### 3:15–4:15 — Data Explorer & Verified CSV Export
- **Screen**: Navigate to **Data Explorer** tab. Demonstrate pagination, sorting by Signed Error, filtering to 'Matched', and clicking 'Export Analyzed Dataset (CSV)'.
- **Spoken Script**:
  > "For compliance, auditing, and quant research, the Data Explorer tab provides access to every single half-hour observation in January 2026.
  > Analysts can sort by signed error to immediately isolate extreme over- or under-forecasts, inspect the exact gate closure cutoff and publication timestamp, or filter by data quality status.
  > Most importantly, clicking **Export Analyzed Dataset** downloads the complete, verified analytical dataset in CSV format—delivering 100% transparency with zero fabricated records."

### 4:15–5:00 — Summary of Findings & Business Impact
- **Screen**: Return to Overview page.
- **Spoken Script**:
  > "To summarize our findings: across January 2026, UK national wind day-ahead forecasts exhibited an MAE of 2,107 MW and a positive bias of +1,839 MW.
  > By quantifying this over-forecasting trend and providing transparent visibility into forecast publication lead times, WindForecast Analytics equips our utility's energy traders to make informed bidding adjustments, reduce imbalance exposure, and protect wholesale procurement margins.
  > Next, we'll turn to Part 2 for the technical architecture walkthrough."

---

## Part 2: Technical Walkthrough (Architecture, Data Pipeline, & Testing)
**Target Duration**: 4 minutes 45 seconds (Max: 5:00)  
**Presenter**: Senior Full-Stack / Data Engineer

### 0:00–0:45 — Full-Stack Architecture Overview
- **Screen**: Show `docs/ARCHITECTURE.md` mermaid diagram or code structure in IDE.
- **Spoken Script**:
  > "Welcome to the technical walkthrough. WindForecast Analytics is built on a modern, decoupled full-stack architecture:
  > On the backend, we use Python 3.11 with FastAPI, Pandas, HTTPX, and Pydantic v2.
  > On the frontend, we built a responsive React 18 single-page application using Vite, TypeScript, and Recharts, styled with an enterprise CSS design system.
  > The system strictly enforces the principle of backend authority: all data ingestion, timezone normalization, decision-cutoff filtering, and mathematical accuracy calculations are computed authoritatively by pure Python modules—never hardcoded or approximated in the UI."

### 0:45–1:30 — Elexon Data Sources & Robust Ingestion
- **Screen**: Open `backend/app/services/elexon_client.py`.
- **Spoken Script**:
  > "Let's examine data ingestion in `elexon_client.py`. We connect directly to the official Elexon Insights Solution BMRS Stream APIs:
  > `FUELHH/stream` provides half-hourly outturn generation by fuel type.
  > `WINDFOR/stream` provides national wind generation forecasts.
  > Querying an entire month of multi-fuel records in a single stream request can cause network timeouts. Our client implements bounded time-window chunking, retrieving data in reliable 7-day windows with automatic exponential backoff retries.
  > To ensure high performance and resilience during offline evaluation or upstream API outages, retrieved records are cached locally to disk, with automatic fallback and transparent data source tracking."

### 1:30–2:15 — Data Cleaning & Decision-Time Cutoff Selection
- **Screen**: Open `backend/app/services/data_cleaner.py` and `forecast_selector.py`.
- **Spoken Script**:
  > "In `data_cleaner.py`, all timestamps are normalized into timezone-aware UTC datetime objects. For `FUELHH`, we apply a strict filter: `fuelType == 'WIND'`, immediately discarding all conventional and interconnect fuel types. Invalid or negative generation values are audited, and duplicate settlement periods are deterministically resolved by retaining the latest publication timestamp.
  > In `forecast_selector.py`, we implement the critical business rule for Day-Ahead purchasing decisions. For power delivered on day D, wholesale market orders close on day D-1. We calculate the gate closure cutoff—defaulting to 11:00 UTC D-1—and strictly filter forecasts to `publishTime <= cutoffTime`.
  > Among all eligible runs, we select the latest published forecast, recording the exact publication timestamp and lead time in hours. If no forecast was published prior to cutoff, the period is marked as missing—we never look ahead into future runs."

### 2:15–3:00 — Matching Engine & Mathematical Metrics
- **Screen**: Open `backend/app/services/matcher.py` and `backend/app/analytics/metrics.py`.
- **Spoken Script**:
  > "In `matcher.py`, forecasts and actuals are joined exclusively on the target delivery period timestamp `startTime`.
  > Because WINDFOR national forecasts are published at hourly resolution while FUELHH records actuals half-hourly, our outer join identifies exactly 744 matched periods out of 1,488 half-hours, with the remaining 744 audited as `MISSING_FORECAST`. We never fabricate or interpolate unobserved half-hours.
  > In `metrics.py`, we implemented pure, independently testable Python functions for signed error, MAE, RMSE, Mean Signed Error / Bias, Maximum Absolute Error, and Weighted Absolute Percentage Error. For percentage metrics, we enforce a conditional threshold of 100 MW on actuals to prevent mathematical division-by-zero singularities."

### 3:00–4:00 — Automated Testing Suite & Code Quality
- **Screen**: Terminal running `python -m pytest backend/tests -v` and `npm run test` in `frontend/`.
- **Spoken Script**:
  > "Quality engineering is central to this project. Let's run our test suites:
  > First, the backend Pytest suite: running `python -m pytest backend/tests -v`.
  > All 24 tests pass in 3.4 seconds. These tests verify hand-calculated mathematical examples, cutoff boundary conditions, post-cutoff forecast exclusion, duplicate resolution, and all FastAPI endpoints using mocked fixtures.
  > Next, on the frontend: running `npm run test`.
  > All 5 Vitest component tests pass cleanly. Furthermore, running `npm run build` verifies that the TypeScript codebase compiles with zero type errors or bundle issues."

### 4:00–5:00 — Docker Containerization, Deployment, & Engineering Trade-offs
- **Screen**: Show `docker-compose.yml`, `backend/Dockerfile`, and `frontend/Dockerfile`.
- **Spoken Script**:
  > "Finally, let's look at deployment.
  > We containerized both services with multi-stage Dockerfiles. The frontend is built with Node.js and served via lightweight Nginx Alpine on port 3000, while the backend runs FastAPI via Uvicorn on port 8000 with Docker health checks. Both services orchestrate seamlessly via `docker compose up --build`.
  > For production hosting, the React frontend is pre-configured for Vercel with SPA routing in `vercel.json`, and the backend includes a `Procfile` and environment configuration for Heroku or Render.
  > In terms of technical trade-offs: for a focused single-month dataset of ~1,500 periods, an in-memory Pandas pipeline with disk caching delivers sub-millisecond API response times without the maintenance or credential overhead of an external relational database.
  > WindForecast Analytics is fully tested, containerized, documented, and ready for production deployment. Thank you."

---

## YouTube Upload Metadata

- **Title**: WindForecast Analytics: UK National Wind Generation Day-Ahead Forecast Accuracy (MVP Demo)
- **Visibility**: Unlisted (accessible only via link)
- **Category**: Science & Technology
- **Tags**: `wind energy`, `energy trading`, `UK electricity market`, `Elexon BMRS`, `forecast accuracy`, `FastAPI`, `React`, `Docker`
- **Description**:
  ```text
  WindForecast Analytics MVP Demonstration
  National Wind Generation Day-Ahead Forecast Accuracy | UK | January 2026

  Timestamps:
  Part 1: Customer Presentation
  0:00 - Introduction & Commercial Electricity Market Context
  0:30 - Overview Dashboard: KPIs & Time-Series Outturn
  1:15 - Forecast Comparison & Publication Vintage History
  2:15 - Accuracy Metrics & Error Distribution
  3:15 - Data Explorer & Real Analyzed CSV Export
  4:15 - Commercial Findings & Business Impact

  Part 2: Technical Walkthrough
  4:45 - Architecture: FastAPI + React + TypeScript + Docker
  5:30 - Elexon BMRS API Ingestion (FUELHH & WINDFOR Streams)
  6:15 - Data Cleaning & Decision-Time Cutoff Selection (D-1 11:00 UTC)
  7:00 - Matching Engine & Pure Mathematical Metrics
  7:45 - Automated Test Suites (24 Pytest + 5 Vitest)
  8:45 - Docker Containerization & Deployment Architecture

  Repository: Public Anonymous GitHub Repository
  Datasets: Elexon BMRS FUELHH (WIND) and WINDFOR
  ```
