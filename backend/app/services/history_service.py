"""
Historical thermal activity analysis service.

Given a thermal event location, queries the `thermal_events` table
for historical observations at/near the same geographic coordinates.

All values come from real database queries — nothing is hardcoded.

Key metrics calculated:
    detections_7d         — hotspot count in last 7 days within radius
    detections_30d        — hotspot count in last 30 days
    detections_90d        — hotspot count in last 90 days
    active_days           — distinct calendar days with a detection
    average_frp           — mean FRP over the historical window
    maximum_frp           — peak FRP in the historical window
    historical_baseline   — average FRP (same as average_frp; None if no history)
    current_frp           — FRP of this specific event
    anomaly_ratio         — current_frp / historical_baseline (None if no baseline)
    persistence_score     — [0.0–1.0] active_days / max_possible_days

Design:
  - Uses PostGIS ST_DWithin with geography for accurate km-distance filtering.
  - Excludes the current event itself from historical stats.
  - Returns None for baseline/anomaly when there is genuinely no history
    rather than fabricating zeros.
  - The historical window is 90 days by default.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.thermal_event import ThermalEvent

logger = logging.getLogger(__name__)

# Radius around event location to gather historical observations (km)
HISTORY_RADIUS_KM: float = 1.0

# Maximum history lookback in days
HISTORY_WINDOW_DAYS: int = 90


async def calculate_history(
    event: ThermalEvent,
    db: AsyncSession,
    radius_km: float = HISTORY_RADIUS_KM,
) -> dict[str, Any]:
    """
    Calculate historical thermal activity statistics for an event location.

    Args:
        event:     ThermalEvent ORM object.
        db:        Async DB session.
        radius_km: Spatial search radius in km.

    Returns:
        Dict with historical statistics. Values may be None where
        insufficient history exists.
    """
    lat: float = event.latitude
    lon: float = event.longitude
    current_frp: float = event.frp or 0.0
    radius_m: float = radius_km * 1000.0

    now = datetime.now(timezone.utc)
    cutoff_90d = now - timedelta(days=90)
    cutoff_30d = now - timedelta(days=30)
    cutoff_7d  = now - timedelta(days=7)

    # ── Single comprehensive query ─────────────────────────────────────────
    # Fetch all historical events near this location in the last 90 days,
    # excluding the current event itself.
    # We use ST_DWithin with geography for accurate km-radius filtering.
    query = text(
        """
        SELECT
            acq_date,
            frp,
            observed_at,
            created_at
        FROM thermal_events
        WHERE
            id != :event_id
            AND ST_DWithin(
                geom::geography,
                ST_MakePoint(:lon, :lat)::geography,
                :radius_m
            )
            AND (
                observed_at >= :cutoff_90d
                OR (observed_at IS NULL AND created_at >= :cutoff_90d)
            )
        ORDER BY COALESCE(observed_at, created_at) DESC
        """
    )

    try:
        result = await db.execute(
            query,
            {
                "event_id": event.id,
                "lat": lat,
                "lon": lon,
                "radius_m": radius_m,
                "cutoff_90d": cutoff_90d,
            },
        )
        rows = result.fetchall()
    except Exception as exc:
        logger.error("Historical query failed for event %s: %s", event.id, exc)
        rows = []

    # ── Aggregate from rows ────────────────────────────────────────────────
    detections_7d = 0
    detections_30d = 0
    detections_90d = len(rows)

    active_dates: set = set()
    frp_values: list[float] = []

    for row in rows:
        # Determine the effective timestamp for this historical row
        ts = row.observed_at or row.created_at
        if ts and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # Count detections by time window
        if ts:
            if ts >= cutoff_7d:
                detections_7d += 1
            if ts >= cutoff_30d:
                detections_30d += 1

        # Collect active dates
        if row.acq_date:
            active_dates.add(row.acq_date)

        # Collect FRP values (exclude None/zero)
        if row.frp is not None and row.frp > 0:
            frp_values.append(float(row.frp))

    # ── Derived metrics ────────────────────────────────────────────────────
    active_days: int = len(active_dates)

    average_frp: float | None = None
    maximum_frp: float | None = None
    historical_baseline: float | None = None
    anomaly_ratio: float | None = None

    if frp_values:
        average_frp = round(sum(frp_values) / len(frp_values), 2)
        maximum_frp = round(max(frp_values), 2)
        historical_baseline = average_frp  # baseline = mean historical FRP

        if historical_baseline and historical_baseline > 0 and current_frp > 0:
            anomaly_ratio = round(current_frp / historical_baseline, 3)
        elif current_frp > 0:
            # No historical FRP data but current event exists — anomaly ratio undefined
            anomaly_ratio = None

    # Maximum FRP should include the current event if we have no history
    if maximum_frp is None and current_frp > 0:
        maximum_frp = current_frp

    # ── Persistence score ──────────────────────────────────────────────────
    # Fraction of the last 90 days on which a detection was recorded nearby.
    # score = active_days / 90  (capped at 1.0)
    persistence_score: float = min(active_days / 90.0, 1.0) if active_days > 0 else 0.0

    logger.debug(
        "History for event %s: total=%d 7d=%d 30d=%d 90d=%d "
        "active_days=%d avg_frp=%s max_frp=%s anomaly=%.2f",
        event.id,
        detections_90d,
        detections_7d,
        detections_30d,
        detections_90d,
        active_days,
        average_frp,
        maximum_frp,
        anomaly_ratio or 0.0,
    )

    return {
        "event_id": event.id,
        "radius_km": radius_km,
        "detections_7d": detections_7d,
        "detections_30d": detections_30d,
        "detections_90d": detections_90d,
        "active_days": active_days,
        "average_frp": average_frp,
        "maximum_frp": maximum_frp,
        "historical_baseline": historical_baseline,
        "current_frp": current_frp,
        "anomaly_ratio": anomaly_ratio,
        "persistence_score": round(persistence_score, 4),
        "has_history": detections_90d > 0,
    }
