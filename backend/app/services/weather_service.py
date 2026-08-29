"""
Open-Meteo weather context service.

Provides weather conditions at a specific location and date
to support future hotspot classification and attribution.

API: https://api.open-meteo.com/v1/forecast
     https://archive-api.open-meteo.com/v1/archive

No API key required.

Note:
  Weather data is NOT yet connected to hotspot classification.
  This service provides the structure and endpoint for future use.
"""

import logging
from datetime import date, timedelta
from typing import Optional

import httpx

from app.schemas.weather import WeatherResponse

logger = logging.getLogger(__name__)

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def _select_api_url(query_date: date) -> str:
    """
    Select the correct Open-Meteo API endpoint.

    - Forecast API: for dates within the last ~7 days and future
    - Archive API: for older historical dates
    """
    today = date.today()
    if query_date >= today - timedelta(days=7):
        return OPEN_METEO_FORECAST_URL
    return OPEN_METEO_ARCHIVE_URL


async def fetch_weather(
    latitude: float,
    longitude: float,
    query_date: date,
    timeout: int = 15,
) -> Optional[WeatherResponse]:
    """
    Fetch weather conditions for a specific location and date.

    Args:
        latitude:   Latitude in WGS84.
        longitude:  Longitude in WGS84.
        query_date: Date for weather data.
        timeout:    HTTP timeout in seconds.

    Returns:
        WeatherResponse with conditions, or None on failure.
    """
    api_url = _select_api_url(query_date)
    date_str = query_date.isoformat()

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": date_str,
        "end_date": date_str,
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "apparent_temperature_max",
            "precipitation_sum",
            "wind_speed_10m_max",
            "wind_direction_10m_dominant",
            "weather_code",
        ]),
        "timezone": "UTC",
    }

    logger.info(
        "Fetching weather — lat=%.4f lon=%.4f date=%s api=%s",
        latitude, longitude, date_str, api_url,
    )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(api_url, params=params)
            response.raise_for_status()

        data = response.json()
        daily = data.get("daily", {})

        # Open-Meteo returns arrays — take first (and only) element
        def _first(key: str) -> Optional[float]:
            values = daily.get(key, [])
            return values[0] if values else None

        return WeatherResponse(
            latitude=latitude,
            longitude=longitude,
            date=query_date,
            temperature_max=_first("temperature_2m_max"),
            temperature_min=_first("temperature_2m_min"),
            apparent_temperature_max=_first("apparent_temperature_max"),
            precipitation_sum=_first("precipitation_sum"),
            wind_speed_max=_first("wind_speed_10m_max"),
            wind_direction_dominant=(
                int(_first("wind_direction_10m_dominant"))
                if _first("wind_direction_10m_dominant") is not None
                else None
            ),
            weather_code=(
                int(_first("weather_code"))
                if _first("weather_code") is not None
                else None
            ),
            source="open-meteo",
        )

    except httpx.HTTPError as exc:
        logger.error("Open-Meteo request failed: %s", exc)
        return None
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("Failed to parse Open-Meteo response: %s", exc)
        return None
