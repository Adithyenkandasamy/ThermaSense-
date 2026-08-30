"""
Unit and integration tests for ThermalEvent foundation (Module 4).

Tests:
  - ThermalEvent ORM model & schema serialization
  - 1:N relationship with ThermalObservation (nullable event_id)
  - EventRepository CRUD, pagination, and temporal/spatial filtering
  - EventService validations and error handling
  - Events API endpoints: GET /api/events, GET /api/events/{id}
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
from app.repositories import event_repository, observation_repository
from app.services import event_service
from app.services.observation_normalizer import _generate_observation_hash


@pytest_asyncio.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an isolated in-memory test database with full schema."""
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


@pytest.mark.asyncio
async def test_create_and_get_event(async_session: AsyncSession):
    """Test creating an event and fetching it by ID."""
    started = datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc)
    event = await event_service.create_event(
        async_session,
        centroid_latitude=34.05,
        centroid_longitude=-118.25,
        started_at=started,
        status="active",
        total_frp=125.4,
        max_confidence="high",
        observation_count=3,
        description="Wildfire cluster detection in Southern California",
    )
    await async_session.commit()

    assert event.id is not None
    assert event.status == "active"
    assert event.centroid_latitude == 34.05
    assert event.centroid_longitude == -118.25
    assert event.total_frp == 125.4

    fetched = await event_service.get_event(async_session, event.id)
    assert fetched is not None
    assert fetched.id == event.id
    assert fetched.status == "active"
    assert fetched.description == "Wildfire cluster detection in Southern California"


@pytest.mark.asyncio
async def test_invalid_status_raises_error(async_session: AsyncSession):
    """Test that invalid statuses are rejected at the service level."""
    started = datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="Invalid status"):
        await event_service.create_event(
            async_session,
            centroid_latitude=34.05,
            centroid_longitude=-118.25,
            started_at=started,
            status="pending",  # Invalid, only active/inactive allowed
        )


@pytest.mark.asyncio
async def test_event_observation_relationship_and_unlinking(
    async_session: AsyncSession,
):
    """Test 1:N relationship, linking observations, and SET NULL on event deletion."""
    obs_hash = _generate_observation_hash(
        "VIIRS_NOAA20_NRT", 34.05, -118.25, "2026-08-29", "1000", "NOAA-20", "VIIRS"
    )
    obs_id = uuid.uuid4()
    obs_dict = {
        "id": obs_id,
        "source": "VIIRS_NOAA20_NRT",
        "latitude": 34.05,
        "longitude": -118.25,
        "acquisition_datetime": datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc),
        "acq_date": "2026-08-29",
        "acq_time": "1000",
        "satellite": "NOAA-20",
        "instrument": "VIIRS",
        "brightness": 330.0,
        "bright_ti4": 330.0,
        "bright_ti5": 298.0,
        "frp": 45.0,
        "confidence": "high",
        "daynight": "D",
        "raw_data": {"test": "obs"},
        "observation_hash": obs_hash,
    }
    await observation_repository.bulk_create_observations(
        async_session, [obs_dict]
    )
    await async_session.commit()

    # Create event
    event = await event_service.create_event(
        async_session,
        centroid_latitude=34.05,
        centroid_longitude=-118.25,
        started_at=datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc),
        status="active",
    )
    await async_session.commit()

    # Link observation to event
    linked_count = await event_service.link_observations(
        async_session, event.id, [obs_id]
    )
    await async_session.commit()
    assert linked_count == 1

    # Reload event and verify relationship
    loaded_event = await event_service.get_event(async_session, event.id)
    assert loaded_event is not None
    assert len(loaded_event.observations) == 1
    assert loaded_event.observations[0].id == obs_id

    # Observation still exists and its event_id is set
    obs = await observation_repository.get_observation_by_id(
        async_session, obs_id
    )
    assert obs is not None
    assert obs.event_id == event.id

    # Delete event: observation should remain, but with event_id = None
    deleted = await event_service.delete_event(async_session, event.id)
    await async_session.commit()
    assert deleted is True

    obs_after = await observation_repository.get_observation_by_id(
        async_session, obs_id
    )
    assert obs_after is not None
    assert obs_after.event_id is None


@pytest.mark.asyncio
async def test_list_events_filtering(async_session: AsyncSession):
    """Test filtering events by status, started_at temporal range, and spatial bbox."""
    # Create 3 events
    e1 = await event_service.create_event(
        async_session,
        centroid_latitude=37.77,
        centroid_longitude=-122.41,
        started_at=datetime(2026, 8, 28, 8, 0, tzinfo=timezone.utc),
        status="active",
        observation_count=2,
    )
    e2 = await event_service.create_event(
        async_session,
        centroid_latitude=34.05,
        centroid_longitude=-118.25,
        started_at=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
        status="inactive",
        observation_count=5,
    )
    e3 = await event_service.create_event(
        async_session,
        centroid_latitude=40.71,
        centroid_longitude=-74.00,
        started_at=datetime(2026, 8, 30, 14, 0, tzinfo=timezone.utc),
        status="active",
        observation_count=1,
    )
    await async_session.commit()

    # Filter by status = active
    active_events, total = await event_service.list_events(
        async_session, status="active"
    )
    assert total == 2
    assert {e.id for e in active_events} == {e1.id, e3.id}

    # Filter by started_at date range
    events_date, total = await event_service.list_events(
        async_session,
        start_after=datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc),
        start_before=datetime(2026, 8, 29, 23, 59, tzinfo=timezone.utc),
    )
    assert total == 1
    assert events_date[0].id == e2.id

    # Filter by bounding box (California bbox)
    events_bbox, total = await event_service.list_events(
        async_session,
        min_lat=32.0,
        max_lat=39.0,
        min_lon=-125.0,
        max_lon=-114.0,
    )
    assert total == 2
    assert {e.id for e in events_bbox} == {e1.id, e2.id}


@pytest.mark.asyncio
async def test_events_api_endpoints(client: AsyncClient, async_session: AsyncSession):
    """Test GET /api/events and GET /api/events/{event_id} routes."""
    # Seed an event
    started = datetime(2026, 8, 29, 15, 30, tzinfo=timezone.utc)
    event = await event_service.create_event(
        async_session,
        centroid_latitude=35.5,
        centroid_longitude=-119.5,
        started_at=started,
        status="active",
        total_frp=88.5,
        max_confidence="high",
        observation_count=4,
        description="Central Valley fire event",
    )
    await async_session.commit()

    # 1. GET /api/events
    resp = await client.get("/api/events")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["limit"] == 50
    assert data["offset"] == 0
    assert len(data["events"]) >= 1

    matching = next((e for e in data["events"] if e["id"] == str(event.id)), None)
    assert matching is not None
    assert matching["status"] == "active"
    assert matching["centroid_latitude"] == 35.5
    assert matching["centroid_longitude"] == -119.5
    assert matching["total_frp"] == 88.5

    # 2. GET /api/events?status=inactive -> 0
    resp_inactive = await client.get("/api/events?status=inactive")
    assert resp_inactive.status_code == 200
    assert resp_inactive.json()["total"] == 0

    # 3. GET /api/events?status=invalid -> 400
    resp_invalid = await client.get("/api/events?status=invalid")
    assert resp_invalid.status_code == 400

    # 4. GET /api/events/{id}
    resp_single = await client.get(f"/api/events/{event.id}")
    assert resp_single.status_code == 200
    single_data = resp_single.json()
    assert single_data["id"] == str(event.id)
    assert single_data["description"] == "Central Valley fire event"
    assert isinstance(single_data["observations"], list)

    # 5. GET /api/events/{random_id} -> 404
    random_id = uuid.uuid4()
    resp_404 = await client.get(f"/api/events/{random_id}")
    assert resp_404.status_code == 404
