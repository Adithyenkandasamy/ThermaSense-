"""Alerts API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.thermal_event import RiskLevel, ThermalEvent
from app.schemas.thermal_event import ThermalEventSummary

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("", response_model=list[ThermalEventSummary])
async def list_alerts(db: AsyncSession = Depends(get_db)) -> list[ThermalEventSummary]:
    result = await db.execute(
        select(ThermalEvent)
        .where(ThermalEvent.risk_level.in_([RiskLevel.HIGH, RiskLevel.EXTREME]))
        .order_by(ThermalEvent.risk_score.desc(), ThermalEvent.created_at.desc())
        .limit(100)
    )
    return [ThermalEventSummary.model_validate(event) for event in result.scalars().all()]
