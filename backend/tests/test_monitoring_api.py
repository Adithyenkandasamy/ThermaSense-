"""
Unit & integration tests for monitoring endpoints (Module 2).
"""

from unittest.mock import AsyncMock, patch
import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.main import app
from app.models.ingestion_log import IngestionLog


@pytest.mark.asyncio
async def test_monitoring_status_endpoint():
    """Verify GET /api/monitoring/status returns expected structure without exposing secrets."""
    async def mock_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = mock_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/monitoring/status")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert "monitoring_enabled" in data
    assert "scheduler_running" in data
    assert "poll_interval_minutes" in data
    assert "monitoring_area" in data
    assert "sources" in data
    assert isinstance(data["sources"], list)
    assert "last_successful_ingestion" in data
    assert "next_scheduled_run" in data
    assert "last_ingestion_status" in data



@pytest.mark.asyncio
async def test_monitoring_logs_endpoint_mock_db():
    """Verify GET /api/monitoring/logs returns paginated ingestion history."""
    fake_log = IngestionLog(
        id=uuid.uuid4(),
        source="VIIRS_NOAA20_NRT",
        area="world",
        day_range=1,
        requested_at=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 8, 29, 12, 1, tzinfo=timezone.utc),
        status="success",
        records_fetched=100,
        records_validated=98,
        records_stored=80,
        duplicates_skipped=18,
        invalid_records=2,
        error_message=None,
    )

    async def mock_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = mock_get_db

    with patch(
        "app.services.observation_service.list_ingestion_logs",
        new=AsyncMock(return_value=([fake_log], 1)),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get(
                "/api/monitoring/logs",
                params={"limit": 10, "offset": 0, "status": "success"},
            )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["logs"]) == 1
    log_item = data["logs"][0]
    assert log_item["source"] == "VIIRS_NOAA20_NRT"
    assert log_item["records_fetched"] == 100
    assert log_item["records_validated"] == 98
    assert log_item["records_stored"] == 80
    assert log_item["duplicates_skipped"] == 18
    assert log_item["invalid_records"] == 2
    assert log_item["status"] == "success"


@pytest.mark.asyncio
async def test_monitoring_run_endpoint():
    """Verify POST /api/monitoring/run triggers an ingestion cycle."""
    mock_run_result = {
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": [
            {
                "source": "VIIRS_NOAA20_NRT",
                "fetched": 50,
                "validated": 50,
                "stored": 50,
                "duplicates": 0,
                "invalid": 0,
                "status": "success",
            }
        ],
    }

    with patch(
        "app.scheduler.firms_scheduler.run_monitoring_cycle",
        new=AsyncMock(return_value=mock_run_result),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post("/api/monitoring/run")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["results"]) == 1
    assert data["results"][0]["source"] == "VIIRS_NOAA20_NRT"
