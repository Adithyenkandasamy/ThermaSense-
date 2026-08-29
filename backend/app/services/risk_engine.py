"""
Extended risk assessment engine.

Builds on the existing FRP/brightness risk foundation (classifier.py)
and extends it with:

    - Industrial proximity factor  (nearby facilities → higher risk)
    - Historical anomaly factor    (current >> baseline → higher risk)
    - Persistence factor           (repeated detections → higher risk)
    - Classification confidence    (high confidence → higher risk accuracy)

The result is a risk_score (0–100) and risk_level (LOW/MODERATE/HIGH/EXTREME).

This is the SINGLE authoritative risk calculation for analysis.
The original classifier.py still handles quick risk assignment at
ingestion time (before full context is available). This engine
produces the refined, context-aware risk used in EventAnalysis.
"""

import logging
import math

from app.models.thermal_event import RiskLevel, ThermalEvent

logger = logging.getLogger(__name__)

# Weights for each risk factor (must sum to ~1.0 for interpretability)
W_FRP = 0.35           # Fire radiative power
W_BRIGHTNESS = 0.10   # Brightness temperature
W_PROXIMITY = 0.20    # Industrial proximity
W_ANOMALY = 0.20      # Historical anomaly
W_PERSISTENCE = 0.10  # Persistence score
W_CONFIDENCE = 0.05   # Satellite detection confidence


def _frp_component(frp: float) -> float:
    """
    Log-scale FRP → [0, 60].
    FRP of 0 MW → 0; FRP of 1000 MW → 60.
    """
    if frp <= 0:
        return 0.0
    return min(math.log1p(frp) / math.log1p(1000) * 60, 60)


def _brightness_component(brightness: float) -> float:
    """
    Brightness temperature → [0, 20].
    300 K (background) → 0; 500 K → 20.
    """
    return max(0.0, min((brightness - 300) / 200 * 20, 20)) if brightness > 300 else 0.0


def _confidence_component(confidence_str: str | None) -> float:
    """Satellite confidence → [0, 20]."""
    mapping = {
        "high": 20.0,
        "nominal": 10.0,
        "n": 5.0,       # VIIRS NRT nominal
        "l": 0.0,
        "low": 0.0,
    }
    if confidence_str is None:
        return 5.0
    c = confidence_str.lower().strip()
    if c in mapping:
        return mapping[c]
    try:
        return float(c) * 0.20  # numeric 0–100 → 0–20
    except ValueError:
        return 5.0


def _proximity_component(nearest_facility_km: float | None) -> float:
    """
    Industrial proximity → [0, 25].
    Very close facility (< 0.5 km) → 25; distant (> 15 km) → 0.
    """
    if nearest_facility_km is None:
        return 0.0
    km = nearest_facility_km
    if km <= 0.5:
        return 25.0
    if km <= 2.0:
        return 20.0
    if km <= 5.0:
        return 12.0
    if km <= 10.0:
        return 6.0
    if km <= 15.0:
        return 2.0
    return 0.0


def _anomaly_component(anomaly_ratio: float | None) -> float:
    """
    Historical anomaly ratio → [0, 30].
    anomaly_ratio = current_frp / historical_baseline.
    No history (None) → 5 (small non-zero — unknown is mildly concerning).
    ratio = 1 (normal) → 0; ratio ≥ 10 → 30.
    """
    if anomaly_ratio is None:
        return 5.0  # unknown — slightly elevated concern
    if anomaly_ratio <= 1.0:
        return 0.0
    # log scale: ratio=2→8, ratio=5→20, ratio=10→30
    return min(math.log(anomaly_ratio) / math.log(10) * 30, 30)


def _persistence_component(persistence_score: float) -> float:
    """
    Persistence score [0, 1] → [0, 15].
    Highly persistent = higher cumulative risk.
    """
    return min(persistence_score * 15, 15)


def calculate_risk(
    event: ThermalEvent,
    context: dict,
    history: dict,
    classification_result: dict,
) -> dict:
    """
    Calculate context-aware risk score and level.

    Args:
        event:                 ThermalEvent ORM object.
        context:               Output of build_event_context().
        history:               Output of calculate_history().
        classification_result: Output of classify_event().

    Returns:
        {
            "risk_score": float,   # 0–100
            "risk_level": RiskLevel,
            "components": {...},   # breakdown for evidence/debugging
        }
    """
    frp = event.frp or 0.0
    brightness = event.brightness or 0.0
    confidence_str = event.confidence

    nearest_km = context.get("nearest_facility_km")
    anomaly_ratio = history.get("anomaly_ratio")
    persistence_score = history.get("persistence_score", 0.0)

    # ── Compute individual components ──────────────────────────────────────
    c_frp         = _frp_component(frp)
    c_brightness  = _brightness_component(brightness)
    c_confidence  = _confidence_component(confidence_str)
    c_proximity   = _proximity_component(nearest_km)
    c_anomaly     = _anomaly_component(anomaly_ratio)
    c_persistence = _persistence_component(persistence_score)

    # ── Weighted sum ───────────────────────────────────────────────────────
    # Normalise each component to 0–100 scale first, then weight
    # FRP (0-60 max) + brightness (0-20 max) + confidence (0-20 max) = 100 max base
    # Proximity (0-25 max) + anomaly (0-30 max) + persistence (0-15 max) = 70 max extra
    # Total raw max ≈ 170 — we cap at 100

    raw_score = (
        c_frp
        + c_brightness
        + c_confidence
        + c_proximity
        + c_anomaly
        + c_persistence
    )

    # Scale down from 0-170 to 0-100
    risk_score = round(min(raw_score / 1.70, 100.0), 2)

    # ── Determine risk level ───────────────────────────────────────────────
    if risk_score >= 80:
        level = RiskLevel.EXTREME
    elif risk_score >= 55:
        level = RiskLevel.HIGH
    elif risk_score >= 28:
        level = RiskLevel.MODERATE
    else:
        level = RiskLevel.LOW

    # ── Hard overrides ─────────────────────────────────────────────────────
    # Very high FRP always warrants at least HIGH
    if frp > 500 and level == RiskLevel.MODERATE:
        level = RiskLevel.HIGH
    # Industrial event near facility with anomalous reading is always HIGH+
    if (
        classification_result.get("classification") is not None
        and str(classification_result["classification"].value
                if hasattr(classification_result["classification"], "value")
                else classification_result["classification"]) == "INDUSTRIAL_THERMAL"
        and nearest_km is not None
        and nearest_km <= 2.0
        and anomaly_ratio is not None
        and anomaly_ratio > 3.0
        and level == RiskLevel.MODERATE
    ):
        level = RiskLevel.HIGH

    logger.debug(
        "Risk for event %s: score=%.1f level=%s frp_c=%.1f prox_c=%.1f anom_c=%.1f",
        event.id, risk_score, level.value,
        c_frp, c_proximity, c_anomaly,
    )

    return {
        "risk_score": risk_score,
        "risk_level": level,
        "components": {
            "frp_component": round(c_frp, 2),
            "brightness_component": round(c_brightness, 2),
            "confidence_component": round(c_confidence, 2),
            "proximity_component": round(c_proximity, 2),
            "anomaly_component": round(c_anomaly, 2),
            "persistence_component": round(c_persistence, 2),
        },
    }
