"""
ThermaSense FastAPI application.

Entry point for the API server.
"""

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


async def _scheduled_ingest() -> None:
    """
    Background task: fetch and ingest NASA FIRMS data.
    Called by APScheduler every `poll_interval_minutes` minutes.
    """
    from app.database import AsyncSessionLocal
    from app.services.ingest_service import run_ingestion

    logger.info("Scheduled FIRMS ingestion starting...")
    async with AsyncSessionLocal() as session:
        try:
            result = await run_ingestion(session)
            await session.commit()
            logger.info(
                "Scheduled ingestion complete — %s",
                result.get("message", "no details"),
            )
        except Exception as exc:
            await session.rollback()
            logger.error("Scheduled ingestion failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Startup:
      - Start APScheduler for background FIRMS polling
      - Run an immediate first ingestion so data is ready right away

    Shutdown:
      - Stop the scheduler cleanly
    """
    # ── Startup ────────────────────────────────────────────────────
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _scheduled_ingest,
        trigger="interval",
        minutes=settings.poll_interval_minutes,
        id="firms_ingest",
        name="NASA FIRMS Ingestion",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "APScheduler started — FIRMS poll every %d minutes",
        settings.poll_interval_minutes,
    )

    # Immediate first fetch on startup
    logger.info("Running initial FIRMS ingestion on startup...")
    await _scheduled_ingest()

    yield

    # ── Shutdown ───────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="ThermaSense API",
        description=(
            "AI-enabled geospatial thermal-event intelligence platform. "
            "Ingests NASA FIRMS satellite data and enriches thermal events "
            "with geospatial context and Groq AI-powered classification."
        ),
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ───────────────────────────────────────────────────────────
    origins = (
        ["*"]
        if settings.is_development
        else ["https://thermasense.example.com"]
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes ─────────────────────────────────────────────────────────
    app.include_router(api_router)

    return app


app = create_app()
