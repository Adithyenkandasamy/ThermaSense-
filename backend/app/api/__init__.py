"""API router — registers all route modules."""

from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.hotspots import router as hotspots_router
from app.api.routes.ingestion import router as ingestion_router
from app.api.routes.context import router as context_router

api_router = APIRouter()

# Health check at root
api_router.include_router(health_router)

# Hotspot observation endpoints
api_router.include_router(hotspots_router)

# FIRMS ingestion trigger
api_router.include_router(ingestion_router)

# Context services (weather, geospatial)
api_router.include_router(context_router)
