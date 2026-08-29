"""
Pydantic schemas for thermal observations.

Used for API request validation and response serialization.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── API Response Schemas ─────────────────────────────────────────────


class HotspotResponse(BaseModel):
    """A single satellite thermal observation returned by the API."""

    id: str = Field(..., description="Unique observation identifier")
    latitude: float = Field(..., description="Latitude in WGS84")
    longitude: float = Field(..., description="Longitude in WGS84")
    acquisition_datetime: datetime = Field(
        ..., description="Date and time of satellite detection"
    )
    satellite: str = Field(..., description="Satellite name (e.g., NOAA-20)")
    instrument: str = Field(..., description="Instrument name (e.g., VIIRS)")
    brightness: Optional[float] = Field(
        None, description="Brightness temperature (Kelvin)"
    )
    bright_ti4: Optional[float] = Field(
        None, description="VIIRS I-4 channel brightness temperature (K)"
    )
    bright_ti5: Optional[float] = Field(
        None, description="VIIRS I-5 channel brightness temperature (K)"
    )
    frp: Optional[float] = Field(
        None, description="Fire Radiative Power (MW)"
    )
    confidence: Optional[str] = Field(
        None, description="Detection confidence (low, nominal, high)"
    )
    daynight: Optional[str] = Field(
        None, description="Day or night detection (D/N)"
    )
    source: str = Field(
        default="FIRMS", description="Data source identifier"
    )


class HotspotListResponse(BaseModel):
    """Wrapper for a list of thermal observations."""

    total: int = Field(..., description="Total number of observations returned")
    satellite_source: str = Field(
        ..., description="FIRMS source used for this fetch"
    )
    day_range: int = Field(..., description="Number of days queried")
    area: str = Field(..., description="Area parameter used (bbox or 'world')")
    observations: list[HotspotResponse] = Field(
        default_factory=list, description="List of hotspot observations"
    )


# ── Ingestion Request / Response ─────────────────────────────────────


class IngestionRequest(BaseModel):
    """Parameters for triggering a FIRMS data fetch."""

    satellite: str = Field(
        default="NOAA-20",
        description="Satellite source: 'NOAA-20' or 'NOAA-21'",
    )
    day_range: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Number of past days to fetch (1-5)",
    )
    area: Optional[str] = Field(
        default=None,
        description=(
            "Area to query. Use 'world' for global data or "
            "'xmin,ymin,xmax,ymax' for a bounding box. "
            "Defaults to 'world'."
        ),
    )


class IngestionResponse(BaseModel):
    """Response from a FIRMS ingestion trigger."""

    status: str = Field(..., description="'ok' or 'error'")
    message: str = Field(..., description="Human-readable result summary")
    total_fetched: int = Field(
        default=0, description="Number of observations fetched"
    )
    satellite_source: str = Field(
        default="", description="FIRMS source identifier used"
    )
    observations: list[HotspotResponse] = Field(
        default_factory=list, description="Fetched observations"
    )
