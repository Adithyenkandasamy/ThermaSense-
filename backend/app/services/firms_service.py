"""
NASA FIRMS Area API service.

Fetches near real-time (NRT) VIIRS thermal anomaly data
from the FIRMS Area API and returns structured observations.

API format:
  GET /api/area/csv/{MAP_KEY}/{source}/{area}/{day_range}

Supported sources:
  VIIRS_NOAA20_NRT  — NOAA-20 satellite
  VIIRS_NOAA21_NRT  — NOAA-21 satellite

References:
  https://firms.modaps.eosdis.nasa.gov/api/area/
"""

import asyncio
import csv
import hashlib
import io
import logging
from datetime import date, datetime
from typing import Optional

import httpx

from app.core.config import get_settings
from app.schemas.observation import HotspotResponse

logger = logging.getLogger(__name__)

FIRMS_BASE_URL = "https://firms.modaps.eosdis.nasa.gov"

# Mapping of user-friendly names to FIRMS source identifiers
SATELLITE_SOURCES: dict[str, str] = {
    "NOAA-20": "VIIRS_NOAA20_NRT",
    "NOAA-21": "VIIRS_NOAA21_NRT",
}

DEFAULT_SATELLITE = "NOAA-20"
DEFAULT_AREA = "world"
DEFAULT_DAY_RANGE = 1
MAX_DAY_RANGE = 5


def _mask_key(key: str) -> str:
    """Mask MAP_KEY for logging/errors to avoid exposing secrets."""
    if not key:
        return "***"
    if len(key) <= 6:
        return "***"
    return f"{key[:3]}...{key[-3:]}"


def _mask_url(url: str, map_key: str) -> str:
    """Replace map key with masked representation in URL."""
    if map_key and map_key in url:
        return url.replace(map_key, _mask_key(map_key))
    return url


def _resolve_source(satellite: str) -> str:
    """Convert a user-friendly satellite name to a FIRMS source identifier."""
    source = SATELLITE_SOURCES.get(satellite.upper().replace(" ", "-"))
    if source is None:
        source = SATELLITE_SOURCES.get(satellite)
    if source is None:
        # Allow passing the raw FIRMS source name directly
        if satellite in SATELLITE_SOURCES.values():
            return satellite
        raise ValueError(
            f"Unknown satellite '{satellite}'. "
            f"Supported: {list(SATELLITE_SOURCES.keys())}"
        )
    return source


def _build_url(
    map_key: str,
    source: str,
    area: str,
    day_range: int,
) -> str:
    """Build the FIRMS Area API URL."""
    return (
        f"{FIRMS_BASE_URL}/api/area/csv/{map_key}/{source}/{area}/{day_range}"
    )


def _generate_observation_id(row: dict[str, str], index: int) -> str:
    """
    Generate a deterministic ID for an observation.

    Uses a hash of key fields so the same observation always
    produces the same ID, even across fetches.
    """
    key = (
        f"{row.get('latitude', '')}"
        f"{row.get('longitude', '')}"
        f"{row.get('acq_date', '')}"
        f"{row.get('acq_time', '')}"
        f"{row.get('satellite', '')}"
    )
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _safe_float(val: str) -> Optional[float]:
    """Return float or None — never raises."""
    try:
        return float(val.strip()) if val.strip() else None
    except ValueError:
        return None


def _safe_str(val: str) -> Optional[str]:
    """Return stripped string or None."""
    stripped = val.strip() if val else ""
    return stripped or None


def _parse_acquisition_datetime(acq_date: str, acq_time: str) -> Optional[datetime]:
    """
    Parse FIRMS date and time into a datetime object.

    FIRMS uses:
      acq_date: "YYYY-MM-DD"
      acq_time: "HHMM" (24-hour, zero-padded)
    """
    try:
        d = date.fromisoformat(acq_date.strip())
        time_str = acq_time.strip().zfill(4)
        hour = int(time_str[:2])
        minute = int(time_str[2:])
        return datetime(d.year, d.month, d.day, hour, minute)
    except (ValueError, AttributeError):
        return None


def _parse_csv_to_observations(
    raw_csv: str,
    source_name: str,
) -> list[HotspotResponse]:
    """
    Parse raw FIRMS CSV text into a list of HotspotResponse objects.

    Steps:
      1. Read CSV with DictReader
      2. Validate required fields (lat, lon, acq_date, acq_time)
      3. Convert to structured HotspotResponse
      4. Skip rows with missing required fields

    Returns:
        List of validated observations (may be empty).
    """
    if not raw_csv or not raw_csv.strip():
        logger.warning("Empty FIRMS CSV received")
        return []

    observations: list[HotspotResponse] = []
    skipped = 0

    reader = csv.DictReader(io.StringIO(raw_csv))

    for index, row in enumerate(reader):
        lat = _safe_float(row.get("latitude", ""))
        lon = _safe_float(row.get("longitude", ""))
        acq_date_str = row.get("acq_date", "").strip()
        acq_time_str = row.get("acq_time", "").strip()

        # ── Validate required fields ──────────────────────────
        if lat is None or lon is None or not acq_date_str or not acq_time_str:
            skipped += 1
            continue

        acq_dt = _parse_acquisition_datetime(acq_date_str, acq_time_str)
        if acq_dt is None:
            skipped += 1
            continue

        # VIIRS uses bright_ti4 as the primary brightness channel
        brightness = _safe_float(row.get("bright_ti4", ""))
        if brightness is None:
            brightness = _safe_float(row.get("brightness", ""))

        obs_id = _generate_observation_id(row, index)

        observations.append(
            HotspotResponse(
                id=obs_id,
                latitude=lat,
                longitude=lon,
                acquisition_datetime=acq_dt,
                satellite=_safe_str(row.get("satellite", "")) or "Unknown",
                instrument=_safe_str(row.get("instrument", "")) or "VIIRS",
                brightness=brightness,
                bright_ti4=_safe_float(row.get("bright_ti4", "")),
                bright_ti5=_safe_float(row.get("bright_ti5", "")),
                frp=_safe_float(row.get("frp", "")),
                confidence=_safe_str(row.get("confidence", "")),
                daynight=_safe_str(row.get("daynight", "")),
                source=source_name,
            )
        )

    logger.info(
        "Parsed %d valid observations, skipped %d malformed rows",
        len(observations),
        skipped,
    )
    return observations


async def fetch_hotspots(
    map_key: str,
    satellite: str = DEFAULT_SATELLITE,
    day_range: int = DEFAULT_DAY_RANGE,
    area: Optional[str] = None,
    timeout: Optional[int] = None,
    max_retries: Optional[int] = None,
    retry_delay_seconds: Optional[float] = None,
) -> tuple[list[HotspotResponse], str, str]:
    """
    Fetch thermal hotspot data from NASA FIRMS with retry and failure handling.

    Args:
        map_key:             NASA FIRMS MAP_KEY.
        satellite:           User-friendly satellite name ('NOAA-20' or 'NOAA-21').
        day_range:           Number of past days (1-5).
        area:                Bounding box 'xmin,ymin,xmax,ymax' or 'world'.
        timeout:             HTTP timeout in seconds (default from settings).
        max_retries:         Max retry attempts (default from settings).
        retry_delay_seconds: Base retry delay in seconds (default from settings).

    Returns:
        Tuple of (observations, source_name, area_used).

    Raises:
        ValueError: if satellite name is invalid or map_key is missing.
        RuntimeError: if FIRMS returns an error response after retries.
    """
    if not map_key:
        raise ValueError(
            "FIRMS_MAP_KEY is not configured. "
            "Obtain a free key at https://firms.modaps.eosdis.nasa.gov/api/"
        )

    settings = get_settings()
    timeout_sec = timeout if timeout is not None else settings.firms_timeout_seconds
    retries = max_retries if max_retries is not None else settings.firms_max_retries
    delay_sec = (
        retry_delay_seconds
        if retry_delay_seconds is not None
        else settings.firms_retry_delay_seconds
    )

    # Validate day range
    day_range = max(1, min(day_range, MAX_DAY_RANGE))

    # Resolve satellite → FIRMS source name
    source = _resolve_source(satellite)

    # Default area
    area_used = area if area else DEFAULT_AREA

    # Build URL
    url = _build_url(map_key, source, area_used, day_range)
    masked_url = _mask_url(url, map_key)

    logger.info(
        "Fetching FIRMS data — source=%s area=%s days=%d (timeout=%ds, max_retries=%d)",
        source,
        area_used,
        day_range,
        timeout_sec,
        retries,
    )

    attempt = 0
    last_error: Optional[Exception] = None

    while attempt <= retries:
        attempt += 1
        try:
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                response = await client.get(url)

            # Check for non-retryable 4xx client errors (except 429 rate limit)
            if 400 <= response.status_code < 500 and response.status_code != 429:
                error_text = response.text[:300]
                masked_err = error_text.replace(map_key, _mask_key(map_key)) if map_key else error_text
                raise RuntimeError(
                    f"FIRMS API client error ({response.status_code}): {masked_err}"
                )

            # Check for 5xx server errors or 429 rate limit
            if response.status_code != 200:
                error_text = response.text[:300]
                masked_err = error_text.replace(map_key, _mask_key(map_key)) if map_key else error_text
                raise httpx.HTTPStatusError(
                    f"FIRMS API status {response.status_code}: {masked_err}",
                    request=response.request,
                    response=response,
                )

            raw_csv = response.text

            # FIRMS sometimes returns error messages as plain text with 200 OK
            if raw_csv.startswith("Error") or "Invalid MAP_KEY" in raw_csv:
                masked_err = raw_csv[:300].replace(map_key, _mask_key(map_key)) if map_key else raw_csv[:300]
                raise RuntimeError(f"FIRMS API error: {masked_err}")

            line_count = raw_csv.count("\n")
            logger.info(
                "FIRMS returned %d lines (approx %d observations)",
                line_count,
                max(0, line_count - 1),
            )

            observations = _parse_csv_to_observations(raw_csv, source)
            return observations, source, area_used

        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            last_error = exc
            if attempt <= retries:
                backoff = delay_sec * (2 ** (attempt - 1))
                logger.warning(
                    "FIRMS fetch attempt %d/%d failed: %s. Retrying in %.1fs...",
                    attempt,
                    retries + 1,
                    str(exc),
                    backoff,
                )
                await asyncio.sleep(backoff)
            else:
                logger.error(
                    "FIRMS fetch failed after %d attempts: %s",
                    attempt,
                    str(exc),
                )
        except RuntimeError as exc:
            # Domain or unrecoverable client errors (invalid key, bad parameters)
            logger.error("FIRMS fetch unrecoverable error: %s", exc)
            raise

    raise RuntimeError(
        f"FIRMS fetch failed after {retries + 1} attempts: {last_error}"
    )

