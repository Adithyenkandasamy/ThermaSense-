"""
Pydantic schemas for weather context.

Structure only — full Open-Meteo integration will be
connected to hotspot classification in a future phase.
"""

import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WeatherRequest(BaseModel):
    """Parameters for a weather context lookup."""

    latitude: float = Field(..., description="Latitude in WGS84")
    longitude: float = Field(..., description="Longitude in WGS84")
    date: datetime.date = Field(..., description="Date for weather data (YYYY-MM-DD)")


class WeatherResponse(BaseModel):
    """Weather conditions at a specific location and date."""

    latitude: float
    longitude: float
    date: datetime.date
    temperature_max: Optional[float] = Field(
        None, description="Maximum temperature (°C)"
    )
    temperature_min: Optional[float] = Field(
        None, description="Minimum temperature (°C)"
    )
    apparent_temperature_max: Optional[float] = Field(
        None, description="Maximum apparent temperature (°C)"
    )
    precipitation_sum: Optional[float] = Field(
        None, description="Total precipitation (mm)"
    )
    wind_speed_max: Optional[float] = Field(
        None, description="Maximum wind speed (km/h)"
    )
    wind_direction_dominant: Optional[int] = Field(
        None, description="Dominant wind direction (degrees)"
    )
    relative_humidity_mean: Optional[float] = Field(
        None, description="Mean relative humidity (%)"
    )
    weather_code: Optional[int] = Field(
        None, description="WMO weather interpretation code"
    )
    source: str = Field(
        default="open-meteo", description="Data source identifier"
    )
