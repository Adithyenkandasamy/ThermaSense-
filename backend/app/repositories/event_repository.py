"""
Event repository — database access layer for ThermalEvent.

All direct database queries for ThermalEvent live here.
Routes and services never touch SQLAlchemy sessions directly.
"""

import logging
import uuid
from datetime import datetime
from typing import Literal, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.thermal_event import ThermalEvent
from app.models.thermal_observation import ThermalObservation

logger = logging.getLogger(__name__)


async def create_event(
    session: AsyncSession,
    *,
    centroid_latitude: float,
    centroid_longitude: float,
    started_at: datetime,
    ended_at: Optional[datetime] = None,
    status: str = "active",
    total_frp: Optional[float] = None,
    max_confidence: Optional[str] = None,
    observation_count: int = 0,
    description: Optional[str] = None,
) -> ThermalEvent:
    """Insert a new thermal event."""
    event = ThermalEvent(
        id=uuid.uuid4(),
        centroid_latitude=centroid_latitude,
        centroid_longitude=centroid_longitude,
        started_at=started_at,
        ended_at=ended_at,
        status=status,
        total_frp=total_frp,
        max_confidence=max_confidence,
        observation_count=observation_count,
        description=description,
    )
    session.add(event)
    await session.flush()
    logger.info("Created ThermalEvent %s", event.id)
    return event


async def get_event_by_id(
    session: AsyncSession,
    event_id: uuid.UUID,
) -> Optional[ThermalEvent]:
    """Fetch a single event by UUID with its linked observations."""
    result = await session.execute(
        select(ThermalEvent)
        .options(selectinload(ThermalEvent.observations))
        .execution_options(populate_existing=True)
        .where(ThermalEvent.id == event_id)
    )
    return result.scalar_one_or_none()


async def update_event(
    session: AsyncSession,
    event_id: uuid.UUID,
    **kwargs,
) -> Optional[ThermalEvent]:
    """Update an existing thermal event with the given fields."""
    event = await get_event_by_id(session, event_id)
    if event is None:
        return None

    for key, value in kwargs.items():
        if hasattr(event, key):
            setattr(event, key, value)

    await session.flush()
    logger.info("Updated ThermalEvent %s: %s", event_id, list(kwargs.keys()))
    return event


async def delete_event(
    session: AsyncSession,
    event_id: uuid.UUID,
) -> bool:
    """
    Delete a thermal event. Unlinks observations (sets event_id=NULL)
    rather than cascading deletes.

    Returns True if the event existed and was deleted.
    """
    event = await get_event_by_id(session, event_id)
    if event is None:
        return False

    # Unlink observations before deleting
    for obs in event.observations:
        obs.event_id = None

    await session.delete(event)
    await session.flush()
    logger.info("Deleted ThermalEvent %s", event_id)
    return True


async def list_events(
    session: AsyncSession,
    *,
    status: Optional[str] = None,
    start_after: Optional[datetime] = None,
    start_before: Optional[datetime] = None,
    min_lat: Optional[float] = None,
    max_lat: Optional[float] = None,
    min_lon: Optional[float] = None,
    max_lon: Optional[float] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[ThermalEvent], int]:
    """
    Paginated, filterable list of thermal events.

    Filtering uses started_at for temporal queries.

    Returns:
        Tuple of (events, total_count).
    """
    query = select(ThermalEvent).options(
        selectinload(ThermalEvent.observations)
    )
    count_query = select(func.count(ThermalEvent.id))

    # ── Apply filters ─────────────────────────────────────────
    if status:
        query = query.where(ThermalEvent.status == status)
        count_query = count_query.where(ThermalEvent.status == status)
    if start_after:
        query = query.where(ThermalEvent.started_at >= start_after)
        count_query = count_query.where(ThermalEvent.started_at >= start_after)
    if start_before:
        query = query.where(ThermalEvent.started_at <= start_before)
        count_query = count_query.where(ThermalEvent.started_at <= start_before)
    if min_lat is not None:
        query = query.where(ThermalEvent.centroid_latitude >= min_lat)
        count_query = count_query.where(ThermalEvent.centroid_latitude >= min_lat)
    if max_lat is not None:
        query = query.where(ThermalEvent.centroid_latitude <= max_lat)
        count_query = count_query.where(ThermalEvent.centroid_latitude <= max_lat)
    if min_lon is not None:
        query = query.where(ThermalEvent.centroid_longitude >= min_lon)
        count_query = count_query.where(ThermalEvent.centroid_longitude >= min_lon)
    if max_lon is not None:
        query = query.where(ThermalEvent.centroid_longitude <= max_lon)
        count_query = count_query.where(ThermalEvent.centroid_longitude <= max_lon)

    # ── Order, paginate ───────────────────────────────────────
    query = query.order_by(ThermalEvent.started_at.desc())
    query = query.limit(limit).offset(offset)

    # ── Execute ───────────────────────────────────────────────
    result = await session.execute(query)
    events = result.scalars().unique().all()

    count_result = await session.execute(count_query)
    total = count_result.scalar_one()

    return events, total


async def link_observations_to_event(
    session: AsyncSession,
    event_id: uuid.UUID,
    observation_ids: list[uuid.UUID],
) -> int:
    """
    Link a batch of observations to an event by setting event_id.

    Returns the number of observations actually updated.
    """
    updated = 0
    for obs_id in observation_ids:
        result = await session.execute(
            select(ThermalObservation).where(ThermalObservation.id == obs_id)
        )
        obs = result.scalar_one_or_none()
        if obs is not None:
            obs.event_id = event_id
            updated += 1

    await session.flush()
    # If event is already in the current session, refresh observations attribute
    event = await get_event_by_id(session, event_id)
    if event is not None:
        await session.refresh(event, attribute_names=["observations"])

    logger.info(
        "Linked %d observations to event %s", updated, event_id
    )
    return updated
