"""Health check endpoint."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service health check")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Returns the overall health of the service.

    Checks:
    - API is reachable
    - Database connection is alive
    - PostGIS extension is installed
    """
    db_status = "ok"
    postgis_version: str | None = None
    db_error: str | None = None

    try:
        # Verify DB connectivity AND PostGIS in one query
        result = await db.execute(text("SELECT PostGIS_Lib_Version()"))
        postgis_version = result.scalar_one()
    except Exception as exc:
        db_status = "error"
        db_error = str(exc)

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "thermasense-api",
        "version": "0.1.0",
        "checks": {
            "database": db_status,
            "postgis_version": postgis_version,
            "database_error": db_error,
        },
    }
