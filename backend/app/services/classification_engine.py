"""
Thermal event classification engine.

Classifies a thermal event into one of the following categories
using a deterministic rule-based approach driven by real evidence:

    INDUSTRIAL_THERMAL       — heat from refinery / power plant / factory
    WILDFIRE                 — uncontrolled fire spreading through vegetation
    AGRICULTURAL_BURNING     — crop/field burning
    MINING_ACTIVITY          — heat signatures from mining operations
    OTHER_THERMAL_SOURCE     — identifiable but non-standard thermal source
    UNKNOWN                  — insufficient evidence

The architecture is designed so the rule engine can be replaced by
an ML model later — the interface (inputs / outputs) stays the same.

Inputs:
    context  — output of context_service.build_event_context()
    history  — output of history_service.calculate_history()
    event    — ThermalEvent ORM object (provides frp, brightness, confidence, etc.)

Outputs:
    {
        "classification": EventClassification,  # enum value
        "confidence": float,                    # 0.0–1.0
        "evidence": {                           # what drove the decision
            "rules_fired": [...],
            "primary_factor": str,
            ...
        }
    }

Rules are ordered by specificity (most specific first).
Each rule contributes to a score for each class.
The class with the highest score wins.
"""

import logging
from typing import Any

from app.models.thermal_event import EventClassification, ThermalEvent

logger = logging.getLogger(__name__)

# Distance thresholds (km)
CLOSE_FACILITY_KM = 2.0      # Facility is "close" at under 2 km
NEARBY_FACILITY_KM = 5.0     # Facility is "nearby" at under 5 km

# FRP thresholds (MW)
FRP_HIGH = 100.0             # High FRP for classification context
FRP_VERY_HIGH = 300.0        # Very high FRP

# Industrial facility types that strongly suggest INDUSTRIAL_THERMAL
INDUSTRIAL_TYPES = {"REFINERY", "PETROCHEMICAL", "LNG", "FACTORY", "POWER_PLANT", "STORAGE", "WATER_WORKS", "WASTE_TREATMENT", "INDUSTRIAL"}
MINING_TYPES = {"MINE"}

# Land-cover classes associated with wildfire
WILDFIRE_LAND_COVERS = {"FOREST", "GRASSLAND", "CROPLAND", "BARE_LAND"}
# Land-cover classes associated with agricultural burning
AGRI_LAND_COVERS = {"CROPLAND"}
# Land-cover classes associated with industrial activity
INDUSTRIAL_LAND_COVERS = {"BUILT_UP"}


def _nearest_facility_distance(context: dict) -> float | None:
    """Return distance to nearest facility in km, or None."""
    nearest_km = context.get("nearest_facility_km")
    if nearest_km is not None:
        return float(nearest_km)
    facilities = context.get("nearby_facilities", [])
    if facilities:
        return min(f["distance_km"] for f in facilities)
    return None


def _nearest_facility_type(context: dict) -> str | None:
    """Return facility_type of the nearest facility, or None."""
    nearest = context.get("nearest_facility")
    if nearest:
        return nearest.get("type")
    facilities = context.get("nearby_facilities", [])
    if facilities:
        return min(facilities, key=lambda f: f["distance_km"]).get("type")
    return None


def classify_event(
    event: ThermalEvent,
    context: dict[str, Any],
    history: dict[str, Any],
) -> dict[str, Any]:
    """
    Classify a thermal event using rule-based scoring.

    Returns:
        {
            "classification": str,  # EventClassification value
            "confidence": float,
            "evidence": dict,
        }
    """
    frp = event.frp or 0.0
    brightness = event.brightness or 0.0
    confidence_str = (event.confidence or "").lower().strip()
    land_cover = context.get("land_cover", "UNKNOWN")
    nearby_facilities = context.get("nearby_facilities", [])
    anomaly_ratio = history.get("anomaly_ratio")
    persistence_score = history.get("persistence_score", 0.0)
    has_history = history.get("has_history", False)

    nearest_km = _nearest_facility_distance(context)
    nearest_type = _nearest_facility_type(context)

    # ── Score accumulator for each class ──────────────────────────────────
    # Each rule adds weight to a classification bucket.
    scores: dict[str, float] = {
        "INDUSTRIAL_THERMAL": 0.0,
        "WILDFIRE": 0.0,
        "AGRICULTURAL_BURNING": 0.0,
        "MINING_ACTIVITY": 0.0,
        "OTHER_THERMAL_SOURCE": 0.0,
        "UNKNOWN": 0.1,  # small base weight
    }

    rules_fired: list[str] = []

    # ── Rule 1: Industrial facility very close ─────────────────────────────
    if nearest_km is not None and nearest_type in INDUSTRIAL_TYPES:
        if nearest_km <= CLOSE_FACILITY_KM:
            scores["INDUSTRIAL_THERMAL"] += 4.0
            rules_fired.append(f"industrial_facility_very_close ({nearest_km:.2f}km, {nearest_type})")
        elif nearest_km <= NEARBY_FACILITY_KM:
            scores["INDUSTRIAL_THERMAL"] += 2.0
            rules_fired.append(f"industrial_facility_nearby ({nearest_km:.2f}km, {nearest_type})")

    # ── Rule 2: Mining facility close ─────────────────────────────────────
    if nearest_km is not None and nearest_type in MINING_TYPES:
        if nearest_km <= NEARBY_FACILITY_KM:
            scores["MINING_ACTIVITY"] += 3.0
            scores["INDUSTRIAL_THERMAL"] += 1.0
            rules_fired.append(f"mine_nearby ({nearest_km:.2f}km)")

    # ── Rule 3: Land cover is BUILT_UP ─────────────────────────────────────
    if land_cover == "BUILT_UP":
        scores["INDUSTRIAL_THERMAL"] += 2.5
        rules_fired.append("land_cover=BUILT_UP")

    # ── Rule 4: Land cover suggests wildfire ──────────────────────────────
    if land_cover in ("FOREST", "GRASSLAND") and nearest_km is None:
        scores["WILDFIRE"] += 3.0
        rules_fired.append(f"land_cover={land_cover} with no facility nearby")
    elif land_cover in ("FOREST", "GRASSLAND"):
        scores["WILDFIRE"] += 1.5
        rules_fired.append(f"land_cover={land_cover}")

    # ── Rule 5: Cropland → agricultural burning ───────────────────────────
    if land_cover == "CROPLAND":
        if nearest_km is None or nearest_km > NEARBY_FACILITY_KM:
            scores["AGRICULTURAL_BURNING"] += 3.0
            rules_fired.append("land_cover=CROPLAND without nearby facility")
        else:
            scores["AGRICULTURAL_BURNING"] += 1.0
            scores["INDUSTRIAL_THERMAL"] += 1.0
            rules_fired.append("land_cover=CROPLAND with nearby facility")

    # ── Rule 6: Very high FRP with no industrial context ──────────────────
    if frp > FRP_VERY_HIGH and nearest_km is None:
        scores["WILDFIRE"] += 2.0
        rules_fired.append(f"very_high_frp={frp} without facility")
    elif frp > FRP_VERY_HIGH and nearest_km is not None and nearest_km <= CLOSE_FACILITY_KM:
        # Very high FRP near a facility — industrial
        scores["INDUSTRIAL_THERMAL"] += 2.0
        rules_fired.append(f"very_high_frp={frp} near facility")

    # ── Rule 7: Persistent activity ───────────────────────────────────────
    if persistence_score > 0.3:
        # Persistent hotspot — more likely industrial (industrial burns continuously)
        scores["INDUSTRIAL_THERMAL"] += 1.5
        rules_fired.append(f"persistent_activity (score={persistence_score:.2f})")
    elif persistence_score > 0.1:
        scores["INDUSTRIAL_THERMAL"] += 0.5
        rules_fired.append(f"recurring_activity (score={persistence_score:.2f})")

    # ── Rule 8: Anomaly ratio ─────────────────────────────────────────────
    if anomaly_ratio is not None:
        if anomaly_ratio > 5.0:
            # Extreme anomaly — more likely wildfire or industrial accident
            scores["WILDFIRE"] += 1.5
            scores["INDUSTRIAL_THERMAL"] += 1.0
            rules_fired.append(f"extreme_anomaly_ratio={anomaly_ratio:.2f}")
        elif anomaly_ratio > 2.0:
            scores["WILDFIRE"] += 0.5
            rules_fired.append(f"elevated_anomaly_ratio={anomaly_ratio:.2f}")

    # ── Rule 9: Confidence indicator ──────────────────────────────────────
    if confidence_str in ("high", "nominal"):
        # High satellite confidence — apply a small boost to leading class
        for k in scores:
            if scores[k] == max(scores.values()):
                scores[k] += 0.3
        rules_fired.append(f"high_satellite_confidence={confidence_str}")
    elif confidence_str == "low":
        # Low confidence — push toward UNKNOWN
        scores["UNKNOWN"] += 1.0
        rules_fired.append("low_satellite_confidence")

    # ── Rule 10: Power plant type specifically ────────────────────────────
    if nearest_type == "POWER_PLANT" and nearest_km is not None and nearest_km <= CLOSE_FACILITY_KM:
        scores["INDUSTRIAL_THERMAL"] += 1.0
        scores["MINING_ACTIVITY"] = max(0, scores["MINING_ACTIVITY"] - 0.5)
        rules_fired.append(f"power_plant_nearby ({nearest_km:.2f}km)")

    # ── Rule 11: No evidence at all ───────────────────────────────────────
    if not nearby_facilities and land_cover == "UNKNOWN" and not has_history:
        scores["UNKNOWN"] += 2.0
        rules_fired.append("no_context_available")

    # ── Determine winner ──────────────────────────────────────────────────
    best_class = max(scores, key=lambda k: scores[k])
    best_score = scores[best_class]
    total_score = sum(scores.values())

    # Normalise confidence to [0, 1]
    raw_confidence = best_score / total_score if total_score > 0 else 0.0
    # Apply sigmoid-like shaping to keep confidence realistic
    confidence = min(0.97, max(0.1, raw_confidence))

    # Map to EventClassification enum value
    classification_map = {
        "INDUSTRIAL_THERMAL": EventClassification.INDUSTRIAL_THERMAL,
        "WILDFIRE": EventClassification.WILDFIRE,
        "AGRICULTURAL_BURNING": EventClassification.AGRICULTURAL_BURNING,
        "MINING_ACTIVITY": EventClassification.MINING_ACTIVITY,
        "OTHER_THERMAL_SOURCE": EventClassification.OTHER_THERMAL_SOURCE,
        "UNKNOWN": EventClassification.UNKNOWN,
    }
    classification = classification_map.get(best_class, EventClassification.UNKNOWN)

    logger.debug(
        "Event %s classified as %s (confidence=%.2f) — rules: %s",
        event.id,
        classification.value,
        confidence,
        "; ".join(rules_fired) or "none",
    )

    return {
        "classification": classification,
        "confidence": round(confidence, 4),
        "evidence": {
            "rules_fired": rules_fired,
            "primary_factor": rules_fired[0] if rules_fired else "no_evidence",
            "scores": {k: round(v, 3) for k, v in scores.items()},
            "nearest_facility_km": nearest_km,
            "nearest_facility_type": nearest_type,
            "land_cover": land_cover,
            "frp": frp,
            "anomaly_ratio": anomaly_ratio,
            "persistence_score": persistence_score,
        },
    }
