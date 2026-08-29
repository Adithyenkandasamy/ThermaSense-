"""
Thermal events API routes.

Endpoints:
  GET  /api/v1/events               - paginated list with filters
  GET  /api/v1/events/latest        - events from last 24 hours
  GET  /api/v1/events/stats         - summary statistics
  GET  /api/v1/events/{id}          - single event detail
  GET  /api/v1/events/{id}/context  - geospatial context (facilities, land cover)
  GET  /api/v1/events/{id}/history  - historical analysis
  GET  /api/v1/events/{id}/analysis - stored EventAnalysis (does NOT re-run AI)
  POST /api/v1/events/{id}/analyze  - trigger/re-trigger full analysis
"""

import logging
from datetime import datetime, timedelta, timezone
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.thermal_event import RiskLevel, ThermalEvent
from app.schemas.thermal_event import (
    PaginatedEvents,
    StatsResponse,
    ThermalEventResponse,
    ThermalEventSummary,
)
from app.services.ingest_service import get_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["events"])


# ── GET /api/v1/events ──────────────────────────────────────────────────────
@router.get("", response_model=PaginatedEvents, summary="List thermal events")
async def list_events(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    risk_level: RiskLevel | None = Query(None),
    min_frp: float | None = Query(None, ge=0),
    satellite: str | None = Query(None),
    days: int = Query(1, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
) -> PaginatedEvents:
    from sqlalchemy import func as sa_func

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = select(ThermalEvent).where(ThermalEvent.created_at >= cutoff)

    if risk_level:
        query = query.where(ThermalEvent.risk_level == risk_level)
    if min_frp is not None:
        query = query.where(ThermalEvent.frp >= min_frp)
    if satellite:
        query = query.where(ThermalEvent.satellite.ilike(f"%{satellite}%"))

    count_query = select(sa_func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

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
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await db.execute(
        select(ThermalEvent)
        .where(ThermalEvent.created_at >= cutoff)
        .order_by(ThermalEvent.risk_score.desc())
        .limit(limit)
    )
    return [ThermalEventSummary.model_validate(e) for e in result.scalars().all()]


# ── GET /api/v1/events/stats ────────────────────────────────────────────────
@router.get("/stats", response_model=StatsResponse, summary="Summary statistics")
async def stats(db: AsyncSession = Depends(get_db)) -> StatsResponse:
    data = await get_stats(db)
    return StatsResponse(**data)


# ── GET /api/v1/events/{id} ─────────────────────────────────────────────────
@router.get("/{event_id}", response_model=ThermalEventResponse, summary="Get event by ID")
async def get_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
) -> ThermalEventResponse:
    te = await db.get(ThermalEvent, event_id)
    if not te:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return ThermalEventResponse.model_validate(te)


# ── GET /api/v1/events/{id}/context ────────────────────────────────────────
@router.get("/{event_id}/context", summary="Geospatial context for an event")
async def get_event_context(
    event_id: int,
    radius_km: float = Query(10.0, ge=0.1, le=50.0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return geospatial context for the event:
      - Nearby industrial facilities (PostGIS ST_DWithin)
      - Land-cover classification
    """
    te = await db.get(ThermalEvent, event_id)
    if not te:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    from app.services.context_service import build_event_context
    return await build_event_context(te, db, radius_km=radius_km)


# ── GET /api/v1/events/{id}/history ────────────────────────────────────────
@router.get("/{event_id}/history", summary="Historical thermal activity at event location")
async def get_event_history(
    event_id: int,
    radius_km: float = Query(1.0, ge=0.1, le=10.0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return historical thermal activity at/near the event location.
    Uses real PostGIS spatial queries against the thermal_events table.
    """
    te = await db.get(ThermalEvent, event_id)
    if not te:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    from app.services.history_service import calculate_history
    return await calculate_history(te, db, radius_km=radius_km)


# ── GET /api/v1/events/{id}/analysis ───────────────────────────────────────
@router.get("/{event_id}/analysis", summary="Stored investigation for an event")
async def get_event_analysis(
    event_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return the stored EventAnalysis for an event.

    This does NOT trigger a new AI call — it returns what was computed
    during ingestion or the last POST /analyze call.

    Returns 404 if analysis has not been run yet.
    Use POST /analyze to trigger analysis.
    """
    te = await db.get(ThermalEvent, event_id)
    if not te:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    from app.services.analysis_service import get_analysis_for_event
    analysis = await get_analysis_for_event(event_id, db)

    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No analysis found for event {event_id}. "
                "POST /api/v1/events/{event_id}/analyze to trigger analysis."
            ),
        )

    # Return structured response
    evidence = analysis.evidence or {}
    packet = evidence.get("packet", {})
    ai_result = evidence.get("ai_result", {})

    return {
        "event": {
            "id": te.id,
            "latitude": te.latitude,
            "longitude": te.longitude,
            "acq_date": str(te.acq_date),
            "acq_time": te.acq_time,
            "frp": te.frp,
            "brightness": te.brightness,
            "confidence": te.confidence,
            "satellite": te.satellite,
            "risk_level": te.risk_level.value,
            "risk_score": te.risk_score,
        },
        "context": packet.get("geographic_context", {}),
        "history": packet.get("historical_context", {}),
        "analysis": {
            "id": analysis.id,
            "classification": analysis.classification.value,
            "confidence": analysis.confidence,
            "risk_score": analysis.risk_score,
            "risk_level": analysis.risk_level.value,
            "persistence_score": analysis.persistence_score,
            "anomaly_score": analysis.anomaly_score,
            "industrial_context_score": analysis.industrial_context_score,
            "summary": analysis.summary,
            "reasoning": analysis.reasoning,
            "recommended_action": analysis.recommended_action,
            "engine_version": analysis.engine_version,
            "created_at": analysis.created_at.isoformat(),
            "updated_at": analysis.updated_at.isoformat(),
            "ai_mode": ai_result.get("ai_mode", "UNKNOWN"),
        },
    }


# ── POST /api/v1/events/{id}/analyze ───────────────────────────────────────
@router.post("/{event_id}/analyze", summary="Trigger full analysis for an event")
async def analyze_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Run (or re-run) the complete analysis pipeline for one event.

    This is the only endpoint that triggers a new AI call.
    GET /analysis uses stored results.
    """
    te = await db.get(ThermalEvent, event_id)
    if not te:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    from app.services.analysis_service import process_event
    from app.services.connection_manager import manager as ws_manager

    try:
        result = await process_event(event_id, db)

        # Broadcast to WebSocket clients
        if ws_manager.connection_count > 0:
            await ws_manager.broadcast(
                {
                    "type": "THERMAL_EVENT_ANALYZED",
                    "event_id": event_id,
                    "classification": result.get("classification", "UNKNOWN"),
                    "risk_level": result.get("risk_level", "UNKNOWN"),
                    "risk_score": result.get("risk_score", 0.0),
                    "latitude": te.latitude,
                    "longitude": te.longitude,
                    "frp": te.frp,
                }
            )

        return {
            "status": "ok",
            "event_id": event_id,
            "analysis_id": result.get("analysis_id"),
            "classification": result.get("classification"),
            "risk_level": result.get("risk_level"),
            "risk_score": result.get("risk_score"),
            "message": "Analysis complete. GET /analysis to retrieve full results.",
        }
    except Exception as exc:
        logger.error("Analysis failed for event %s: %s", event_id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {exc}",
        )
