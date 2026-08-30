"""
Unit tests for FIRMS scheduler lifecycle, job execution, and resilience.
"""

from unittest.mock import AsyncMock, patch
import pytest

from app.scheduler import firms_scheduler


@pytest.mark.asyncio
async def test_scheduler_lifecycle():
    """Test start and stop scheduler."""
    scheduler = firms_scheduler.start_scheduler()
    assert scheduler is not None
    assert scheduler.running is True

    status = firms_scheduler.get_scheduler_status()
    assert status["scheduler_running"] is True
    assert status["poll_interval_minutes"] > 0
    assert len(status["sources"]) >= 1

    firms_scheduler.stop_scheduler()
    status_after = firms_scheduler.get_scheduler_status()
    assert status_after["scheduler_running"] is False


@pytest.mark.asyncio
async def test_run_monitoring_cycle_multi_source_success():
    """Test monitoring cycle running all configured sources."""
    mock_summary_20 = {
        "source": "VIIRS_NOAA20_NRT",
        "fetched": 20,
        "validated": 20,
        "stored": 20,
        "duplicates": 0,
        "invalid": 0,
        "status": "success",
    }
    mock_summary_21 = {
        "source": "VIIRS_NOAA21_NRT",
        "fetched": 15,
        "validated": 15,
        "stored": 15,
        "duplicates": 0,
        "invalid": 0,
        "status": "success",
    }

    async def mock_ingest(session, source, area, day_range):
        if "NOAA20" in source:
            return mock_summary_20
        return mock_summary_21

    with patch("app.scheduler.firms_scheduler.observation_service.ingest_firms_data", side_effect=mock_ingest):
        result = await firms_scheduler.run_monitoring_cycle()

    assert result["status"] == "success"
    assert len(result["results"]) == 2
    assert result["results"][0]["status"] == "success"
    assert result["results"][1]["status"] == "success"


@pytest.mark.asyncio
async def test_run_monitoring_cycle_partial_failure_does_not_crash_scheduler():
    """Test that a failure in one source does not crash the other source or future cycles."""
    async def mock_ingest(session, source, area, day_range):
        if "NOAA20" in source:
            raise RuntimeError("FIRMS API 503 Service Unavailable")
        return {
            "source": "VIIRS_NOAA21_NRT",
            "fetched": 10,
            "validated": 10,
            "stored": 10,
            "duplicates": 0,
            "invalid": 0,
            "status": "success",
        }

    with patch("app.scheduler.firms_scheduler.observation_service.ingest_firms_data", side_effect=mock_ingest):
        result = await firms_scheduler.run_monitoring_cycle()

    assert result["status"] == "partial_success"
    assert len(result["results"]) == 2
    assert result["results"][0]["status"] == "failed"
    assert result["results"][1]["status"] == "success"


@pytest.mark.asyncio
async def test_scheduler_prevents_overlapping_runs():
    """Test that concurrent cycle requests are skipped if one is already running."""
    with patch.object(firms_scheduler._job_lock, "locked", return_value=True):
        result = await firms_scheduler.run_monitoring_cycle()
        assert result["status"] == "skipped"
        assert "already in progress" in result["message"]
