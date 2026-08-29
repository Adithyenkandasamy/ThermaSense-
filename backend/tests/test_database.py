"""
End-to-end database repository and service integration tests.
Tests table creation, storage, deduplication, filtering, pagination, and ingestion logging.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.thermal_observation import ThermalObservation
from app.repositories import ingestion_repository, observation_repository
from app.services.observation_normalizer import _generate_observation_hash


@pytest_asyncio.fixture
async def async_session():
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


@pytest.mark.asyncio
async def test_observation_crud_and_deduplication(async_session: AsyncSession):
    """Test inserting observations, deduplicating on second insert, and querying."""
    obs_hash1 = _generate_observation_hash(
        "VIIRS_NOAA20_NRT", 37.77, -122.41, "2026-08-29", "1200", "NOAA-20", "VIIRS"
    )
    obs_hash2 = _generate_observation_hash(
        "VIIRS_NOAA20_NRT", 34.05, -118.24, "2026-08-29", "1200", "NOAA-20", "VIIRS"
    )

    batch1 = [
        {
            "id": uuid.uuid4(),
            "source": "VIIRS_NOAA20_NRT",
            "latitude": 37.77,
            "longitude": -122.41,
            "acquisition_datetime": datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
            "acq_date": "2026-08-29",
            "acq_time": "1200",
            "satellite": "NOAA-20",
            "instrument": "VIIRS",
            "brightness": 320.5,
            "bright_ti4": 320.5,
            "bright_ti5": 295.0,
            "frp": 15.0,
            "confidence": "nominal",
            "daynight": "D",
            "raw_data": {"test": "data1"},
            "observation_hash": obs_hash1,
        },
        {
            "id": uuid.uuid4(),
            "source": "VIIRS_NOAA20_NRT",
            "latitude": 34.05,
            "longitude": -118.24,
            "acquisition_datetime": datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
            "acq_date": "2026-08-29",
            "acq_time": "1200",
            "satellite": "NOAA-20",
            "instrument": "VIIRS",
            "brightness": 310.0,
            "bright_ti4": 310.0,
            "bright_ti5": 290.0,
            "frp": 8.0,
            "confidence": "high",
            "daynight": "D",
            "raw_data": {"test": "data2"},
            "observation_hash": obs_hash2,
        },
    ]

    # First insert: 2 inserted, 0 duplicates
    inserted, duplicates = await observation_repository.bulk_create_observations(
        async_session, batch1
    )
    await async_session.commit()
    assert inserted == 2
    assert duplicates == 0

    # Second insert with same items + 1 new item
    obs_hash3 = _generate_observation_hash(
        "VIIRS_NOAA21_NRT", 40.71, -74.00, "2026-08-29", "1300", "NOAA-21", "VIIRS"
    )
    batch2 = [
        batch1[0],  # Duplicate
        batch1[1],  # Duplicate
        {
            "id": uuid.uuid4(),
            "source": "VIIRS_NOAA21_NRT",
            "latitude": 40.71,
            "longitude": -74.00,
            "acquisition_datetime": datetime(2026, 8, 29, 13, 0, tzinfo=timezone.utc),
            "acq_date": "2026-08-29",
            "acq_time": "1300",
            "satellite": "NOAA-21",
            "instrument": "VIIRS",
            "brightness": 330.0,
            "bright_ti4": 330.0,
            "bright_ti5": 298.0,
            "frp": 25.0,
            "confidence": "high",
            "daynight": "D",
            "raw_data": {"test": "data3"},
            "observation_hash": obs_hash3,
        },
    ]

    inserted, duplicates = await observation_repository.bulk_create_observations(
        async_session, batch2
    )
    await async_session.commit()
    assert inserted == 1
    assert duplicates == 2

    # Query with filters
    results, total = await observation_repository.list_observations(
        async_session,
        satellite="NOAA-20",
    )
    assert total == 2
    assert len(results) == 2

    # Query with bounding box filter
    results_bbox, total_bbox = await observation_repository.list_observations(
        async_session,
        min_lat=35.0,
        max_lat=42.0,
        min_lon=-125.0,
        max_lon=-70.0,
    )
    assert total_bbox == 2  # SF (37.77, -122.41) and NY (40.71, -74.00)

    # Query by ID
    single_obs = await observation_repository.get_observation_by_id(
        async_session, batch1[0]["id"]
    )
    assert single_obs is not None
    assert single_obs.latitude == 37.77


@pytest.mark.asyncio
async def test_ingestion_log_workflow(async_session: AsyncSession):
    """Test creating and completing an ingestion log."""
    log = await ingestion_repository.create_ingestion_log(
        async_session,
        source="VIIRS_NOAA20_NRT",
        area="world",
        day_range=1,
    )
    await async_session.commit()
    assert log.status == "pending"

    updated = await ingestion_repository.update_ingestion_log(
        async_session,
        log.id,
        status="success",
        records_fetched=100,
        records_stored=80,
        duplicates_skipped=20,
        invalid_records=0,
    )
    await async_session.commit()
    assert updated is not None
    assert updated.status == "success"
    assert updated.records_stored == 80
    assert updated.duplicates_skipped == 20
    assert updated.completed_at is not None
