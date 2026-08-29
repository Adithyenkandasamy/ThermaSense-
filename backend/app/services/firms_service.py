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

import csv
import hashlib
import io
import logging
from datetime import date, datetime
from typing import Optional

import httpx

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
    timeout: int = 60,
) -> tuple[list[HotspotResponse], str, str]:
    """
    Fetch thermal hotspot data from NASA FIRMS.

    Args:
        map_key:   Your NASA FIRMS MAP_KEY.
        satellite: User-friendly satellite name ('NOAA-20' or 'NOAA-21').
        day_range: Number of past days (1-5).
        area:      Bounding box 'xmin,ymin,xmax,ymax' or 'world'.
        timeout:   HTTP timeout in seconds.

    Returns:
        Tuple of (observations, source_name, area_used).

    Raises:
        ValueError: if satellite name is invalid.
        httpx.HTTPError: on network or HTTP errors.
        RuntimeError: if FIRMS returns an error response.
    """
    if not map_key:
        raise ValueError(
            "FIRMS_MAP_KEY is not configured. "
            "Obtain a free key at https://firms.modaps.eosdis.nasa.gov/api/"
        )

    # Validate day range
    day_range = max(1, min(day_range, MAX_DAY_RANGE))

    # Resolve satellite → FIRMS source name
    source = _resolve_source(satellite)

    # Default area
    area_used = area if area else DEFAULT_AREA

    # Build URL
    url = _build_url(map_key, source, area_used, day_range)

    logger.info(
        "Fetching FIRMS data — source=%s area=%s days=%d",
        source, area_used, day_range,
    )

    # ── HTTP request ──────────────────────────────────────────
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)

    # Check for FIRMS error responses
    if response.status_code != 200:
        error_text = response.text[:500]
        raise RuntimeError(
            f"FIRMS API returned status {response.status_code}: {error_text}"
        )

    raw_csv = response.text

    # FIRMS sometimes returns error messages as plain text
    if raw_csv.startswith("Error") or "Invalid" in raw_csv[:100]:
        raise RuntimeError(f"FIRMS API error: {raw_csv[:300]}")

    line_count = raw_csv.count("\n")
    logger.info(
        "FIRMS returned %d lines (approx %d observations)",
        line_count,
        max(0, line_count - 1),
    )

    # ── Parse CSV ─────────────────────────────────────────────
    observations = _parse_csv_to_observations(raw_csv, source)

    return observations, source, area_used
