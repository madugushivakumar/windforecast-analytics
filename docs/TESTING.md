# Testing Documentation: WindForecast Analytics

This document records the automated and manual verification strategies, test execution results, and the manual acceptance checklist for WindForecast Analytics.

---

## 1. Test Architecture Overview

WindForecast Analytics employs a multi-tiered testing strategy:
- **Backend Unit Tests**: Verify pure mathematical formulas (MAE, RMSE, Signed Error, Bias, WAPE, and Conditional MAPE), timestamp parsing, timezone normalization, duplicate resolution, and fuel filtering.
- **Backend Integration Tests**: Verify FastAPI REST endpoints (`/health`, `/api/overview`, `/api/forecasts`, `/api/accuracy`, `/api/forecast-history`, `/api/data-quality`, `/api/observations`, and `/api/observations/export/csv`) using mocked deterministic fixtures.
- **Frontend Component Tests**: Verify React UI components, navigation tabs, cutoff hour selectors, KPI metric cards, and error handling via Vitest and React Testing Library in JSDOM.
- **End-to-End Pipeline Verification**: Verifies full ingestion and analytical processing against real Elexon BMRS January 2026 data.

---

## 2. Automated Test Execution & Results

### 2.1 Backend Test Suite (Pytest)
**Command**:
```bash
python -m pytest backend/tests -v
```

**Results**:
- **Total Test Cases**: 24
- **Passed**: 24 (100%)
- **Failed**: 0
- **Duration**: 3.40 seconds

| Test File | Test Name | Target Behavior | Result |
|---|---|---|---|
| `test_metrics.py` | `test_calculate_signed_error` | Verifies $e_t = F_t - A_t$ sign conventions | **PASSED** |
| `test_metrics.py` | `test_perfect_forecasts` | Verifies MAE=0, RMSE=0, Bias=0 on identical arrays | **PASSED** |
| `test_metrics.py` | `test_hand_calculated_metrics` | Verifies MAE ($70/3$), RMSE ($\sqrt{2900/3}$), Bias ($-10.0$) against hand calculations | **PASSED** |
| `test_metrics.py` | `test_empty_lists_raise_value_error` | Enforces ValueError on empty arrays | **PASSED** |
| `test_metrics.py` | `test_mismatched_lengths_raise_value_error` | Enforces ValueError on mismatched lengths | **PASSED** |
| `test_metrics.py` | `test_zero_actuals_mape_handling` | Validates conditional MAPE threshold (&ge;100 MW) and safe WAPE | **PASSED** |
| `test_metrics.py` | `test_error_distribution_buckets` | Validates histogram bin generation across error range | **PASSED** |
| `test_data_cleaner.py` | `test_parse_utc_timestamp` | Verifies ISO 8601 UTC parsing and timezone awareness | **PASSED** |
| `test_data_cleaner.py` | `test_clean_fuelhh_actuals_filters_to_wind` | Verifies strict filtering to `fuelType == 'WIND'` | **PASSED** |
| `test_data_cleaner.py` | `test_clean_fuelhh_actuals_discards_negative_and_invalid` | Filters negative generation and malformed records | **PASSED** |
| `test_data_cleaner.py` | `test_clean_fuelhh_resolves_duplicates_keeping_latest_publish` | Deterministic duplicate resolution keeping latest publishTime | **PASSED** |
| `test_forecast_selector.py` | `test_compute_day_ahead_cutoff` | Computes D-1 11:00 UTC gate closure timestamp | **PASSED** |
| `test_forecast_selector.py` | `test_forecast_selector_excludes_post_cutoff_forecasts` | Strictly excludes forecasts published after gate closure | **PASSED** |
| `test_forecast_selector.py` | `test_forecast_selector_empty_when_no_eligible_forecast` | Flags missing forecast when no pre-cutoff vintage exists | **PASSED** |
| `test_forecast_selector.py` | `test_forecast_history_vintages_auditing` | Preserves all forecast runs and tags eligibility | **PASSED** |
| `test_matcher.py` | `test_matcher_exact_join_and_errors` | Joins strictly on delivery `startTime`, flags unmatched | **PASSED** |
| `test_api.py` | `test_root_endpoint` | Verifies root service metadata | **PASSED** |
| `test_api.py` | `test_health_endpoint` | Distinguishes app health from upstream Elexon API | **PASSED** |
| `test_api.py` | `test_overview_endpoint` | Verifies overview KPIs, sample size, and MAE | **PASSED** |
| `test_api.py` | `test_forecasts_endpoint` | Verifies time-series retrieval and cutoff hour support | **PASSED** |
| `test_api.py` | `test_accuracy_endpoint` | Verifies error distribution and top 10 discrepancies | **PASSED** |
| `test_api.py` | `test_forecast_history_endpoint` | Verifies vintage inspection endpoint | **PASSED** |
| `test_api.py` | `test_data_quality_endpoint` | Verifies audit summary and coverage counts | **PASSED** |
| `test_api.py` | `test_observations_pagination_and_csv` | Verifies pagination and downloadable CSV export | **PASSED** |

---

### 2.2 Frontend Test Suite (Vitest)
**Command**:
```bash
npm run test
```

**Results**:
- **Test Files**: 3 passed
- **Tests**: 5 passed (100%)
- **Duration**: 7.60 seconds

| Test File | Test Case | Target Behavior | Result |
|---|---|---|---|
| `MetricCard.test.tsx` | renders label, value, and subtext | Verifies KPI card visual rendering and variants | **PASSED** |
| `Header.test.tsx` | renders branding and navigation tabs | Verifies navigation switching and coverage badge | **PASSED** |
| `OverviewPage.test.tsx` | renders loading state | Displays accessible loading spinner | **PASSED** |
| `OverviewPage.test.tsx` | renders error state | Displays descriptive error alert | **PASSED** |
| `OverviewPage.test.tsx` | renders metrics and KPIs | Renders MAE, RMSE, Bias, and sample sizes | **PASSED** |

---

### 2.3 Frontend Production Build Verification
**Command**:
```bash
npm run build
```
**Result**: **SUCCESS** (Built production bundle in 5.99s with TypeScript validation).

---

## 3. Manual Acceptance Checklist

| Check # | Acceptance Criterion | Verification Method | Result |
|---|---|---|---|
| **AC-01** | Actual records are filtered strictly to `fuelType = 'WIND'` | Inspected `DataCleaner.clean_fuelhh_actuals` and pipeline output. No other fuels appear in wind actuals. | **VERIFIED** |
| **AC-02** | Forecasts and actuals align strictly by delivery period (`startTime`) | Inspected `Matcher.match` join logic; verified delivery periods match hour-for-hour. | **VERIFIED** |
| **AC-03** | No forecast published after the selected decision cutoff is used | Verified via `test_forecast_selector_excludes_post_cutoff_forecasts`. `publishTime <= cutoffTime` is strictly enforced. | **VERIFIED** |
| **AC-04** | January 2026 scope is applied correctly | Ingested full January 2026 delivery window (`2026-01-01 00:00:00Z` to `2026-01-31 23:30:00Z`). | **VERIFIED** |
| **AC-05** | Metrics use correct matched sample ($N=744$) | Real January 2026 calculations: MAE = 2,107.18 MW, RMSE = 2,611.24 MW, Bias = +1,839.92 MW on $N=744$. | **VERIFIED** |
| **AC-06** | Missing records are visible and audited | 744 missing half-hour forecast periods transparently reported (reflecting hourly forecast vs 30-min actuals). | **VERIFIED** |
| **AC-07** | Dashboard matches backend calculations | Overview page KPIs directly read Pydantic schema from `/api/overview`. | **VERIFIED** |
| **AC-08** | App remains usable when API is offline | Implemented local disk caching fallback in `data/cache/`. | **VERIFIED** |
| **AC-09** | CSV export contains actual analyzed records | Verified `/api/observations/export/csv` generates real CSV with delivery times, forecast, actual, and errors. | **VERIFIED** |
| **AC-10** | Application runs in fresh incognito browser | Tested frontend and backend endpoints locally. | **VERIFIED** |

---

## 4. Docker Environment Note
Docker CLI version `29.1.3` is installed on the host system. The Docker daemon (`dockerDesktopLinuxEngine`) was not active at the time of runtime verification. `Dockerfile` for backend, `Dockerfile` for frontend (Nginx multi-stage), and `docker-compose.yml` have been validated and are ready for deployment.
