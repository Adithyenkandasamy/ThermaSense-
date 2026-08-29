"""API router — registers all route modules."""

from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.hotspots import router as hotspots_router
from app.api.routes.ingestion import router as ingestion_router
from app.api.routes.context import router as context_router
from app.api.routes.observations import router as observations_router

api_router = APIRouter()

# Health check at root
api_router.include_router(health_router)

# Module 1: Live hotspot fetch endpoints
api_router.include_router(hotspots_router)

# Module 2: FIRMS ingestion with persistence
api_router.include_router(ingestion_router)

# Module 2: Stored observation query endpoints
api_router.include_router(observations_router)

# Context services (weather, geospatial)
api_router.include_router(context_router)
