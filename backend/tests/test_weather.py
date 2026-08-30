"""
Weather context service + route tests.

Covers: recent forecast lookup, historical archive lookup, hour matching,
invalid coordinates, timeouts, HTTP failures, missing/partial data, and
the /api/context/weather route error mapping.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.schemas.weather import WeatherContext
from app.services import weather_service
from app.services.weather_service import (
    OPEN_METEO_ARCHIVE_URL,
    OPEN_METEO_FORECAST_URL,
    fetch_weather,
)

REQUEST_GET_METHOD = httpx.Request(
    "GET", "https://api.open-meteo.com/v1/forecast?latitude=10.3753&longitude=77.3753"
)


def _hourly_payload(hours, temps, humidities, winds, directions, precip):
    return {
        "hourly": {
            "time": hours,
            "temperature_2m": temps,
            "relative_humidity_2m": humidities,
            "wind_speed_10m": winds,
            "wind_direction_10m": directions,
            "precipitation": precip,
        }
    }


def _mock_open_meteo(payload: dict):
    mock_client = AsyncMock()
    mock_client.get.return_value = httpx.Response(
        200, request=REQUEST_GET_METHOD, json=payload
    )
    return mock_client


@pytest.mark.asyncio
async def test_fetch_weather_recent_uses_forecast_and_matches_hour():
    """Verify recent observation uses forecast API and matches the hour bucket."""
    hours = ["2026-08-29T11:00", "2026-08-29T12:00", "2026-08-29T13:00"]
    payload = _hourly_payload(
        hours=hours,
        temps=[31.0, 32.5, 33.1],
        humidities=[62.0, 55.0, 50.0],
        winds=[12.0, 18.5, 21.0],
        directions=[180, 190, 200],
        precip=[0.0, 0.2, 0.0],
    )
    mock_client = _mock_open_meteo(payload)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        result = await fetch_weather(
            latitude=10.3753,
            longitude=77.3753,
            acquisition_datetime=datetime(2026, 8, 29, 12, 30, tzinfo=timezone.utc),
        )

    assert mock_client.get.call_count == 1
    assert mock_client.get.call_args[0][0] == OPEN_METEO_FORECAST_URL
    assert mock_client.get.call_args[1]["params"]["start_date"] == "2026-08-29"
    assert "past_days" not in mock_client.get.call_args[1]["params"]

    assert isinstance(result, WeatherContext)
    assert result.source == "open-meteo"
    assert result.temperature == 32.5
    assert result.relative_humidity == 55.0
    assert result.wind_speed == 18.5
    assert result.wind_direction == 190.0
    assert result.precipitation == 0.2
    assert result.weather_timestamp == datetime(
        2026, 8, 29, 12, 0, tzinfo=timezone.utc
    )


@pytest.mark.asyncio
async def test_fetch_weather_naive_datetime_treated_as_utc():
    """A naive acquisition datetime is interpreted as UTC."""
    hours = ["2026-08-29T12:00"]
    payload = _hourly_payload(
        hours=hours, temps=[29.0], humidities=[60.0],
        winds=[10.0], directions=[150], precip=[0.0],
    )
    mock_client = _mock_open_meteo(payload)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        result = await fetch_weather(
            latitude=10.3753,
            longitude=77.3753,
            acquisition_datetime=datetime(2026, 8, 29, 12, 0),
        )

    assert result.temperature == 29.0
    assert result.weather_timestamp == datetime(
        2026, 8, 29, 12, 0, tzinfo=timezone.utc
    )


@pytest.mark.asyncio
async def test_fetch_weather_historical_uses_archive_url():
    """Dates older than the forecast window use the archive API."""
    hours = ["2026-01-15T12:00"]
    payload = _hourly_payload(
        hours=hours, temps=[24.0], humidities=[70.0],
        winds=[8.0], directions=[90], precip=[1.5],
    )
    mock_client = _mock_open_meteo(payload)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        result = await fetch_weather(
            latitude=10.3753,
            longitude=77.3753,
            acquisition_datetime=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
        )

    assert mock_client.get.call_args[0][0] == OPEN_METEO_ARCHIVE_URL
    assert "past_days" not in mock_client.get.call_args[1]["params"]
    assert result.temperature == 24.0
    assert result.precipitation == 1.5


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "latitude,longitude",
    [
        (91.0, 0.0),
        (-91.0, 0.0),
        (0.0, 181.0),
        (0.0, -181.0),
        (float("nan"), 0.0),
    ],
)
async def test_fetch_weather_invalid_coordinates_raise(latitude, longitude):
    """Invalid coordinates raise ValueError (never hit the API)."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        with pytest.raises(ValueError):
            await fetch_weather(
                latitude=latitude,
                longitude=longitude,
                acquisition_datetime=datetime(
                    2026, 8, 29, 12, 0, tzinfo=timezone.utc
                ),
            )
    mock_client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_weather_timeout_raises_runtime_error():
    """A timeout is reported as an API failure (no silent fallback)."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectTimeout("timed out")

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        with pytest.raises(RuntimeError, match="timed out"):
            await fetch_weather(
                latitude=10.3753,
                longitude=77.3753,
                acquisition_datetime=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
            )


@pytest.mark.asyncio
async def test_fetch_weather_http_error_raises_runtime_error():
    """A non-2xx response raises RuntimeError."""
    mock_client = AsyncMock()
    mock_client.get.return_value = httpx.Response(
        500, request=REQUEST_GET_METHOD, text="Internal Server Error"
    )

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        with pytest.raises(RuntimeError):
            await fetch_weather(
                latitude=10.3753,
                longitude=77.3753,
                acquisition_datetime=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
            )


@pytest.mark.asyncio
async def test_fetch_weather_missing_data_returns_nulls_not_fakes():
    """Empty hourly data yields explicit null fields (source preserved)."""
    mock_client = _mock_open_meteo({"hourly": {"time": []}})

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        result = await fetch_weather(
            latitude=10.3753,
            longitude=77.3753,
            acquisition_datetime=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
        )

    assert result.source == "open-meteo"
    assert result.temperature is None
    assert result.relative_humidity is None
    assert result.wind_speed is None
    assert result.wind_direction is None
    assert result.precipitation is None
    assert result.weather_timestamp == datetime(
        2026, 8, 29, 12, 0, tzinfo=timezone.utc
    )


@pytest.mark.asyncio
async def test_fetch_weather_hour_not_returned_returns_nulls():
    """When the observation hour is outside the returned range, nulls."""
    hours = ["2026-08-29T21:00", "2026-08-29T22:00"]
    payload = _hourly_payload(
        hours=hours, temps=[30.0, 29.0], humidities=[60.0, 62.0],
        winds=[5.0, 6.0], directions=[120, 130], precip=[0.0, 0.0],
    )
    mock_client = _mock_open_meteo(payload)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        result = await fetch_weather(
            latitude=10.3753,
            longitude=77.3753,
            acquisition_datetime=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
        )

    assert result.temperature is None
    assert result.precipitation is None


@pytest.mark.asyncio
async def test_fetch_weather_partial_null_values_preserved():
    """Null measurements stay null while available values are returned."""
    hours = ["2026-08-29T12:00"]
    payload = _hourly_payload(
        hours=hours, temps=[32.5], humidities=[None],
        winds=[18.5], directions=[190], precip=[None],
    )
    mock_client = _mock_open_meteo(payload)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        result = await fetch_weather(
            latitude=10.3753,
            longitude=77.3753,
            acquisition_datetime=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
        )

    assert result.temperature == 32.5
    assert result.wind_speed == 18.5
    assert result.relative_humidity is None
    assert result.precipitation is None


@pytest.mark.asyncio
async def test_fetch_weather_invalid_json_raises_runtime_error():
    """Malformed JSON body raises RuntimeError."""
    mock_client = AsyncMock()
    mock_client.get.return_value = httpx.Response(
        200,
        request=REQUEST_GET_METHOD,
        text="<html>not json</html>",
        headers={"content-type": "text/html"},
    )

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        with pytest.raises(RuntimeError):
            await fetch_weather(
                latitude=10.3753,
                longitude=77.3753,
                acquisition_datetime=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
            )


# ── Route tests ──────────────────────────────────────────────────────


@pytest.fixture
def sample_context() -> WeatherContext:
    return WeatherContext(
        temperature=32.5,
        relative_humidity=55.0,
        wind_speed=18.5,
        wind_direction=190.0,
        precipitation=0.2,
        weather_timestamp=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
        source="open-meteo",
    )


@pytest.mark.asyncio
async def test_weather_route_success(sample_context):
    """Route returns the exact WeatherContext contract."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    with patch(
        "app.api.routes.context.fetch_weather", new=AsyncMock(return_value=sample_context)
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get(
                "/api/context/weather",
                params={
                    "latitude": 10.3753,
                    "longitude": 77.3753,
                    "acquisition_datetime": "2026-08-29T12:30:00Z",
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert set(
        ["temperature", "relative_humidity", "wind_speed",
         "wind_direction", "precipitation", "weather_timestamp", "source"]
    ) == set(data.keys())
    assert data["temperature"] == 32.5
    assert data["source"] == "open-meteo"
    parsed_ts = datetime.fromisoformat(data["weather_timestamp"].replace("Z", "+00:00"))
    assert parsed_ts == datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_weather_route_invalid_coordinates_422():
    """Out-of-range coordinates are rejected by validation (422)."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get(
            "/api/context/weather",
            params={
                "latitude": 91.0,
                "longitude": 77.3753,
                "acquisition_datetime": "2026-08-29T12:30:00Z",
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_weather_route_service_value_error_400():
    """Service ValueError is surfaced as 400."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    with patch(
        "app.api.routes.context.fetch_weather",
        new=AsyncMock(side_effect=ValueError("Invalid coordinates")),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get(
                "/api/context/weather",
                params={
                    "latitude": 10.3753,
                    "longitude": 77.3753,
                    "acquisition_datetime": "2026-08-29T12:30:00Z",
                },
            )

    assert response.status_code == 400
    assert "Invalid coordinates" in response.json()["detail"]


@pytest.mark.asyncio
async def test_weather_route_service_runtime_error_502():
    """Service RuntimeError (API failure) is surfaced as 502."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    with patch(
        "app.api.routes.context.fetch_weather",
        new=AsyncMock(side_effect=RuntimeError("Open-Meteo request failed")),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get(
                "/api/context/weather",
                params={
                    "latitude": 10.3753,
                    "longitude": 77.3753,
                    "acquisition_datetime": "2026-08-29T12:30:00Z",
                },
            )

    assert response.status_code == 502
    assert "Open-Meteo" in response.json()["detail"]