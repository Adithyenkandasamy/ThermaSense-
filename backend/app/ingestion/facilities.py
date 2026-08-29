"""
Industrial facility ingestion via OpenStreetMap Overpass API.

Fetches industrial facilities (refineries, power plants, factories, mines, etc.)
within the configured demo bounding box and stores them in the
`industrial_facilities` PostGIS table.

Design decisions:
  - Uses the public Overpass API (no auth required).
  - Falls back to deterministic DEMO data if the Overpass call fails.
  - Safe to run repeatedly — all inserts use ON CONFLICT DO NOTHING.
  - Geometry is stored as PostGIS POINT (centroid for ways/relations).

Overpass QL query targets:
  amenity=industrial
  landuse=industrial
  man_made=petroleum_well / works / water_works / storage_tank
  industrial=refinery / factory / mine / power_station / LNG / petrochemical
  power=plant
  landuse=quarry
"""

import logging
import math
from typing import Any

import httpx
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.thermal_event import IndustrialFacility

logger = logging.getLogger(__name__)

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"

# How long to wait for Overpass (it can be slow under load)
OVERPASS_TIMEOUT_SECONDS = 45

# OSM tag-to-facility_type mappings — order matters (first match wins)
TAG_TYPE_MAP = [
    # Refinery / Petrochemical
    ({"industrial": "refinery"}, "REFINERY"),
    ({"industrial": "oil_refinery"}, "REFINERY"),
    ({"industrial": "petroleum"}, "REFINERY"),
    ({"industrial": "petrochemical"}, "PETROCHEMICAL"),
    ({"man_made": "petroleum_well"}, "REFINERY"),
    # Power plant
    ({"power": "plant"}, "POWER_PLANT"),
    ({"power": "generator"}, "POWER_PLANT"),
    ({"industrial": "power_station"}, "POWER_PLANT"),
    # LNG / Gas
    ({"industrial": "lng_terminal"}, "LNG"),
    ({"industrial": "gas_plant"}, "LNG"),
    ({"industrial": "gas"}, "LNG"),
    # Mine / Quarry
    ({"landuse": "quarry"}, "MINE"),
    ({"industrial": "mine"}, "MINE"),
    ({"industrial": "quarry"}, "MINE"),
    # General factory / industrial
    ({"industrial": "factory"}, "FACTORY"),
    ({"industrial": "manufacturing"}, "FACTORY"),
    ({"amenity": "industrial"}, "FACTORY"),
    ({"landuse": "industrial"}, "FACTORY"),
    ({"man_made": "works"}, "FACTORY"),
    # Water / waste
    ({"man_made": "water_works"}, "WATER_WORKS"),
    ({"man_made": "wastewater_plant"}, "WASTE_TREATMENT"),
    ({"man_made": "storage_tank"}, "STORAGE"),
]


def _classify_tags(tags: dict[str, str]) -> str:
    """Map OSM tags to a normalised facility type string."""
    for tag_filter, facility_type in TAG_TYPE_MAP:
        for key, value in tag_filter.items():
            if tags.get(key, "").lower() == value.lower():
                return facility_type
    return "INDUSTRIAL"


def _centroid(element: dict[str, Any]) -> tuple[float, float] | None:
    """
    Extract (lat, lon) centroid from an Overpass element.

    Handles:
      - node: has `lat`, `lon` directly
      - way/relation with `center`: use the center field
      - way/relation with `bounds`: use the midpoint of bounds
    """
    etype = element.get("type")

    if etype == "node":
        lat = element.get("lat")
        lon = element.get("lon")
        if lat is not None and lon is not None:
            return float(lat), float(lon)

    # ways and relations — prefer pre-computed center
    center = element.get("center")
    if center:
        return float(center["lat"]), float(center["lon"])

    # fallback: midpoint of bounds
    bounds = element.get("bounds")
    if bounds:
        lat = (bounds["minlat"] + bounds["maxlat"]) / 2
        lon = (bounds["minlon"] + bounds["maxlon"]) / 2
        return lat, lon

    return None


def _build_overpass_query(bbox: tuple[float, float, float, float]) -> str:
    """
    Build an Overpass QL query that fetches industrial features within bbox.

    bbox: (xmin, ymin, xmax, ymax) in WGS84.
    Overpass expects: south,west,north,east = (ymin,xmin,ymax,xmax).
    """
    xmin, ymin, xmax, ymax = bbox
    # Overpass bbox order: south, west, north, east
    bb = f"{ymin},{xmin},{ymax},{xmax}"

    return f"""
[out:json][timeout:45];
(
  node["power"="plant"]({bb});
  way["power"="plant"]({bb});
  node["industrial"~"refinery|oil_refinery|petroleum|petrochemical|factory|manufacturing|mine|quarry|gas_plant|lng_terminal|power_station"]({bb});
  way["industrial"~"refinery|oil_refinery|petroleum|petrochemical|factory|manufacturing|mine|quarry|gas_plant|lng_terminal|power_station"]({bb});
  node["man_made"~"petroleum_well|works|water_works|storage_tank|wastewater_plant"]({bb});
  way["man_made"~"petroleum_well|works|water_works|storage_tank|wastewater_plant"]({bb});
  way["landuse"="industrial"]({bb});
  way["landuse"="quarry"]({bb});
);
out center tags;
""".strip()


async def _fetch_overpass(bbox: tuple[float, float, float, float]) -> list[dict]:
    """
    Call Overpass API and return a list of raw elements.

    Returns empty list on failure (caller handles fallback).
    """
    query = _build_overpass_query(bbox)
    try:
        async with httpx.AsyncClient(timeout=OVERPASS_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                OVERPASS_ENDPOINT,
                data={"data": query},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()
            elements = data.get("elements", [])
            logger.info("Overpass returned %d raw elements", len(elements))
            return elements
    except Exception as exc:
        logger.warning("Overpass API call failed: %s — will use demo fallback", exc)
        return []


def _parse_elements(elements: list[dict]) -> list[dict]:
    """
    Convert raw Overpass elements into normalised facility dicts.

    Returns list of dicts with:
      external_id, name, facility_type, latitude, longitude
    """
    seen_ids: set[str] = set()
    facilities = []

    for el in elements:
        tags = el.get("tags", {})

        # Must have at least a name or a recognisable tag
        name = (
            tags.get("name")
            or tags.get("operator")
            or tags.get("brand")
            or tags.get("industrial", "")
            or tags.get("man_made", "")
            or tags.get("power", "")
            or "Unnamed Industrial Site"
        ).strip()
        if not name:
            name = "Unnamed Industrial Site"

        coord = _centroid(el)
        if coord is None:
            continue  # skip elements without usable geometry

        lat, lon = coord
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue

        facility_type = _classify_tags(tags)
        ext_id = f"OSM-{el.get('type', 'x')}-{el.get('id', 0)}"

        if ext_id in seen_ids:
            continue
        seen_ids.add(ext_id)

        facilities.append(
            {
                "external_id": ext_id,
                "name": name[:200],
                "facility_type": facility_type,
                "latitude": lat,
                "longitude": lon,
                "source": "OSM",
                "facility_metadata": {
                    "osm_id": el.get("id"),
                    "osm_type": el.get("type"),
                    "tags": {k: v for k, v in tags.items() if k != "name"},
                },
            }
        )

    return facilities


# ── Demo fallback facilities covering the Western-US demo region ──────────
_DEMO_FACILITIES = [
    # California refineries / industrial
    {
        "external_id": "DEMO-FAC-CHEVRON-RICHMOND",
        "name": "Chevron Richmond Refinery",
        "facility_type": "REFINERY",
        "latitude": 37.9255,
        "longitude": -122.3477,
        "source": "DEMO",
    },
    {
        "external_id": "DEMO-FAC-TESORO-WILMINGTON",
        "name": "Marathon Wilmington Refinery",
        "facility_type": "REFINERY",
        "latitude": 33.7897,
        "longitude": -118.2607,
        "source": "DEMO",
    },
    {
        "external_id": "DEMO-FAC-VALERO-BENICIA",
        "name": "Valero Benicia Refinery",
        "facility_type": "REFINERY",
        "latitude": 38.0497,
        "longitude": -122.1397,
        "source": "DEMO",
    },
    {
        "external_id": "DEMO-FAC-GEOTHERMAL-COSO",
        "name": "Coso Geothermal Power Plant",
        "facility_type": "POWER_PLANT",
        "latitude": 36.0472,
        "longitude": -117.7878,
        "source": "DEMO",
    },
    {
        "external_id": "DEMO-FAC-GEYSERS-POWER",
        "name": "The Geysers Geothermal Complex",
        "facility_type": "POWER_PLANT",
        "latitude": 38.7857,
        "longitude": -122.7545,
        "source": "DEMO",
    },
    {
        "external_id": "DEMO-FAC-DIABLO-CANYON",
        "name": "Diablo Canyon Power Plant",
        "facility_type": "POWER_PLANT",
        "latitude": 35.2110,
        "longitude": -120.8540,
        "source": "DEMO",
    },
    {
        "external_id": "DEMO-FAC-KERNSRIVER-OILFIELD",
        "name": "Kern River Oil Field",
        "facility_type": "REFINERY",
        "latitude": 35.3730,
        "longitude": -118.9060,
        "source": "DEMO",
    },
    {
        "external_id": "DEMO-FAC-BLYTHE-SOLAR",
        "name": "Desert Sunlight Solar Farm",
        "facility_type": "POWER_PLANT",
        "latitude": 33.7297,
        "longitude": -115.4540,
        "source": "DEMO",
    },
    {
        "external_id": "DEMO-FAC-CEMENT-MOJAVE",
        "name": "Lehigh Southwest Cement Plant",
        "facility_type": "FACTORY",
        "latitude": 34.9240,
        "longitude": -118.1540,
        "source": "DEMO",
    },
    {
        "external_id": "DEMO-FAC-BORAX-MINE",
        "name": "Rio Tinto Boron Operations (Borax Mine)",
        "facility_type": "MINE",
        "latitude": 35.0030,
        "longitude": -117.6520,
        "source": "DEMO",
    },
    {
        "external_id": "DEMO-FAC-GOLD-MINE-NEVADA",
        "name": "Barrick Goldstrike Mine",
        "facility_type": "MINE",
        "latitude": 40.8520,
        "longitude": -116.3990,
        "source": "DEMO",
    },
    {
        "external_id": "DEMO-FAC-HENDERSON-CHEM",
        "name": "Henderson Chemical Complex",
        "facility_type": "PETROCHEMICAL",
        "latitude": 36.0236,
        "longitude": -114.9692,
        "source": "DEMO",
    },
    # India demo region (covers existing DB demo events at lat~12.x, lon~78-79)
    {
        "external_id": "DEMO-FAC-REFINERY-001",
        "name": "Example Refinery",
        "facility_type": "REFINERY",
        "latitude": 12.3499,
        "longitude": 78.9068,
        "source": "DEMO",
    },
    {
        "external_id": "DEMO-FAC-POWER-002",
        "name": "North Thermal Power Plant",
        "facility_type": "POWER_PLANT",
        "latitude": 12.361,
        "longitude": 78.886,
        "source": "DEMO",
    },
    {
        "external_id": "DEMO-FAC-MINE-003",
        "name": "Eastern Quarry Complex",
        "facility_type": "MINE",
        "latitude": 12.66,
        "longitude": 78.61,
        "source": "DEMO",
    },
]


async def _upsert_facilities(
    db: AsyncSession, facilities: list[dict]
) -> tuple[int, int]:
    """
    Upsert a list of normalised facility dicts.

    Returns (inserted_count, skipped_count).
    """
    inserted = 0
    skipped = 0

    for fac in facilities:
        geom = from_shape(Point(fac["longitude"], fac["latitude"]), srid=4326)
        values = {
            "external_id": fac["external_id"],
            "name": fac["name"],
            "facility_type": fac["facility_type"],
            "latitude": fac["latitude"],
            "longitude": fac["longitude"],
            "geom": geom,
            "source": fac.get("source", "OSM"),
            "facility_metadata": fac.get("facility_metadata", {}),
        }
        stmt = (
            pg_insert(IndustrialFacility)
            .values(**values)
            .on_conflict_do_nothing(constraint="uq_industrial_facilities_external_id")
            .returning(IndustrialFacility.id)
        )
        row = (await db.execute(stmt)).fetchone()
        if row:
            inserted += 1
        else:
            skipped += 1

    await db.flush()
    return inserted, skipped


async def sync_facilities(
    db: AsyncSession,
    bbox: tuple[float, float, float, float] | None = None,
) -> dict:
    """
    Fetch industrial facilities from Overpass API and upsert into DB.

    Args:
        db:   Async SQLAlchemy session.
        bbox: (xmin, ymin, xmax, ymax) bounding box to search.
              Defaults to the config demo_bbox.

    Returns:
        Summary dict with counts and source info.
    """
    from app.config import get_settings

    settings = get_settings()
    if bbox is None:
        bbox = settings.demo_bbox

    logger.info("Starting facility sync for bbox=%s", bbox)

    # ── 1. Try Overpass ─────────────────────────────────────────────
    elements = await _fetch_overpass(bbox)
    source = "OSM"

    if elements:
        facilities = _parse_elements(elements)
        logger.info("Parsed %d valid facilities from Overpass", len(facilities))
    else:
        # ── 2. Fallback to demo data ─────────────────────────────────
        logger.warning("Overpass unavailable — seeding deterministic DEMO facilities")
        facilities = _DEMO_FACILITIES
        source = "DEMO_FALLBACK"

    if not facilities:
        return {
            "status": "ok",
            "source": source,
            "fetched": 0,
            "inserted": 0,
            "skipped_duplicates": 0,
            "message": "No facilities found in bounding box.",
        }

    inserted, skipped = await _upsert_facilities(db, facilities)

    logger.info(
        "Facility sync complete — source=%s inserted=%d skipped=%d",
        source, inserted, skipped,
    )

    return {
        "status": "ok",
        "source": source,
        "fetched": len(facilities),
        "inserted": inserted,
        "skipped_duplicates": skipped,
        "message": (
            f"Facility sync complete (source={source}). "
            f"Inserted {inserted} new facilities, skipped {skipped} duplicates."
        ),
    }
