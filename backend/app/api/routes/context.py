"""
Context API routes.

Endpoints:
  GET /api/context/weather — Fetch weather conditions for a location
"""

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.schemas.weather import WeatherResponse
from app.services.weather_service import fetch_weather

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/context", tags=["context"])


@router.get(
    "/weather",
    response_model=WeatherResponse,
    summary="Fetch weather context for a location",
)
async def get_weather(
    latitude: float = Query(..., description="Latitude in WGS84"),
    longitude: float = Query(..., description="Longitude in WGS84"),
    date: date = Query(..., description="Date for weather data (YYYY-MM-DD)"),
) -> WeatherResponse:
    """
    Fetch weather conditions at a specific location and date
    using the Open-Meteo API.

    This context data will be used in future phases for
    hotspot classification and attribution analysis.
    """
    result = await fetch_weather(
        latitude=latitude,
        longitude=longitude,
        query_date=date,
    )

    if result is None:
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch weather data from Open-Meteo",
        )

    return result
