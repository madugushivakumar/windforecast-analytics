"""
Reproducible Analysis Script for WindForecast Analytics:
Executes the authoritative January 2026 Day-Ahead wind forecast evaluation,
preserves complete audit trails, generates machine-readable artifacts,
and runs an independent verification routine against the generated outputs.
"""

import sys
import os
import json
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import numpy as np
import pandas as pd

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.services.pipeline import pipeline_service
from app.services.forecast_selector import get_market_cutoff_info


def compute_file_hash(filepath: Path) -> str:
    """Computes SHA-256 hash of a file for manifest auditing."""
    if not filepath.exists():
        return "NOT_FOUND"
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_git_commit() -> str:
    """Retrieves current git commit hash if available."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(backend_dir.parent),
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT"


def run_reproducible_analysis(
    output_dir: Optional[Path] = None,
    cutoff_hour_utc: int = 11,
    cutoff_minute_utc: int = 0,
    window_type: str = "decision",
    resolution: str = "hourly"
) -> Dict[str, Any]:
    """
    Executes full pipeline and writes artifacts to output_dir.
    """
    if output_dir is None:
        output_dir = backend_dir.parent / "artifacts" / "january_2026"
    output_dir.mkdir(parents=True, exist_ok=True)

    execution_timestamp = datetime.now(timezone.utc).isoformat()
    logger_header = f"=== Reproducible Analysis Execution at {execution_timestamp} ==="
    print(logger_header)

    # 1. Execute Pipeline
    df_matched = pipeline_service.run_pipeline(
        target_year=2026,
        target_month=1,
        cutoff_hour_utc=cutoff_hour_utc,
        cutoff_minute_utc=cutoff_minute_utc,
        window_type=window_type,
        resolution=resolution,
        force_refresh=False
    )
    metrics = pipeline_service.compute_accuracy_metrics()
    dq = pipeline_service.dq_summary
    cutoff_info = get_market_cutoff_info(cutoff_hour_utc, cutoff_minute_utc)

    # 2. Generate Observation-level Analysis CSV
    csv_path = output_dir / "observations_analysis.csv"
    csv_rows = []
    for _, r in df_matched.iterrows():
        csv_rows.append({
            "delivery_start_time_utc": r["startTime"].isoformat() if hasattr(r["startTime"], "isoformat") else str(r["startTime"]),
            "settlement_date": str(r.get("settlementDate", "")),
            "settlement_period": str(r.get("settlementPeriod", "")),
            "decision_date": str(r.get("decision_date", "")),
            "decision_cutoff_utc": r["decision_cutoff"].isoformat() if pd.notna(r.get("decision_cutoff")) and hasattr(r["decision_cutoff"], "isoformat") else "",
            "selected_publish_time_utc": r["selected_publish_time"].isoformat() if pd.notna(r.get("selected_publish_time")) and hasattr(r["selected_publish_time"], "isoformat") else "",
            "forecast_mw": float(r["forecast_mw"]) if pd.notna(r.get("forecast_mw")) else None,
            "actual_mw": float(r["actual_mw"]) if pd.notna(r.get("actual_mw")) else None,
            "actual_hh0_mw": float(r["actual_hh0_mw"]) if pd.notna(r.get("actual_hh0_mw")) else None,
            "actual_hh1_mw": float(r["actual_hh1_mw"]) if pd.notna(r.get("actual_hh1_mw")) else None,
            "signed_error_mw": float(r["signed_error_mw"]) if pd.notna(r.get("signed_error_mw")) else None,
            "abs_error_mw": float(r["abs_error_mw"]) if pd.notna(r.get("abs_error_mw")) else None,
            "squared_error_mw2": float(r["squared_error_mw2"]) if pd.notna(r.get("squared_error_mw2")) else None,
            "lead_time_hours": float(r["lead_time_hours"]) if pd.notna(r.get("lead_time_hours")) else None,
            "evaluation_resolution": resolution,
            "status": str(r.get("status", ""))
        })
    df_csv = pd.DataFrame(csv_rows)
    df_csv.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"Generated CSV observations artifact: {csv_path.name} ({len(df_csv)} rows)")

    # 3. Generate Analysis Summary JSON
    summary_path = output_dir / "analysis_summary.json"
    summary_data = {
        "project": "WindForecast Analytics",
        "run_timestamp_utc": execution_timestamp,
        "target_period": "January 2026",
        "window_type": window_type,
        "window_description": "Decisions Jan 1 to Jan 31 delivering Jan 2 to Feb 1" if window_type == "decision" else "Deliveries Jan 1 to Jan 31",
        "decision_window_utc": {
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-02-01T00:00:00Z",
            "convention": "inclusive start, exclusive end"
        },
        "delivery_window_utc": {
            "start": "2026-01-02T00:00:00Z",
            "end": "2026-02-01T23:00:00Z" if resolution == "hourly" else "2026-02-01T23:30:00Z"
        },
        "evaluation_resolution": resolution,
        "resolution_description": "Hourly arithmetic mean power ((A00 + A30)/2 MW) vs 1-hour forecast" if resolution == "hourly" else "Half-hourly exact join",
        "effective_cutoff": {
            "hour_utc": cutoff_hour_utc,
            "minute_utc": cutoff_minute_utc,
            "rule_string": f"{cutoff_hour_utc:02d}:{cutoff_minute_utc:02d} UTC on Day D-1",
            "market_name": cutoff_info["market_name"],
            "type": cutoff_info["type"],
            "is_official_exchange_closure": cutoff_info["is_official_exchange_closure"],
            "description": cutoff_info["rule_description"],
            "source_url": cutoff_info["source_url"]
        },
        "data_provenance": {
            "overall": pipeline_service.data_source,
            "fuelhh_actuals": pipeline_service.client.get_dataset_provenance("FUELHH"),
            "windfor_forecasts": pipeline_service.client.get_dataset_provenance("WINDFOR")
        },
        "coverage": {
            "expected_periods": dq.total_expected_periods if dq else 744,
            "matched_periods": dq.matched_periods_count if dq else 744,
            "missing_forecasts": dq.missing_forecast_periods if dq else 0,
            "missing_actuals": dq.missing_actual_periods if dq else 0,
            "coverage_percentage": dq.data_coverage_percentage if dq else 100.0,
            "coverage_denominator": "744 delivery hours (31 days * 24 hours)" if resolution == "hourly" else "1488 half-hours (31 days * 48 periods)"
        },
        "metrics": {
            "sample_size": metrics.sample_size,
            "mae_mw": metrics.mae_mw,
            "rmse_mw": metrics.rmse_mw,
            "mean_signed_error_bias_mw": metrics.mean_signed_error_mw,
            "max_abs_error_mw": metrics.max_abs_error_mw,
            "min_signed_error_mw": metrics.min_signed_error_mw,
            "max_signed_error_mw": metrics.max_signed_error_mw,
            "error_std_mw": metrics.error_std_mw,
            "wape_percentage": metrics.wape_percentage,
            "conditional_mape_percentage": metrics.mape_percentage,
            "conditional_mape_threshold_mw": 100.0,
            "unit": "MW"
        },
        "validation_status": "PENDING_VERIFICATION"
    }

    # 4. Independent Recomputation & Cross-Check from Saved CSV
    val_report = run_independent_validation(csv_path, summary_data)
    summary_data["validation_status"] = "PASSED" if val_report["all_checks_passed"] else "FAILED"
    summary_data["independent_validation"] = val_report

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    print(f"Generated Analysis Summary artifact: {summary_path.name}")

    # 5. Generate Data Quality Report JSON
    dq_path = output_dir / "data_quality_report.json"
    dq_data = {
        "execution_timestamp_utc": execution_timestamp,
        "provenance": summary_data["data_provenance"],
        "record_counts": {
            "actual_records_fetched": dq.actual_records_fetched if dq else 0,
            "wind_actual_records_retained": dq.wind_actual_records_retained if dq else 0,
            "forecast_records_fetched": dq.forecast_records_fetched if dq else 0,
            "invalid_generation_records_discarded": dq.invalid_generation_records if dq else 0,
            "duplicate_records_resolved": dq.duplicate_records_resolved if dq else 0,
            "missing_actual_periods": dq.missing_actual_periods if dq else 0,
            "missing_forecast_periods": dq.missing_forecast_periods if dq else 0,
            "matched_periods": dq.matched_periods_count if dq else 0,
            "total_expected_periods": dq.total_expected_periods if dq else 744,
            "coverage_percentage": dq.data_coverage_percentage if dq else 100.0
        },
        "audit_notes": dq.notes if dq else []
    }
    with open(dq_path, "w", encoding="utf-8") as f:
        json.dump(dq_data, f, indent=2)
    print(f"Generated Data Quality report: {dq_path.name}")

    # 6. Generate Run Manifest JSON
    manifest_path = output_dir / "run_manifest.json"
    cache_files = list(settings.CACHE_DIR.glob("*.json"))
    manifest_data = {
        "manifest_version": "1.0",
        "execution_timestamp_utc": execution_timestamp,
        "git_commit": get_git_commit(),
        "command": f"python backend/reproduce_analysis.py --cutoff-hour {cutoff_hour_utc} --cutoff-minute {cutoff_minute_utc} --window {window_type} --resolution {resolution}",
        "python_version": sys.version,
        "input_cache_files": [
            {
                "file_name": p.name,
                "size_bytes": p.stat().st_size,
                "sha256": compute_file_hash(p)
            }
            for p in sorted(cache_files)
        ],
        "output_artifacts": {
            "analysis_summary_json": {"file": "analysis_summary.json", "sha256": compute_file_hash(summary_path)},
            "observations_analysis_csv": {"file": "observations_analysis.csv", "sha256": compute_file_hash(csv_path)},
            "data_quality_report_json": {"file": "data_quality_report.json", "sha256": compute_file_hash(dq_path)},
        }
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"Generated Run Manifest: {manifest_path.name}")

    # 7. Generate Validation Log Markdown
    log_path = output_dir / "validation_log.md"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"# Analysis Validation & Verification Log\n\n")
        f.write(f"- **Executed At**: `{execution_timestamp}`\n")
        f.write(f"- **Git Commit**: `{manifest_data['git_commit']}`\n")
        f.write(f"- **Cutoff**: `{summary_data['effective_cutoff']['rule_string']}` ({summary_data['effective_cutoff']['market_name']})\n")
        f.write(f"- **Resolution**: `{resolution}`\n")
        f.write(f"- **Window Type**: `{window_type}`\n")
        f.write(f"- **Overall Status**: **{summary_data['validation_status']}**\n\n")
        f.write(f"## Independent Verification Checks\n\n")
        f.write(f"| Check Description | Target Value | Computed Value | Status |\n")
        f.write(f"|---|---|---|---|\n")
        for check in val_report["checks"]:
            f.write(f"| {check['description']} | `{check['expected']}` | `{check['computed']}` | **{check['status']}** |\n")
        f.write(f"\n## Independent Metric Comparison\n\n")
        f.write(f"| Metric | Primary Pipeline | Independent CSV Recomputation | Difference | Status |\n")
        f.write(f"|---|---|---|---|---|\n")
        for m in val_report["metrics_comparison"]:
            f.write(f"| {m['metric']} | {m['pipeline_val']} | {m['recomputed_val']} | {m['diff']:.4f} | **{m['status']}** |\n")
    print(f"Generated Validation Log: {log_path.name}")

    return {
        "status": summary_data["validation_status"],
        "artifacts_dir": str(output_dir),
        "summary": summary_data
    }


def run_independent_validation(csv_path: Path, summary_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Performs completely independent mathematical recomputation directly from the exported CSV.
    Validates formulas, boundary integrity, lookahead bias prevention, and sample sizes.
    """
    df = pd.read_csv(csv_path)
    checks = []
    metrics_comp = []
    all_passed = True

    # Check 1: Record count
    total_rows = len(df)
    expected_rows = summary_data["coverage"]["expected_periods"]
    chk_rows = total_rows == expected_rows
    checks.append({
        "description": "Total Rows Equal Expected Comparison Periods",
        "expected": expected_rows,
        "computed": total_rows,
        "status": "PASS" if chk_rows else "FAIL"
    })
    if not chk_rows:
        all_passed = False

    # Check 2: Matched rows count
    df_matched = df[df["status"] == "MATCHED"].copy()
    matched_count = len(df_matched)
    expected_matched = summary_data["coverage"]["matched_periods"]
    chk_matched = matched_count == expected_matched
    checks.append({
        "description": "Matched Observations Count",
        "expected": expected_matched,
        "computed": matched_count,
        "status": "PASS" if chk_matched else "FAIL"
    })
    if not chk_matched:
        all_passed = False

    # Check 3: Lookahead bias check (publishTime <= decision_cutoff for 100% of matched records)
    pub_series = pd.to_datetime(df_matched["selected_publish_time_utc"], utc=True)
    cutoff_series = pd.to_datetime(df_matched["decision_cutoff_utc"], utc=True)
    lookahead_violations = int((pub_series > cutoff_series).sum())
    chk_lookahead = lookahead_violations == 0
    checks.append({
        "description": "Zero Lookahead Bias (publishTime <= decisionCutoff for all records)",
        "expected": 0,
        "computed": lookahead_violations,
        "status": "PASS" if chk_lookahead else "FAIL"
    })
    if not chk_lookahead:
        all_passed = False

    # Check 4: Decision window boundary check (all decision dates strictly in Jan 2026)
    dec_dates = pd.to_datetime(df["decision_date"], format="%Y-%m-%d")
    out_of_bounds = int(((dec_dates < pd.Timestamp("2026-01-01")) | (dec_dates > pd.Timestamp("2026-01-31"))).sum())
    chk_dec = out_of_bounds == 0
    checks.append({
        "description": "Decision Dates Strictly in January 2026 (2026-01-01 to 2026-01-31)",
        "expected": 0,
        "computed": out_of_bounds,
        "status": "PASS" if chk_dec else "FAIL"
    })
    if not chk_dec:
        all_passed = False

    # Check 5: Independent metrics recomputation from raw numbers in CSV
    f = df_matched["forecast_mw"].values
    a = df_matched["actual_mw"].values
    errors = f - a

    indep_mae = float(np.mean(np.abs(errors)))
    indep_rmse = float(np.sqrt(np.mean(errors ** 2)))
    indep_bias = float(np.mean(errors))
    indep_max_abs = float(np.max(np.abs(errors)))
    indep_min_signed = float(np.min(errors))
    indep_max_signed = float(np.max(errors))
    indep_std_err = float(np.std(errors, ddof=1))
    indep_wape = float((np.sum(np.abs(errors)) / np.sum(a)) * 100.0)

    # Conditional MAPE: a >= 100
    mask_mape = a >= 100.0
    indep_mape = float(np.mean(np.abs(errors[mask_mape]) / a[mask_mape]) * 100.0)

    target_metrics = summary_data["metrics"]
    metrics_to_check = [
        ("MAE (MW)", target_metrics["mae_mw"], indep_mae),
        ("RMSE (MW)", target_metrics["rmse_mw"], indep_rmse),
        ("Mean Signed Error / Bias (MW)", target_metrics["mean_signed_error_bias_mw"], indep_bias),
        ("Max Absolute Error (MW)", target_metrics["max_abs_error_mw"], indep_max_abs),
        ("Min Signed Error (MW)", target_metrics["min_signed_error_mw"], indep_min_signed),
        ("Max Signed Error (MW)", target_metrics["max_signed_error_mw"], indep_max_signed),
        ("Error Std Dev (MW)", target_metrics["error_std_mw"], indep_std_err),
        ("WAPE (%)", target_metrics["wape_percentage"], indep_wape),
        ("Conditional MAPE (%)", target_metrics["conditional_mape_percentage"], indep_mape),
    ]

    for label, pipe_val, indep_val in metrics_to_check:
        diff = abs(pipe_val - indep_val)
        chk_pass = diff < 0.05
        if not chk_pass:
            all_passed = False
        metrics_comp.append({
            "metric": label,
            "pipeline_val": round(pipe_val, 2),
            "recomputed_val": round(indep_val, 2),
            "diff": diff,
            "status": "PASS" if chk_pass else "FAIL"
        })

    return {
        "all_checks_passed": all_passed,
        "checks": checks,
        "metrics_comparison": metrics_comp
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reproduce WindForecast Analytics January 2026 Evaluation")
    parser.add_argument("--cutoff-hour", type=int, default=11, help="Cutoff hour UTC (default: 11)")
    parser.add_argument("--cutoff-minute", type=int, default=0, help="Cutoff minute UTC (default: 0)")
    parser.add_argument("--window", type=str, default="decision", choices=["decision", "delivery"], help="Window type")
    parser.add_argument("--resolution", type=str, default="hourly", choices=["hourly", "half-hourly"], help="Resolution")
    args = parser.parse_args()

    result = run_reproducible_analysis(
        cutoff_hour_utc=args.cutoff_hour,
        cutoff_minute_utc=args.cutoff_minute,
        window_type=args.window,
        resolution=args.resolution
    )
    print("\nExecution Completed. Status:", result["status"])
    if result["status"] == "PASSED":
        sys.exit(0)
    else:
        sys.exit(1)
