import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("elexon_client")
logging.basicConfig(level=logging.INFO)


class ElexonClientError(Exception):
    """Raised when an error occurs during communication with Elexon API."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class ElexonApiClient:
    """
    Robust API client for Elexon BMRS Insights Solution REST & Stream endpoints.
    Handles bounded chunking, timeouts, retries, and local disk cache fallback.
    """
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        cache_dir: Optional[Path] = None,
    ):
        self.base_url = (base_url or settings.ELEXON_API_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.ELEXON_REQUEST_TIMEOUT_SECONDS
        self.max_retries = max_retries or settings.ELEXON_MAX_RETRIES
        self.cache_dir = cache_dir or settings.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Provenance tracking per dataset: dataset -> {"cache_hits": int, "api_fetches": int, "last_source": str}
        self.provenance: Dict[str, Dict[str, Any]] = {
            "FUELHH": {"cache_hits": 0, "api_fetches": 0, "last_source": "UNINITIALIZED", "last_retrieval_utc": None},
            "WINDFOR": {"cache_hits": 0, "api_fetches": 0, "last_source": "UNINITIALIZED", "last_retrieval_utc": None}
        }

    def _get_cache_path(self, dataset: str, start_iso: str, end_iso: str) -> Path:
        clean_start = start_iso.replace(":", "-")
        clean_end = end_iso.replace(":", "-")
        return self.cache_dir / f"{dataset}_{clean_start}_{clean_end}.json"

    def get_dataset_provenance(self, dataset: str) -> str:
        """
        Returns authoritative provenance label:
        'DISK_CACHE', 'LIVE_API', 'MIXED_CACHE_API', or 'UNINITIALIZED'.
        """
        prov = self.provenance.get(dataset, {})
        hits = prov.get("cache_hits", 0)
        fetches = prov.get("api_fetches", 0)
        if hits > 0 and fetches == 0:
            return "DISK_CACHE"
        elif fetches > 0 and hits == 0:
            return "LIVE_API"
        elif hits > 0 and fetches > 0:
            return "MIXED_CACHE_API"
        return prov.get("last_source", "UNINITIALIZED")

    def _request_with_retry(self, url: str, params: Dict[str, str]) -> List[Dict[str, Any]]:
        headers = {
            "User-Agent": "WindForecast-Analytics/1.0",
            "Accept": "application/json"
        }
        
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Fetching {url} with params {params} (attempt {attempt}/{self.max_retries})")
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(url, params=params, headers=headers)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, list):
                            return data
                        elif isinstance(data, dict) and "data" in data:
                            return data["data"]
                        else:
                            return []
                    elif response.status_code in (500, 502, 503, 504, 429):
                        logger.warning(f"Upstream returned HTTP {response.status_code}: {response.text[:200]}")
                        last_error = ElexonClientError(
                            f"Elexon API returned HTTP {response.status_code}",
                            status_code=response.status_code,
                            response_text=response.text
                        )
                        time.sleep(1.0 * attempt)
                    else:
                        raise ElexonClientError(
                            f"Elexon API returned client error HTTP {response.status_code}",
                            status_code=response.status_code,
                            response_text=response.text
                        )
            except httpx.RequestError as exc:
                logger.warning(f"Network error on attempt {attempt}: {exc}")
                last_error = ElexonClientError(f"Network communication failed: {exc}")
                time.sleep(1.0 * attempt)

        raise last_error or ElexonClientError("Max retries exceeded without successful response.")

    def fetch_stream_chunked(
        self,
        dataset: str,
        start_dt: datetime,
        end_dt: datetime,
        chunk_days: int = 7,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetches dataset stream across date ranges by splitting into safe chunk_days windows.
        Merges results and leverages local disk cache if available.
        Tracks source provenance and safely handles corrupted cache entries.
        """
        all_records: List[Dict[str, Any]] = []
        curr_start = start_dt

        if dataset not in self.provenance:
            self.provenance[dataset] = {"cache_hits": 0, "api_fetches": 0, "last_source": "UNINITIALIZED", "last_retrieval_utc": None}
        self.provenance[dataset]["cache_hits"] = 0
        self.provenance[dataset]["api_fetches"] = 0

        while curr_start < end_dt:
            curr_end = min(curr_start + timedelta(days=chunk_days), end_dt)
            start_iso = curr_start.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_iso = curr_end.strftime("%Y-%m-%dT%H:%M:%SZ")
            cache_file = self._get_cache_path(dataset, start_iso, end_iso)

            chunk_records: Optional[List[Dict[str, Any]]] = None
            if use_cache and cache_file.exists():
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        chunk_records = data
                        self.provenance[dataset]["cache_hits"] += 1
                        logger.info(f"Loaded {len(chunk_records)} cached records for {dataset} [{start_iso} to {end_iso}]")
                    else:
                        logger.warning(f"Corrupted cache file (not a list): {cache_file}. Falling back to live fetch.")
                except Exception as e:
                    logger.warning(f"Failed to read cache {cache_file}: {e}. Falling back to live fetch.")

            if chunk_records is None:
                url = f"{self.base_url}/datasets/{dataset}/stream"
                # For FUELHH outturns, publication occurs after settlement period ends.
                # Extend publishDateTimeTo by 2 hours for live API queries to capture boundary records
                # such as period 48 (startTime 23:30 published at 00:00 next day).
                query_pub_to = (curr_end + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ") if dataset == "FUELHH" else end_iso
                params = {
                    "publishDateTimeFrom": start_iso,
                    "publishDateTimeTo": query_pub_to
                }
                try:
                    chunk_records = self._request_with_retry(url, params)
                    self.provenance[dataset]["api_fetches"] += 1
                    if use_cache and chunk_records:
                        try:
                            with open(cache_file, "w", encoding="utf-8") as f:
                                json.dump(chunk_records, f)
                        except Exception as e:
                            logger.warning(f"Failed to write cache {cache_file}: {e}")
                except ElexonClientError as e:
                    logger.error(f"Failed to fetch {dataset} stream chunk {start_iso} to {end_iso}: {e}")
                    raise

            all_records.extend(chunk_records)
            curr_start = curr_end

        prov_label = self.get_dataset_provenance(dataset)
        self.provenance[dataset]["last_source"] = prov_label
        self.provenance[dataset]["last_retrieval_utc"] = datetime.now(timezone.utc).isoformat()
        return all_records

    def fetch_fuelhh(
        self,
        start_dt: datetime,
        end_dt: datetime,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """Fetch FUELHH actual outturn records within the specified time window."""
        return self.fetch_stream_chunked("FUELHH", start_dt, end_dt, chunk_days=settings.ELEXON_CHUNK_DAYS, use_cache=use_cache)

    def fetch_windfor(
        self,
        start_dt: datetime,
        end_dt: datetime,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """Fetch WINDFOR forecast records within the specified time window."""
        return self.fetch_stream_chunked("WINDFOR", start_dt, end_dt, chunk_days=settings.ELEXON_CHUNK_DAYS, use_cache=use_cache)
