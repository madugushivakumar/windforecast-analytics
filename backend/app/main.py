import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx

from app.core.config import settings
from app.api.endpoints import router as analytics_router
from app.services.pipeline import pipeline_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing WindForecast Analytics Backend...")
    # Optional pipeline pre-warming on startup
    try:
        logger.info("Pre-warming analytical dataset for January 2026...")
        pipeline_service.run_pipeline()
        logger.info("Analytics pipeline pre-warmed successfully.")
    except Exception as e:
        logger.warning(f"Initial pipeline warm-up encountered notice (will lazily load on demand): {e}")
    yield
    logger.info("Shutting down WindForecast Analytics Backend...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="GB National Wind Generation Day-Ahead Forecast Accuracy Analytics (Elexon BMRS)",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analytics_router)


@app.get("/", tags=["System"])
def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "documentation": "/docs",
        "health": "/health",
        "analysis_scope": "January 2026 GB Wind Day-Ahead Market",
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }


@app.get("/health", tags=["System"])
def health_check():
    """
    Distinguishes server availability from upstream Elexon data source health.
    """
    upstream_status = "UNKNOWN"
    upstream_latency_ms = None
    
    try:
        t0 = datetime.now()
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{settings.ELEXON_API_BASE_URL}/datasets/FUELHH?settlementDateFrom=2026-01-01&settlementDateTo=2026-01-01")
            upstream_latency_ms = round((datetime.now() - t0).total_seconds() * 1000, 1)
            if resp.status_code == 200:
                upstream_status = "HEALTHY"
            else:
                upstream_status = f"DEGRADED (HTTP {resp.status_code})"
    except Exception as exc:
        upstream_status = f"UNREACHABLE ({type(exc).__name__})"

    pipeline_ready = not pipeline_service.df_matched.empty

    return {
        "status": "HEALTHY",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "upstream_elexon_api": {
            "status": upstream_status,
            "latency_ms": upstream_latency_ms,
            "base_url": settings.ELEXON_API_BASE_URL
        },
        "pipeline": {
            "is_ready": pipeline_ready,
            "records_matched": len(pipeline_service.df_matched) if pipeline_ready else 0,
            "data_source": pipeline_service.data_source
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
