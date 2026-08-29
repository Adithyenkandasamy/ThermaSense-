"""
Observation repository — database access layer.

All direct database queries for ThermalObservation live here.
Routes and services never touch SQLAlchemy sessions directly.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.thermal_observation import ThermalObservation

logger = logging.getLogger(__name__)


async def create_observation(
    session: AsyncSession,
    observation: ThermalObservation,
) -> ThermalObservation:
    """Insert a single observation. Raises on duplicate hash."""
    session.add(observation)
    await session.flush()
    return observation


async def bulk_create_observations(
    session: AsyncSession,
    observations: list[dict],
) -> tuple[int, int]:
    """
    Bulk insert observations using ON CONFLICT DO NOTHING.

    Args:
        session: Async database session.
        observations: List of dicts matching ThermalObservation columns.

    Returns:
        Tuple of (inserted_count, duplicate_count).
    """
    if not observations:
        return 0, 0

    bind = session.bind
    dialect_name = bind.dialect.name if bind else "postgresql"

    if dialect_name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        stmt = sqlite_insert(ThermalObservation).values(observations)
        stmt = stmt.on_conflict_do_nothing(index_elements=["observation_hash"])
    else:
        stmt = pg_insert(ThermalObservation).values(observations)
        stmt = stmt.on_conflict_do_nothing(index_elements=["observation_hash"])

    result = await session.execute(stmt)
    inserted = result.rowcount  # type: ignore[union-attr]

    duplicates = len(observations) - inserted
    logger.info(
        "Bulk insert: %d inserted, %d duplicates skipped",
        inserted,
        duplicates,
    )
    return inserted, duplicates


async def get_observation_by_id(
    session: AsyncSession,
    observation_id: uuid.UUID,
) -> Optional[ThermalObservation]:
    """Fetch a single observation by UUID."""
    result = await session.execute(
        select(ThermalObservation).where(ThermalObservation.id == observation_id)
    )
    return result.scalar_one_or_none()


async def get_observation_by_hash(
    session: AsyncSession,
    observation_hash: str,
) -> Optional[ThermalObservation]:
    """Check if an observation with this hash already exists."""
    result = await session.execute(
        select(ThermalObservation).where(
            ThermalObservation.observation_hash == observation_hash
        )
    )
    return result.scalar_one_or_none()


async def list_observations(
    session: AsyncSession,
    *,
    source: Optional[str] = None,
    satellite: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    min_lat: Optional[float] = None,
    min_lon: Optional[float] = None,
    max_lat: Optional[float] = None,
    max_lon: Optional[float] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[ThermalObservation], int]:
    """
    Paginated, filterable list of stored observations.

    Returns:
        Tuple of (observations, total_count).
    """
    query = select(ThermalObservation)
    count_query = select(func.count(ThermalObservation.id))

    # ── Apply filters ─────────────────────────────────────────
    if source:
        query = query.where(ThermalObservation.source == source)
        count_query = count_query.where(ThermalObservation.source == source)
    if satellite:
        query = query.where(ThermalObservation.satellite == satellite)
        count_query = count_query.where(ThermalObservation.satellite == satellite)
    if start_date:
        query = query.where(ThermalObservation.acquisition_datetime >= start_date)
        count_query = count_query.where(
            ThermalObservation.acquisition_datetime >= start_date
        )
    if end_date:
        query = query.where(ThermalObservation.acquisition_datetime <= end_date)
        count_query = count_query.where(
            ThermalObservation.acquisition_datetime <= end_date
        )
    if min_lat is not None:
        query = query.where(ThermalObservation.latitude >= min_lat)
        count_query = count_query.where(ThermalObservation.latitude >= min_lat)
    if max_lat is not None:
        query = query.where(ThermalObservation.latitude <= max_lat)
        count_query = count_query.where(ThermalObservation.latitude <= max_lat)
    if min_lon is not None:
        query = query.where(ThermalObservation.longitude >= min_lon)
        count_query = count_query.where(ThermalObservation.longitude >= min_lon)
    if max_lon is not None:
        query = query.where(ThermalObservation.longitude <= max_lon)
        count_query = count_query.where(ThermalObservation.longitude <= max_lon)

    # ── Order, paginate ───────────────────────────────────────
    query = query.order_by(ThermalObservation.acquisition_datetime.desc())
    query = query.limit(limit).offset(offset)

    # ── Execute ───────────────────────────────────────────────
    result = await session.execute(query)
    observations = result.scalars().all()

    count_result = await session.execute(count_query)
    total = count_result.scalar_one()

    return observations, total
