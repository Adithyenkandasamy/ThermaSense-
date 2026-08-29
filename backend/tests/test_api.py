"""
API endpoint tests for health, hotspots, observations, and ingestion routes.
"""

from unittest.mock import AsyncMock, patch
import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.main import app
from app.models.thermal_observation import ThermalObservation


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "thermasense-api"


@pytest.mark.asyncio
async def test_observations_list_with_mock_db():
    """Verify observations endpoint handles query params and pagination with mock DB."""
    fake_obs = ThermalObservation(
        id=uuid.uuid4(),
        source="VIIRS_NOAA20_NRT",
        latitude=37.7749,
        longitude=-122.4194,
        acquisition_datetime=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
        acq_date="2026-08-29",
        acq_time="1200",
        satellite="NOAA-20",
        instrument="VIIRS",
        brightness=320.0,
        bright_ti4=320.0,
        bright_ti5=290.0,
        frp=10.5,
        confidence="nominal",
        daynight="D",
        observation_hash="testhash12345678901234567890123456789012345678901234567890123456",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async def mock_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = mock_get_db

    with patch(
        "app.services.observation_service.list_observations",
        new=AsyncMock(return_value=([fake_obs], 1)),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get(
                "/api/observations",
                params={"limit": 10, "offset": 0},
            )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["observations"]) == 1
    assert data["observations"][0]["satellite"] == "NOAA-20"


@pytest.mark.asyncio
async def test_observation_invalid_uuid():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/observations/not-a-uuid")
    assert response.status_code == 400
    assert "Invalid UUID" in response.json()["detail"]


@pytest.mark.asyncio
async def test_ingestion_request_validation():
    """Verify ingestion request rejects invalid day_range."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post(
            "/api/ingestion/firms",
            json={"day_range": 10},  # Max allowed is 5
        )
    assert response.status_code == 422  # Pydantic validation error

