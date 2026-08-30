"""
Tests for FIRMS API retry, backoff, secret masking, and failure handling.
"""

from unittest.mock import AsyncMock, patch
import pytest
import httpx

from app.services import firms_service


@pytest.mark.asyncio
async def test_firms_fetch_retries_on_500_server_error():
    """Verify fetch_hotspots retries up to max_retries on transient 500 errors."""
    mock_request = httpx.Request("GET", "https://firms.modaps.eosdis.nasa.gov/api/area/csv/testkey/VIIRS_NOAA20_NRT/world/1")
    response_500 = httpx.Response(500, request=mock_request, text="Internal Server Error")
    
    valid_csv = (
        "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
        "37.77,-122.41,320.5,0.4,0.4,2026-08-29,1200,N20,VIIRS,nominal,2.0NRT,295.0,15.0,D\n"
    )
    response_200 = httpx.Response(200, request=mock_request, text=valid_csv)

    mock_client = AsyncMock()
    # First 2 calls fail with 500, 3rd call succeeds with 200
    mock_client.get.side_effect = [response_500, response_500, response_200]

    with patch("httpx.AsyncClient") as mock_client_cls, patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        observations, source, area = await firms_service.fetch_hotspots(
            map_key="test_secret_map_key_12345",
            satellite="NOAA-20",
            max_retries=3,
            retry_delay_seconds=0.1,
        )

    assert len(observations) == 1
    assert source == "VIIRS_NOAA20_NRT"
    assert mock_client.get.call_count == 3
    assert mock_sleep.call_count == 2


@pytest.mark.asyncio
async def test_firms_fetch_fails_after_max_retries():
    """Verify fetch_hotspots raises RuntimeError after exceeding max_retries."""
    mock_request = httpx.Request("GET", "https://firms.modaps.eosdis.nasa.gov/api/area/csv/testkey/VIIRS_NOAA20_NRT/world/1")
    response_503 = httpx.Response(503, request=mock_request, text="Service Unavailable")

    mock_client = AsyncMock()
    mock_client.get.return_value = response_503

    with patch("httpx.AsyncClient") as mock_client_cls, patch("asyncio.sleep", new=AsyncMock()):
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        with pytest.raises(RuntimeError) as exc_info:
            await firms_service.fetch_hotspots(
                map_key="test_secret_map_key_12345",
                satellite="NOAA-20",
                max_retries=2,
                retry_delay_seconds=0.1,
            )

    assert "attempts" in str(exc_info.value)
    # Never expose the full map key in errors
    assert "test_secret_map_key_12345" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_firms_non_retryable_400_error_raises_immediately():
    """Verify non-retryable 4xx error raises without retrying."""
    mock_request = httpx.Request("GET", "https://firms.modaps.eosdis.nasa.gov/api/area/csv/testkey/VIIRS_NOAA20_NRT/world/1")
    response_400 = httpx.Response(400, request=mock_request, text="Bad Request: invalid coordinates")

    mock_client = AsyncMock()
    mock_client.get.return_value = response_400

    with patch("httpx.AsyncClient") as mock_client_cls, patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        with pytest.raises(RuntimeError) as exc_info:
            await firms_service.fetch_hotspots(
                map_key="test_secret_map_key_12345",
                satellite="NOAA-20",
                max_retries=3,
            )

    assert mock_client.get.call_count == 1
    assert mock_sleep.call_count == 0
    assert "400" in str(exc_info.value)
    assert "test_secret_map_key_12345" not in str(exc_info.value)


def test_mask_key_and_url():
    """Verify key masking does not expose secret keys."""
    key = "cc9bbdc3216ebdaab31d9b11fbf502a9"
    masked = firms_service._mask_key(key)
    assert key not in masked
    assert masked == "cc9...2a9"

    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_NOAA20_NRT/world/1"
    masked_url = firms_service._mask_url(url, key)
    assert key not in masked_url
    assert "cc9...2a9" in masked_url
