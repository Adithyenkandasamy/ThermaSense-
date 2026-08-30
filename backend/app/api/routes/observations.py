"""
Stored observations API routes (Module 2).

Endpoints:
  GET /api/observations      — Paginated list of stored observations
  GET /api/observations/{id} — Single observation by UUID
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.observation import ObservationListResponse, ObservationResponse
from app.services import observation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/observations", tags=["observations"])


@router.get(
    "",
    response_model=ObservationListResponse,
    summary="List stored thermal observations",
)
async def list_observations(
    source: Optional[str] = Query(
        default=None,
        description="Filter by FIRMS source (e.g. VIIRS_NOAA20_NRT)",
    ),
    satellite: Optional[str] = Query(
        default=None,
        description="Filter by satellite name",
    ),
    start_date: Optional[datetime] = Query(
        default=None,
        description="Filter observations after this datetime (ISO 8601)",
    ),
    end_date: Optional[datetime] = Query(
        default=None,
        description="Filter observations before this datetime (ISO 8601)",
    ),
    min_lat: Optional[float] = Query(
        default=None, ge=-90, le=90,
        description="Minimum latitude",
    ),
    max_lat: Optional[float] = Query(
        default=None, ge=-90, le=90,
        description="Maximum latitude",
    ),
    min_lon: Optional[float] = Query(
        default=None, ge=-180, le=180,
        description="Minimum longitude",
    ),
    max_lon: Optional[float] = Query(
        default=None, ge=-180, le=180,
        description="Maximum longitude",
    ),
    limit: int = Query(
        default=50, ge=1, le=500,
        description="Page size (max 500)",
    ),
    offset: int = Query(
        default=0, ge=0,
        description="Pagination offset",
    ),
    db: AsyncSession = Depends(get_db),
) -> ObservationListResponse:
    """
    Query stored thermal observations with optional filters.

    Supports filtering by source, satellite, date range, and
    geographic bounding box. Results are paginated and ordered
    by acquisition datetime descending.
    """
    observations, total = await observation_service.list_observations(
        db,
        source=source,
        satellite=satellite,
        start_date=start_date,
        end_date=end_date,
        min_lat=min_lat,
        min_lon=min_lon,
        max_lat=max_lat,
        max_lon=max_lon,
        limit=limit,
        offset=offset,
    )

    return ObservationListResponse(
        total=total,
        limit=limit,
        offset=offset,
        observations=[
            ObservationResponse(
                id=str(obs.id),
                source=obs.source,
                latitude=obs.latitude,
                longitude=obs.longitude,
                acquisition_datetime=obs.acquisition_datetime,
                acq_date=obs.acq_date,
                acq_time=obs.acq_time,
                satellite=obs.satellite,
                instrument=obs.instrument,
                brightness=obs.brightness,
                bright_ti4=obs.bright_ti4,
                bright_ti5=obs.bright_ti5,
                frp=obs.frp,
                confidence=obs.confidence,
                daynight=obs.daynight,
                observation_hash=obs.observation_hash,
                event_id=str(obs.event_id) if obs.event_id else None,
                created_at=obs.created_at,
                updated_at=obs.updated_at,
            )
            for obs in observations
        ],
    )


@router.get(
    "/{observation_id}",
    response_model=ObservationResponse,
    summary="Get a specific stored observation",
)
async def get_observation(
    observation_id: str,
    db: AsyncSession = Depends(get_db),
) -> ObservationResponse:
    """Retrieve a single stored observation by its UUID."""
    try:
        obs_uuid = uuid.UUID(observation_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid UUID format: {observation_id}",
        )

    obs = await observation_service.get_observation(db, obs_uuid)

    if obs is None:
        raise HTTPException(
            status_code=404,
            detail=f"Observation {observation_id} not found",
        )

    return ObservationResponse(
        id=str(obs.id),
        source=obs.source,
        latitude=obs.latitude,
        longitude=obs.longitude,
        acquisition_datetime=obs.acquisition_datetime,
        acq_date=obs.acq_date,
        acq_time=obs.acq_time,
        satellite=obs.satellite,
        instrument=obs.instrument,
        brightness=obs.brightness,
        bright_ti4=obs.bright_ti4,
        bright_ti5=obs.bright_ti5,
        frp=obs.frp,
        confidence=obs.confidence,
        daynight=obs.daynight,
        observation_hash=obs.observation_hash,
        event_id=str(obs.event_id) if obs.event_id else None,
        created_at=obs.created_at,
        updated_at=obs.updated_at,
    )
