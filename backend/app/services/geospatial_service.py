"""
Geospatial context service.

Provides geographic context around thermal observations
using OpenStreetMap data via the Overpass API.

Planned capabilities:
  - Find nearby industrial areas
  - Find nearby buildings
  - Find nearby roads
  - Find nearby forest / vegetation features
  - Find nearby land-use areas

This service is a modular placeholder — the Overpass API
integration can be added without changing the FIRMS
ingestion code or other service modules.

Future API: https://overpass-api.de/api/interpreter
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"

# Default search radius in meters
DEFAULT_RADIUS_M = 2000


@dataclass
class NearbyFeature:
    """A geographic feature found near a thermal observation."""

    feature_type: str       # e.g. "industrial", "forest", "building"
    name: Optional[str] = None
    distance_m: Optional[float] = None
    osm_id: Optional[int] = None
    osm_type: Optional[str] = None  # "node", "way", "relation"
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class GeospatialContext:
    """
    Geographic context around a specific location.

    Contains lists of nearby features by category.
    """

    latitude: float
    longitude: float
    radius_m: float = DEFAULT_RADIUS_M
    industrial: list[NearbyFeature] = field(default_factory=list)
    buildings: list[NearbyFeature] = field(default_factory=list)
    roads: list[NearbyFeature] = field(default_factory=list)
    forests: list[NearbyFeature] = field(default_factory=list)
    landuse: list[NearbyFeature] = field(default_factory=list)
    source: str = "openstreetmap"


async def fetch_nearby_context(
    latitude: float,
    longitude: float,
    radius_m: float = DEFAULT_RADIUS_M,
) -> GeospatialContext:
    """
    Fetch geographic context around a location.

    TODO: Implement Overpass API queries for each feature category.

    This placeholder returns an empty GeospatialContext so the
    endpoint and data structure are available immediately.

    Args:
        latitude:  Latitude in WGS84.
        longitude: Longitude in WGS84.
        radius_m:  Search radius in meters.

    Returns:
        GeospatialContext with nearby features (empty until
        Overpass API integration is implemented).
    """
    logger.info(
        "Geospatial context requested — lat=%.4f lon=%.4f radius=%dm "
        "(Overpass integration not yet implemented)",
        latitude, longitude, radius_m,
    )

    return GeospatialContext(
        latitude=latitude,
        longitude=longitude,
        radius_m=radius_m,
    )


# ── Future Overpass Queries ─────────────────────────────────────────
#
# Example query for industrial areas within radius:
#
# [out:json][timeout:10];
# (
#   way["landuse"="industrial"](around:{radius},{lat},{lon});
#   relation["landuse"="industrial"](around:{radius},{lat},{lon});
# );
# out center;
#
# Similar queries for:
#   - building=* (buildings)
#   - highway=* (roads)
#   - natural=wood, landuse=forest (forests)
#   - landuse=* (general land use)
