"""
Geospatial context service.

Given a thermal event location, returns:
  - Nearby industrial facilities (found via PostGIS ST_DWithin)
  - Land-cover information

This replaces the placeholder that always returned empty lists.

Design:
  - Uses geography type for accurate km-based distance calculations.
  - Uses spatial index on industrial_facilities.geom for performance.
  - Never does Python-side distance filtering — the DB does it.
  - Nearby is defined as within NEARBY_RADIUS_KM (default 10 km).
"""

import logging
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.landcover import lookup_land_cover
from app.models.thermal_event import IndustrialFacility, ThermalEvent

logger = logging.getLogger(__name__)

# Radius for "nearby" facility search (kilometres)
NEARBY_RADIUS_KM: float = 10.0


async def build_event_context(
    event: ThermalEvent,
    db: AsyncSession,
    radius_km: float = NEARBY_RADIUS_KM,
) -> dict[str, Any]:
    """
    Build geospatial context for a thermal event.

    Queries the PostGIS `industrial_facilities` table for any facility
    within `radius_km` of the event location, and looks up land cover.

    Args:
        event:     The ThermalEvent ORM object.
        db:        Async DB session.
        radius_km: Search radius in kilometres.

    Returns:
        {
            "event_id": int,
            "location": {"latitude": float, "longitude": float},
            "nearby_facilities": [
                {
                    "id": int,
                    "name": str,
                    "type": str,
                    "distance_km": float,
                    "latitude": float,
                    "longitude": float,
                    "source": str,
                }
            ],
            "nearest_facility": {...} | None,  # the closest one
            "nearest_facility_km": float | None,
            "land_cover": str,
            "radius_km": float,
        }
    """
    lat: float = event.latitude
    lon: float = event.longitude

    # ── PostGIS nearby facility query ─────────────────────────────────
    # We cast the event point and facility geom to geography so that
    # ST_DWithin uses metres (we convert radius_km → metres here).
    # ST_Distance also returns metres with geography; we divide by 1000.
    radius_m = radius_km * 1000.0

    # Build a literal WKT point for the event location
    # Using ST_MakePoint(lon, lat)::geography for the event side
    query = text(
        """
        SELECT
            f.id,
            f.name,
            f.facility_type,
            f.latitude,
            f.longitude,
            f.source,
            ST_Distance(
                f.geom::geography,
                ST_MakePoint(:lon, :lat)::geography
            ) / 1000.0 AS distance_km
        FROM industrial_facilities f
        WHERE ST_DWithin(
            f.geom::geography,
            ST_MakePoint(:lon, :lat)::geography,
            :radius_m
        )
        ORDER BY distance_km ASC
        LIMIT 20
        """
    )

    try:
        result = await db.execute(
            query,
            {"lat": lat, "lon": lon, "radius_m": radius_m},
        )
        rows = result.fetchall()
    except Exception as exc:
        logger.error("PostGIS nearby facility query failed: %s", exc)
        rows = []

    nearby: list[dict[str, Any]] = []
    for row in rows:
        nearby.append(
            {
                "id": row.id,
                "name": row.name,
                "type": row.facility_type,
                "distance_km": round(float(row.distance_km), 3),
                "latitude": float(row.latitude),
                "longitude": float(row.longitude),
                "source": row.source,
            }
        )

    nearest = nearby[0] if nearby else None
    nearest_km = nearby[0]["distance_km"] if nearby else None

    # ── Land cover ─────────────────────────────────────────────────────
    land_cover = lookup_land_cover(lat, lon)

    logger.debug(
        "Context for event %s: %d nearby facilities within %.1f km, land_cover=%s",
        event.id,
        len(nearby),
        radius_km,
        land_cover,
    )

    return {
        "event_id": event.id,
        "location": {"latitude": lat, "longitude": lon},
        "nearby_facilities": nearby,
        "nearest_facility": nearest,
        "nearest_facility_km": nearest_km,
        "land_cover": land_cover,
        "radius_km": radius_km,
    }
