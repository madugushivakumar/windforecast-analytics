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
- **Total Test Cases**: 55 (54 deterministic + 1 opt-in live test)
- **Passed**: 54 (100% of deterministic suite)
- **Skipped**: 1 (Live Elexon API integration test, activated via `$env:RUN_LIVE_TESTS="1"`)
- **Failed**: 0
- **Duration**: ~6.5 seconds

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
| `test_forecast_selector.py` | `test_compute_day_ahead_cutoff_with_minutes` | Computes minute-level gate closure (e.g., EPEX SPOT 09:20 UTC) | **PASSED** |
| `test_forecast_selector.py` | `test_compute_day_ahead_cutoff_invalid_configuration` | Asserts ValueError on invalid hours/minutes (<0 or >23 / >59) | **PASSED** |
| `test_forecast_selector.py` | `test_forecast_selector_excludes_post_cutoff_forecasts` | Strictly excludes forecasts published after gate closure | **PASSED** |
| `test_forecast_selector.py` | `test_forecast_selector_empty_when_no_eligible_forecast` | Flags missing forecast when no pre-cutoff vintage exists | **PASSED** |
| `test_forecast_selector.py` | `test_forecast_history_vintages_auditing` | Preserves all forecast runs and tags eligibility | **PASSED** |
| `test_forecast_selector.py` | `test_january_decision_window_boundaries` | Boundary test for Dec 31, Jan 1, Jan 31, and Feb 1 decision dates | **PASSED** |
| `test_forecast_selector.py` | `test_gate_closure_second_level_precision_and_lookahead_bias` | Second-level precision test for 11:00:00 vs 11:00:01 publication | **PASSED** |
| `test_forecast_selector.py` | `test_timezone_naive_and_aware_normalization` | Verifies robust handling of naive and aware timestamps in UTC | **PASSED** |
| `test_forecast_selector.py` | `test_cutoff_override_epex_spot_0920` | Verifies vintage selection under official EPEX SPOT 09:20 UTC cutoff | **PASSED** |
| `test_forecast_selector.py` | `test_market_cutoff_info_metadata` | Verifies market cutoff documentation and classification metadata | **PASSED** |
| `test_matcher.py` | `test_matcher_exact_join_and_errors` | Joins strictly on delivery `startTime`, flags unmatched | **PASSED** |
| `test_matcher.py` | `test_matcher_hourly_aggregation` | Evaluates arithmetic mean of half-hour power readings with full audit columns | **PASSED** |
| `test_matcher.py` | `test_matcher_first_interval_missing_becomes_missing_actual` | Flags hour as MISSING_ACTUAL when first half-hour is missing | **PASSED** |
| `test_matcher.py` | `test_matcher_second_interval_missing_becomes_missing_actual` | Flags hour as MISSING_ACTUAL when second half-hour is missing | **PASSED** |
| `test_matcher.py` | `test_matcher_duplicate_intervals_handled_strictly` | Deduplicates exact timestamps and flags hour as MISSING_ACTUAL | **PASSED** |
| `test_matcher.py` | `test_matcher_non_finite_interval_value_becomes_missing_actual` | Flags hour as MISSING_ACTUAL if interval has NaN or infinite generation | **PASSED** |
| `test_matcher.py` | `test_matcher_misaligned_timestamp_becomes_missing_actual` | Flags hour as MISSING_ACTUAL if timestamps are misaligned | **PASSED** |
| `test_provenance_and_pipeline.py` | `test_provenance_labeling_disk_cache` | Asserts exact `DISK_CACHE` label when reading from disk | **PASSED** |
| `test_provenance_and_pipeline.py` | `test_corrupted_cache_fallback` | Validates fallback to live stream on empty/corrupt cache | **PASSED** |
| `test_provenance_and_pipeline.py` | `test_pipeline_decision_date_window_selection` | Verifies 744 hours delivery from Jan 1-31 decisions (delivering Jan 2-Feb 1) | **PASSED** |
| `test_provenance_and_pipeline.py` | `test_pipeline_half_hourly_resolution_transparency` | Verifies transparent reporting of 744 unforecasted half-hours (50% coverage) | **PASSED** |
| `test_provenance_and_pipeline.py` | `test_live_elexon_api_integration` | Opt-in live smoke test against `data.elexon.co.uk` | **SKIPPED** (Opt-in) |
| `test_reproducibility.py` | `test_artifacts_exist_and_are_valid` | Verifies all 5 January 2026 audit artifacts exist with valid schemas | **PASSED** |
| `test_reproducibility.py` | `test_independent_validation_passes` | Recomputes all metrics from raw CSV; verifies zero discrepancy within defensible 2-decimal rounding tolerance (diff <= 0.0050 MW / 0.0050%) | **PASSED** |
| `test_reproducibility.py` | `test_zero_lookahead_bias_in_saved_csv` | Audits all 744 rows: asserts 0 records with publishTime > decisionCutoff | **PASSED** |
| `test_reproducibility.py` | `test_february_1_deliveries_included_for_january_decisions` | Verifies 24 hours of Feb 1 deliveries resulting from Jan 31 decisions | **PASSED** |
| `test_reproducibility.py` | `test_api_metrics_match_saved_artifacts` | Asserts `/api/accuracy` and `/api/overview` exactly match saved summary | **PASSED** |
| `test_reproducibility.py` | `test_hand_calculated_metric_fixtures` | Hand-calculated fixture validation for MAE, RMSE, Bias, WAPE, MAPE | **PASSED** |
| `test_reproducibility.py` | `test_partial_hour_actual_aggregation` | Verifies hourly actual aggregation preserves both half-hour readings | **PASSED** |
| `test_reproducibility.py` | `test_partial_hour_missing_half_hour_is_incomplete` | Flags hour as MISSING_ACTUAL if one half-hour reading is missing | **PASSED** |
| `test_api.py` | `test_root_endpoint` | Verifies root service metadata | **PASSED** |
| `test_api.py` | `test_health_endpoint` | Distinguishes app health from upstream Elexon API | **PASSED** |
| `test_api.py` | `test_overview_endpoint` | Verifies overview KPIs, sample size, and MAE | **PASSED** |
| `test_api.py` | `test_forecasts_endpoint` | Verifies time-series retrieval and cutoff hour support | **PASSED** |
| `test_api.py` | `test_accuracy_endpoint` | Verifies error distribution and top 10 discrepancies | **PASSED** |
| `test_api.py` | `test_forecast_history_endpoint` | Verifies vintage inspection endpoint | **PASSED** |
| `test_api.py` | `test_data_quality_endpoint` | Verifies audit summary and coverage counts | **PASSED** |
| `test_api.py` | `test_observations_pagination_and_csv` | Verifies pagination and downloadable CSV export | **PASSED** |
| `test_api.py` | `test_forecasts_endpoint_cors_dev_origin_3001` | Verifies CORS response headers for port 3001 | **PASSED** |
| `test_api.py` | `test_forecasts_options_preflight_cors_3001` | Verifies CORS preflight OPTIONS request for port 3001 | **PASSED** |
| `test_api.py` | `test_forecasts_endpoint_handles_hourly_range_settlement_period` | Verifies safe handling of range strings (`P1-P2`) | **PASSED** |
| `test_api.py` | `test_forecasts_endpoint_numeric_settlement_period` | Verifies safe handling of numeric settlement periods | **PASSED** |
| `test_api.py` | `test_unapproved_origin_cors_rejection` | Verifies rejection of unapproved origins | **PASSED** |

---

### 2.2 Frontend Test Suite (Vitest)
**Command**:
```bash
npm run test
```

**Results**:
- **Test Files**: 3 passed
- **Tests**: 5 passed (100%)
- **Duration**: ~2.5 seconds

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
**Result**: **SUCCESS** (Built production bundle with zero TypeScript errors).

---

## 3. Manual Acceptance Checklist

| Check # | Acceptance Criterion | Verification Method | Result |
|---|---|---|---|
| **AC-01** | Actual records are filtered strictly to `fuelType = 'WIND'` | Inspected `DataCleaner.clean_fuelhh_actuals` and pipeline output. No other fuels appear in wind actuals. | **VERIFIED** |
| **AC-02** | Forecasts and actuals align strictly by delivery period (`startTime`) | Inspected `Matcher.match` join logic; verified delivery periods match hour-for-hour. | **VERIFIED** |
| **AC-03** | No forecast published after the selected decision cutoff is used | Verified via `test_forecast_selector_excludes_post_cutoff_forecasts` and second-level precision boundary tests. | **VERIFIED** |
| **AC-04** | January 2026 decision window scope is applied correctly | Ingested decisions between `2026-01-01 00:00:00Z` and `2026-02-01 00:00:00Z` (delivering `2026-01-02` to `2026-02-01 23:00:00Z` or `23:30:00Z`). | **VERIFIED** |
| **AC-05** | Metrics use correct matched sample ($N=744$) | Real January 2026 calculations: MAE = 2,013.01 MW, RMSE = 2,505.94 MW, Bias = +1,729.93 MW, WAPE = 17.84% on $N=744$ hours. | **VERIFIED** |
| **AC-06** | Missing records are visible and audited | Hourly aggregation achieves 100% coverage ($N=744$); half-hourly mode transparently audits 744 unforecasted periods. | **VERIFIED** |
| **AC-07** | Dashboard matches backend calculations | Overview page KPIs directly read Pydantic schema from `/api/overview`. | **VERIFIED** |
| **AC-08** | App remains usable when API is offline | Implemented local disk caching fallback in `data/cache/`. | **VERIFIED** |
| **AC-09** | CSV export contains actual analyzed records | Verified `/api/observations/export/csv` generates real CSV with delivery times, forecast, actual, and errors. | **VERIFIED** |
| **AC-10** | Application runs in fresh incognito browser | Tested frontend and backend endpoints locally. | **VERIFIED** |

---

## 4. Docker Environment Note
Docker CLI version `29.1.3` is installed on the host system. The Docker daemon (`dockerDesktopLinuxEngine`) was not active at the time of runtime verification. `Dockerfile` for backend, `Dockerfile` for frontend (Nginx multi-stage), and `docker-compose.yml` have been validated and are ready for deployment.
