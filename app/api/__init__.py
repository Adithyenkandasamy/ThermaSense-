"""API router — registers all route modules."""

from fastapi import APIRouter

from app.api.routes.events import ingest_router, router as events_router
from app.api.routes.health import router as health_router

api_router = APIRouter()

# Health check lives at root (always reachable)
api_router.include_router(health_router)

# Events & ingestion endpoints under /api/v1
api_router.include_router(events_router)
api_router.include_router(ingest_router)
