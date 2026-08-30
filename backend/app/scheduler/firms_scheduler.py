"""
Continuous monitoring scheduler for NASA FIRMS (Module 2).

Runs periodic background ingestion jobs via APScheduler AsyncIOScheduler.
Reuses the existing ingestion pipeline in observation_service.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.core.database import get_db_context
from app.services import observation_service

logger = logging.getLogger(__name__)

# Global scheduler instance & runtime tracking state
_scheduler: Optional[AsyncIOScheduler] = None
_job_lock = asyncio.Lock()

_runtime_state: dict[str, Any] = {
    "last_successful_ingestion": None,
    "last_ingestion_status": None,
    "last_run_at": None,
    "last_error": None,
}


async def run_monitoring_cycle() -> dict[str, Any]:
    """
    Execute one complete monitoring cycle across all configured FIRMS sources.

    Prevents overlapping execution using an asyncio lock.
    Reuses the existing observation_service.ingest_firms_data pipeline.
    """
    if _job_lock.locked():
        logger.warning("Monitoring cycle already in progress — skipping concurrent run")
        return {
            "status": "skipped",
            "message": "Monitoring cycle already in progress",
            "results": [],
        }

    async with _job_lock:
        settings = get_settings()
        sources = settings.firms_sources
        area = settings.firms_monitoring_area
        day_range = settings.firms_day_range

        logger.info(
            "Starting scheduled FIRMS monitoring cycle (sources=%s, area=%s, days=%d)",
            sources,
            area,
            day_range,
        )

        results: list[dict[str, Any]] = []
        any_success = False
        any_failure = False
        now_utc = datetime.now(timezone.utc)
        _runtime_state["last_run_at"] = now_utc

        for source in sources:
            try:
                async with get_db_context() as session:
                    summary = await observation_service.ingest_firms_data(
                        session=session,
                        source=source,
                        area=area,
                        day_range=day_range,
                    )
                    results.append(summary)
                    if summary.get("status") == "success":
                        any_success = True
                    else:
                        any_failure = True
            except Exception as exc:
                any_failure = True
                err_msg = str(exc)
                logger.error(
                    "Error during scheduled ingestion for source %s: %s",
                    source,
                    err_msg,
                    exc_info=True,
                )
                results.append({
                    "source": source,
                    "status": "failed",
                    "error": err_msg,
                })

        if any_success and not any_failure:
            cycle_status = "success"
            _runtime_state["last_successful_ingestion"] = datetime.now(timezone.utc)
            _runtime_state["last_error"] = None
        elif any_success and any_failure:
            cycle_status = "partial_success"
            _runtime_state["last_successful_ingestion"] = datetime.now(timezone.utc)
            _runtime_state["last_error"] = "Some sources failed during the cycle"
        else:
            cycle_status = "failed"
            _runtime_state["last_error"] = "All sources failed during the cycle"

        _runtime_state["last_ingestion_status"] = cycle_status

        logger.info(
            "Completed FIRMS monitoring cycle (status=%s, results=%s)",
            cycle_status,
            results,
        )

        return {
            "status": cycle_status,
            "timestamp": now_utc.isoformat(),
            "results": results,
        }


def get_next_run_time() -> Optional[datetime]:
    """Get the datetime of the next scheduled run if scheduler is running."""
    if _scheduler is not None and _scheduler.running:
        job = _scheduler.get_job("firms_monitoring_job")
        if job and job.next_run_time:
            return job.next_run_time
    return None


def get_scheduler_status() -> dict[str, Any]:
    """
    Return runtime information for monitoring status API.
    """
    settings = get_settings()
    is_running = _scheduler is not None and _scheduler.running

    return {
        "monitoring_enabled": settings.firms_monitoring_enabled,
        "scheduler_running": is_running,
        "poll_interval_minutes": settings.firms_poll_interval_minutes,
        "monitoring_area": settings.firms_monitoring_area,
        "sources": settings.firms_sources,
        "last_successful_ingestion": _runtime_state.get("last_successful_ingestion"),
        "next_scheduled_run": get_next_run_time(),
        "last_ingestion_status": _runtime_state.get("last_ingestion_status"),
    }


def start_scheduler() -> Optional[AsyncIOScheduler]:
    """
    Initialize and start the AsyncIOScheduler.
    """
    global _scheduler
    settings = get_settings()

    if not settings.firms_monitoring_enabled:
        logger.info("FIRMS continuous monitoring is disabled (FIRMS_MONITORING_ENABLED=False)")
        return None

    if _scheduler is not None and _scheduler.running:
        logger.warning("FIRMS scheduler is already running")
        return _scheduler

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        run_monitoring_cycle,
        trigger=IntervalTrigger(minutes=settings.firms_poll_interval_minutes),
        id="firms_monitoring_job",
        name="NASA FIRMS Continuous Monitoring Ingestion",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()

    logger.info(
        "FIRMS monitoring scheduler started (interval=%d min, sources=%s, area=%s)",
        settings.firms_poll_interval_minutes,
        settings.firms_sources,
        settings.firms_monitoring_area,
    )
    return _scheduler


def stop_scheduler() -> None:
    """
    Cleanly shut down the scheduler on application shutdown.
    """
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("FIRMS monitoring scheduler shut down cleanly")
    _scheduler = None
