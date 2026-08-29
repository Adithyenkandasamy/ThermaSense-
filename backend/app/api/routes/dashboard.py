"""Dashboard API routes."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.thermal_event import ThermalEvent
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


@router.get("/trends")
async def dashboard_trends(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return daily thermal event counts and average FRP for the last N days.

    Useful for charting activity trends on the frontend.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        text(
            """
            SELECT
                DATE(COALESCE(observed_at, created_at)) AS day,
                COUNT(*) AS event_count,
                AVG(frp) AS avg_frp,
                MAX(frp) AS max_frp,
                COUNT(CASE WHEN risk_level = 'EXTREME' THEN 1 END) AS extreme_count,
                COUNT(CASE WHEN risk_level = 'HIGH' THEN 1 END) AS high_count
            FROM thermal_events
            WHERE COALESCE(observed_at, created_at) >= :cutoff
            GROUP BY day
            ORDER BY day DESC
            """
        ),
        {"cutoff": cutoff},
    )
    rows = result.fetchall()

    trends = [
        {
            "date": str(row.day),
            "event_count": row.event_count,
            "avg_frp": round(float(row.avg_frp), 2) if row.avg_frp else None,
            "max_frp": round(float(row.max_frp), 2) if row.max_frp else None,
            "extreme_count": row.extreme_count,
            "high_count": row.high_count,
        }
        for row in rows
    ]

    return {
        "days": days,
        "trends": trends,
        "total_events": sum(t["event_count"] for t in trends),
    }
