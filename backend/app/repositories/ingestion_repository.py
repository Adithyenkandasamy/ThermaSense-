"""
Ingestion log repository — database access layer.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
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
    log.records_stored = records_stored
    log.duplicates_skipped = duplicates_skipped
    log.invalid_records = invalid_records
    log.error_message = error_message

    await session.flush()
    return log
