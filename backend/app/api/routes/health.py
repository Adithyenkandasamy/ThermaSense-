"""Health check endpoint."""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service health check")
async def health_check() -> dict:
    """
    Returns the overall health of the ThermaSense API.

    No external dependencies are checked in the MVP —
    the endpoint simply confirms the API is reachable.
    """
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "thermasense-api",
        "version": "0.1.0",
    }
