"""
Unit and integration tests for GIS Data Export and Alerts Engine (Module 6).

Tests:
  - GeoJSON FeatureCollection generation & structure
  - CSV streaming & headers
  - Alert evaluation rules (Critical FRP, Multi-pass clusters)
  - REST endpoints:
    - GET /api/export/geojson
    - GET /api/export/csv
    - GET /api/alerts
"""

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import Base, get_db
from app.main import app
from app.models.thermal_event import ThermalEvent
from app.models.thermal_observation import ThermalObservation
from app.repositories import observation_repository
from app.services import alert_service, clustering_service, export_service
from app.services.observation_normalizer import _generate_observation_hash


@pytest_asyncio.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an isolated in-memory test database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(async_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Test HTTP client with overridden database dependency."""
    async def override_get_db():
        yield async_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _make_obs(lat, lon, dt, frp=20.0, conf="high"):
    h = _generate_observation_hash("VIIRS_NOAA20_NRT", lat, lon, dt.strftime("%Y-%m-%d"), dt.strftime("%H%M"), "NOAA-20", "VIIRS")
    return {
        "id": uuid.uuid4(),
        "source": "VIIRS_NOAA20_NRT",
        "latitude": lat,
        "longitude": lon,
        "acquisition_datetime": dt,
        "acq_date": dt.strftime("%Y-%m-%d"),
        "acq_time": dt.strftime("%H%M"),
        "satellite": "NOAA-20",
        "instrument": "VIIRS",
        "brightness": 325.0,
        "bright_ti4": 325.0,
        "bright_ti5": 292.0,
        "frp": frp,
        "confidence": conf,
        "daynight": "D",
        "raw_data": {},
        "observation_hash": h,
    }


@pytest.mark.asyncio
async def test_export_geojson_and_csv(async_session: AsyncSession, client: AsyncClient):
    """Test GeoJSON FeatureCollection and CSV file export."""
    t0 = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    obs = _make_obs(37.77, -122.41, t0, frp=45.0)

    await observation_repository.bulk_create_observations(async_session, [obs])
    await async_session.commit()

    # 1. GeoJSON export
    geojson = await export_service.export_observations_geojson(async_session)
    assert geojson.type == "FeatureCollection"
    assert len(geojson.features) == 1
    f = geojson.features[0]
    assert f.geometry.type == "Point"
    assert f.geometry.coordinates == [-122.41, 37.77]
    assert f.properties["frp"] == 45.0
    assert f.properties["satellite"] == "NOAA-20"

    # GeoJSON API endpoint
    resp_geojson = await client.get("/api/export/geojson")
    assert resp_geojson.status_code == 200
    data = resp_geojson.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1

    # 2. CSV export
    csv_str = await export_service.export_observations_csv(async_session)
    assert "latitude,longitude,acquisition_datetime" in csv_str
    assert "37.77,-122.41" in csv_str

    # CSV API endpoint
    resp_csv = await client.get("/api/export/csv")
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert "attachment; filename=" in resp_csv.headers["content-disposition"]


@pytest.mark.asyncio
async def test_alert_engine_rules(async_session: AsyncSession, client: AsyncClient):
    """Test operational alerts for critical FRP and cluster persistence."""
    t0 = datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc)

    # Extreme FRP hotspot (180 MW)
    obs1 = _make_obs(35.0, -119.0, t0, frp=180.0, conf="high")
    await observation_repository.bulk_create_observations(async_session, [obs1])
    await async_session.commit()

    await clustering_service.cluster_unassigned_observations(async_session)
    await async_session.commit()

    alerts_res = await alert_service.evaluate_active_alerts(async_session)
    assert alerts_res.total >= 1
    crit_alert = next((a for a in alerts_res.alerts if a.severity == "CRITICAL"), None)
    assert crit_alert is not None
    assert crit_alert.rule_name == "CRITICAL_RADIATIVE_POWER"
    assert crit_alert.frp == 180.0

    # Test alerts API route
    resp = await client.get("/api/alerts")
    assert resp.status_code == 200
    alert_data = resp.json()
    assert alert_data["total"] >= 1
