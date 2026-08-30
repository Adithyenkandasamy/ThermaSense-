"""API router — registers all route modules."""

from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.hotspots import router as hotspots_router
from app.api.routes.ingestion import router as ingestion_router
from app.api.routes.context import router as context_router
from app.api.routes.observations import router as observations_router
from app.api.routes.monitoring import router as monitoring_router
from app.api.routes.events import router as events_router
from app.api.routes.attribution import router as attribution_router
from app.api.routes.export import router as export_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.clustering import router as clustering_router

api_router = APIRouter()

# Health check at root
api_router.include_router(health_router)

# Module 1: Live hotspot fetch endpoints
api_router.include_router(hotspots_router)

# Module 2: FIRMS ingestion with persistence
api_router.include_router(ingestion_router)

# Module 2: Stored observation query endpoints
api_router.include_router(observations_router)

# Module 2: Continuous monitoring endpoints
api_router.include_router(monitoring_router)

# Module 4: Thermal Events endpoints
api_router.include_router(events_router)

# Module 5: Attribution & Intelligence endpoints
api_router.include_router(attribution_router)

# Module 6: Export and Alerts endpoints
api_router.include_router(export_router)
api_router.include_router(alerts_router)

# Phase 10: Spatio-Temporal Event Clustering
api_router.include_router(clustering_router)

# Context services (weather, geospatial)
api_router.include_router(context_router)


