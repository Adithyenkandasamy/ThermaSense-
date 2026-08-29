"""
ThermaSense FastAPI application.

Entry point for the API server.
MVP version — no database, no background scheduler.
Data is fetched on-demand from NASA FIRMS and returned directly.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.app_debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="ThermaSense API",
        description=(
            "Geospatial intelligence platform for satellite thermal "
            "anomaly data. Fetches real-time data from NASA FIRMS "
            "and provides structured observation data for analysis."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
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

    logger.info("ThermaSense API initialized (env=%s)", settings.app_env)

    return app


app = create_app()
