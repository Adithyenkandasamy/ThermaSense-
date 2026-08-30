"""
Monitoring API endpoints (Module 2).

Endpoints:
  GET  /api/monitoring/status — Current scheduler & ingestion status
  GET  /api/monitoring/logs   — Historical ingestion logs with pagination/filters
  POST /api/monitoring/run    — Manually trigger one monitoring cycle
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.database import get_db
from app.schemas.monitoring import (
    IngestionLogItem,
    MonitoringLogsResponse,
    MonitoringRunResponse,
    MonitoringStatusResponse,
)
from app.scheduler import firms_scheduler
from app.services import observation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get(
    "/status",
    response_model=MonitoringStatusResponse,
    summary="Get continuous monitoring status",
)
async def get_monitoring_status(
    db: AsyncSession = Depends(get_db),
) -> MonitoringStatusResponse:
    """
    Return current monitoring configuration and runtime status.

    Includes scheduler state, poll interval, monitored area, sources,
    next scheduled run time, and last ingestion result.
    """
    status_dict = firms_scheduler.get_scheduler_status()

    # Fall back to DB history if in-memory state is empty (e.g. after server restart)
    if status_dict["last_successful_ingestion"] is None:
        last_success = await observation_service.get_latest_successful_ingestion_log(db)
        if last_success and isinstance(getattr(last_success, "completed_at", None), datetime):
            status_dict["last_successful_ingestion"] = last_success.completed_at

    if status_dict["last_ingestion_status"] is None:
        latest_log = await observation_service.get_latest_ingestion_log(db)
        if latest_log and isinstance(getattr(latest_log, "status", None), str):
            status_dict["last_ingestion_status"] = latest_log.status

    return MonitoringStatusResponse(**status_dict)



@router.get(
    "/logs",
    response_model=MonitoringLogsResponse,
    summary="List ingestion run history logs",
)
async def get_monitoring_logs(
    source: Optional[str] = Query(
        default=None,
        description="Filter logs by FIRMS source ID (e.g. VIIRS_NOAA20_NRT)",
    ),
    status: Optional[str] = Query(
        default=None,
        description="Filter logs by status (pending, success, partial, error)",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
        description="Number of logs to return per page",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Offset for pagination",
    ),
    db: AsyncSession = Depends(get_db),
) -> MonitoringLogsResponse:
    """
    Retrieve paginated history of FIRMS ingestion runs, ordered newest first.
    """
    logs, total = await observation_service.list_ingestion_logs(
        db,
        source=source,
        status=status,
        limit=limit,
        offset=offset,
    )

    items = [
        IngestionLogItem(
            id=str(log.id),
            source=log.source,
            area=log.area,
            day_range=log.day_range,
            requested_at=log.requested_at,
            completed_at=log.completed_at,
            status=log.status,
            records_fetched=log.records_fetched,
            records_validated=getattr(log, "records_validated", 0),
            records_stored=log.records_stored,
            duplicates_skipped=log.duplicates_skipped,
            invalid_records=log.invalid_records,
            error_message=log.error_message,
        )
        for log in logs
    ]

    return MonitoringLogsResponse(
        total=total,
        limit=limit,
        offset=offset,
        logs=items,
    )


@router.post(
    "/run",
    response_model=MonitoringRunResponse,
    summary="Trigger a monitoring ingestion cycle immediately",
)
async def trigger_monitoring_run() -> MonitoringRunResponse:
    """
    Manually trigger one monitoring cycle across configured FIRMS sources.

    Uses the exact same pipeline and deduplication as the scheduled job.
    """
    logger.info("Manual monitoring run triggered via API")
    result = await firms_scheduler.run_monitoring_cycle()
    return MonitoringRunResponse(
        status=result.get("status", "unknown"),
        timestamp=result.get("timestamp"),
        results=result.get("results", []),
    )
