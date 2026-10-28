import io
import csv
from datetime import datetime, timezone
from typing import Optional
import pandas as pd
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import Response

from app.services.pipeline import pipeline_service
from app.analytics.metrics import compute_error_distribution
from app.schemas.metrics import OverviewResponse, AccuracyMetrics
from app.schemas.data_quality import DataQualitySummary

router = APIRouter(prefix="/api", tags=["Analytics"])


@router.get("/overview", response_model=OverviewResponse)
def get_overview(
    cutoff_hour: int = Query(11, ge=0, le=23, description="Decision cutoff hour UTC on Day D-1"),
    window_type: str = Query("decision", pattern="^(decision|delivery)$", description="decision (Jan 1-31 decisions) or delivery (Jan 1-31 delivery)"),
    resolution: str = Query("hourly", pattern="^(hourly|half-hourly)$", description="hourly (aggregated) or half-hourly"),
    force_refresh: bool = Query(False, description="Force re-fetch from upstream API")
):
    """
    Returns executive summary metrics, data coverage, and time-series preview
    for January 2026 Day-Ahead wind forecast performance.
    """
    try:
        pipeline_service.run_pipeline(
            cutoff_hour_utc=cutoff_hour,
            window_type=window_type,
            resolution=resolution,
            force_refresh=force_refresh
        )
        return pipeline_service.get_overview()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate overview analytics: {str(e)}")


@router.get("/forecasts")
def get_forecasts(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    cutoff_hour: int = Query(11, ge=0, le=23),
    window_type: str = Query("decision", pattern="^(decision|delivery)$"),
    resolution: str = Query("hourly", pattern="^(hourly|half-hourly)$")
):
    """
    Returns detailed forecast and actual time-series records for comparison charts.
    """
    pipeline_service.run_pipeline(
        cutoff_hour_utc=cutoff_hour,
        window_type=window_type,
        resolution=resolution
    )
    df = pipeline_service.df_matched.copy()
    
    if df.empty:
        return {"data": [], "total": 0}

    if start_date:
        try:
            start_dt = pd.to_datetime(start_date, utc=True)
            df = df[df["startTime"] >= start_dt]
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD.")
            
    if end_date:
        try:
            end_dt = pd.to_datetime(end_date, utc=True) + pd.Timedelta(days=1)
            df = df[df["startTime"] < end_dt]
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD.")

    results = []
    for _, r in df.iterrows():
        results.append({
            "startTime": r["startTime"].isoformat() if hasattr(r["startTime"], "isoformat") else str(r["startTime"]),
            "settlementDate": r.get("settlementDate"),
            "settlementPeriod": int(r["settlementPeriod"]) if pd.notna(r.get("settlementPeriod")) else None,
            "decisionCutoff": r["decision_cutoff"].isoformat() if pd.notna(r.get("decision_cutoff")) and hasattr(r["decision_cutoff"], "isoformat") else str(r.get("decision_cutoff")),
            "selectedPublishTime": r["selected_publish_time"].isoformat() if pd.notna(r.get("selected_publish_time")) and hasattr(r["selected_publish_time"], "isoformat") else str(r.get("selected_publish_time")),
            "leadTimeHours": float(r["lead_time_hours"]) if pd.notna(r.get("lead_time_hours")) else None,
            "forecast_mw": float(r["forecast_mw"]) if pd.notna(r.get("forecast_mw")) else None,
            "actual_mw": float(r["actual_mw"]) if pd.notna(r.get("actual_mw")) else None,
            "signed_error_mw": float(r["signed_error_mw"]) if pd.notna(r.get("signed_error_mw")) else None,
            "abs_error_mw": float(r["abs_error_mw"]) if pd.notna(r.get("abs_error_mw")) else None,
            "status": r.get("status")
        })

    return {
        "cutoff_hour_utc": cutoff_hour,
        "count": len(results),
        "data": results
    }


@router.get("/accuracy")
def get_accuracy_analysis(
    cutoff_hour: int = Query(11, ge=0, le=23),
    window_type: str = Query("decision", pattern="^(decision|delivery)$"),
    resolution: str = Query("hourly", pattern="^(hourly|half-hourly)$"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """
    Returns comprehensive quantitative accuracy metrics, error distributions,
    and extreme error periods.
    """
    pipeline_service.run_pipeline(
        cutoff_hour_utc=cutoff_hour,
        window_type=window_type,
        resolution=resolution
    )
    df = pipeline_service.df_matched.copy()

    if start_date:
        start_dt = pd.to_datetime(start_date, utc=True)
        df = df[df["startTime"] >= start_dt]
    if end_date:
        end_dt = pd.to_datetime(end_date, utc=True) + pd.Timedelta(days=1)
        df = df[df["startTime"] < end_dt]

    metrics = pipeline_service.compute_accuracy_metrics(df)
    
    # Matched rows for distributions
    matched_rows = df[df["status"] == "MATCHED"]
    errors = matched_rows["signed_error_mw"].dropna().astype(float).tolist()
    distribution = compute_error_distribution(errors, bucket_count=10)

    # Largest absolute error periods (top 10)
    top_errors = []
    if not matched_rows.empty:
        sorted_by_err = matched_rows.sort_values(by="abs_error_mw", ascending=False).head(10)
        for _, r in sorted_by_err.iterrows():
            top_errors.append({
                "startTime": r["startTime"].isoformat() if hasattr(r["startTime"], "isoformat") else str(r["startTime"]),
                "forecast_mw": float(r["forecast_mw"]),
                "actual_mw": float(r["actual_mw"]),
                "signed_error_mw": float(r["signed_error_mw"]),
                "abs_error_mw": float(r["abs_error_mw"]),
                "error_type": "OVER_FORECAST" if r["signed_error_mw"] > 0 else "UNDER_FORECAST"
            })

    return {
        "metrics": metrics,
        "error_distribution": distribution,
        "largest_error_periods": top_errors
    }


@router.get("/forecast-history")
def get_forecast_history(
    start_time: str = Query(..., description="Target delivery start time (ISO 8601 UTC)")
):
    """
    Returns all published forecast vintages for a specific delivery period.
    """
    try:
        dt = pd.to_datetime(start_time, utc=True).to_pydatetime()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid start_time ISO format.")

    if pipeline_service.df_clean_forecasts.empty:
        pipeline_service.run_pipeline()

    vintages = pipeline_service.selector.get_forecast_history_for_period(
        pipeline_service.df_clean_forecasts,
        dt
    )
    return {
        "delivery_start_time": start_time,
        "vintages_count": len(vintages),
        "vintages": vintages
    }


@router.get("/data-quality", response_model=DataQualitySummary)
def get_data_quality(
    window_type: str = Query("decision", pattern="^(decision|delivery)$"),
    resolution: str = Query("hourly", pattern="^(hourly|half-hourly)$"),
    cutoff_hour: int = Query(11, ge=0, le=23)
):
    """
    Returns data quality audit summary, record counts, and missing period counts.
    """
    pipeline_service.run_pipeline(
        cutoff_hour_utc=cutoff_hour,
        window_type=window_type,
        resolution=resolution
    )
    if pipeline_service.dq_summary is None:
        total_p = 744 if resolution == "hourly" else 1488
        return DataQualitySummary(
            actual_records_fetched=0,
            wind_actual_records_retained=0,
            forecast_records_fetched=0,
            invalid_generation_records=0,
            duplicate_records_resolved=0,
            missing_actual_periods=0,
            missing_forecast_periods=0,
            matched_periods_count=len(pipeline_service.df_matched),
            total_expected_periods=total_p,
            data_coverage_percentage=round((len(pipeline_service.df_matched) / total_p) * 100.0, 2),
            last_updated_utc=datetime.now(timezone.utc).isoformat(),
            data_source=pipeline_service.data_source,
            notes=["Data quality summary generated from active analysis dataset."]
        )
    return pipeline_service.dq_summary


@router.get("/observations")
def get_observations(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort_by: str = Query("startTime"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    status: Optional[str] = Query(None),
    min_error: Optional[float] = Query(None),
    max_error: Optional[float] = Query(None),
    cutoff_hour: int = Query(11, ge=0, le=23),
    window_type: str = Query("decision", pattern="^(decision|delivery)$"),
    resolution: str = Query("hourly", pattern="^(hourly|half-hourly)$")
):
    """
    Paginated, filterable observations for Data Explorer view.
    """
    pipeline_service.run_pipeline(
        cutoff_hour_utc=cutoff_hour,
        window_type=window_type,
        resolution=resolution
    )
    df = pipeline_service.df_matched.copy()

    if status:
        df = df[df["status"] == status.upper()]
    if min_error is not None:
        df = df[df["abs_error_mw"] >= min_error]
    if max_error is not None:
        df = df[df["abs_error_mw"] <= max_error]

    ascending = (sort_order == "asc")
    if sort_by in df.columns:
        df.sort_values(by=sort_by, ascending=ascending, inplace=True)
    else:
        df.sort_values(by="startTime", ascending=True, inplace=True)

    total_records = len(df)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged_df = df.iloc[start_idx:end_idx]

    rows = []
    for _, r in paged_df.iterrows():
        rows.append({
            "startTime": r["startTime"].isoformat() if hasattr(r["startTime"], "isoformat") else str(r["startTime"]),
            "settlementDate": r.get("settlementDate"),
            "settlementPeriod": str(r.get("settlementPeriod")) if pd.notna(r.get("settlementPeriod")) else None,
            "decisionCutoff": r["decision_cutoff"].isoformat() if pd.notna(r.get("decision_cutoff")) and hasattr(r["decision_cutoff"], "isoformat") else str(r.get("decision_cutoff")),
            "selectedPublishTime": r["selected_publish_time"].isoformat() if pd.notna(r.get("selected_publish_time")) and hasattr(r["selected_publish_time"], "isoformat") else str(r.get("selected_publish_time")),
            "forecast_mw": float(r["forecast_mw"]) if pd.notna(r.get("forecast_mw")) else None,
            "actual_mw": float(r["actual_mw"]) if pd.notna(r.get("actual_mw")) else None,
            "signed_error_mw": float(r["signed_error_mw"]) if pd.notna(r.get("signed_error_mw")) else None,
            "abs_error_mw": float(r["abs_error_mw"]) if pd.notna(r.get("abs_error_mw")) else None,
            "lead_time_hours": float(r["lead_time_hours"]) if pd.notna(r.get("lead_time_hours")) else None,
            "status": r.get("status")
        })

    return {
        "page": page,
        "page_size": page_size,
        "total_records": total_records,
        "total_pages": (total_records + page_size - 1) // page_size if total_records > 0 else 1,
        "records": rows
    }


@router.get("/observations/export/csv")
def export_observations_csv(
    cutoff_hour: int = Query(11, ge=0, le=23),
    window_type: str = Query("decision", pattern="^(decision|delivery)$"),
    resolution: str = Query("hourly", pattern="^(hourly|half-hourly)$")
):
    """
    Exports all matched observations for the analyzed period as a downloadable CSV.
    Contains real analyzed records directly from the pipeline.
    """
    pipeline_service.run_pipeline(
        cutoff_hour_utc=cutoff_hour,
        window_type=window_type,
        resolution=resolution
    )
    df = pipeline_service.df_matched.copy()

    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        "Delivery_Start_Time_UTC",
        "Settlement_Date",
        "Settlement_Period",
        "Decision_Date",
        "Decision_Cutoff_UTC",
        "Selected_Publish_Time_UTC",
        "Forecast_MW",
        "Actual_MW",
        "Signed_Error_MW",
        "Abs_Error_MW",
        "Squared_Error_MW2",
        "Lead_Time_Hours",
        "Status"
    ])

    for _, r in df.iterrows():
        writer.writerow([
            r["startTime"].isoformat() if hasattr(r["startTime"], "isoformat") else str(r["startTime"]),
            r.get("settlementDate", ""),
            r.get("settlementPeriod", ""),
            r.get("decision_date", ""),
            r["decision_cutoff"].isoformat() if pd.notna(r.get("decision_cutoff")) and hasattr(r["decision_cutoff"], "isoformat") else "",
            r["selected_publish_time"].isoformat() if pd.notna(r.get("selected_publish_time")) and hasattr(r["selected_publish_time"], "isoformat") else "",
            r["forecast_mw"] if pd.notna(r.get("forecast_mw")) else "",
            r["actual_mw"] if pd.notna(r.get("actual_mw")) else "",
            r["signed_error_mw"] if pd.notna(r.get("signed_error_mw")) else "",
            r["abs_error_mw"] if pd.notna(r.get("abs_error_mw")) else "",
            r.get("squared_error_mw2", ""),
            r["lead_time_hours"] if pd.notna(r.get("lead_time_hours")) else "",
            r.get("status", "")
        ])

    csv_data = output.getvalue()
    filename = f"windforecast_analytics_jan2026_{window_type}_{resolution}_cutoff_{cutoff_hour}utc.csv"
    
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
