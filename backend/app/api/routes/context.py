"""
Context API routes.

Endpoints:
  GET /api/context/weather — Fetch weather conditions for a location
  GET /api/context/geospatial — Fetch OpenStreetMap land use and nearby features
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.schemas.geospatial import GeospatialResponse
from app.schemas.weather import WeatherContext
from app.services.geospatial_service import DEFAULT_RADIUS_M, fetch_nearby_context
from app.services.weather_service import (
    MAX_LATITUDE,
    MAX_LONGITUDE,
    MIN_LATITUDE,
    MIN_LONGITUDE,
    fetch_weather,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/context", tags=["context"])


@router.get(
    "/weather",
    response_model=WeatherContext,
    summary="Fetch weather context for a location and time",
)
async def get_weather(
    latitude: float = Query(
        ..., ge=MIN_LATITUDE, le=MAX_LATITUDE, description="Latitude in WGS84"
    ),
    longitude: float = Query(
        ..., ge=MIN_LONGITUDE, le=MAX_LONGITUDE, description="Longitude in WGS84"
    ),
    acquisition_datetime: datetime = Query(
        ...,
        description="Thermal observation time (ISO 8601, UTC)",
    ),
) -> WeatherContext:
    """
    Fetch weather conditions at a specific observation time and location
    using the Open-Meteo API.

    Recent observations use the forecast API; older observations use the
    historical archive API. Missing measurements are returned as null.
    """
    try:
        return await fetch_weather(
            latitude=latitude,
            longitude=longitude,
            acquisition_datetime=acquisition_datetime,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        logger.error("Weather context fetch failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch weather data from Open-Meteo: {exc}",
        )


@router.get(
    "/geospatial",
    response_model=GeospatialResponse,
    summary="Fetch geospatial and land use context for a location",
)
async def get_geospatial(
    latitude: float = Query(..., description="Latitude in WGS84"),
    longitude: float = Query(..., description="Longitude in WGS84"),
    radius_m: float = Query(
        DEFAULT_RADIUS_M,
        ge=100.0,
        le=10000.0,
        description="Search radius in meters (100m - 10,000m)",
    ),
) -> GeospatialResponse:
    """
    Fetch OpenStreetMap geographic context around a thermal anomaly
    (nearby industrial zones, forests, croplands, roads, and buildings).
    """
    context = await fetch_nearby_context(
        latitude=latitude,
        longitude=longitude,
        radius_m=radius_m,
    )

    return GeospatialResponse(
        latitude=context.latitude,
        longitude=context.longitude,
        radius_m=context.radius_m,
        industrial=[
            {
                "feature_type": f.feature_type,
                "name": f.name,
                "distance_m": f.distance_m,
                "osm_id": f.osm_id,
                "osm_type": f.osm_type,
                "tags": f.tags,
            }
            for f in context.industrial
        ],
        forests=[
            {
                "feature_type": f.feature_type,
                "name": f.name,
                "distance_m": f.distance_m,
                "osm_id": f.osm_id,
                "osm_type": f.osm_type,
                "tags": f.tags,
            }
            for f in context.forests
        ],
        croplands=[
            {
                "feature_type": f.feature_type,
                "name": f.name,
                "distance_m": f.distance_m,
                "osm_id": f.osm_id,
                "osm_type": f.osm_type,
                "tags": f.tags,
            }
            for f in context.croplands
        ],
        roads=[
            {
                "feature_type": f.feature_type,
                "name": f.name,
                "distance_m": f.distance_m,
                "osm_id": f.osm_id,
                "osm_type": f.osm_type,
                "tags": f.tags,
            }
            for f in context.roads
        ],
        buildings=[
            {
                "feature_type": f.feature_type,
                "name": f.name,
                "distance_m": f.distance_m,
                "osm_id": f.osm_id,
                "osm_type": f.osm_type,
                "tags": f.tags,
            }
            for f in context.buildings
        ],
        source=context.source,
    )
