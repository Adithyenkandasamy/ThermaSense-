"""
FIRMS ingestion trigger endpoint (Module 2).

Endpoint:
  POST /api/ingestion/firms — Fetch, normalize, validate, store
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.ingestion import IngestionRequestV2, IngestionSummary
from app.services import observation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


@router.post(
    "/firms",
    response_model=IngestionSummary,
    summary="Ingest FIRMS data into database",
)
async def trigger_firms_ingestion(
    request: IngestionRequestV2 = IngestionRequestV2(),
    db: AsyncSession = Depends(get_db),
) -> IngestionSummary:
    """
    Fetch thermal anomaly data from NASA FIRMS, normalize,
    validate, deduplicate, and store in PostgreSQL.

    Body parameters:
    - `source`: FIRMS source ID (VIIRS_NOAA20_NRT or VIIRS_NOAA21_NRT)
    - `area`: 'world' or 'xmin,ymin,xmax,ymax'
    - `day_range`: 1–5 days
    """
    try:
        summary = await observation_service.ingest_firms_data(
            db,
            source=request.source,
            area=request.area,
            day_range=request.day_range,
        )
        return IngestionSummary(**summary)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        return IngestionSummary(
            source=request.source,
            status="error",
            error=str(exc),
        )
    except Exception as exc:
        logger.error("Ingestion failed: %s", exc, exc_info=True)
        return IngestionSummary(
            source=request.source,
            status="error",
            error=f"Ingestion failed: {exc}",
        )
