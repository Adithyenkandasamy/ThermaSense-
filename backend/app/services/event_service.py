"""
Event service — business logic orchestrator for ThermalEvent.

Provides event lifecycle operations that delegate to the
event_repository for database access. No clustering or
attribution logic; this is purely the data foundation.
"""

import logging
import uuid
from datetime import datetime
from typing import Literal, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.thermal_event import ThermalEvent
from app.repositories import event_repository

logger = logging.getLogger(__name__)

VALID_STATUSES = {"active", "inactive"}


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
    """
    Create a new thermal event.

    Raises:
        ValueError: If status is not 'active' or 'inactive'.
    """
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}"
        )

    return await event_repository.create_event(
        session,
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


async def get_event(
    session: AsyncSession,
    event_id: uuid.UUID,
) -> Optional[ThermalEvent]:
    """Retrieve a single thermal event by UUID."""
    return await event_repository.get_event_by_id(session, event_id)


async def update_event(
    session: AsyncSession,
    event_id: uuid.UUID,
    **kwargs,
) -> Optional[ThermalEvent]:
    """
    Update a thermal event.

    Raises:
        ValueError: If an invalid status is provided.
    """
    if "status" in kwargs and kwargs["status"] not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{kwargs['status']}'. Must be one of: {VALID_STATUSES}"
        )

    return await event_repository.update_event(session, event_id, **kwargs)


async def delete_event(
    session: AsyncSession,
    event_id: uuid.UUID,
) -> bool:
    """Delete a thermal event and unlink its observations."""
    return await event_repository.delete_event(session, event_id)


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
    """Paginated, filterable listing of thermal events."""
    return await event_repository.list_events(
        session,
        status=status,
        start_after=start_after,
        start_before=start_before,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
        limit=limit,
        offset=offset,
    )


async def link_observations(
    session: AsyncSession,
    event_id: uuid.UUID,
    observation_ids: list[uuid.UUID],
) -> int:
    """
    Link observations to an event.

    Returns the count of observations actually linked.
    """
    # Verify event exists
    event = await event_repository.get_event_by_id(session, event_id)
    if event is None:
        raise ValueError(f"Event {event_id} not found")

    return await event_repository.link_observations_to_event(
        session, event_id, observation_ids
    )


async def get_event_summary_for_attribution(
    session: AsyncSession,
    event_id: uuid.UUID,
) -> Optional[dict]:
    """
    Fetch a ThermalEvent with all associated observations and compute
    a rich summary payload ready for the Attribution & Cause Engine.
    """
    event = await event_repository.get_event_by_id(session, event_id)
    if event is None:
        return None

    observations = event.observations or []
    frp_vals = [o.frp for o in observations if o.frp is not None]
    brightness_vals = [o.brightness for o in observations if o.brightness is not None]
    daynight_vals = [o.daynight for o in observations if o.daynight]
    satellites = list(set(o.satellite for o in observations if o.satellite))

    duration_hours = 0.0
    if event.started_at and event.ended_at:
        duration_hours = max(
            0.0,
            (event.ended_at - event.started_at).total_seconds() / 3600.0,
        )

    return {
        "event": event,
        "observations": observations,
        "summary": {
            "event_id": str(event.id),
            "status": event.status,
            "centroid": {
                "latitude": event.centroid_latitude,
                "longitude": event.centroid_longitude,
            },
            "started_at": event.started_at,
            "ended_at": event.ended_at,
            "duration_hours": duration_hours,
            "observation_count": len(observations),
            "total_frp": sum(frp_vals) if frp_vals else 0.0,
            "max_frp": max(frp_vals) if frp_vals else 0.0,
            "avg_frp": sum(frp_vals) / len(frp_vals) if frp_vals else 0.0,
            "max_brightness": max(brightness_vals) if brightness_vals else None,
            "max_confidence": event.max_confidence,
            "satellites": satellites,
            "daynight_counts": {
                "day": sum(1 for d in daynight_vals if d == "D"),
                "night": sum(1 for d in daynight_vals if d == "N"),
            },
        },
    }

