"""
End-to-end tests for Module 2 ingestion pipeline, deduplication, logging, and monitoring.
"""

from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

import uuid
from datetime import datetime, timezone

from app.core.database import Base, get_db
from app.main import app
from app.schemas.observation import HotspotResponse


def _make_hotspots(count: int, source: str = "VIIRS_NOAA20_NRT", start_id: int = 1, tag: str = "t1") -> list[HotspotResponse]:
    """Helper to generate dummy HotspotResponse items."""
    hotspots = []
    for i in range(start_id, start_id + count):
        hotspots.append(
            HotspotResponse(
                id=f"hotspot_{source}_{tag}_{i}",
                latitude=round(10.0 + (i * 0.0001), 6),
                longitude=round(77.0 + (i * 0.0001), 6),
                acquisition_datetime=datetime(2099, 1, 1, 12, 0, tzinfo=timezone.utc),
                satellite=f"NOAA-{tag}",
                instrument="VIIRS",
                brightness=320.0,
                bright_ti4=320.0,
                bright_ti5=295.0,
                frp=12.0,
                confidence="nominal",
                daynight="D",
                source=source,
            )
        )
    return hotspots


@pytest.mark.asyncio
async def test_end_to_end_deduplication_and_logging():
    """
    Verify complete deduplication cycle:
    1st run: 50 fetched -> 50 stored -> 0 duplicates
    2nd run: 50 fetched -> 0 stored -> 50 duplicates
    3rd run: 50 old + 25 new -> 25 stored -> 50 duplicates
    """
    import uuid
    run_tag = uuid.uuid4().hex[:8]
    area_tag = f"area_{run_tag}"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        batch_1 = _make_hotspots(50, source="VIIRS_NOAA20_NRT", start_id=1, tag=run_tag)

        # ── 1st Ingestion ─────────────────────────────────────
        with patch("app.services.observation_service.fetch_hotspots", new=AsyncMock(return_value=(batch_1, "VIIRS_NOAA20_NRT", area_tag))):
            res1 = await ac.post("/api/ingestion/firms", json={
                "source": "VIIRS_NOAA20_NRT",
                "area": area_tag,
                "day_range": 1,
            })
            assert res1.status_code == 200
            data1 = res1.json()
            assert data1["fetched"] == 50
            assert data1["validated"] == 50
            assert data1["stored"] == 50
            assert data1["duplicates"] == 0
            assert data1["status"] == "success"

        # ── 2nd Ingestion (Exact duplicate) ───────────────────
        with patch("app.services.observation_service.fetch_hotspots", new=AsyncMock(return_value=(batch_1, "VIIRS_NOAA20_NRT", area_tag))):
            res2 = await ac.post("/api/ingestion/firms", json={
                "source": "VIIRS_NOAA20_NRT",
                "area": area_tag,
                "day_range": 1,
            })
            assert res2.status_code == 200
            data2 = res2.json()
            assert data2["fetched"] == 50
            assert data2["validated"] == 50
            assert data2["stored"] == 0
            assert data2["duplicates"] == 50
            assert data2["status"] == "success"

        # ── 3rd Ingestion (50 old + 25 new) ───────────────────
        batch_3 = batch_1 + _make_hotspots(25, source="VIIRS_NOAA20_NRT", start_id=51, tag=run_tag)
        with patch("app.services.observation_service.fetch_hotspots", new=AsyncMock(return_value=(batch_3, "VIIRS_NOAA20_NRT", area_tag))):
            res3 = await ac.post("/api/ingestion/firms", json={
                "source": "VIIRS_NOAA20_NRT",
                "area": area_tag,
                "day_range": 1,
            })
            assert res3.status_code == 200
            data3 = res3.json()
            assert data3["fetched"] == 75
            assert data3["validated"] == 75
            assert data3["stored"] == 25
            assert data3["duplicates"] == 50
            assert data3["status"] == "success"

        # ── Verify Monitoring Logs ────────────────────
        logs_res = await ac.get("/api/monitoring/logs", params={"source": "VIIRS_NOAA20_NRT", "limit": 10})
        assert logs_res.status_code == 200
        logs_data = logs_res.json()
        assert logs_data["total"] >= 3
        latest_log = logs_data["logs"][0]
        assert latest_log["records_fetched"] == 75
        assert latest_log["records_stored"] == 25
        assert latest_log["duplicates_skipped"] == 50

        # ── Verify Monitoring Status ──────────────────
        status_res = await ac.get("/api/monitoring/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["last_successful_ingestion"] is not None
        assert status_data["last_ingestion_status"] == "success"


