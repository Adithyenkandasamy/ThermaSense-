"""
Open-Meteo weather context service.

Provides weather conditions at the exact time and location of a
thermal observation, to support hotspot classification and the
Attribution Engine.

API: https://api.open-meteo.com/v1/forecast
     https://archive-api.open-meteo.com/v1/archive

No API key required.

Behavior contract:
  - Inputs: latitude, longitude, acquisition_datetime (timezone-aware UTC).
  - Returns a WeatherContext aligned to the hourly bucket of the
    observation time.
  - Invalid coordinates raise ValueError.
  - Timeouts, HTTP errors, and unparseable payloads raise RuntimeError.
  - Missing measurements are returned as null — the service never
    fabricates or invents weather values.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx

from app.schemas.weather import WeatherContext

logger = logging.getLogger(__name__)

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Historical window (in days) servable by the forecast API via past_days.
FORECAST_PAST_DAYS = 7

HOURLY_FIELDS = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "precipitation",
]

MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0


def _validate_coordinates(latitude: float, longitude: float) -> None:
    """Raise ValueError for coordinates outside WGS84 bounds."""
    if not (
        MIN_LATITUDE <= latitude <= MAX_LATITUDE
        and MIN_LONGITUDE <= longitude <= MAX_LONGITUDE
    ):
        raise ValueError(
            f"Invalid coordinates: latitude={latitude}, longitude={longitude}. "
            f"Expected lat in [{MIN_LATITUDE}, {MAX_LATITUDE}] and "
            f"lon in [{MIN_LONGITUDE}, {MAX_LONGITUDE}]."
        )


def _coerce_utc(value: datetime) -> datetime:
    """Treat naive datetimes as UTC and normalize to a UTC-aware datetime."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _select_api_url(query_date: date) -> str:
    """
    Select the correct Open-Meteo API endpoint for a date.

    - Forecast API: dates within the last ~7 days and future
    - Archive API: older historical dates
    """
    today = date.today()
    if query_date >= today - timedelta(days=FORECAST_PAST_DAYS):
        return OPEN_METEO_FORECAST_URL
    return OPEN_METEO_ARCHIVE_URL


def _hourly_params(
    latitude: float,
    longitude: float,
    observation_dt: datetime,
) -> dict:
    """Build the query parameters for an Open-Meteo hourly request."""
    date_str = observation_dt.date().isoformat()
    return {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(HOURLY_FIELDS),
        "start_date": date_str,
        "end_date": date_str,
        "timezone": "UTC",
    }


def _floor_to_hour(value: datetime) -> datetime:
    """Floor a datetime to the start of its hour (UTC)."""
    return value.replace(minute=0, second=0, microsecond=0)


def _find_hour_index(times: list, target: datetime) -> Optional[int]:
    """Return the index of the hourly bucket matching `target`, else None."""
    target = _floor_to_hour(target)
    for idx, raw in enumerate(times):
        try:
            parsed = datetime.fromisoformat(str(raw))
        except (TypeError, ValueError):
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if _floor_to_hour(parsed) == target:
            return idx
    return None


async def fetch_weather(
    latitude: float,
    longitude: float,
    acquisition_datetime: datetime,
    timeout: int = 15,
) -> WeatherContext:
    """
    Fetch weather context for a specific observation time and location.

    Args:
        latitude:            Latitude in WGS84.
        longitude:           Longitude in WGS84.
        acquisition_datetime Observation time — recent observations use the
                             forecast API, older ones the archive API.
        timeout:             HTTP timeout in seconds.

    Returns:
        WeatherContext aligned to the acquisition hour. Numeric fields are
        None when the measurement is genuinely unavailable.

    Raises:
        ValueError:  Invalid coordinates.
        RuntimeError: Timeout, HTTP error, or unparseable API response.
    """
    _validate_coordinates(latitude, longitude)
    observation_dt = _coerce_utc(acquisition_datetime)
    target_hour = _floor_to_hour(observation_dt)

    api_url = _select_api_url(observation_dt.date())
    params = _hourly_params(latitude, longitude, observation_dt)

    logger.info(
        "Fetching weather — lat=%.4f lon=%.4f time=%s api=%s",
        latitude, longitude, observation_dt.isoformat(), api_url,
    )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(api_url, params=params)
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException as exc:
        logger.error("Open-Meteo request timed out: %s", exc)
        raise RuntimeError(
            f"Open-Meteo request timed out after {timeout}s"
        ) from exc
    except httpx.HTTPError as exc:
        logger.error("Open-Meteo request failed: %s", exc)
        raise RuntimeError(f"Open-Meteo request failed: {exc}") from exc
    except ValueError as exc:  # JSON decode failure
        logger.error("Open-Meteo returned invalid JSON: %s", exc)
        raise RuntimeError("Open-Meteo returned an invalid response") from exc

    return _build_context(data, target_hour)


def _build_context(data: dict, target: datetime) -> WeatherContext:
    """Build a WeatherContext from an Open-Meteo payload (hourly block)."""
    hourly = data.get("hourly")
    if not isinstance(hourly, dict):
        raise RuntimeError("Open-Meteo response is missing hourly data")
    if not isinstance(hourly.get("time"), list) or not hourly["time"]:
        # No data rows for the requested period (e.g. beyond forecast
        # horizon). Express this as explicit nulls — never fake values.
        logger.warning("No hourly data returned for %s", target.isoformat())
        return WeatherContext(weather_timestamp=target)

    idx = _find_hour_index(hourly["time"], target)
    if idx is None:
        # The requested observation hour is outside the returned hourly
        # range. Never fall back to an arbitrary bucket — express the
        # missing data as explicit nulls instead.
        logger.warning(
            "No hourly bucket matches %s; weather unavailable",
            target.isoformat(),
        )
        return WeatherContext(weather_timestamp=target)

    # Recover a UTC timestamp for the matched bucket.
    bucket_dt = _hour_to_datetime(hourly["time"], idx, target)

    def _value(key: str) -> Optional[float]:
        values = hourly.get(key)
        if not isinstance(values, list) or idx >= len(values):
            return None
        raw = values[idx]
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    return WeatherContext(
        temperature=_value("temperature_2m"),
        relative_humidity=_value("relative_humidity_2m"),
        wind_speed=_value("wind_speed_10m"),
        wind_direction=_value("wind_direction_10m"),
        precipitation=_value("precipitation"),
        weather_timestamp=bucket_dt,
        source="open-meteo",
    )


def _hour_to_datetime(times: list, idx: int, fallback: datetime) -> datetime:
    """Parse the matched bucket timestamp; fall back to the target hour."""
    try:
        raw = times[idx]
        parsed = datetime.fromisoformat(str(raw))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        return _floor_to_hour(fallback)