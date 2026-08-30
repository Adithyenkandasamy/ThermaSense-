"""
Ingestion log repository — database access layer.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion_log import IngestionLog


async def create_ingestion_log(
    session: AsyncSession,
    *,
    source: str,
    area: str,
    day_range: int,
) -> IngestionLog:
    """Create a new ingestion log entry (status=pending)."""
    log = IngestionLog(
        source=source,
        area=area,
        day_range=day_range,
        status="pending",
        requested_at=datetime.now(timezone.utc),
    )
    session.add(log)
    await session.flush()
    return log


async def update_ingestion_log(
    session: AsyncSession,
    log_id: uuid.UUID,
    *,
    status: str,
    records_fetched: int = 0,
    records_validated: int = 0,
    records_stored: int = 0,
    duplicates_skipped: int = 0,
    invalid_records: int = 0,
    error_message: Optional[str] = None,
) -> Optional[IngestionLog]:
    """Update an ingestion log entry on completion."""
    result = await session.execute(
        select(IngestionLog).where(IngestionLog.id == log_id)
    )
    log = result.scalar_one_or_none()
    if log is None:
        return None

    log.status = status
    log.completed_at = datetime.now(timezone.utc)
    log.records_fetched = records_fetched
    log.records_validated = records_validated
    log.records_stored = records_stored
    log.duplicates_skipped = duplicates_skipped
    log.invalid_records = invalid_records
    log.error_message = error_message

    await session.flush()
    return log


async def list_ingestion_logs(
    session: AsyncSession,
    *,
    source: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[IngestionLog], int]:
    """
    Paginated, filterable list of ingestion logs ordered newest first.
    """
    query = select(IngestionLog)
    count_query = select(func.count(IngestionLog.id))

    if source:
        query = query.where(IngestionLog.source == source)
        count_query = count_query.where(IngestionLog.source == source)
    if status:
        query = query.where(IngestionLog.status == status)
        count_query = count_query.where(IngestionLog.status == status)

    query = query.order_by(IngestionLog.requested_at.desc())
    query = query.limit(limit).offset(offset)

    result = await session.execute(query)
    logs = result.scalars().all()

    count_result = await session.execute(count_query)
    total = count_result.scalar_one()

    return logs, total


async def get_latest_ingestion_log(
    session: AsyncSession,
) -> Optional[IngestionLog]:
    """Fetch the single most recent ingestion log."""
    query = select(IngestionLog).order_by(IngestionLog.requested_at.desc()).limit(1)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_latest_successful_ingestion_log(
    session: AsyncSession,
) -> Optional[IngestionLog]:
    """Fetch the most recent successful ingestion log."""
    query = (
        select(IngestionLog)
        .where(IngestionLog.status == "success")
        .order_by(IngestionLog.completed_at.desc())
        .limit(1)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()

