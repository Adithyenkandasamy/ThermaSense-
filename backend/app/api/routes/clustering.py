"""
Spatio-Temporal Event Clustering API routes (Phase 10).

Endpoints:
  POST /api/clustering/run    — Trigger clustering of unassigned observations
  GET  /api/clustering/status — Clustering statistics & configuration
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.thermal_event import ThermalEvent
from app.models.thermal_observation import ThermalObservation
from app.services import clustering_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clustering", tags=["clustering"])


# ── Request / Response Schemas ──────────────────────────────────────────

class ClusteringRunRequest(BaseModel):
    """Optional parameters to override clustering thresholds for this run."""

    spatial_threshold_km: Optional[float] = Field(
        None,
        ge=0.1,
        le=500.0,
        description=(
            "Max centroid distance in km to consider an observation part of "
            "an active event. Defaults to the server config value."
        ),
    )
    temporal_threshold_hours: Optional[float] = Field(
        None,
        ge=0.1,
        le=168.0,
        description=(
            "Max time gap in hours between observation and event window boundary. "
            "Defaults to the server config value."
        ),
    )
    observation_ids: Optional[list[str]] = Field(
        None,
        description=(
            "Limit clustering to specific observation UUIDs. "
            "If omitted, all unassigned observations are processed."
        ),
    )


class ClusteringRunResponse(BaseModel):
    """Result summary from a clustering run."""

    observations_processed: int = Field(
        ..., description="Number of unassigned observations that were processed"
    )
    events_created: int = Field(
        ..., description="Number of new ThermalEvents created"
    )
    events_updated: int = Field(
        ..., description="Number of existing ThermalEvents that received new observations"
    )
    spatial_threshold_km: float = Field(
        ..., description="Spatial threshold used (km)"
    )
    temporal_threshold_hours: float = Field(
        ..., description="Temporal threshold used (hours)"
    )


class ClusteringStatusResponse(BaseModel):
    """Current clustering state and configuration."""

    # Configuration
    spatial_threshold_km: float = Field(
        ..., description="Configured spatial threshold (km)"
    )
    temporal_threshold_hours: float = Field(
        ..., description="Configured temporal threshold (hours)"
    )

    # Observation assignment stats
    total_observations: int = Field(
        ..., description="Total observations in database"
    )
    assigned_observations: int = Field(
        ..., description="Observations that have been clustered into an event"
    )
    unassigned_observations: int = Field(
        ..., description="Observations not yet assigned to any event"
    )

    # Event stats
    total_events: int = Field(
        ..., description="Total thermal events in database"
    )
    active_events: int = Field(
        ..., description="Events with status='active'"
    )
    inactive_events: int = Field(
        ..., description="Events with status='inactive'"
    )


# ── Endpoints ───────────────────────────────────────────────────────────


@router.post(
    "/run",
    response_model=ClusteringRunResponse,
    summary="Run spatio-temporal clustering on unassigned observations",
)
async def run_clustering(
    request: ClusteringRunRequest = ClusteringRunRequest(),
    db: AsyncSession = Depends(get_db),
) -> ClusteringRunResponse:
    """
    Cluster all unassigned ThermalObservation records into ThermalEvents.

    For each unassigned observation:
    1. Find the nearest active event within spatial + temporal thresholds.
    2. If found → attach observation to that event and refresh its centroid,
       observation_count, total_frp, max_confidence, and ended_at.
    3. If not found → create a new active ThermalEvent seeded from this
       observation.

    Thresholds can be overridden per-request; defaults come from server config.
    """
    # Parse optional observation UUID list
    obs_uuids: Optional[list[uuid.UUID]] = None
    if request.observation_ids:
        try:
            obs_uuids = [uuid.UUID(oid) for oid in request.observation_ids]
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid observation UUID in list: {exc}",
            )

    try:
        result = await clustering_service.cluster_unassigned_observations(
            db,
            observation_ids=obs_uuids,
            spatial_threshold_km=request.spatial_threshold_km,
            temporal_threshold_hours=request.temporal_threshold_hours,
        )
        await db.commit()
    except Exception as exc:
        logger.error("Clustering run failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Clustering failed: {exc}",
        )

    return ClusteringRunResponse(**result)


@router.get(
    "/status",
    response_model=ClusteringStatusResponse,
    summary="Get clustering statistics and configuration",
)
async def clustering_status(
    db: AsyncSession = Depends(get_db),
) -> ClusteringStatusResponse:
    """
    Return current clustering configuration and database assignment statistics.

    Reports:
    - Configured spatial / temporal thresholds
    - Total, assigned, and unassigned observation counts
    - Total, active, and inactive event counts
    """
    settings = get_settings()

    # Observation counts
    total_obs_res = await db.execute(
        select(func.count(ThermalObservation.id))
    )
    total_obs: int = total_obs_res.scalar_one() or 0

    assigned_obs_res = await db.execute(
        select(func.count(ThermalObservation.id)).where(
            ThermalObservation.event_id.is_not(None)
        )
    )
    assigned_obs: int = assigned_obs_res.scalar_one() or 0

    # Event counts
    total_events_res = await db.execute(
        select(func.count(ThermalEvent.id))
    )
    total_events: int = total_events_res.scalar_one() or 0

    active_events_res = await db.execute(
        select(func.count(ThermalEvent.id)).where(ThermalEvent.status == "active")
    )
    active_events: int = active_events_res.scalar_one() or 0

    return ClusteringStatusResponse(
        spatial_threshold_km=settings.clustering_spatial_threshold_km,
        temporal_threshold_hours=settings.clustering_temporal_threshold_hours,
        total_observations=total_obs,
        assigned_observations=assigned_obs,
        unassigned_observations=total_obs - assigned_obs,
        total_events=total_events,
        active_events=active_events,
        inactive_events=total_events - active_events,
    )
