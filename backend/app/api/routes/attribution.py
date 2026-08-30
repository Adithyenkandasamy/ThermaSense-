"""
Thermal Anomaly Attribution API routes.

Endpoints:
  GET /api/attribution/event/{event_id}             — Attribution analysis for a clustered event
  GET /api/attribution/observation/{observation_id} — Attribution analysis for a single observation
  GET /api/events/{event_id}/intelligence          — Backward-compatible alias for event intelligence
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.attribution import AttributionResult
from app.services import attribution_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["attribution"])


@router.get(
    "/api/attribution/event/{event_id}",
    response_model=AttributionResult,
    summary="Get cause attribution for a thermal event",
)
async def get_event_attribution(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AttributionResult:
    """
    Perform multi-source evidence fusion for a ThermalEvent and return
    a structured attribution result with primary cause, confidence,
    individual cause score breakdown, and factor evidence list.
    """
    result = await attribution_service.classify_event(db, event_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"ThermalEvent {event_id} not found",
        )
    return result


@router.get(
    "/api/attribution/observation/{observation_id}",
    response_model=AttributionResult,
    summary="Get cause attribution for a single observation",
)
async def get_observation_attribution(
    observation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AttributionResult:
    """
    Perform multi-source evidence fusion for a single ThermalObservation.
    """
    result = await attribution_service.classify_observation(db, observation_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"ThermalObservation {observation_id} not found",
        )
    return result


# Backward-compatibility endpoint
@router.get(
    "/api/events/{event_id}/intelligence",
    response_model=AttributionResult,
    summary="Get cause attribution intelligence for a thermal event",
    include_in_schema=True,
)
async def get_event_intelligence_alias(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AttributionResult:
    """Alias for /api/attribution/event/{event_id}."""
    return await get_event_attribution(event_id, db)
