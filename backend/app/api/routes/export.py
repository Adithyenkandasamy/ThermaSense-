"""
GIS Data Export API routes.

Endpoints:
  GET /api/export/geojson — Download observations as GeoJSON RFC 7946 FeatureCollection
  GET /api/export/csv     — Download observations as CSV file
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.export import GeoJsonFeatureCollection
from app.services import export_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get(
    "/geojson",
    response_model=GeoJsonFeatureCollection,
    summary="Export stored observations as standard GeoJSON",
)
async def export_geojson(
    source: Optional[str] = Query(None, description="FIRMS source filter"),
    satellite: Optional[str] = Query(None, description="Satellite name"),
    start_date: Optional[datetime] = Query(None, description="Acquisition start date"),
    end_date: Optional[datetime] = Query(None, description="Acquisition end date"),
    min_lat: Optional[float] = Query(None, description="Minimum latitude"),
    max_lat: Optional[float] = Query(None, description="Maximum latitude"),
    min_lon: Optional[float] = Query(None, description="Minimum longitude"),
    max_lon: Optional[float] = Query(None, description="Maximum longitude"),
    limit: int = Query(1000, ge=1, le=5000, description="Max records to export"),
    db: AsyncSession = Depends(get_db),
) -> GeoJsonFeatureCollection:
    """
    Export matching thermal observations as an RFC 7946 GeoJSON FeatureCollection,
    compatible with QGIS, ArcGIS, Mapbox, and Leaflet.
    """
    return await export_service.export_observations_geojson(
        db,
        source=source,
        satellite=satellite,
        start_date=start_date,
        end_date=end_date,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
        limit=limit,
    )


@router.get(
    "/csv",
    summary="Export stored observations as CSV file",
)
async def export_csv(
    source: Optional[str] = Query(None, description="FIRMS source filter"),
    satellite: Optional[str] = Query(None, description="Satellite name"),
    start_date: Optional[datetime] = Query(None, description="Acquisition start date"),
    end_date: Optional[datetime] = Query(None, description="Acquisition end date"),
    min_lat: Optional[float] = Query(None, description="Minimum latitude"),
    max_lat: Optional[float] = Query(None, description="Maximum latitude"),
    min_lon: Optional[float] = Query(None, description="Minimum longitude"),
    max_lon: Optional[float] = Query(None, description="Maximum longitude"),
    limit: int = Query(5000, ge=1, le=10000, description="Max records to export"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Stream matching observations as an RFC 4180 CSV attachment.
    """
    csv_data = await export_service.export_observations_csv(
        db,
        source=source,
        satellite=satellite,
        start_date=start_date,
        end_date=end_date,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
        limit=limit,
    )

    filename = f"thermasense_hotspots_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
