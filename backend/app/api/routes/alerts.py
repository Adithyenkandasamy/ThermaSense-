"""Alerts API routes.

GET  /api/v1/alerts           — list HIGH/EXTREME events (last 100)
GET  /api/v1/alerts/recent    — recent alerts (last 24h, including simulated)
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.thermal_event import EventAnalysis, RiskLevel, ThermalEvent
from app.schemas.thermal_event import ThermalEventSummary

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("", response_model=list[ThermalEventSummary])
async def list_alerts(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[ThermalEventSummary]:
    """Return all HIGH and EXTREME risk events, newest first."""
    result = await db.execute(
        select(ThermalEvent)
        .where(ThermalEvent.risk_level.in_([RiskLevel.HIGH, RiskLevel.EXTREME]))
        .order_by(ThermalEvent.risk_score.desc(), ThermalEvent.created_at.desc())
        .limit(limit)
    )
    return [ThermalEventSummary.model_validate(event) for event in result.scalars().all()]


@router.get("/recent")
async def recent_alerts(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Return recent HIGH/EXTREME events with analysis summary.
    Used by the frontend Alert Center.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = await db.execute(
        select(ThermalEvent, EventAnalysis)
        .join(EventAnalysis, EventAnalysis.event_id == ThermalEvent.id, isouter=True)
        .where(
            ThermalEvent.risk_level.in_([RiskLevel.HIGH, RiskLevel.EXTREME]),
            ThermalEvent.created_at >= cutoff,
        )
        .order_by(ThermalEvent.risk_score.desc(), ThermalEvent.created_at.desc())
        .limit(50)
    )
    rows = result.fetchall()

    alerts = []
    for event, analysis in rows:
        alerts.append({
            "event_id": event.id,
            "risk_level": event.risk_level.value,
            "risk_score": event.risk_score,
            "classification": analysis.classification.value if analysis else "UNKNOWN",
            "latitude": event.latitude,
            "longitude": event.longitude,
            "frp": event.frp,
            "timestamp": event.observed_at.isoformat() if event.observed_at else event.created_at.isoformat(),
            "summary": analysis.summary if analysis else event.ai_summary or "High-risk thermal event detected.",
            "simulated": event.source == "DEMO",
            "confidence": analysis.confidence if analysis else None,
        })

    return alerts
