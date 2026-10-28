# Data Dictionary: WindForecast Analytics

This document defines the schema, data types, units, and transformation rules for all datasets ingested from Elexon BMRS Insights Solution and processed in WindForecast Analytics.

---

## 1. Upstream Dataset: FUELHH (Actual Generation)
**Provider**: Elexon BMRS (Insights Solution API)  
**Endpoint**: `/datasets/FUELHH/stream` and `/datasets/FUELHH`  
**Description**: Half-hourly outturn generation (actual power delivered to the GB transmission system) broken down by fuel type.

| Field Name | Raw Type | Target Type | Units | Description & Transformation Rules |
|---|---|---|---|---|
| `dataset` | string | string | - | Always `"FUELHH"`. Used for source identification. |
| `publishTime` | string (ISO 8601) | datetime (UTC) | UTC timestamp | Timestamp when the actual outturn reading was published by Elexon/National Grid ESO. |
| `startTime` | string (ISO 8601) | datetime (UTC) | UTC timestamp | **Primary Key**: Start time of the 30-minute settlement period during which electricity was delivered. Parsed to UTC-aware datetime. |
| `settlementDate` | string (YYYY-MM-DD) | date | - | Calendar date to which the settlement period belongs (in Great Britain local market terms). |
| `settlementPeriod` | integer | integer | - | Settlement period number within the settlement day (normally 1 to 48; 46 or 50 during clock changes). |
| `fuelType` | string | string | - | Categorical fuel type identifier. **Filtering Rule**: Retain only records where `fuelType == "WIND"`. All other fuels (`BIOMASS`, `NUCLEAR`, `CCGT`, etc.) are discarded from wind analysis. |
| `generation` | integer/float | float | Megawatts (MW) | Total actual generation produced by GB wind farms connected to the transmission system. Must be non-negative ($\ge 0.0$). If null or negative, flagged as invalid. |

---

## 2. Upstream Dataset: WINDFOR (Forecast Generation)
**Provider**: Elexon BMRS (Insights Solution API)  
**Endpoint**: `/datasets/WINDFOR/stream` and `/datasets/WINDFOR`  
**Description**: Wind generation forecasts produced by the National Energy System Operator (NESO) and published via Elexon at periodic intervals.

| Field Name | Raw Type | Target Type | Units | Description & Transformation Rules |
|---|---|---|---|---|
| `dataset` | string | string | - | Always `"WINDFOR"`. |
| `publishTime` | string (ISO 8601) | datetime (UTC) | UTC timestamp | **Vintage Identifier**: The exact timestamp when this forecast run was published. Critical for decision-time eligibility filtering. Must satisfy `publishTime <= cutoffTime`. |
| `startTime` | string (ISO 8601) | datetime (UTC) | UTC timestamp | **Target Delivery Timestamp**: The start time of the target 30-minute or 1-hour interval for which wind generation is predicted. |
| `generation` | integer/float | float | Megawatts (MW) | Forecasted wind generation value. Must be non-negative ($\ge 0.0$). |

---

## 3. Matched Analysis Schema (Analytical Observation)
Produced by joining the latest eligible WINDFOR record with the FUELHH WIND record on `startTime`.

| Analytical Field | Type | Units | Calculation / Semantics |
|---|---|---|---|
| `delivery_start_time` | datetime (UTC) | ISO 8601 UTC | Matches `startTime` of delivery period. |
| `settlement_date` | string (YYYY-MM-DD) | - | Target delivery date. |
| `settlement_period` | integer | - | Target delivery half-hour period (1–48). |
| `decision_date` | string (YYYY-MM-DD) | - | Date on which the Day-Ahead purchasing decision was taken ($D-1$). |
| `decision_cutoff` | datetime (UTC) | ISO 8601 UTC | Gate closure timestamp (e.g. 11:00 UTC on $D-1$). |
| `selected_publish_time` | datetime (UTC) | ISO 8601 UTC | Publication timestamp of the forecast actually selected ($\le \text{decision\_cutoff}$). |
| `lead_time_hours` | float | Hours | Duration between forecast publication and delivery start: $(\text{startTime} - \text{publishTime})$ in hours. |
| `forecast_mw` | float | MW | Forecasted generation ($F_t$). |
| `actual_mw` | float | MW | Delivered actual wind generation ($A_t$). |
| `signed_error_mw` | float | MW | $e_t = F_t - A_t$. Positive = Over-forecast; Negative = Under-forecast. |
| `abs_error_mw` | float | MW | $|e_t| = |F_t - A_t|$. |
| `squared_error_mw2` | float | $\text{MW}^2$ | $(F_t - A_t)^2$. |
| `status` | string | - | `"MATCHED"`, `"MISSING_FORECAST"`, `"MISSING_ACTUAL"`, `"INVALID_VALUE"`. |

---

## 4. Aggregate Metric Definitions
- **Matched Observations ($N$)**: Total count of delivery periods having both a valid, eligible forecast and a valid actual reading.
- **Mean Absolute Error (MAE)**:
  $$\text{MAE} = \frac{1}{N} \sum_{t=1}^N |F_t - A_t| \quad [\text{MW}]$$
- **Root Mean Squared Error (RMSE)**:
  $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{t=1}^N (F_t - A_t)^2} \quad [\text{MW}]$$
- **Mean Signed Error / Bias**:
  $$\text{Bias} = \frac{1}{N} \sum_{t=1}^N (F_t - A_t) \quad [\text{MW}]$$
- **Maximum Absolute Error**:
  $$\text{MaxAbsErr} = \max_{t} |F_t - A_t| \quad [\text{MW}]$$
- **Mean Absolute Percentage Error (MAPE)**:
  $$\text{MAPE} = \frac{1}{N_{\text{valid}}} \sum_{t \in \{t \mid A_t > \tau\}} \frac{|F_t - A_t|}{A_t} \times 100\%$$
  *Policy*: Threshold $\tau = 100 \text{ MW}$ to avoid division by near-zero actuals; explicitly documented and never displayed without qualification.
