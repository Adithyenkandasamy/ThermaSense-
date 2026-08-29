"""
Hotspot observation API routes.

Endpoints:
  GET /api/hotspots      — Fetch thermal observations from FIRMS
  GET /api/hotspots/{id} — Get a specific observation by ID
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_app_settings
from app.core.config import Settings
from app.schemas.observation import HotspotListResponse, HotspotResponse
from app.services.firms_service import fetch_hotspots

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hotspots", tags=["hotspots"])

# ── In-memory cache for the last fetch ──────────────────────────────
# Allows GET /api/hotspots/{id} to work without re-fetching.
# This is a temporary MVP approach — will be replaced with DB storage.
_last_fetch_cache: list[HotspotResponse] = []


@router.get(
    "",
    response_model=HotspotListResponse,
    summary="Fetch thermal hotspot observations",
)
async def get_hotspots(
    satellite: str = Query(
        default="NOAA-20",
        description="Satellite source: 'NOAA-20' or 'NOAA-21'",
    ),
    days: int = Query(
        default=1,
        ge=1,
        le=5,
        description="Number of past days to fetch (1-5)",
    ),
    bbox: Optional[str] = Query(
        default=None,
        description=(
            "Bounding box as 'xmin,ymin,xmax,ymax' in WGS84. "
            "Omit for global ('world') data."
        ),
    ),
    settings: Settings = Depends(get_app_settings),
) -> HotspotListResponse:
    """
    Fetch thermal anomaly observations from NASA FIRMS.

    The data is fetched on-demand from the FIRMS Area API.
    Results are returned directly as structured JSON.

    - Use `satellite` to select NOAA-20 or NOAA-21
    - Use `days` for 1–5 day historical range
    - Use `bbox` for regional data or omit for global
    """
    global _last_fetch_cache

    try:
        observations, source_name, area_used = await fetch_hotspots(
            map_key=settings.firms_map_key,
            satellite=satellite,
            day_range=days,
            area=bbox,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.error("FIRMS fetch failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch data from NASA FIRMS: {exc}",
        )

    # Cache for individual lookups
    _last_fetch_cache = observations

    return HotspotListResponse(
        total=len(observations),
        satellite_source=source_name,
        day_range=days,
        area=area_used,
        observations=observations,
    )


@router.get(
    "/{hotspot_id}",
    response_model=HotspotResponse,
    summary="Get a specific observation",
)
async def get_hotspot(hotspot_id: str) -> HotspotResponse:
    """
    Retrieve a specific observation by ID from the last fetch.

    Note: This is an MVP approach. The observation must exist
    in the most recent fetch cache. A database-backed lookup
    will replace this in a future phase.
    """
    for obs in _last_fetch_cache:
        if obs.id == hotspot_id:
            return obs

    raise HTTPException(
        status_code=404,
        detail=(
            f"Observation '{hotspot_id}' not found. "
            "It may not be in the current fetch cache. "
            "Try fetching hotspots first via GET /api/hotspots."
        ),
    )
