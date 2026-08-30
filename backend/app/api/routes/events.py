"""
Thermal Events API routes.

Endpoints:
  GET  /api/events          — Paginated, filterable list of events
  GET  /api/events/{id}     — Single event with linked observations
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.event import (
    EventListResponse,
    EventObservationSummary,
    EventResponse,
)
from app.services import event_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])


def _event_to_response(event) -> EventResponse:
    """Convert a ThermalEvent ORM instance to its Pydantic response."""
    observations = []
    for obs in (event.observations or []):
        observations.append(
            EventObservationSummary(
                id=str(obs.id),
                latitude=obs.latitude,
                longitude=obs.longitude,
                acquisition_datetime=obs.acquisition_datetime,
                satellite=obs.satellite,
                instrument=obs.instrument,
                brightness=obs.brightness,
                frp=obs.frp,
                confidence=obs.confidence,
            )
        )

    return EventResponse(
        id=str(event.id),
        status=event.status,
        centroid_latitude=event.centroid_latitude,
        centroid_longitude=event.centroid_longitude,
        started_at=event.started_at,
        ended_at=event.ended_at,
        last_detected_at=event.ended_at,  # semantic alias
        total_frp=event.total_frp,
        max_frp=max(
            (o.frp for o in (event.observations or []) if o.frp is not None),
            default=None,
        ),
        max_confidence=event.max_confidence,
        observation_count=event.observation_count,
        description=event.description,
        created_at=event.created_at,
        updated_at=event.updated_at,
        observations=observations,
    )


@router.get(
    "",
    response_model=EventListResponse,
    summary="List thermal events with filtering and pagination",
)
async def list_events(
    status: Optional[str] = Query(
        None,
        description="Filter by event status ('active' or 'inactive')",
    ),
    start_after: Optional[datetime] = Query(
        None,
        description="Filter: started_at >= this ISO 8601 timestamp",
    ),
    start_before: Optional[datetime] = Query(
        None,
        description="Filter: started_at <= this ISO 8601 timestamp",
    ),
    min_lat: Optional[float] = Query(None, description="Minimum latitude"),
    max_lat: Optional[float] = Query(None, description="Maximum latitude"),
    min_lon: Optional[float] = Query(None, description="Minimum longitude"),
    max_lon: Optional[float] = Query(None, description="Maximum longitude"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
) -> EventListResponse:
    """
    Retrieve a paginated list of thermal events.

    Supports filtering by status, temporal range (using started_at),
    and spatial bounding box (centroid coordinates).
    """
    # Validate status if provided
    if status and status not in ("active", "inactive"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Must be 'active' or 'inactive'.",
        )

    events, total = await event_service.list_events(
        db,
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

    return EventListResponse(
        total=total,
        limit=limit,
        offset=offset,
        events=[_event_to_response(e) for e in events],
    )


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    summary="Get a single thermal event by ID",
)
async def get_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> EventResponse:
    """
    Retrieve a single thermal event by its UUID,
    including all linked thermal observations.
    """
    event = await event_service.get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return _event_to_response(event)
