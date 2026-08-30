"""
Geospatial context service.

Provides geographic context around thermal observations
using OpenStreetMap data via the Overpass API.

Capabilities:
  - Find nearby industrial areas, flares, power plants
  - Find nearby forests, woodlands, vegetation
  - Find nearby farmlands, croplands, agricultural land
  - Find nearby roads and transport corridors
  - Find nearby buildings and built infrastructure

Includes in-memory coordinate-caching and fault-tolerant fallbacks.
"""

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_RADIUS_M = 2000
HTTP_TIMEOUT_SECONDS = 15.0

# In-memory cache: key -> (timestamp, GeospatialContext)
_GEOSPATIAL_CACHE: dict[str, tuple[float, Any]] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour


@dataclass
class NearbyFeature:
    """A geographic feature found near a thermal observation."""

    feature_type: str       # "industrial", "forest", "cropland", "road", "building"
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
    forests: list[NearbyFeature] = field(default_factory=list)
    croplands: list[NearbyFeature] = field(default_factory=list)
    roads: list[NearbyFeature] = field(default_factory=list)
    buildings: list[NearbyFeature] = field(default_factory=list)
    source: str = "openstreetmap"


def calculate_haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate the great-circle distance between two points in meters using Haversine formula.
    """
    r = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 1)


def build_overpass_query(latitude: float, longitude: float, radius_m: float) -> str:
    """
    Build optimized Overpass QL query string to search for land use and features.
    """
    return f"""
    [out:json][timeout:12];
    (
      // Industrial
      way["landuse"="industrial"](around:{radius_m},{latitude},{longitude});
      node["man_made"="flare"](around:{radius_m},{latitude},{longitude});
      way["power"="plant"](around:{radius_m},{latitude},{longitude});
      node["power"="plant"](around:{radius_m},{latitude},{longitude});

      // Forests & Wooded Areas
      way["landuse"="forest"](around:{radius_m},{latitude},{longitude});
      way["natural"="wood"](around:{radius_m},{latitude},{longitude});
      relation["landuse"="forest"](around:{radius_m},{latitude},{longitude});
      relation["natural"="wood"](around:{radius_m},{latitude},{longitude});

      // Croplands & Farmland
      way["landuse"="farmland"](around:{radius_m},{latitude},{longitude});
      way["landuse"="orchard"](around:{radius_m},{latitude},{longitude});
      way["landuse"="farmyard"](around:{radius_m},{latitude},{longitude});

      // Roads & Transport
      way["highway"~"motorway|trunk|primary|secondary"](around:{radius_m},{latitude},{longitude});

      // Buildings
      way["building"](around:{radius_m},{latitude},{longitude});
    );
    out center tags 30;
    """


def parse_osm_elements(
    elements: list[dict[str, Any]], target_lat: float, target_lon: float
) -> tuple[
    list[NearbyFeature],
    list[NearbyFeature],
    list[NearbyFeature],
    list[NearbyFeature],
    list[NearbyFeature],
]:
    """
    Parse Overpass JSON elements and categorize them into feature groups.
    """
    industrial: list[NearbyFeature] = []
    forests: list[NearbyFeature] = []
    croplands: list[NearbyFeature] = []
    roads: list[NearbyFeature] = []
    buildings: list[NearbyFeature] = []

    for el in elements:
        tags = el.get("tags", {})
        osm_id = el.get("id")
        osm_type = el.get("type")
        name = tags.get("name")

        # Determine feature coordinate
        feat_lat = el.get("lat")
        feat_lon = el.get("lon")
        if feat_lat is None and "center" in el:
            feat_lat = el["center"].get("lat")
            feat_lon = el["center"].get("lon")

        distance_m = None
        if feat_lat is not None and feat_lon is not None:
            distance_m = calculate_haversine_distance(
                target_lat, target_lon, float(feat_lat), float(feat_lon)
            )

        # Categorize
        if (
            tags.get("landuse") == "industrial"
            or tags.get("man_made") == "flare"
            or tags.get("power") == "plant"
        ):
            industrial.append(
                NearbyFeature(
                    feature_type="industrial",
                    name=name or tags.get("industrial") or "Industrial Zone",
                    distance_m=distance_m,
                    osm_id=osm_id,
                    osm_type=osm_type,
                    tags=tags,
                )
            )
        elif (
            tags.get("landuse") == "forest"
            or tags.get("natural") == "wood"
        ):
            forests.append(
                NearbyFeature(
                    feature_type="forest",
                    name=name or "Forest / Woodland",
                    distance_m=distance_m,
                    osm_id=osm_id,
                    osm_type=osm_type,
                    tags=tags,
                )
            )
        elif (
            tags.get("landuse") in ("farmland", "orchard", "farmyard")
        ):
            croplands.append(
                NearbyFeature(
                    feature_type="cropland",
                    name=name or tags.get("crop") or "Agricultural Farmland",
                    distance_m=distance_m,
                    osm_id=osm_id,
                    osm_type=osm_type,
                    tags=tags,
                )
            )
        elif "highway" in tags:
            roads.append(
                NearbyFeature(
                    feature_type="road",
                    name=name or tags.get("ref") or f"Highway ({tags.get('highway')})",
                    distance_m=distance_m,
                    osm_id=osm_id,
                    osm_type=osm_type,
                    tags=tags,
                )
            )
        elif "building" in tags:
            buildings.append(
                NearbyFeature(
                    feature_type="building",
                    name=name or f"Building ({tags.get('building')})",
                    distance_m=distance_m,
                    osm_id=osm_id,
                    osm_type=osm_type,
                    tags=tags,
                )
            )

    # Sort each category by proximity
    for group in (industrial, forests, croplands, roads, buildings):
        group.sort(key=lambda x: (x.distance_m is None, x.distance_m or 0))

    return industrial, forests, croplands, roads, buildings


async def fetch_nearby_context(
    latitude: float,
    longitude: float,
    radius_m: float = DEFAULT_RADIUS_M,
    use_cache: bool = True,
) -> GeospatialContext:
    """
    Fetch geographic land cover and features around a coordinate via Overpass API.

    Args:
        latitude:  Latitude in WGS84.
        longitude: Longitude in WGS84.
        radius_m:  Search radius in meters (default 2000m).
        use_cache: Whether to use in-memory coordinate cache.

    Returns:
        GeospatialContext with categorized nearby features.
    """
    # Cache key rounded to ~100m precision (3 decimal places)
    cache_key = f"{round(latitude, 3)}_{round(longitude, 3)}_{int(radius_m)}"
    now = time.time()

    if use_cache and cache_key in _GEOSPATIAL_CACHE:
        cached_time, cached_data = _GEOSPATIAL_CACHE[cache_key]
        if now - cached_time < CACHE_TTL_SECONDS:
            logger.debug("Returning cached geospatial context for key %s", cache_key)
            return cached_data

    query = build_overpass_query(latitude, longitude, radius_m)

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(
                OVERPASS_API_URL,
                data={"data": query},
                headers={"User-Agent": "ThermaSense-Geospatial-Service/1.0"},
            )

        if response.status_code == 200:
            payload = response.json()
            elements = payload.get("elements", [])
            industrial, forests, croplands, roads, buildings = parse_osm_elements(
                elements, latitude, longitude
            )

            context = GeospatialContext(
                latitude=latitude,
                longitude=longitude,
                radius_m=radius_m,
                industrial=industrial,
                forests=forests,
                croplands=croplands,
                roads=roads,
                buildings=buildings,
                source="openstreetmap",
            )

            if use_cache:
                _GEOSPATIAL_CACHE[cache_key] = (now, context)

            return context

        logger.warning(
            "Overpass API returned status %d for lat=%.4f, lon=%.4f",
            response.status_code,
            latitude,
            longitude,
        )
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        logger.warning(
            "Overpass API request failed (transient network error): %s", exc
        )
    except Exception as exc:
        logger.error(
            "Unexpected error parsing Overpass geospatial data: %s", exc, exc_info=True
        )

    # Fallback to empty context on transient network / Overpass outage
    return GeospatialContext(
        latitude=latitude,
        longitude=longitude,
        radius_m=radius_m,
        source="openstreetmap",
    )
