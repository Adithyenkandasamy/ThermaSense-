"""
Automated Attribution & Cause Classification Engine.

Fuses:
  - Satellite Telemetry (FRP, brightness, day/night pass, duration, cluster size)
  - OpenStreetMap Geospatial Context (forests, farmlands, industrial facilities, gas flares)
  - Open-Meteo Weather Conditions (temperature, relative humidity, wind speed, precipitation)

Produces transparent, structured attribution reports with evidence factors,
individual cause probabilities, and reasoning summaries.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.thermal_event import ThermalEvent
from app.models.thermal_observation import ThermalObservation
from app.repositories import observation_repository
from app.schemas.attribution import (
    AttributionResult,
    CauseScore,
    CauseType,
    EvidenceItem,
)
from app.services import event_service, geospatial_service, weather_service
from app.services.geospatial_service import GeospatialContext
from app.schemas.weather import WeatherContext

logger = logging.getLogger(__name__)

ALL_CAUSES: list[CauseType] = [
    "vegetation_fire",
    "agricultural_burning",
    "industrial_heat",
    "gas_flare",
    "volcanic_activity",
]

# Minimum score threshold needed to classify as a known cause rather than 'unknown'
MIN_CLASSIFICATION_THRESHOLD = 35.0


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _evaluate_evidence_and_scores(
    *,
    latitude: float,
    longitude: float,
    started_at: datetime,
    ended_at: Optional[datetime],
    total_frp: float,
    max_frp: float,
    observation_count: int,
    brightness: Optional[float],
    bright_ti4: Optional[float],
    day_count: int,
    night_count: int,
    geo_ctx: Optional[GeospatialContext],
    weather_ctx: Optional[WeatherContext],
) -> tuple[dict[CauseType, float], list[EvidenceItem]]:
    """
    Transparent rule-based scoring function.
    Evaluates satellite, geospatial, and weather factors.
    """
    scores: dict[CauseType, float] = {
        "vegetation_fire": 5.0,
        "agricultural_burning": 5.0,
        "industrial_heat": 5.0,
        "gas_flare": 5.0,
        "volcanic_activity": 0.0,
    }
    evidence: list[EvidenceItem] = []

    dt_start = _ensure_utc(started_at)
    dt_end = _ensure_utc(ended_at)
    duration_hours = 0.0
    if dt_start and dt_end:
        duration_hours = max(
            0.0,
            (dt_end - dt_start).total_seconds() / 3600.0,
        )

    # ── 1. Geospatial Rules ───────────────────────────────────────
    if geo_ctx:
        # Check industrial facilities
        min_ind_dist = min([f.distance_m for f in geo_ctx.industrial], default=None)
        # Check for explicit gas flares in tags
        gas_flare_features = [
            f for f in geo_ctx.industrial
            if f.tags.get("man_made") == "flare" or "flare" in (f.name or "").lower()
        ]
        min_flare_dist = min([f.distance_m for f in gas_flare_features], default=None)

        if min_flare_dist is not None and min_flare_dist <= 500.0:
            scores["gas_flare"] += 60.0
            evidence.append(
                EvidenceItem(
                    factor="Gas Flare Infrastructure Proximity",
                    value=f"{min_flare_dist:.0f}m from active gas flare stack",
                    impact="supports",
                    source="geospatial",
                    supports_cause="gas_flare",
                )
            )
        elif min_ind_dist is not None:
            if min_ind_dist <= 400.0:
                scores["industrial_heat"] += 45.0
                scores["gas_flare"] += 25.0
                evidence.append(
                    EvidenceItem(
                        factor="Industrial Facility Proximity",
                        value=f"{min_ind_dist:.0f}m from registered industrial/manufacturing facility",
                        impact="supports",
                        source="geospatial",
                        supports_cause="industrial_heat",
                    )
                )
            elif min_ind_dist <= 1200.0:
                scores["industrial_heat"] += 20.0
                evidence.append(
                    EvidenceItem(
                        factor="Industrial Buffer Zone",
                        value=f"{min_ind_dist:.0f}m from industrial zone",
                        impact="supports",
                        source="geospatial",
                        supports_cause="industrial_heat",
                    )
                )

        # Check forest & vegetative cover
        min_for_dist = min([f.distance_m for f in geo_ctx.forests], default=None)
        if min_for_dist is not None:
            if min_for_dist <= 300.0:
                scores["vegetation_fire"] += 45.0
                evidence.append(
                    EvidenceItem(
                        factor="Forest / Woodland Proximity",
                        value=f"{min_for_dist:.0f}m from forest/woodland canopy",
                        impact="supports",
                        source="geospatial",
                        supports_cause="vegetation_fire",
                    )
                )
            elif min_for_dist <= 1200.0:
                scores["vegetation_fire"] += 25.0
                evidence.append(
                    EvidenceItem(
                        factor="Vegetation Buffer Proximity",
                        value=f"{min_for_dist:.0f}m from forest boundary",
                        impact="supports",
                        source="geospatial",
                        supports_cause="vegetation_fire",
                    )
                )

        # Check agricultural farmlands
        min_agr_dist = min([f.distance_m for f in geo_ctx.croplands], default=None)
        if min_agr_dist is not None:
            if min_agr_dist <= 300.0:
                scores["agricultural_burning"] += 40.0
                evidence.append(
                    EvidenceItem(
                        factor="Cropland / Farmland Proximity",
                        value=f"{min_agr_dist:.0f}m from agricultural farmland parcel",
                        impact="supports",
                        source="geospatial",
                        supports_cause="agricultural_burning",
                    )
                )
            elif min_agr_dist <= 1000.0:
                scores["agricultural_burning"] += 20.0
                evidence.append(
                    EvidenceItem(
                        factor="Agricultural Zone Buffer",
                        value=f"{min_agr_dist:.0f}m from farmland",
                        impact="supports",
                        source="geospatial",
                        supports_cause="agricultural_burning",
                    )
                )

    # ── 2. Satellite Telemetry Rules ─────────────────────────────
    # Fire Radiative Power (FRP)
    if max_frp >= 100.0:
        scores["vegetation_fire"] += 35.0
        scores["agricultural_burning"] -= 15.0
        evidence.append(
            EvidenceItem(
                factor="High Radiative Intensity",
                value=f"Peak FRP of {max_frp:.1f} MW",
                impact="supports",
                source="satellite",
                supports_cause="vegetation_fire",
            )
        )
    elif max_frp >= 50.0:
        scores["vegetation_fire"] += 20.0
        evidence.append(
            EvidenceItem(
                factor="Substantial Fire Radiative Power",
                value=f"Peak FRP of {max_frp:.1f} MW",
                impact="supports",
                source="satellite",
                supports_cause="vegetation_fire",
            )
        )
    elif 5.0 <= max_frp <= 35.0:
        scores["agricultural_burning"] += 20.0
        scores["gas_flare"] += 15.0
        evidence.append(
            EvidenceItem(
                factor="Moderate Radiative Profile",
                value=f"Peak FRP of {max_frp:.1f} MW typical of open stubble/flaring",
                impact="supports",
                source="satellite",
                supports_cause="agricultural_burning",
            )
        )

    # Thermal Brightness
    eff_ti4 = bright_ti4 or brightness
    if eff_ti4 and eff_ti4 >= 340.0:
        scores["gas_flare"] += 25.0
        scores["vegetation_fire"] += 15.0
        evidence.append(
            EvidenceItem(
                factor="Elevated Brightness Temperature (T4)",
                value=f"{eff_ti4:.1f} K",
                impact="supports",
                source="satellite",
                supports_cause="gas_flare",
            )
        )

    # Day / Night Pass Behavior
    if day_count > 0 and night_count > 0:
        scores["vegetation_fire"] += 25.0
        scores["industrial_heat"] += 15.0
        scores["agricultural_burning"] -= 15.0
        evidence.append(
            EvidenceItem(
                factor="Day & Night Continuous Thermal Persistence",
                value=f"{observation_count} detections across both Day ({day_count}) and Night ({night_count})",
                impact="supports",
                source="satellite",
                supports_cause="vegetation_fire",
            )
        )
    elif night_count > 0 and day_count == 0:
        scores["industrial_heat"] += 25.0
        scores["gas_flare"] += 20.0
        scores["agricultural_burning"] -= 20.0
        evidence.append(
            EvidenceItem(
                factor="Nighttime-Only Detection",
                value="Nighttime acquisition without corresponding daylight fire front",
                impact="supports",
                source="satellite",
                supports_cause="industrial_heat",
            )
        )
    elif day_count > 0 and night_count == 0 and duration_hours <= 6.0:
        scores["agricultural_burning"] += 20.0
        evidence.append(
            EvidenceItem(
                factor="Daytime Short-Duration Burn",
                value=f"Daytime pass with duration {duration_hours:.1f}h",
                impact="supports",
                source="satellite",
                supports_cause="agricultural_burning",
            )
        )

    # Multi-observation cluster spread
    if observation_count >= 4:
        scores["vegetation_fire"] += 15.0

    # ── 3. Weather Context Rules ─────────────────────────────────
    if weather_ctx:
        rh = weather_ctx.relative_humidity
        wind = weather_ctx.wind_speed

        if rh is not None and rh < 25.0 and wind is not None and wind > 15.0:
            scores["vegetation_fire"] += 25.0
            evidence.append(
                EvidenceItem(
                    factor="Severe Fire Weather Conditions",
                    value=f"Low relative humidity ({rh:.0f}%) and wind speed ({wind:.1f} km/h)",
                    impact="supports",
                    source="weather",
                    supports_cause="vegetation_fire",
                )
            )
        elif rh is not None and rh > 70.0:
            scores["vegetation_fire"] -= 15.0
            evidence.append(
                EvidenceItem(
                    factor="High Ambient Humidity",
                    value=f"Relative humidity {rh:.0f}% dampening wildfire spread risk",
                    impact="contradicts",
                    source="weather",
                    supports_cause="vegetation_fire",
                )
            )

    return scores, evidence


def _compile_attribution_result(
    *,
    entity_id: str,
    entity_type: str,
    scores: dict[CauseType, float],
    evidence: list[EvidenceItem],
) -> AttributionResult:
    """Compile scores and evidence into the final AttributionResult."""
    # Ensure all scores non-negative
    cleaned_scores = {k: max(0.0, v) for k, v in scores.items()}
    total_points = sum(cleaned_scores.values()) or 1.0

    # Sort causes by raw score
    sorted_causes = sorted(cleaned_scores.items(), key=lambda x: x[1], reverse=True)
    top_cause, top_score = sorted_causes[0]
    second_cause, second_score = sorted_causes[1] if len(sorted_causes) > 1 else (None, 0.0)

    # If top score is below threshold or lacks sufficient distinguishing evidence -> unknown
    if top_score < MIN_CLASSIFICATION_THRESHOLD:
        primary_cause: CauseType = "unknown"
        confidence = 0.20
        summary = (
            f"Thermal anomaly at {entity_id} classified as unknown due to insufficient "
            f"conclusive evidence (highest cause score: {top_score:.1f} points)."
        )
    else:
        primary_cause = top_cause
        # Compute normalized confidence (0.50 to 0.95)
        margin = max(0.0, top_score - second_score)
        norm_ratio = top_score / total_points
        calc_conf = 0.45 + (norm_ratio * 0.35) + min(0.18, margin * 0.005)
        confidence = round(min(0.96, max(0.50, calc_conf)), 2)
        summary = (
            f"Classified as {primary_cause.replace('_', ' ')} with {int(confidence * 100)}% "
            f"confidence based on {len(evidence)} multi-source evidence markers."
        )

    # Compute normalized probability distribution across causes
    possible_causes = [
        CauseScore(
            cause=cause,
            score=round(raw_score, 1),
            normalized_score=round(raw_score / total_points, 3),
        )
        for cause, raw_score in sorted_causes
    ]

    return AttributionResult(
        primary_cause=primary_cause,
        confidence=confidence,
        possible_causes=possible_causes,
        evidence=evidence,
        reasoning_summary=summary,
        entity_type="event" if entity_type == "event" else "observation",
        entity_id=entity_id,
        classified_at=datetime.now(timezone.utc),
    )


async def classify_event(
    session: AsyncSession,
    event_id: uuid.UUID,
) -> Optional[AttributionResult]:
    """
    Perform cause attribution for a clustered ThermalEvent.
    """
    event_data = await event_service.get_event_summary_for_attribution(
        session, event_id
    )
    if event_data is None:
        return None

    event: ThermalEvent = event_data["event"]
    observations: list[ThermalObservation] = event_data["observations"]
    summary: dict = event_data["summary"]

    lat = event.centroid_latitude
    lon = event.centroid_longitude
    started_at = event.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    # Fetch context
    weather_ctx = None
    try:
        weather_ctx = await weather_service.fetch_weather(
            latitude=lat,
            longitude=lon,
            acquisition_datetime=started_at,
        )
    except Exception as exc:
        logger.warning("Weather context error for event %s: %s", event_id, exc)

    geo_ctx = None
    try:
        geo_ctx = await geospatial_service.fetch_nearby_context(
            latitude=lat,
            longitude=lon,
            radius_m=3000.0,
        )
    except Exception as exc:
        logger.warning("Geospatial context error for event %s: %s", event_id, exc)

    # Evaluate rules
    scores, evidence = _evaluate_evidence_and_scores(
        latitude=lat,
        longitude=lon,
        started_at=started_at,
        ended_at=event.ended_at,
        total_frp=summary["total_frp"],
        max_frp=summary["max_frp"],
        observation_count=summary["observation_count"],
        brightness=summary.get("max_brightness"),
        bright_ti4=None,
        day_count=summary["daynight_counts"]["day"],
        night_count=summary["daynight_counts"]["night"],
        geo_ctx=geo_ctx,
        weather_ctx=weather_ctx,
    )

    return _compile_attribution_result(
        entity_id=str(event.id),
        entity_type="event",
        scores=scores,
        evidence=evidence,
    )


async def classify_observation(
    session: AsyncSession,
    observation_id: uuid.UUID,
) -> Optional[AttributionResult]:
    """
    Perform cause attribution for a single standalone ThermalObservation.
    """
    obs = await observation_repository.get_observation_by_id(session, observation_id)
    if obs is None:
        return None

    dt = obs.acquisition_datetime
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Fetch context
    weather_ctx = None
    try:
        weather_ctx = await weather_service.fetch_weather(
            latitude=obs.latitude,
            longitude=obs.longitude,
            acquisition_datetime=dt,
        )
    except Exception as exc:
        logger.warning("Weather context error for observation %s: %s", observation_id, exc)

    geo_ctx = None
    try:
        geo_ctx = await geospatial_service.fetch_nearby_context(
            latitude=obs.latitude,
            longitude=obs.longitude,
            radius_m=2000.0,
        )
    except Exception as exc:
        logger.warning("Geospatial context error for observation %s: %s", observation_id, exc)

    day_count = 1 if obs.daynight == "D" else 0
    night_count = 1 if obs.daynight == "N" else 0

    scores, evidence = _evaluate_evidence_and_scores(
        latitude=obs.latitude,
        longitude=obs.longitude,
        started_at=dt,
        ended_at=dt,
        total_frp=obs.frp or 0.0,
        max_frp=obs.frp or 0.0,
        observation_count=1,
        brightness=obs.brightness,
        bright_ti4=obs.bright_ti4,
        day_count=day_count,
        night_count=night_count,
        geo_ctx=geo_ctx,
        weather_ctx=weather_ctx,
    )

    return _compile_attribution_result(
        entity_id=str(obs.id),
        entity_type="observation",
        scores=scores,
        evidence=evidence,
    )
