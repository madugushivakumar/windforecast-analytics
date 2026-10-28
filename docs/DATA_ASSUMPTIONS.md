# Data Assumptions & Market Rule Documentation: WindForecast Analytics

This document records all domain assumptions, market rules, timestamp interpretations, and potential data limitations applied in the WindForecast Analytics platform.

---

## 1. Scope & Decision Time Semantics (January 2026)
### The Business Challenge
In the UK wholesale power market, utilities purchase electricity on day-ahead power exchanges (e.g., EPEX SPOT Day-Ahead Auction and Nord Pool GB).
For power delivered on delivery date $D$, market participants submit binding price/volume orders on the morning of day $D-1$.
The order book gate closure takes place at:
- **Primary Auction Cutoff**: **11:00 UTC** (12:00 CET/BST) on day $D-1$.
- **Alternative Auction Cutoff**: **12:00 UTC** (Nord Pool / GB Auction 2).

### The Implementation Rule
1. For every half-hour delivery period on delivery day $D$ ($t \in D$):
   - The decision date is $D-1$.
   - The decision cutoff timestamp is set to $T_{\text{cutoff}} = (D-1) \text{ at 11:00:00 UTC}$ (configurable to 12:00 UTC or Intraday horizons).
2. **Forecast Eligibility**:
   - Only forecasts with `publishTime <= T_cutoff` are eligible.
   - Any forecast published after `T_cutoff` is excluded because a trader placing day-ahead auction orders could not have observed future information.
3. **Vintage Selection**:
   - Among all eligible forecasts for delivery period $t$, the system selects the forecast with the maximum (latest) `publishTime`.
   - The selected `publishTime` is preserved in every record for auditing and transparency.
4. **January 2026 Boundary Handling**:
   - Purchasing decisions made in January 2026 span decision dates from **2026-01-01** through **2026-01-31**.
   - These decisions procure power delivered from **2026-01-01 00:00 UTC** (decided on 2025-12-31 at 11:00 UTC) through **2026-02-01 23:30 UTC** (decided on 2026-01-31 at 11:00 UTC).
   - In the analytics views, users can explore either:
     - **Delivery Window**: All half-hours delivered between 2026-01-01 00:00 UTC and 2026-01-31 23:30 UTC.
     - **Decision Window**: All purchasing decisions executed in January 2026.

---

## 2. Timezone & Timestamp Handling
- All timestamps from Elexon BMRS (`startTime`, `publishTime`) are provided in ISO 8601 UTC format (`...Z`).
- In January, Great Britain operates on Greenwich Mean Time (GMT, UTC+0), meaning GB local clock time equals UTC.
- All internal processing in Python and Pandas uses timezone-aware UTC datetime objects (`datetime.timezone.utc`).
- The frontend formats timestamps in UTC (ISO 8601) with optional local conversion for user clarity.

---

## 3. Data Cleaning & Integrity Rules
1. **Actual Fuel Filtering**:
   - `FUELHH` contains generation for all GB generation sources. We apply an exact filter: `fuelType == "WIND"`.
   - All other fuel types (`BIOMASS`, `NUCLEAR`, `CCGT`, `OCGT`, etc.) are excluded from wind calculations.
2. **Deterministic Duplicate Resolution**:
   - If multiple `FUELHH` records exist for the identical `startTime` and `fuelType == "WIND"`, the record with the latest `publishTime` is retained, and a duplicate event is logged in the Data Quality report.
   - If multiple `WINDFOR` records exist for the identical `(startTime, publishTime)` tuple, identical duplicates are deduplicated.
3. **Missing Data Policy**:
   - If an actual generation reading is missing for a half-hour period, it is **never** filled with zero ($0.0 \text{ MW}$) unless an authoritative transmission record verifies zero generation. It is marked as `MISSING_ACTUAL`.
   - If no forecast was published prior to the decision cutoff for a delivery period, it is marked as `MISSING_FORECAST`.
   - Only periods with both valid forecast and actual observations (`MATCHED`) are included in MAE, RMSE, and Bias aggregations.
   - The Data Quality panel transparently displays the counts of matched, missing, and excluded periods.
4. **Zero Generation & MAPE Policy**:
   - Because actual wind generation can occasionally approach zero (during extreme lulls or curtailment), standard MAPE ($|F - A| / A$) produces mathematical singularities ($\infty$).
   - The platform calculates Mean Absolute Error (MAE in MW) and Root Mean Squared Error (RMSE in MW) as the authoritative commercial metrics.
   - Where MAPE is reported, observations where $A_t < 100 \text{ MW}$ are excluded or calculated via Weighted Absolute Percentage Error (WAPE = $\sum |e_t| / \sum A_t$), and the policy is explicitly surfaced in the UI.

---

## 4. API Resilience & Caching Strategy
1. **Live vs Cached Operation**:
   - The backend performs live queries against Elexon BMRS API (`data.elexon.co.uk`).
   - Responses are partitioned into 5-to-7 day chunks to avoid API timeouts.
   - To guard against transient Elexon API outages or network disruptions during evaluation, retrieved clean observations are cached locally to disk (`data/cache/`), enabling instantaneous sub-second queries and offline evaluation.
   - The API response explicitly returns a `source` indicator (`"LIVE_API"` or `"DISK_CACHE"`) and the timestamp of last successful retrieval.
