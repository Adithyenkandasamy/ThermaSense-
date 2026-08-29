"""
NASA FIRMS HTTP client.

Fetches near real-time (NRT) VIIRS fire hotspot data as CSV
from the FIRMS Area API:
https://firms.modaps.eosdis.nasa.gov/api/area/

API format:
  GET /api/area/csv/{map_key}/{source}/{area}/{day_range}

Sources used:
  VIIRS_SNPP_NRT  — Suomi NPP (real-time, ~10-min latency)
"""

import logging

import httpx

logger = logging.getLogger(__name__)

FIRMS_BASE_URL = "https://firms.modaps.eosdis.nasa.gov"
DEFAULT_SOURCE = "VIIRS_SNPP_NRT"


async def fetch_firms_csv(
    api_key: str,
    bbox: tuple[float, float, float, float],
    day_range: int = 1,
    source: str = DEFAULT_SOURCE,
    timeout: int = 30,
) -> str:
    """
    Fetch FIRMS hotspot data as raw CSV text.

    Args:
        api_key:   Your NASA FIRMS map key.
        bbox:      (xmin, ymin, xmax, ymax) in WGS84.
        day_range: How many past days to include (1 = today only).
        source:    FIRMS product name.
        timeout:   HTTP timeout in seconds.

    Returns:
        Raw CSV string (with header row).

    Raises:
        httpx.HTTPError: on network or HTTP errors.
    """
    xmin, ymin, xmax, ymax = bbox
    area = f"{xmin},{ymin},{xmax},{ymax}"
    url = f"{FIRMS_BASE_URL}/api/area/csv/{api_key}/{source}/{area}/{day_range}"

    logger.info("Fetching FIRMS data — source=%s bbox=%s days=%d", source, area, day_range)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()

    text = response.text
    line_count = text.count("\n")
    logger.info("FIRMS returned %d lines (approx %d events)", line_count, max(0, line_count - 1))
    return text
