# Data Assumptions & Market Rule Documentation: WindForecast Analytics

This document records all domain assumptions, market rules, timestamp interpretations, and potential data limitations applied in the WindForecast Analytics platform.

---

## 1. Scope & Decision Time Semantics (January 2026)
### The Business Challenge
In the UK wholesale power market, utilities purchase electricity on day-ahead power exchanges (e.g., EPEX SPOT Day-Ahead Auction and Nord Pool GB).
For power delivered on delivery date $D$, market participants submit binding price/volume orders on the morning of day $D-1$.

### Official Market Gate Closures vs. Operational Modelling Assumptions
Authoritative market research confirms the following official published gate closures and forecast cycles:
1. **Official EPEX SPOT GB 60min Day-Ahead Auction**:
   - Publisher: EPEX SPOT SE (`https://www.epexspot.com/en/market-data`)
   - Order Book Gate Closure: **09:20 GMT/UTC** daily on Day $D-1$. Auction results published from 09:30 GMT.
2. **Official Nord Pool GB Day-Ahead Auction (N2EX)**:
   - Publisher: Nord Pool European Market (`https://www.nordpoolgroup.com/trading/Day-ahead-trading/Auction-GB/`)
   - Order Book Gate Closure: **09:50 GMT/UTC** (10:50 CET) daily on Day $D-1$. Auction results published by 10:00 GMT.
3. **EPEX SPOT GB 30min Day-Ahead Auction**:
   - Order Book Gate Closure: **15:30 GMT/UTC** daily on Day $D-1$.
4. **Continental Single Day-Ahead Coupling (SDAC)**:
   - Order Book Gate Closure: **12:00 CET** (**11:00 UTC** in winter).
5. **NESO National WINDFOR Forecast Publication Schedule**:
   - National Grid ESO (NESO) publishes updated national wind generation forecasts via Elexon BMRS up to 8 times daily at approximately: **03:30, 05:30, 08:30, 10:30, 12:30, 16:30, 19:30, and 23:30 GMT/UTC**.

### Workflow Decision & Implemented Cutoff Configuration
- **Default Operational Assumption**: **11:00:00 UTC on Day $D-1$**.
  - This models a commercial utility's late-morning procurement decision window (aligned with the European SDAC reference).
  - Crucially, an 11:00 UTC cutoff allows capturing the latest **10:30 UTC NESO forecast update**, providing procurement desks with the freshest meteorological forecast prior to midday trading operations.
- **Configurable Cutoff Support**: The platform allows traders and auditors to configure any cutoff hour (0-23) and minute (0-59) via `--cutoff-hour` and `--cutoff-minute` (or API query params `cutoff_hour` and `cutoff_minute`).
  - Example: Overriding to the official **EPEX SPOT GB 60min Auction closure at 09:20 UTC** evaluates the earlier **08:30 UTC NESO forecast update** (yielding MAE = 2,038.91 MW, RMSE = 2,504.76 MW, Bias = +1,747.89 MW, WAPE = 18.07%).
  - At the **11:00 UTC operational cutoff**, the latest eligible forecast is the **10:30 UTC NESO update** (yielding MAE = 2,013.01 MW, RMSE = 2,505.94 MW, Bias = +1,729.93 MW, WAPE = 17.84%).
  - The API response explicitly returns structured `cutoff_info` metadata clarifying whether the active cutoff is an official exchange closure or an operational modelling assumption.

### The Implementation Rule
1. For every hourly or half-hourly delivery period on delivery day $D$ ($t \in D$):
   - The decision date is $D-1$.
   - The decision cutoff timestamp is set to $T_{\text{cutoff}} = (D-1) \text{ at } H_{\text{cutoff}}:M_{\text{cutoff}}:00\text{ UTC}$.
2. **Forecast Eligibility**:
   - Only forecasts with `publishTime <= T_cutoff` are eligible.
   - Any forecast published strictly after `T_cutoff` (`publishTime > T_cutoff`) is excluded to prevent lookahead bias.
3. **Vintage Selection**:
   - Among all eligible forecasts for delivery period $t$, the system selects the forecast with the maximum (latest) `publishTime`.
   - The selected `publishTime` is preserved in every record for auditing and transparency.
4. **January 2026 Boundary Handling**:
   - Purchasing decisions made in January 2026 span decision dates from **2026-01-01** through **2026-01-31** (exclusive of February 1, 00:00 UTC).
   - Under day-ahead rules, these decisions procure power delivered from **2026-01-02 00:00 UTC** (decided on 2026-01-01) through **2026-02-01 23:00 UTC** (decided on 2026-01-31).
   - Decisions executed on December 31, 2025 (delivering January 1, 2026) are correctly identified as December 2025 purchasing decisions.
   - In the analytics views, users can explore either:
     - **Decision Window (Primary)**: All purchasing decisions executed in January 2026 (744 hourly delivery periods from Jan 2 to Feb 1).
     - **Delivery Window (Alternative)**: Delivery periods occurring strictly within January 2026 (Jan 1 to Jan 31).

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
