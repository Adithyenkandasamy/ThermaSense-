"""
FIRMS ingestion trigger endpoint.

Endpoint:
  POST /api/ingestion/firms — Trigger a FIRMS data fetch
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_app_settings
from app.core.config import Settings
from app.schemas.observation import IngestionRequest, IngestionResponse
from app.services.firms_service import fetch_hotspots

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


@router.post(
    "/firms",
    response_model=IngestionResponse,
    summary="Trigger FIRMS data ingestion",
)
async def trigger_firms_ingestion(
    request: IngestionRequest = IngestionRequest(),
    settings: Settings = Depends(get_app_settings),
) -> IngestionResponse:
    """
    Manually trigger a NASA FIRMS data fetch.

    In the MVP, data is fetched and returned directly.
    In future phases, this will also persist data to the database.

    Body parameters:
    - `satellite`: 'NOAA-20' or 'NOAA-21'
    - `day_range`: 1–5 days
    - `area`: 'world' or 'xmin,ymin,xmax,ymax'
    """
    try:
        observations, source_name, area_used = await fetch_hotspots(
            map_key=settings.firms_map_key,
            satellite=request.satellite,
            day_range=request.day_range,
            area=request.area,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        return IngestionResponse(
            status="error",
            message=str(exc),
            total_fetched=0,
            satellite_source=request.satellite,
        )
    except Exception as exc:
        logger.error("FIRMS ingestion failed: %s", exc)
        return IngestionResponse(
            status="error",
            message=f"FIRMS fetch failed: {exc}",
            total_fetched=0,
            satellite_source=request.satellite,
        )

    return IngestionResponse(
        status="ok",
        message=f"Fetched {len(observations)} observations from {source_name}",
        total_fetched=len(observations),
        satellite_source=source_name,
        observations=observations,
    )
