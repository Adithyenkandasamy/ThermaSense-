"""
Pydantic schemas for thermal events.

Used for API request validation and response serialization.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Embedded Observation Summary ─────────────────────────────────────


class EventObservationSummary(BaseModel):
    """Lightweight observation summary embedded in event responses."""

    model_config = {"from_attributes": True}

    id: str = Field(..., description="UUID observation identifier")
    latitude: float
    longitude: float
    acquisition_datetime: datetime
    satellite: str
    instrument: str
    brightness: Optional[float] = None
    frp: Optional[float] = None
    confidence: Optional[str] = None


# ── Event Response Schemas ───────────────────────────────────────────


class EventResponse(BaseModel):
    """A single thermal event returned by the API."""

    model_config = {"from_attributes": True}

    id: str = Field(..., description="UUID event identifier")
    status: Literal["active", "inactive"] = Field(
        ..., description="Event status"
    )
    centroid_latitude: float = Field(
        ..., description="Centroid latitude in WGS84"
    )
    centroid_longitude: float = Field(
        ..., description="Centroid longitude in WGS84"
    )
    started_at: datetime = Field(
        ..., description="UTC timestamp of first detection"
    )
    ended_at: Optional[datetime] = Field(
        None, description="UTC timestamp of last detection"
    )
    last_detected_at: Optional[datetime] = Field(
        None, description="Alias for ended_at — UTC timestamp of last detection"
    )
    total_frp: Optional[float] = Field(
        None, description="Sum of fire radiative power (MW)"
    )
    max_frp: Optional[float] = Field(
        None, description="Maximum single-observation FRP across linked observations (MW)"
    )
    max_confidence: Optional[str] = Field(
        None, description="Highest confidence level"
    )
    observation_count: float = Field(
        ..., description="Number of linked observations"
    )
    description: Optional[str] = Field(
        None, description="Human-readable event description"
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    observations: list[EventObservationSummary] = Field(
        default_factory=list,
        description="Linked thermal observations",
    )


class EventListResponse(BaseModel):
    """Paginated list of thermal events."""

    total: int = Field(..., description="Total matching events")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Current offset")
    events: list[EventResponse] = Field(
        default_factory=list, description="Events in this page"
    )
