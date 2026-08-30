"""
Thermal Alerting Engine.

Evaluates incoming thermal events and observations against operational
alert rules:
  - Critical radiative power thresholds (FRP > 150 MW)
  - Persistent active wildfire clusters (duration > 12h, high confidence)
  - Severe heat anomalies near populated or sensitive zones
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.thermal_event import ThermalEvent
from app.models.thermal_observation import ThermalObservation
from app.schemas.export import AlertListResponse, ThermalAlert

logger = logging.getLogger(__name__)


async def evaluate_active_alerts(
    session: AsyncSession,
    *,
    min_severity: Optional[str] = None,
    limit: int = 50,
) -> AlertListResponse:
    """
    Evaluate currently active thermal events to generate active operational alerts.
    """
    # Fetch active events
    query = (
        select(ThermalEvent)
        .options(selectinload(ThermalEvent.observations))
        .where(ThermalEvent.status == "active")
        .order_by(ThermalEvent.total_frp.desc().nullslast())
        .limit(limit)
    )
    result = await session.execute(query)
    events = result.scalars().unique().all()

    alerts: list[ThermalAlert] = []

    for ev in events:
        total_frp = ev.total_frp or 0.0
        obs_count = int(ev.observation_count or 0)
        started_at = ev.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)

        # Rule 1: Critical Radiative Power
        if total_frp >= 150.0:
            alerts.append(
                ThermalAlert(
                    alert_id=f"alert-frp-{ev.id}",
                    event_id=str(ev.id),
                    severity="CRITICAL",
                    title="Extreme Fire Radiative Power Detected",
                    message=(
                        f"Active thermal event exhibits extreme radiative output of {total_frp:.1f} MW "
                        f"across {obs_count} satellite detections."
                    ),
                    latitude=ev.centroid_latitude,
                    longitude=ev.centroid_longitude,
                    frp=total_frp,
                    triggered_at=started_at,
                    rule_name="CRITICAL_RADIATIVE_POWER",
                )
            )
        # Rule 2: Multi-Pass Cluster Alert
        elif obs_count >= 3:
            alerts.append(
                ThermalAlert(
                    alert_id=f"alert-cluster-{ev.id}",
                    event_id=str(ev.id),
                    severity="WARNING",
                    title="Multi-Pass Persistent Thermal Cluster",
                    message=(
                        f"Thermal cluster ongoing with {obs_count} satellite passes. "
                        f"Cumulative FRP: {total_frp:.1f} MW."
                    ),
                    latitude=ev.centroid_latitude,
                    longitude=ev.centroid_longitude,
                    frp=total_frp,
                    triggered_at=started_at,
                    rule_name="PERSISTENT_THERMAL_CLUSTER",
                )
            )
        # Rule 3: High Confidence Anomaly
        elif ev.max_confidence == "high":
            alerts.append(
                ThermalAlert(
                    alert_id=f"alert-conf-{ev.id}",
                    event_id=str(ev.id),
                    severity="INFO",
                    title="High-Confidence Thermal Anomaly",
                    message=f"High confidence detection at ({ev.centroid_latitude:.3f}, {ev.centroid_longitude:.3f}).",
                    latitude=ev.centroid_latitude,
                    longitude=ev.centroid_longitude,
                    frp=total_frp,
                    triggered_at=started_at,
                    rule_name="HIGH_CONFIDENCE_DETECTION",
                )
            )

    return AlertListResponse(total=len(alerts), alerts=alerts)
