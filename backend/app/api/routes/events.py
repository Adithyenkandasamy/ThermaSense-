"""
Thermal events API routes.

Endpoints:
  GET  /api/v1/events          - paginated list with filters
  GET  /api/v1/events/latest   - events from last 24 hours
  GET  /api/v1/events/stats    - summary statistics
  GET  /api/v1/events/{id}     - single event with full AI summary
  POST /api/v1/ingest          - manually trigger FIRMS ingestion
"""

import logging
from datetime import datetime, timedelta, timezone
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.thermal_event import RiskLevel, ThermalEvent
from app.schemas.thermal_event import PaginatedEvents, StatsResponse, ThermalEventResponse, ThermalEventSummary
from app.services.ingest_service import get_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["events"])


# ── GET /api/v1/events ──────────────────────────────────────────────────────
@router.get("", response_model=PaginatedEvents, summary="List thermal events")
async def list_events(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=500, description="Events per page"),
    risk_level: RiskLevel | None = Query(None, description="Filter by risk level"),
    min_frp: float | None = Query(None, ge=0, description="Minimum FRP in MW"),
    satellite: str | None = Query(None, description="Filter by satellite name"),
    days: int = Query(1, ge=1, le=30, description="Only show events from last N days"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedEvents:
    """
    List thermal events with optional filters.
    Ordered by risk_score descending (most dangerous first).
    """
    from sqlalchemy import func

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Build base query
    query = select(ThermalEvent).where(ThermalEvent.created_at >= cutoff)

    if risk_level:
        query = query.where(ThermalEvent.risk_level == risk_level)
    if min_frp is not None:
        query = query.where(ThermalEvent.frp >= min_frp)
    if satellite:
        query = query.where(ThermalEvent.satellite.ilike(f"%{satellite}%"))

    # Count total
    from sqlalchemy import func as sa_func
    count_query = select(sa_func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Paginate
    offset = (page - 1) * per_page
    query = (
        query.order_by(ThermalEvent.risk_score.desc(), ThermalEvent.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )

    result = await db.execute(query)
    events = result.scalars().all()

    return PaginatedEvents(
        total=total,
        page=page,
        per_page=per_page,
        pages=ceil(total / per_page) if total > 0 else 0,
        items=[ThermalEventSummary.model_validate(e) for e in events],
    )


# ── GET /api/v1/events/latest ───────────────────────────────────────────────
@router.get("/latest", response_model=list[ThermalEventSummary], summary="Events from last 24h")
async def latest_events(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[ThermalEventSummary]:
    """Return the most recent events (last 24 hours), sorted by risk score."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    result = await db.execute(
        select(ThermalEvent)
        .where(ThermalEvent.created_at >= cutoff)
        .order_by(ThermalEvent.risk_score.desc())
        .limit(limit)
    )
    events = result.scalars().all()
    return [ThermalEventSummary.model_validate(e) for e in events]


# ── GET /api/v1/events/stats ────────────────────────────────────────────────
@router.get("/stats", response_model=StatsResponse, summary="Summary statistics")
async def stats(db: AsyncSession = Depends(get_db)) -> StatsResponse:
    """Return aggregated stats: total count, by risk level, last 24h count."""
    data = await get_stats(db)
    return StatsResponse(**data)


# ── GET /api/v1/events/{id} ─────────────────────────────────────────────────
@router.get("/{event_id}", response_model=ThermalEventResponse, summary="Get event by ID")
async def get_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
) -> ThermalEventResponse:
    """
    Return full event detail including the Groq AI summary.
    If the event is HIGH/EXTREME and has no summary yet, generates one on-demand.
    """
    from app.config import get_settings
    from app.services.groq_analyst import (
        GROQ_TRIGGER_LEVELS,
        format_summary_text,
        generate_event_summary,
    )

    te = await db.get(ThermalEvent, event_id)
    if not te:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    # On-demand Groq summary if missing
    if te.risk_level in GROQ_TRIGGER_LEVELS and not te.ai_generated:
        settings = get_settings()
        groq_result = await generate_event_summary(
            groq_api_key=settings.groq_api_key,
            event_data={
                "latitude": te.latitude,
                "longitude": te.longitude,
                "frp": te.frp,
                "brightness": te.brightness,
                "confidence": te.confidence,
                "satellite": te.satellite,
                "daynight": te.daynight,
                "acq_date": str(te.acq_date),
                "acq_time": te.acq_time,
                "risk_level": te.risk_level.value,
            },
        )
        if groq_result:
            te.ai_summary = format_summary_text(groq_result)
            te.ai_generated = True

    return ThermalEventResponse.model_validate(te)

