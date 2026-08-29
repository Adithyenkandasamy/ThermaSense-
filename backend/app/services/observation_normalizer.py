"""
Observation normalizer.

Transforms raw FIRMS CSV rows into validated, normalized
data ready for database storage. This is a pure transformation
layer — no database or HTTP calls.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Supported FIRMS sources
SUPPORTED_SOURCES = frozenset({
    "VIIRS_NOAA20_NRT",
    "VIIRS_NOAA21_NRT",
})


@dataclass
class NormalizedObservation:
    """A fully validated, normalized observation ready for DB insertion."""

    source: str
    latitude: float
    longitude: float
    acquisition_datetime: datetime
    acq_date: str
    acq_time: str
    satellite: str
    instrument: str
    brightness: Optional[float] = None
    bright_ti4: Optional[float] = None
    bright_ti5: Optional[float] = None
    frp: Optional[float] = None
    confidence: Optional[str] = None
    daynight: Optional[str] = None
    raw_data: dict[str, Any] = field(default_factory=dict)
    observation_hash: str = ""


@dataclass
class ValidationError:
    """Describes why a row failed validation."""

    row_index: int
    field: str
    message: str


def _safe_float(value: Any) -> Optional[float]:
    """Convert to float or return None. Never raises."""
    if value is None:
        return None
    try:
        s = str(value).strip()
        if not s:
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _safe_str(value: Any) -> Optional[str]:
    """Strip and return string, or None if empty."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _parse_acquisition_datetime(
    acq_date_str: str,
    acq_time_str: str,
) -> Optional[datetime]:
    """
    Parse FIRMS date + time into a timezone-aware UTC datetime.

    FIRMS format:
      acq_date: "YYYY-MM-DD"
      acq_time: "HHMM" (24-hour, zero-padded)
    """
    try:
        d = date.fromisoformat(acq_date_str.strip())
        time_str = acq_time_str.strip().zfill(4)
        hour = int(time_str[:2])
        minute = int(time_str[2:])
        return datetime(d.year, d.month, d.day, hour, minute, tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return None


def _generate_observation_hash(
    source: str,
    latitude: float,
    longitude: float,
    acq_date: str,
    acq_time: str,
    satellite: str,
    instrument: str,
) -> str:
    """
    Generate a deterministic SHA-256 hash for exact duplicate detection.

    Uses only stable identity fields — never volatile fields like
    database IDs or ingestion timestamps.
    """
    identity = (
        f"{source}|"
        f"{latitude:.6f}|"
        f"{longitude:.6f}|"
        f"{acq_date}|"
        f"{acq_time}|"
        f"{satellite}|"
        f"{instrument}"
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def normalize_row(
    row: dict[str, Any],
    source: str,
    row_index: int,
) -> tuple[Optional[NormalizedObservation], Optional[ValidationError]]:
    """
    Normalize and validate a single FIRMS CSV row.

    Args:
        row: Dict from csv.DictReader (raw FIRMS row).
        source: FIRMS source identifier (e.g. VIIRS_NOAA20_NRT).
        row_index: Row number for error reporting.

    Returns:
        Tuple of (NormalizedObservation, None) on success,
        or (None, ValidationError) on failure.
    """
    # ── Validate source ──────────────────────────────────────────
    if source not in SUPPORTED_SOURCES:
        return None, ValidationError(
            row_index=row_index,
            field="source",
            message=f"Unsupported source: {source}",
        )

    # ── Extract and validate coordinates ─────────────────────────
    latitude = _safe_float(row.get("latitude"))
    longitude = _safe_float(row.get("longitude"))

    if latitude is None:
        return None, ValidationError(
            row_index=row_index, field="latitude", message="Missing or invalid latitude"
        )
    if longitude is None:
        return None, ValidationError(
            row_index=row_index, field="longitude", message="Missing or invalid longitude"
        )
    if not (-90 <= latitude <= 90):
        return None, ValidationError(
            row_index=row_index,
            field="latitude",
            message=f"Latitude {latitude} out of range [-90, 90]",
        )
    if not (-180 <= longitude <= 180):
        return None, ValidationError(
            row_index=row_index,
            field="longitude",
            message=f"Longitude {longitude} out of range [-180, 180]",
        )

    # ── Validate acquisition date/time ───────────────────────────
    acq_date_str = str(row.get("acq_date", "")).strip()
    acq_time_str = str(row.get("acq_time", "")).strip()

    if not acq_date_str:
        return None, ValidationError(
            row_index=row_index, field="acq_date", message="Missing acquisition date"
        )
    if not acq_time_str:
        return None, ValidationError(
            row_index=row_index, field="acq_time", message="Missing acquisition time"
        )

    acq_dt = _parse_acquisition_datetime(acq_date_str, acq_time_str)
    if acq_dt is None:
        return None, ValidationError(
            row_index=row_index,
            field="acquisition_datetime",
            message=f"Invalid date/time: {acq_date_str} {acq_time_str}",
        )

    # ── Normalize satellite & instrument ─────────────────────────
    satellite = _safe_str(row.get("satellite")) or "Unknown"
    instrument = _safe_str(row.get("instrument")) or "VIIRS"

    # ── Convert numeric thermal fields ───────────────────────────
    bright_ti4 = _safe_float(row.get("bright_ti4"))
    bright_ti5 = _safe_float(row.get("bright_ti5"))
    brightness = bright_ti4 or _safe_float(row.get("brightness"))
    frp = _safe_float(row.get("frp"))

    # ── Optional metadata ────────────────────────────────────────
    confidence = _safe_str(row.get("confidence"))
    daynight = _safe_str(row.get("daynight"))

    # ── Generate identity hash ───────────────────────────────────
    obs_hash = _generate_observation_hash(
        source=source,
        latitude=latitude,
        longitude=longitude,
        acq_date=acq_date_str,
        acq_time=acq_time_str,
        satellite=satellite,
        instrument=instrument,
    )

    # ── Preserve raw data ────────────────────────────────────────
    raw_data = {k: v for k, v in row.items() if v is not None and str(v).strip()}

    return NormalizedObservation(
        source=source,
        latitude=latitude,
        longitude=longitude,
        acquisition_datetime=acq_dt,
        acq_date=acq_date_str,
        acq_time=acq_time_str,
        satellite=satellite,
        instrument=instrument,
        brightness=brightness,
        bright_ti4=bright_ti4,
        bright_ti5=bright_ti5,
        frp=frp,
        confidence=confidence,
        daynight=daynight,
        raw_data=raw_data,
        observation_hash=obs_hash,
    ), None


def normalize_rows(
    rows: list[dict[str, Any]],
    source: str,
) -> tuple[list[NormalizedObservation], list[ValidationError]]:
    """
    Normalize and validate a batch of FIRMS CSV rows.

    Returns:
        Tuple of (valid_observations, validation_errors).
    """
    valid: list[NormalizedObservation] = []
    errors: list[ValidationError] = []

    for index, row in enumerate(rows):
        obs, err = normalize_row(row, source, index)
        if obs is not None:
            valid.append(obs)
        if err is not None:
            errors.append(err)

    logger.info(
        "Normalization complete: %d valid, %d invalid out of %d rows",
        len(valid),
        len(errors),
        len(rows),
    )
    return valid, errors
