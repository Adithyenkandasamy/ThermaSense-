"""
Tests for geospatial context service and API endpoint (Module 3).
"""

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport, Response

from app.main import app
from app.services.geospatial_service import (
    calculate_haversine_distance,
    parse_osm_elements,
    fetch_nearby_context,
    GeospatialContext,
    _GEOSPATIAL_CACHE,
)


def test_haversine_distance_calculation():
    """Verify Haversine distance matches expected ground truth."""
    # Distance between (0, 0) and (0, 1) degrees on equator is ~111.19 km
    dist = calculate_haversine_distance(0.0, 0.0, 0.0, 1.0)
    assert 111000 <= dist <= 112000

    # Same point distance is 0
    assert calculate_haversine_distance(37.5, -121.5, 37.5, -121.5) == 0.0


def test_parse_osm_elements():
    """Verify parsing and categorizing diverse OSM element tags."""
    mock_elements = [
        {
            "id": 101,
            "type": "way",
            "center": {"lat": 37.505, "lon": -121.505},
            "tags": {"landuse": "industrial", "name": "Chevron Refinery"},
        },
        {
            "id": 102,
            "type": "way",
            "center": {"lat": 37.510, "lon": -121.510},
            "tags": {"landuse": "forest", "name": "Stanislaus National Forest"},
        },
        {
            "id": 103,
            "type": "way",
            "center": {"lat": 37.502, "lon": -121.502},
            "tags": {"landuse": "farmland", "crop": "Wheat"},
        },
        {
            "id": 104,
            "type": "way",
            "center": {"lat": 37.501, "lon": -121.501},
            "tags": {"highway": "primary", "ref": "CA-99"},
        },
        {
            "id": 105,
            "type": "way",
            "center": {"lat": 37.503, "lon": -121.503},
            "tags": {"building": "yes"},
        },
    ]

    target_lat, target_lon = 37.500, -121.500
    ind, forests, crops, roads, bldgs = parse_osm_elements(
        mock_elements, target_lat, target_lon
    )

    assert len(ind) == 1
    assert ind[0].name == "Chevron Refinery"
    assert ind[0].feature_type == "industrial"
    assert ind[0].distance_m > 0

    assert len(forests) == 1
    assert forests[0].name == "Stanislaus National Forest"
    assert forests[0].feature_type == "forest"

    assert len(crops) == 1
    assert crops[0].feature_type == "cropland"

    assert len(roads) == 1
    assert roads[0].name == "CA-99"

    assert len(bldgs) == 1
    assert bldgs[0].feature_type == "building"


@pytest.mark.asyncio
async def test_fetch_nearby_context_success():
    """Verify live context fetching with mock HTTP response."""
    mock_payload = {
        "elements": [
            {
                "id": 201,
                "type": "way",
                "center": {"lat": 12.0, "lon": 77.0},
                "tags": {"natural": "wood", "name": "Bandipur Woods"},
            }
        ]
    }

    mock_resp = Response(200, json=mock_payload, request=AsyncMock())

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        context = await fetch_nearby_context(
            latitude=12.001,
            longitude=77.001,
            radius_m=2000,
            use_cache=False,
        )

        assert isinstance(context, GeospatialContext)
        assert len(context.forests) == 1
        assert context.forests[0].name == "Bandipur Woods"
        assert context.source == "openstreetmap"


@pytest.mark.asyncio
async def test_fetch_nearby_context_caching():
    """Verify that cached context avoids duplicate network queries."""
    _GEOSPATIAL_CACHE.clear()

    mock_payload = {"elements": []}
    mock_resp = Response(200, json=mock_payload, request=AsyncMock())

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        # First call hits network
        ctx1 = await fetch_nearby_context(34.123, -118.456, radius_m=2000, use_cache=True)
        assert mock_post.call_count == 1

        # Second call with same coordinate hits cache
        ctx2 = await fetch_nearby_context(34.123, -118.456, radius_m=2000, use_cache=True)
        assert mock_post.call_count == 1  # No extra call
        assert ctx1.latitude == ctx2.latitude


@pytest.mark.asyncio
async def test_geospatial_api_endpoint():
    """Verify GET /api/context/geospatial route."""
    mock_payload = {
        "elements": [
            {
                "id": 301,
                "type": "node",
                "lat": 10.005,
                "lon": 76.005,
                "tags": {"man_made": "flare", "name": "Offshore Flare"},
            }
        ]
    }
    mock_resp = Response(200, json=mock_payload, request=AsyncMock())

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(
                "/api/context/geospatial",
                params={"latitude": 10.0, "longitude": 76.0, "radius_m": 1500},
            )

            assert res.status_code == 200
            data = res.json()
            assert data["latitude"] == 10.0
            assert data["longitude"] == 76.0
            assert data["radius_m"] == 1500.0
            assert len(data["industrial"]) == 1
            assert data["industrial"][0]["name"] == "Offshore Flare"
            assert data["industrial"][0]["feature_type"] == "industrial"
