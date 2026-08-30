"""
GIS Data Export Service.

Exports stored observations and events to standard GIS formats:
  - GeoJSON (RFC 7946 FeatureCollection)
  - CSV format (for analytics, spreadsheets, and data science workflows)
"""

import csv
import io
import logging
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.thermal_observation import ThermalObservation
from app.repositories import observation_repository
from app.schemas.export import (
    GeoJsonFeature,
    GeoJsonFeatureCollection,
    GeoJsonGeometryPoint,
)

logger = logging.getLogger(__name__)


async def export_observations_geojson(
    session: AsyncSession,
    *,
    source: Optional[str] = None,
    satellite: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    min_lat: Optional[float] = None,
    max_lat: Optional[float] = None,
    min_lon: Optional[float] = None,
    max_lon: Optional[float] = None,
    limit: int = 1000,
) -> GeoJsonFeatureCollection:
    """Export matching observations as standard GeoJSON RFC 7946 FeatureCollection."""
    observations, _ = await observation_repository.list_observations(
        session,
        source=source,
        satellite=satellite,
        start_date=start_date,
        end_date=end_date,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
        limit=limit,
        offset=0,
    )

    features: list[GeoJsonFeature] = []
    for obs in observations:
        feat = GeoJsonFeature(
            id=str(obs.id),
            geometry=GeoJsonGeometryPoint(
                coordinates=[obs.longitude, obs.latitude]
            ),
            properties={
                "id": str(obs.id),
                "source": obs.source,
                "satellite": obs.satellite,
                "instrument": obs.instrument,
                "acquisition_datetime": obs.acquisition_datetime.isoformat() if obs.acquisition_datetime else None,
                "brightness": obs.brightness,
                "bright_ti4": obs.bright_ti4,
                "bright_ti5": obs.bright_ti5,
                "frp": obs.frp,
                "confidence": obs.confidence,
                "daynight": obs.daynight,
                "event_id": str(obs.event_id) if obs.event_id else None,
            },
        )
        features.append(feat)

    return GeoJsonFeatureCollection(features=features)


async def export_observations_csv(
    session: AsyncSession,
    *,
    source: Optional[str] = None,
    satellite: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    min_lat: Optional[float] = None,
    max_lat: Optional[float] = None,
    min_lon: Optional[float] = None,
    max_lon: Optional[float] = None,
    limit: int = 5000,
) -> str:
    """Export matching observations to a CSV string."""
    observations, _ = await observation_repository.list_observations(
        session,
        source=source,
        satellite=satellite,
        start_date=start_date,
        end_date=end_date,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
        limit=limit,
        offset=0,
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "id",
        "latitude",
        "longitude",
        "acquisition_datetime",
        "source",
        "satellite",
        "instrument",
        "brightness",
        "bright_ti4",
        "bright_ti5",
        "frp",
        "confidence",
        "daynight",
        "event_id",
    ])

    for obs in observations:
        writer.writerow([
            str(obs.id),
            obs.latitude,
            obs.longitude,
            obs.acquisition_datetime.isoformat() if obs.acquisition_datetime else "",
            obs.source,
            obs.satellite,
            obs.instrument,
            obs.brightness or "",
            obs.bright_ti4 or "",
            obs.bright_ti5 or "",
            obs.frp or "",
            obs.confidence or "",
            obs.daynight or "",
            str(obs.event_id) if obs.event_id else "",
        ])

    return output.getvalue()
