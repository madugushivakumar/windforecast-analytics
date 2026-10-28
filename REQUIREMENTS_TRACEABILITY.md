# Requirements Traceability Matrix: WindForecast Analytics

This document maps every requirement from the Master Project Build Prompt to its implementation files, automated test cases, and deliverables.

| Req ID | Requirement Description | Implementation Component / File | Verification & Test File | Deliverable Status |
|---|---|---|---|---|
| **REQ-01** | National-level wind generation focus | `backend/app/services/pipeline.py` | `backend/tests/test_api.py` | **VERIFIED** |
| **REQ-02** | Official Elexon API integration (FUELHH & WINDFOR streams) | `backend/app/services/elexon_client.py` | Live stream ingestion & test suites | **VERIFIED** |
| **REQ-03** | Filter actual generation to `fuelType = 'WIND'` | `backend/app/services/data_cleaner.py` | `backend/tests/test_data_cleaner.py` | **VERIFIED** |
| **REQ-04** | Target purchasing decisions executed in January 2026 (delivering Jan 2 to Feb 1) | `backend/app/services/pipeline.py`, `backend/app/core/config.py` | Verified decision-window filtering & boundary tests | **VERIFIED** |
| **REQ-05** | Preserve and use delivery timestamp `startTime` | `backend/app/schemas/observation.py`, `data_cleaner.py` | `backend/tests/test_data_cleaner.py` | **VERIFIED** |
| **REQ-06** | Preserve and use forecast publication timestamp `publishTime` | `backend/app/schemas/observation.py`, `data_cleaner.py` | `backend/tests/test_data_cleaner.py` | **VERIFIED** |
| **REQ-07** | Use generation value `generation` (MW) | `backend/app/schemas/observation.py` | `backend/tests/test_data_cleaner.py` | **VERIFIED** |
| **REQ-08** | Match forecasts and actuals (hourly power arithmetic mean & half-hourly mode) | `backend/app/services/matcher.py` | `backend/tests/test_matcher.py` | **VERIFIED** |
| **REQ-09** | Select latest eligible forecast published before decision cutoff | `backend/app/services/forecast_selector.py` | `backend/tests/test_forecast_selector.py` | **VERIFIED** |
| **REQ-10** | Configurable day-ahead market cutoff rules | `backend/app/services/forecast_selector.py`, `backend/app/core/config.py` | `backend/tests/test_forecast_selector.py` | **VERIFIED** |
| **REQ-11** | No fabrication of data, missing values, or future lookahead | `backend/app/services/data_cleaner.py`, `forecast_selector.py` | `backend/tests/test_data_cleaner.py` | **VERIFIED** |
| **REQ-12** | Pure mathematical forecast accuracy functions (MAE, RMSE, Signed Error, Bias) | `backend/app/analytics/metrics.py` | `backend/tests/test_metrics.py` | **VERIFIED** |
| **REQ-13** | Safe zero-actual handling without misleading MAPE infinities | `backend/app/analytics/metrics.py` | `backend/tests/test_metrics.py` | **VERIFIED** |
| **REQ-14** | Data Quality summaries (counts, invalid records, missing periods, duplicates) | `backend/app/services/data_cleaner.py`, `app/api/endpoints.py` | `backend/tests/test_api.py` | **VERIFIED** |
| **REQ-15** | FastAPI backend with documented REST endpoints | `backend/app/main.py`, `backend/app/api/endpoints.py` | `backend/tests/test_api.py` | **VERIFIED** |
| **REQ-16** | Interactive Swagger / OpenAPI docs & Health check endpoints | `backend/app/main.py` | `backend/tests/test_api.py` | **VERIFIED** |
| **REQ-17** | React frontend with modern responsive enterprise design | `frontend/src/App.tsx`, `frontend/src/index.css` | `npm run build` & Vitest | **VERIFIED** |
| **REQ-18** | Page A: Overview Dashboard with KPIs & Time-Series Chart | `frontend/src/pages/OverviewPage.tsx` | `frontend/src/tests/OverviewPage.test.tsx` | **VERIFIED** |
| **REQ-19** | Page B: Forecast Comparison & Vintage Analysis | `frontend/src/pages/ForecastComparisonPage.tsx` | Vitest & Component review | **VERIFIED** |
| **REQ-20** | Page C: Accuracy Analysis & Error Distribution | `frontend/src/pages/AccuracyPage.tsx` | Vitest & Component review | **VERIFIED** |
| **REQ-21** | Page D: Data Explorer with sorting, filtering, and real CSV Export | `frontend/src/pages/DataExplorerPage.tsx` | API test & Component review | **VERIFIED** |
| **REQ-22** | Centralized API client and environment configuration | `frontend/src/services/api.ts` | Vitest & Component review | **VERIFIED** |
| **REQ-23** | Automated backend unit & integration tests | `backend/tests/` | Pytest runner (31 passed, 1 skipped) | **VERIFIED** |
| **REQ-24** | Automated frontend component tests | `frontend/src/tests/` | Vitest runner (5 passed) | **VERIFIED** |
| **REQ-25** | Dockerfile for backend & multi-stage Dockerfile for frontend | `backend/Dockerfile`, `frontend/Dockerfile` | Docker syntax & multi-stage config | **VERIFIED** |
| **REQ-26** | Docker Compose orchestration | `docker-compose.yml` | Compose configuration | **VERIFIED** |
| **REQ-27** | Production deployment instructions (Vercel + Python host / Heroku) | `docs/DEPLOYMENT.md` | Deployment guide | **VERIFIED** |
| **REQ-28** | Complete project documentation | `docs/ARCHITECTURE.md`, `DATA_DICTIONARY.md`, `DATA_ASSUMPTIONS.md`, `TESTING.md`, `README.md` | Complete & reviewed | **VERIFIED** |
| **REQ-29** | Complete 10-minute Video Demo Script (Customer + Technical) | `docs/VIDEO_SCRIPT.md` | Complete timed script | **VERIFIED** |
| **REQ-30** | Final submission checklist & anonymous repo preparation | `docs/SUBMISSION_CHECKLIST.md` | Complete checklist | **VERIFIED** |
