"""
FIRMS CSV parser.

Converts raw NASA FIRMS CSV text into a list of ThermalEventCreate
Pydantic models ready for DB insertion.

Expected VIIRS_SNPP_NRT CSV columns (subset we care about):
  latitude, longitude, bright_ti4, bright_ti5, scan, track,
  acq_date, acq_time, satellite, confidence, version,
  bright_ti5, frp, daynight
"""

import csv
import io
import logging
from datetime import date

from app.schemas.thermal_event import ThermalEventCreate

logger = logging.getLogger(__name__)


def _safe_float(val: str) -> float | None:
    """Return float or None — never raises."""
    try:
        return float(val.strip()) if val.strip() else None
    except ValueError:
        return None


def _safe_str(val: str) -> str | None:
    return val.strip() or None


def _parse_acq_date(val: str) -> date | None:
    """Parse YYYY-MM-DD date from FIRMS."""
    try:
        return date.fromisoformat(val.strip())
    except (ValueError, AttributeError):
        return None


def parse_firms_csv(raw_csv: str) -> list[ThermalEventCreate]:
    """
    Parse raw FIRMS CSV text into a list of ThermalEventCreate objects.

    Skips rows with missing latitude/longitude/acq_date/acq_time.

    Returns:
        List of parsed events (may be empty if no valid rows).
    """
    if not raw_csv or not raw_csv.strip():
        logger.warning("Empty FIRMS CSV received")
        return []

    events: list[ThermalEventCreate] = []
    skipped = 0

    reader = csv.DictReader(io.StringIO(raw_csv))

    for row in reader:
        lat = _safe_float(row.get("latitude", ""))
        lon = _safe_float(row.get("longitude", ""))
        acq_date = _parse_acq_date(row.get("acq_date", ""))
        acq_time = _safe_str(row.get("acq_time", "")) or ""

        if lat is None or lon is None or acq_date is None or not acq_time:
            skipped += 1
            continue

        # VIIRS uses bright_ti4 for fire pixel brightness (similar to MODIS brightness)
        brightness = _safe_float(row.get("bright_ti4", ""))
        if brightness is None:
            brightness = _safe_float(row.get("brightness", ""))

        events.append(
            ThermalEventCreate(
                latitude=lat,
                longitude=lon,
                acq_date=acq_date,
                acq_time=acq_time.zfill(4),  # ensure 4-digit "HHMM"
                brightness=brightness,
                frp=_safe_float(row.get("frp", "")),
                confidence=_safe_str(row.get("confidence", "")),
                satellite=_safe_str(row.get("satellite", "")),
                instrument=_safe_str(row.get("instrument", "")),
                daynight=_safe_str(row.get("daynight", "")),
                scan=_safe_float(row.get("scan", "")),
                track=_safe_float(row.get("track", "")),
                version=_safe_str(row.get("version", "")),
            )
        )

    logger.info(
        "Parsed %d valid events, skipped %d malformed rows",
        len(events),
        skipped,
    )
    return events
