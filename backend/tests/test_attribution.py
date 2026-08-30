"""
Controlled unit and integration tests for Backend Thermal Anomaly Attribution Engine.

Tests:
  - forest context -> vegetation_fire score increases
  - cropland context -> agricultural_burning score increases
  - industrial context -> industrial_heat score increases
  - gas flare context -> gas_flare score increases
  - no meaningful evidence -> unknown
  - Single observation attribution (classify_observation)
  - REST endpoints:
    - GET /api/attribution/event/{id}
    - GET /api/attribution/observation/{id}
    - GET /api/events/{id}/intelligence
"""

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

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
from app.schemas.weather import WeatherContext
from app.services import attribution_service, clustering_service, event_service
from app.services.geospatial_service import GeospatialContext, NearbyFeature
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


def _make_obs(lat, lon, dt, frp=15.0, conf="high", sat="NOAA-20", daynight="D", ti4=320.0):
    h = _generate_observation_hash("VIIRS_NOAA20_NRT", lat, lon, dt.strftime("%Y-%m-%d"), dt.strftime("%H%M"), sat, "VIIRS")
    return {
        "id": uuid.uuid4(),
        "source": "VIIRS_NOAA20_NRT",
        "latitude": lat,
        "longitude": lon,
        "acquisition_datetime": dt,
        "acq_date": dt.strftime("%Y-%m-%d"),
        "acq_time": dt.strftime("%H%M"),
        "satellite": sat,
        "instrument": "VIIRS",
        "brightness": ti4,
        "bright_ti4": ti4,
        "bright_ti5": 290.0,
        "frp": frp,
        "confidence": conf,
        "daynight": daynight,
        "raw_data": {},
        "observation_hash": h,
    }


@pytest.mark.asyncio
async def test_forest_context_vegetation_fire(async_session: AsyncSession):
    """Forest proximity + high FRP -> primary_cause == 'vegetation_fire'."""
    t0 = datetime(2026, 8, 29, 14, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 29, 22, 0, tzinfo=timezone.utc)

    obs1 = _make_obs(39.5, -121.5, t0, frp=110.0, conf="high", daynight="D")
    obs2 = _make_obs(39.51, -121.51, t1, frp=85.0, conf="high", daynight="N")

    await observation_repository.bulk_create_observations(async_session, [obs1, obs2])
    await async_session.commit()
    await clustering_service.cluster_unassigned_observations(async_session)
    await async_session.commit()

    events, _ = await event_service.list_events(async_session)
    ev_id = events[0].id

    mock_weather = WeatherContext(
        latitude=39.5,
        longitude=-121.5,
        acquisition_datetime=t0,
        temperature=35.0,
        relative_humidity=15.0,
        wind_speed=22.0,
        precipitation=0.0,
    )
    mock_geo = GeospatialContext(
        latitude=39.5,
        longitude=-121.5,
        radius_m=3000.0,
        forests=[
            NearbyFeature(feature_type="forest", name="Sierra National Forest", distance_m=120.0, osm_id=1, osm_type="way", tags={})
        ],
    )

    with patch("app.services.weather_service.fetch_weather", AsyncMock(return_value=mock_weather)), \
         patch("app.services.geospatial_service.fetch_nearby_context", AsyncMock(return_value=mock_geo)):
        res = await attribution_service.classify_event(async_session, ev_id)

    assert res is not None
    assert res.primary_cause == "vegetation_fire"
    assert res.confidence >= 0.70
    veg_score = next(c.score for c in res.possible_causes if c.cause == "vegetation_fire")
    ind_score = next(c.score for c in res.possible_causes if c.cause == "industrial_heat")
    assert veg_score > ind_score
    assert any(e.factor == "Forest / Woodland Proximity" and e.impact == "supports" for e in res.evidence)


@pytest.mark.asyncio
async def test_cropland_context_agricultural_burning(async_session: AsyncSession):
    """Farmland proximity + daytime moderate FRP -> primary_cause == 'agricultural_burning'."""
    t0 = datetime(2026, 8, 29, 11, 0, tzinfo=timezone.utc)
    obs = _make_obs(36.8, -119.8, t0, frp=18.0, conf="nominal", daynight="D")

    await observation_repository.bulk_create_observations(async_session, [obs])
    await async_session.commit()
    await clustering_service.cluster_unassigned_observations(async_session)
    await async_session.commit()

    events, _ = await event_service.list_events(async_session)
    ev_id = events[0].id

    mock_geo = GeospatialContext(
        latitude=36.8,
        longitude=-119.8,
        radius_m=3000.0,
        croplands=[
            NearbyFeature(feature_type="cropland", name="Central Valley Farmland", distance_m=150.0, osm_id=2, osm_type="way", tags={})
        ],
    )

    with patch("app.services.weather_service.fetch_weather", AsyncMock(return_value=None)), \
         patch("app.services.geospatial_service.fetch_nearby_context", AsyncMock(return_value=mock_geo)):
        res = await attribution_service.classify_event(async_session, ev_id)

    assert res is not None
    assert res.primary_cause == "agricultural_burning"
    agri_score = next(c.score for c in res.possible_causes if c.cause == "agricultural_burning")
    veg_score = next(c.score for c in res.possible_causes if c.cause == "vegetation_fire")
    assert agri_score > veg_score
    assert any(e.factor == "Cropland / Farmland Proximity" for e in res.evidence)


@pytest.mark.asyncio
async def test_industrial_context_industrial_heat(async_session: AsyncSession):
    """Industrial plant proximity + nighttime pass -> primary_cause == 'industrial_heat'."""
    t0 = datetime(2026, 8, 29, 2, 30, tzinfo=timezone.utc)
    obs = _make_obs(29.7, -95.1, t0, frp=15.0, conf="nominal", daynight="N")

    await observation_repository.bulk_create_observations(async_session, [obs])
    await async_session.commit()
    await clustering_service.cluster_unassigned_observations(async_session)
    await async_session.commit()

    events, _ = await event_service.list_events(async_session)
    ev_id = events[0].id

    mock_geo = GeospatialContext(
        latitude=29.7,
        longitude=-95.1,
        radius_m=3000.0,
        industrial=[
            NearbyFeature(feature_type="industrial", name="Chemical Plant", distance_m=100.0, osm_id=3, osm_type="way", tags={})
        ],
    )

    with patch("app.services.weather_service.fetch_weather", AsyncMock(return_value=None)), \
         patch("app.services.geospatial_service.fetch_nearby_context", AsyncMock(return_value=mock_geo)):
        res = await attribution_service.classify_event(async_session, ev_id)

    assert res is not None
    assert res.primary_cause == "industrial_heat"
    ind_score = next(c.score for c in res.possible_causes if c.cause == "industrial_heat")
    veg_score = next(c.score for c in res.possible_causes if c.cause == "vegetation_fire")
    assert ind_score > veg_score


@pytest.mark.asyncio
async def test_gas_flare_context(async_session: AsyncSession):
    """Tagged gas flare proximity + high T4 -> primary_cause == 'gas_flare'."""
    t0 = datetime(2026, 8, 29, 1, 0, tzinfo=timezone.utc)
    obs = _make_obs(31.5, -102.5, t0, frp=12.0, conf="nominal", daynight="N", ti4=345.0)

    await observation_repository.bulk_create_observations(async_session, [obs])
    await async_session.commit()
    await clustering_service.cluster_unassigned_observations(async_session)
    await async_session.commit()

    events, _ = await event_service.list_events(async_session)
    ev_id = events[0].id

    mock_geo = GeospatialContext(
        latitude=31.5,
        longitude=-102.5,
        radius_m=3000.0,
        industrial=[
            NearbyFeature(
                feature_type="industrial",
                name="Permian Flare Stack",
                distance_m=80.0,
                osm_id=4,
                osm_type="node",
                tags={"man_made": "flare"},
            )
        ],
    )

    with patch("app.services.weather_service.fetch_weather", AsyncMock(return_value=None)), \
         patch("app.services.geospatial_service.fetch_nearby_context", AsyncMock(return_value=mock_geo)):
        res = await attribution_service.classify_event(async_session, ev_id)

    assert res is not None
    assert res.primary_cause == "gas_flare"
    flare_score = next(c.score for c in res.possible_causes if c.cause == "gas_flare")
    assert flare_score >= 50.0


@pytest.mark.asyncio
async def test_no_meaningful_evidence_returns_unknown(async_session: AsyncSession):
    """No matching land use, low FRP, mild conditions -> primary_cause == 'unknown'."""
    t0 = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    obs = _make_obs(0.0, 0.0, t0, frp=2.0, conf="low", daynight="D")

    await observation_repository.bulk_create_observations(async_session, [obs])
    await async_session.commit()
    await clustering_service.cluster_unassigned_observations(async_session)
    await async_session.commit()

    events, _ = await event_service.list_events(async_session)
    ev_id = events[0].id

    empty_geo = GeospatialContext(latitude=0.0, longitude=0.0, radius_m=3000.0)

    with patch("app.services.weather_service.fetch_weather", AsyncMock(return_value=None)), \
         patch("app.services.geospatial_service.fetch_nearby_context", AsyncMock(return_value=empty_geo)):
        res = await attribution_service.classify_event(async_session, ev_id)

    assert res is not None
    assert res.primary_cause == "unknown"


@pytest.mark.asyncio
async def test_single_observation_attribution(async_session: AsyncSession):
    """Directly classifying a single observation without clustering."""
    t0 = datetime(2026, 8, 29, 15, 0, tzinfo=timezone.utc)
    obs_dict = _make_obs(45.0, -120.0, t0, frp=150.0, conf="high", daynight="D")

    await observation_repository.bulk_create_observations(async_session, [obs_dict])
    await async_session.commit()

    obs_id = obs_dict["id"]

    mock_geo = GeospatialContext(
        latitude=45.0,
        longitude=-120.0,
        radius_m=2000.0,
        forests=[NearbyFeature(feature_type="forest", name="Pine Ridge", distance_m=50.0, osm_id=5, osm_type="way", tags={})],
    )

    with patch("app.services.weather_service.fetch_weather", AsyncMock(return_value=None)), \
         patch("app.services.geospatial_service.fetch_nearby_context", AsyncMock(return_value=mock_geo)):
        res = await attribution_service.classify_observation(async_session, obs_id)

    assert res is not None
    assert res.entity_type == "observation"
    assert res.entity_id == str(obs_id)
    assert res.primary_cause == "vegetation_fire"


@pytest.mark.asyncio
async def test_attribution_api_endpoints(client: AsyncClient, async_session: AsyncSession):
    """Verify REST API routes for event and observation attribution."""
    t0 = datetime(2026, 8, 29, 13, 0, tzinfo=timezone.utc)
    obs_dict = _make_obs(36.5, -119.5, t0, frp=15.0, conf="high", daynight="D")
    await observation_repository.bulk_create_observations(async_session, [obs_dict])
    await async_session.commit()
    await clustering_service.cluster_unassigned_observations(async_session)
    await async_session.commit()

    events, _ = await event_service.list_events(async_session)
    ev_id = events[0].id
    obs_id = obs_dict["id"]

    with patch("app.services.weather_service.fetch_weather", AsyncMock(return_value=None)), \
         patch("app.services.geospatial_service.fetch_nearby_context", AsyncMock(return_value=None)):
        # 1. Event attribution route
        resp_ev = await client.get(f"/api/attribution/event/{ev_id}")
        assert resp_ev.status_code == 200
        data_ev = resp_ev.json()
        assert data_ev["entity_id"] == str(ev_id)
        assert "primary_cause" in data_ev
        assert "possible_causes" in data_ev
        assert "evidence" in data_ev
        assert "reasoning_summary" in data_ev

        # 2. Observation attribution route
        resp_obs = await client.get(f"/api/attribution/observation/{obs_id}")
        assert resp_obs.status_code == 200
        data_obs = resp_obs.json()
        assert data_obs["entity_id"] == str(obs_id)
        assert data_obs["entity_type"] == "observation"

        # 3. Alias /api/events/{id}/intelligence
        resp_alias = await client.get(f"/api/events/{ev_id}/intelligence")
        assert resp_alias.status_code == 200
        assert resp_alias.json()["entity_id"] == str(ev_id)
