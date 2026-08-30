"""
Spatio-Temporal Event Clustering Service.

Responsible for clustering incoming or unassigned ThermalObservation records
into logical ThermalEvent entities based on configurable spatial (Haversine distance)
and temporal proximity thresholds.
"""

import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.thermal_event import ThermalEvent
from app.models.thermal_observation import ThermalObservation
from app.repositories import event_repository

logger = logging.getLogger(__name__)

# Earth radius in kilometers
EARTH_RADIUS_KM = 6371.0

# Confidence ranking
CONFIDENCE_RANKS = {
    "high": 3,
    "nominal": 2,
    "low": 1,
}


def haversine_distance_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate the great circle distance between two points on Earth in kilometers.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


def get_highest_confidence(confidences: Sequence[Optional[str]]) -> Optional[str]:
    """Determine the highest confidence level in a set of confidence strings."""
    best_rank = 0
    best_conf = None
    for c in confidences:
        if not c:
            continue
        rank = CONFIDENCE_RANKS.get(c.lower(), 0)
        if rank > best_rank:
            best_rank = rank
            best_conf = c.lower()
    return best_conf


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def recalculate_event_aggregates(event: ThermalEvent) -> None:
    """
    Recalculate centroid, timestamps, FRP, and counts for a ThermalEvent
    from its in-memory list of linked observations.
    """
    observations = event.observations or []
    if not observations:
        event.observation_count = 0
        event.total_frp = 0.0
        return

    count = len(observations)
    event.observation_count = float(count)
    event.centroid_latitude = sum(o.latitude for o in observations) / count
    event.centroid_longitude = sum(o.longitude for o in observations) / count

    # Timestamps
    datetimes = [o.acquisition_datetime for o in observations]
    event.started_at = min(datetimes)
    event.ended_at = max(datetimes) if count > 1 else datetimes[0]

    # FRP
    frp_vals = [o.frp for o in observations if o.frp is not None]
    event.total_frp = sum(frp_vals) if frp_vals else 0.0

    # Max confidence
    event.max_confidence = get_highest_confidence(
        [o.confidence for o in observations]
    )


async def cluster_unassigned_observations(
    session: AsyncSession,
    *,
    observation_ids: Optional[list[uuid.UUID]] = None,
    spatial_threshold_km: Optional[float] = None,
    temporal_threshold_hours: Optional[float] = None,
) -> dict:
    """
    Cluster unassigned thermal observations into active events.

    Args:
        session: Async database session.
        observation_ids: Optional list of specific observation UUIDs to cluster.
                         If omitted, fetches all unassigned observations.
        spatial_threshold_km: Max distance in km (defaults to config setting).
        temporal_threshold_hours: Max time gap in hours (defaults to config setting).

    Returns:
        Summary dict with counts of clustered observations, events created, and events updated.
    """
    settings = get_settings()
    spatial_thresh = (
        spatial_threshold_km
        if spatial_threshold_km is not None
        else settings.clustering_spatial_threshold_km
    )
    temporal_thresh_hrs = (
        temporal_threshold_hours
        if temporal_threshold_hours is not None
        else settings.clustering_temporal_threshold_hours
    )
    temporal_thresh_secs = temporal_thresh_hrs * 3600.0

    # 1. Fetch unassigned observations ordered chronologically
    query = (
        select(ThermalObservation)
        .where(ThermalObservation.event_id.is_(None))
        .order_by(ThermalObservation.acquisition_datetime.asc())
    )
    if observation_ids:
        query = query.where(ThermalObservation.id.in_(observation_ids))

    obs_result = await session.execute(query)
    unassigned_obs = obs_result.scalars().all()

    if not unassigned_obs:
        return {
            "observations_processed": 0,
            "events_created": 0,
            "events_updated": 0,
            "spatial_threshold_km": spatial_thresh,
            "temporal_threshold_hours": temporal_thresh_hrs,
        }

    # 2. Fetch all active events with their observations preloaded
    events_result = await session.execute(
        select(ThermalEvent)
        .options(selectinload(ThermalEvent.observations))
        .execution_options(populate_existing=True)
        .where(ThermalEvent.status == "active")
    )
    active_events = list(events_result.scalars().unique().all())

    events_created = 0
    events_updated_set = set()

    # 3. Process each observation sequentially
    for obs in unassigned_obs:
        best_event = None
        best_distance = float("inf")

        for event in active_events:
            # Check temporal compatibility with event window
            # Window covers [event.started_at, event.ended_at or event.started_at]
            t_start = _ensure_utc(event.started_at)
            t_end = _ensure_utc(event.ended_at or event.started_at)
            obs_dt = _ensure_utc(obs.acquisition_datetime)

            # Time difference to the closest boundary of the event window
            if obs_dt < t_start:
                time_diff_sec = (t_start - obs_dt).total_seconds()
            elif obs_dt > t_end:
                time_diff_sec = (obs_dt - t_end).total_seconds()
            else:
                time_diff_sec = 0.0

            if time_diff_sec > temporal_thresh_secs:
                continue

            # Check spatial compatibility (Haversine distance to event centroid)
            dist_km = haversine_distance_km(
                obs.latitude,
                obs.longitude,
                event.centroid_latitude,
                event.centroid_longitude,
            )

            if dist_km <= spatial_thresh and dist_km < best_distance:
                best_distance = dist_km
                best_event = event

        if best_event is not None:
            # Attach to existing active event
            obs.event_id = best_event.id
            if best_event.observations is None:
                best_event.observations = []
            best_event.observations.append(obs)
            recalculate_event_aggregates(best_event)
            events_updated_set.add(best_event.id)
        else:
            # Create a new active ThermalEvent
            new_event_id = uuid.uuid4()
            new_event = ThermalEvent(
                id=new_event_id,
                status="active",
                centroid_latitude=obs.latitude,
                centroid_longitude=obs.longitude,
                started_at=obs.acquisition_datetime,
                ended_at=obs.acquisition_datetime,
                total_frp=obs.frp or 0.0,
                max_confidence=obs.confidence.lower() if obs.confidence else None,
                observation_count=1.0,
                description=f"Thermal anomaly detected by {obs.satellite} ({obs.instrument})",
            )
            session.add(new_event)
            obs.event_id = new_event_id
            new_event.observations = [obs]
            active_events.append(new_event)
            events_created += 1

    await session.flush()
    logger.info(
        "Clustering complete: %d observations processed, %d events created, %d events updated",
        len(unassigned_obs),
        events_created,
        len(events_updated_set),
    )

    return {
        "observations_processed": len(unassigned_obs),
        "events_created": events_created,
        "events_updated": len(events_updated_set),
        "spatial_threshold_km": spatial_thresh,
        "temporal_threshold_hours": temporal_thresh_hrs,
    }
