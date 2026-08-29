"""
ThermaSense FastAPI application.

Entry point for the API server.
Module 1: On-demand FIRMS data fetch.
Module 2: PostgreSQL persistence, normalization, deduplication.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import get_settings
from app.core.database import init_db, close_db

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.app_debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Async lifespan — initialize and dispose database engine."""
    await init_db()
    logger.info("ThermaSense API initialized (env=%s)", settings.app_env)
    yield
    await close_db()
    logger.info("ThermaSense API shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="ThermaSense API",
        description=(
            "Geospatial intelligence platform for satellite thermal "
            "anomaly data. Fetches real-time data from NASA FIRMS, "
            "normalizes, validates, and stores observations in PostgreSQL."
        ),
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ───────────────────────────────────────────────────────
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

    # ── Routes ─────────────────────────────────────────────────────
    app.include_router(api_router)

    return app


app = create_app()
