"""
Unit and integration tests for Spatio-Temporal Event Clustering (Module 4 Part B).

Tests:
  - Haversine distance calculation
  - Nearby + close time -> same event cluster
  - Distant locations -> separate events
  - Same location + large time gap -> separate events
  - Incremental observation updates existing active event
  - Centroid arithmetic mean correctness
  - Max FRP, total FRP, and max confidence calculations
  - Duplicate event prevention (idempotence)
  - Attribution Engine summary payload verification
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import Base
from app.models.thermal_event import ThermalEvent
from app.models.thermal_observation import ThermalObservation
from app.repositories import observation_repository
from app.services import clustering_service, event_service
from app.services.clustering_service import (
    haversine_distance_km,
    cluster_unassigned_observations,
)
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


def _make_obs_dict(
    lat: float,
    lon: float,
    dt: datetime,
    frp: float = 10.0,
    confidence: str = "nominal",
    satellite: str = "NOAA-20",
    daynight: str = "D",
) -> dict:
    """Helper to create a test observation dictionary."""
    obs_id = uuid.uuid4()
    acq_date = dt.strftime("%Y-%m-%d")
    acq_time = dt.strftime("%H%M")
    h = _generate_observation_hash(
        "VIIRS_NOAA20_NRT", lat, lon, acq_date, acq_time, satellite, "VIIRS"
    )
    return {
        "id": obs_id,
        "source": "VIIRS_NOAA20_NRT",
        "latitude": lat,
        "longitude": lon,
        "acquisition_datetime": dt,
        "acq_date": acq_date,
        "acq_time": acq_time,
        "satellite": satellite,
        "instrument": "VIIRS",
        "brightness": 320.0,
        "bright_ti4": 320.0,
        "bright_ti5": 295.0,
        "frp": frp,
        "confidence": confidence,
        "daynight": daynight,
        "raw_data": {},
        "observation_hash": h,
    }


def test_haversine_distance():
    """Verify Haversine distance accuracy against known reference points."""
    # Distance from SF (37.7749, -122.4194) to Oakland (37.8044, -122.2711) ~ 13.5 km
    dist = haversine_distance_km(37.7749, -122.4194, 37.8044, -122.2711)
    assert 13.0 <= dist <= 14.5

    # Same point distance is 0
    assert haversine_distance_km(34.0, -118.0, 34.0, -118.0) == 0.0


@pytest.mark.asyncio
async def test_nearby_and_close_time_cluster_same_event(
    async_session: AsyncSession,
):
    """Two observations within 2 km and 2 hours should merge into one event."""
    t0 = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 29, 13, 30, tzinfo=timezone.utc)

    # Coordinates ~1.1 km apart
    obs1 = _make_obs_dict(34.050, -118.250, t0, frp=15.0, confidence="nominal")
    obs2 = _make_obs_dict(34.058, -118.255, t1, frp=25.0, confidence="high")

    await observation_repository.bulk_create_observations(
        async_session, [obs1, obs2]
    )
    await async_session.commit()

    result = await cluster_unassigned_observations(
        async_session,
        spatial_threshold_km=5.0,
        temporal_threshold_hours=24.0,
    )
    await async_session.commit()

    assert result["observations_processed"] == 2
    assert result["events_created"] == 1
    assert result["events_updated"] == 1

    # Verify event metrics
    events_res = await async_session.execute(select(ThermalEvent))
    events = events_res.scalars().all()
    assert len(events) == 1

    ev = events[0]
    assert ev.observation_count == 2
    assert ev.status == "active"
    assert clustering_service._ensure_utc(ev.started_at) == t0
    assert clustering_service._ensure_utc(ev.ended_at) == t1
    assert ev.total_frp == 40.0
    assert ev.max_confidence == "high"
    # Centroid check
    assert pytest.approx(ev.centroid_latitude, 0.0001) == (34.050 + 34.058) / 2
    assert pytest.approx(ev.centroid_longitude, 0.0001) == (-118.250 + -118.255) / 2


@pytest.mark.asyncio
async def test_distant_observations_create_separate_events(
    async_session: AsyncSession,
):
    """Two observations at the same time but distant (> 100 km) create separate events."""
    t0 = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)

    # LA vs San Diego (~180 km)
    obs_la = _make_obs_dict(34.05, -118.25, t0, frp=50.0)
    obs_sd = _make_obs_dict(32.71, -117.16, t0, frp=30.0)

    await observation_repository.bulk_create_observations(
        async_session, [obs_la, obs_sd]
    )
    await async_session.commit()

    result = await cluster_unassigned_observations(
        async_session,
        spatial_threshold_km=5.0,
        temporal_threshold_hours=24.0,
    )
    await async_session.commit()

    assert result["observations_processed"] == 2
    assert result["events_created"] == 2

    events_res = await async_session.execute(select(ThermalEvent))
    events = events_res.scalars().all()
    assert len(events) == 2


@pytest.mark.asyncio
async def test_same_location_large_time_gap_creates_separate_events(
    async_session: AsyncSession,
):
    """Two observations at same location but 48 hours apart create separate events."""
    t0 = datetime(2026, 8, 27, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc)  # 48 hours later

    obs1 = _make_obs_dict(35.0, -119.0, t0, frp=20.0)
    obs2 = _make_obs_dict(35.0, -119.0, t1, frp=25.0)

    await observation_repository.bulk_create_observations(
        async_session, [obs1, obs2]
    )
    await async_session.commit()

    result = await cluster_unassigned_observations(
        async_session,
        spatial_threshold_km=5.0,
        temporal_threshold_hours=24.0,  # 24h limit
    )
    await async_session.commit()

    assert result["observations_processed"] == 2
    assert result["events_created"] == 2

    events_res = await async_session.execute(select(ThermalEvent))
    events = events_res.scalars().all()
    assert len(events) == 2


@pytest.mark.asyncio
async def test_incremental_observation_updates_existing_event(
    async_session: AsyncSession,
):
    """Ingesting an incremental observation later adds it to the existing active event."""
    t0 = datetime(2026, 8, 29, 6, 0, tzinfo=timezone.utc)
    obs1 = _make_obs_dict(36.000, -120.000, t0, frp=10.0, confidence="low")

    await observation_repository.bulk_create_observations(
        async_session, [obs1]
    )
    await async_session.commit()

    # Step 1: Cluster initial observation
    res1 = await cluster_unassigned_observations(async_session)
    await async_session.commit()
    assert res1["events_created"] == 1

    events_res = await async_session.execute(select(ThermalEvent))
    event_initial = events_res.scalars().one()
    initial_event_id = event_initial.id
    assert event_initial.observation_count == 1
    assert event_initial.total_frp == 10.0
    assert event_initial.max_confidence == "low"

    # Step 2: Ingest incremental observation 4 hours later, 2 km away
    t1 = datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc)
    obs2 = _make_obs_dict(36.015, -120.010, t1, frp=50.0, confidence="high")
    await observation_repository.bulk_create_observations(
        async_session, [obs2]
    )
    await async_session.commit()

    # Step 3: Cluster second batch
    res2 = await cluster_unassigned_observations(async_session)
    await async_session.commit()
    assert res2["observations_processed"] == 1
    assert res2["events_created"] == 0
    assert res2["events_updated"] == 1

    # Reload event
    event_updated = await event_service.get_event(async_session, initial_event_id)
    assert event_updated is not None
    assert event_updated.observation_count == 2
    assert event_updated.total_frp == 60.0
    assert event_updated.max_confidence == "high"
    assert clustering_service._ensure_utc(event_updated.started_at) == t0
    assert clustering_service._ensure_utc(event_updated.ended_at) == t1


@pytest.mark.asyncio
async def test_duplicate_clustering_idempotence(
    async_session: AsyncSession,
):
    """Running clustering when all observations are already assigned does nothing."""
    t0 = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    obs1 = _make_obs_dict(37.0, -121.0, t0, frp=15.0)

    await observation_repository.bulk_create_observations(
        async_session, [obs1]
    )
    await async_session.commit()

    # First run
    res1 = await cluster_unassigned_observations(async_session)
    await async_session.commit()
    assert res1["observations_processed"] == 1
    assert res1["events_created"] == 1

    # Second run immediately
    res2 = await cluster_unassigned_observations(async_session)
    await async_session.commit()
    assert res2["observations_processed"] == 0
    assert res2["events_created"] == 0
    assert res2["events_updated"] == 0


@pytest.mark.asyncio
async def test_attribution_engine_summary_interface(
    async_session: AsyncSession,
):
    """Verify that event_service.get_event_summary_for_attribution returns rich payload."""
    t0 = datetime(2026, 8, 29, 8, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)

    obs1 = _make_obs_dict(
        34.0, -118.0, t0, frp=20.0, confidence="nominal", satellite="NOAA-20", daynight="D"
    )
    obs2 = _make_obs_dict(
        34.01, -118.01, t1, frp=80.0, confidence="high", satellite="NOAA-21", daynight="N"
    )

    await observation_repository.bulk_create_observations(
        async_session, [obs1, obs2]
    )
    await async_session.commit()

    await cluster_unassigned_observations(async_session)
    await async_session.commit()

    events_res = await async_session.execute(select(ThermalEvent))
    ev = events_res.scalars().one()

    payload = await event_service.get_event_summary_for_attribution(
        async_session, ev.id
    )
    assert payload is not None
    assert "event" in payload
    assert "observations" in payload
    assert len(payload["observations"]) == 2

    summary = payload["summary"]
    assert summary["event_id"] == str(ev.id)
    assert summary["status"] == "active"
    assert summary["observation_count"] == 2
    assert summary["total_frp"] == 100.0
    assert summary["max_frp"] == 80.0
    assert summary["avg_frp"] == 50.0
    assert summary["max_confidence"] == "high"
    assert summary["duration_hours"] == 4.0
    assert set(summary["satellites"]) == {"NOAA-20", "NOAA-21"}
    assert summary["daynight_counts"]["day"] == 1
    assert summary["daynight_counts"]["night"] == 1
