"""
Pydantic schemas for weather context.

The WeatherContext schema is the exact contract consumed by the
Attribution Engine. It describes environmental conditions at the
time and location of a thermal observation. Every value is Optional
so a genuinely missing measurement is expressed as null — the service
never fabricates weather data.
"""

import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WeatherRequest(BaseModel):
    """Parameters for a weather context lookup."""

    latitude: float = Field(
        ..., ge=-90.0, le=90.0, description="Latitude in WGS84"
    )
    longitude: float = Field(
        ..., ge=-180.0, le=180.0, description="Longitude in WGS84"
    )
    acquisition_datetime: datetime.datetime = Field(
        ..., description="Thermal observation time (ISO 8601, UTC)"
    )


class WeatherContext(BaseModel):
    """
    Weather conditions at a specific observation time and location.

    Independent of UI — this is the structured contract consumed
    directly by the Attribution Engine.
    """

    temperature: Optional[float] = Field(
        None, description="Air temperature at observation hour (°C)"
    )
    relative_humidity: Optional[float] = Field(
        None, description="Relative humidity at observation hour (%)"
    )
    wind_speed: Optional[float] = Field(
        None, description="Wind speed at observation hour (km/h)"
    )
    wind_direction: Optional[float] = Field(
        None, description="Wind direction at observation hour (degrees, 0-360)"
    )
    precipitation: Optional[float] = Field(
        None, description="Precipitation at observation hour (mm)"
    )
    weather_timestamp: Optional[datetime.datetime] = Field(
        None, description="UTC timestamp the weather values correspond to"
    )
    source: str = Field(
        default="open-meteo", description="Data source identifier"
    )


# Backward-compatible export for any existing imports.
WeatherResponse = WeatherContext