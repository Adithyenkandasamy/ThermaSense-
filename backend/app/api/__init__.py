"""API router — registers all route modules."""

from fastapi import APIRouter

from app.api.routes.alerts import router as alerts_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.demo import router as demo_router
from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router
from app.api.routes.ingestion import router as ingestion_router
from app.api.routes.websocket import router as websocket_router

api_router = APIRouter()

# Health check lives at root (always reachable)
api_router.include_router(health_router)

# API endpoints under /api/v1
api_router.include_router(events_router)
api_router.include_router(ingestion_router)
api_router.include_router(dashboard_router)
api_router.include_router(alerts_router)
api_router.include_router(websocket_router)
api_router.include_router(demo_router)
