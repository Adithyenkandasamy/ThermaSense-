"""Ingestion API routes."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.thermal_event import IngestResponse
from app.services.ingest_service import run_ingestion

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["ingestion"])


@router.post("/ingest", response_model=IngestResponse, summary="Trigger FIRMS ingestion")
async def trigger_ingest(db: AsyncSession = Depends(get_db)) -> IngestResponse:
    logger.info("Manual ingestion triggered via API")
    result = await run_ingestion(db)
    return IngestResponse(**result)
