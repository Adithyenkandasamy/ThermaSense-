"""
Alerts API routes.

Endpoints:
  GET /api/alerts — Fetch active operational thermal alerts
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.export import AlertListResponse
from app.services import alert_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get(
    "",
    response_model=AlertListResponse,
    summary="Get active thermal alerts",
)
async def get_alerts(
    min_severity: Optional[str] = Query(None, description="Filter by minimum severity"),
    limit: int = Query(50, ge=1, le=100, description="Max alerts to return"),
    db: AsyncSession = Depends(get_db),
) -> AlertListResponse:
    """
    Evaluate active thermal events and return real-time operational alerts
    (e.g., extreme FRP, persistent wildfire spread).
    """
    return await alert_service.evaluate_active_alerts(
        db,
        min_severity=min_severity,
        limit=limit,
    )
