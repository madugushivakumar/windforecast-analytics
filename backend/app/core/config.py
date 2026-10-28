from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "WindForecast Analytics"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Elexon BMRS API
    ELEXON_API_BASE_URL: str = "https://data.elexon.co.uk/bmrs/api/v1"
    ELEXON_REQUEST_TIMEOUT_SECONDS: float = 30.0
    ELEXON_MAX_RETRIES: int = 3
    ELEXON_CHUNK_DAYS: int = 7
    
    # Default Analysis Parameters
    TARGET_YEAR: int = 2026
    TARGET_MONTH: int = 1
    DEFAULT_CUTOFF_HOUR_UTC: int = 11  # Default operational decision cutoff hour
    DEFAULT_CUTOFF_MINUTE_UTC: int = 0  # Default operational decision cutoff minute
    DEFAULT_CUTOFF_TYPE: str = "operational_modelling_assumption"
    DEFAULT_CUTOFF_DESCRIPTION: str = "Utility operational decision cutoff (11:00 UTC D-1; configurable modelling assumption)"
    
    # Data & Cache Directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    CACHE_DIR: Path = BASE_DIR / "data" / "cache"
    ENABLE_CACHE: bool = True
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "*"
    ]

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


settings = Settings()
