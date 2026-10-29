# Analysis Validation & Verification Log

- **Executed At**: `2026-10-29T09:03:57.013201+00:00`
- **Git Revision**: `b85f47dc2730bb639c3d53f573ce8dfa0a599c8c-dirty`
- **Cutoff**: `11:00 UTC on Day D-1` (Utility Operational Day-Ahead Decision Window)
- **Resolution**: `hourly`
- **Window Type**: `decision`
- **Overall Status**: **PASSED**

## Independent Verification Checks

| Check Description | Target Value | Computed Value | Status |
|---|---|---|---|
| Total Rows Equal Expected Comparison Periods | `744` | `744` | **PASS** |
| Matched Observations Count | `744` | `744` | **PASS** |
| Zero Lookahead Bias (publishTime <= decisionCutoff for all records) | `0` | `0` | **PASS** |
| Decision Dates Strictly in January 2026 (2026-01-01 to 2026-01-31) | `0` | `0` | **PASS** |

## Independent Metric Comparison

| Metric | Primary Pipeline | Independent CSV Recomputation | Difference | Tolerance | Status |
|---|---|---|---|---|---|
| MAE (MW) | 2013.01 | 2013.01 | 0.0019 | 0.0050 | **PASS** |
| RMSE (MW) | 2505.94 | 2505.94 | 0.0031 | 0.0050 | **PASS** |
| Mean Signed Error / Bias (MW) | 1729.93 | 1729.93 | 0.0015 | 0.0050 | **PASS** |
| Max Absolute Error (MW) | 6833.0 | 6833.0 | 0.0000 | 0.0001 | **PASS** |
| Min Signed Error (MW) | -4128.0 | -4128.0 | 0.0000 | 0.0001 | **PASS** |
| Max Signed Error (MW) | 6833.0 | 6833.0 | 0.0000 | 0.0001 | **PASS** |
| Error Std Dev (MW) | 1814.25 | 1814.25 | 0.0026 | 0.0050 | **PASS** |
| WAPE (%) | 17.84 | 17.84 | 0.0002 | 0.0050 | **PASS** |
| Conditional MAPE (%) | 21.61 | 21.61 | 0.0002 | 0.0050 | **PASS** |
