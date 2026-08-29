"""Dashboard API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.dashboard import DashboardSummary
from app.services.ingest_service import get_stats

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(db: AsyncSession = Depends(get_db)) -> DashboardSummary:
    stats = await get_stats(db)
    return DashboardSummary(
        active_events=stats["events_last_24h"],
        high_risk=stats["high_count"],
        extreme_risk=stats["extreme_count"],
        api_status="ok",
        database_status="ok",
        demo_mode=False,
    )
