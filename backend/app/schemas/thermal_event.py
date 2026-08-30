"""
Pydantic schemas for ThermalEvent.

Used for:
- API request validation
- API response serialization
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.thermal_event import RiskLevel


# ── Ingest (internal use) ──────────────────────────────────────────────────
class ThermalEventCreate(BaseModel):
    """Data parsed from NASA FIRMS CSV — used when writing to DB."""

    latitude: float
    longitude: float
    acq_date: date
    acq_time: str  # "HHMM"

    brightness: float | None = None
    frp: float | None = None
    confidence: str | None = None
    satellite: str | None = None
    instrument: str | None = None
    daynight: str | None = None
    scan: float | None = None
    track: float | None = None
    version: str | None = None


# ── API responses ──────────────────────────────────────────────────────────
class ThermalEventResponse(BaseModel):
    """Full event detail returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str | None = None
    source: str
    latitude: float
    longitude: float
    acq_date: date
    acq_time: str

    brightness: float | None
    frp: float | None
    confidence: str | None
    satellite: str | None
    instrument: str | None
    daynight: str | None
    scan: float | None
    track: float | None

    risk_level: RiskLevel
    risk_score: float

    ai_summary: str | None
    ai_generated: bool

    created_at: datetime
    updated_at: datetime


class ThermalEventSummary(BaseModel):
    """Lightweight event for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str = "VIIRS_SNPP_NRT"
    latitude: float
    longitude: float
    acq_date: date
    acq_time: str
    frp: float | None
    brightness: float | None
    confidence: str | None
    satellite: str | None
    risk_level: RiskLevel
    risk_score: float
    ai_summary: str | None


class StatsResponse(BaseModel):
    """Summary statistics for the /stats endpoint."""

    total_events: int
    by_risk_level: dict[str, int]
    last_ingestion: datetime | None
    events_last_24h: int
    extreme_count: int
    high_count: int


class IngestResponse(BaseModel):
    """Response from a manual /ingest trigger."""

    status: str
    fetched: int
    inserted: int
    skipped_duplicates: int
    groq_summaries_generated: int
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class PaginatedEvents(BaseModel):
    """Paginated list of events."""

    total: int
    page: int
    per_page: int
    pages: int
    items: list[ThermalEventSummary]
