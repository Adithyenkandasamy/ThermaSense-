"""
Schemas for GIS data export (GeoJSON RFC 7946) and Alerts Engine.
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ── GeoJSON RFC 7946 Models ──────────────────────────────────────────


class GeoJsonGeometryPoint(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: list[float] = Field(..., description="[longitude, latitude]")


class GeoJsonFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJsonGeometryPoint
    properties: dict[str, Any] = Field(default_factory=dict)
    id: Optional[str] = None


class GeoJsonFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJsonFeature] = Field(default_factory=list)


# ── Alert Engine Models ──────────────────────────────────────────────


class ThermalAlert(BaseModel):
    """An alert triggered by anomalous or critical thermal activity."""

    alert_id: str = Field(..., description="Unique alert identifier")
    event_id: Optional[str] = Field(None, description="Linked ThermalEvent ID")
    observation_id: Optional[str] = Field(None, description="Linked ThermalObservation ID")
    severity: Literal["INFO", "WARNING", "CRITICAL"] = Field(..., description="Alert severity")
    title: str = Field(..., description="Alert title")
    message: str = Field(..., description="Detailed alert description")
    latitude: float
    longitude: float
    frp: Optional[float] = None
    triggered_at: datetime = Field(..., description="Timestamp when condition was detected")
    rule_name: str = Field(..., description="Name of the triggering rule")


class AlertListResponse(BaseModel):
    """List of active thermal alerts."""

    total: int = Field(..., description="Total active alerts")
    alerts: list[ThermalAlert] = Field(default_factory=list)
