"""
Investigation packet builder.

Assembles a complete, structured evidence packet from all upstream
services (context, history, classification, risk) and formats it
for both storage in EventAnalysis and for sending to the AI.

CRITICAL: Every value in the packet comes from the backend.
The AI must NOT be asked to invent facilities, distances, land-cover,
FRP values, anomaly ratios, or any other factual data.

The packet is the single source of truth for one event's analysis.
"""

from typing import Any

from app.models.thermal_event import ThermalEvent


def build_investigation_packet(
    event: ThermalEvent,
    context: dict[str, Any],
    history: dict[str, Any],
    classification_result: dict[str, Any],
    risk_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Assemble the complete investigation packet.

    Args:
        event:                 ThermalEvent ORM object.
        context:               From build_event_context().
        history:               From calculate_history().
        classification_result: From classify_event().
        risk_result:           From calculate_risk().

    Returns:
        Structured investigation packet dict.
    """
    classification = classification_result.get("classification")
    classification_str = (
        classification.value
        if hasattr(classification, "value")
        else str(classification)
    )
    risk_level = risk_result.get("risk_level")
    risk_level_str = (
        risk_level.value
        if hasattr(risk_level, "value")
        else str(risk_level)
    )

    return {
        "event": {
            "id": event.id,
            "latitude": event.latitude,
            "longitude": event.longitude,
            "acq_date": str(event.acq_date),
            "acq_time": event.acq_time,
            "frp": event.frp,
            "brightness": event.brightness,
            "confidence": event.confidence,
            "satellite": event.satellite,
            "instrument": event.instrument,
            "daynight": event.daynight,
            "source": event.source,
        },
        "geographic_context": {
            "land_cover": context.get("land_cover", "UNKNOWN"),
            "search_radius_km": context.get("radius_km", 10.0),
            "nearby_facilities": context.get("nearby_facilities", []),
            "nearest_facility": context.get("nearest_facility"),
            "nearest_facility_km": context.get("nearest_facility_km"),
            "facility_count": len(context.get("nearby_facilities", [])),
        },
        "historical_context": {
            "radius_km": history.get("radius_km", 1.0),
            "detections_7d": history.get("detections_7d", 0),
            "detections_30d": history.get("detections_30d", 0),
            "detections_90d": history.get("detections_90d", 0),
            "active_days": history.get("active_days", 0),
            "average_frp": history.get("average_frp"),
            "maximum_frp": history.get("maximum_frp"),
            "historical_baseline": history.get("historical_baseline"),
            "current_frp": history.get("current_frp"),
            "anomaly_ratio": history.get("anomaly_ratio"),
            "persistence_score": history.get("persistence_score", 0.0),
            "has_history": history.get("has_history", False),
        },
        "classification": {
            "type": classification_str,
            "confidence": classification_result.get("confidence", 0.0),
            "primary_factor": classification_result.get("evidence", {}).get("primary_factor", "unknown"),
            "rules_fired": classification_result.get("evidence", {}).get("rules_fired", []),
        },
        "risk": {
            "score": risk_result.get("risk_score", 0.0),
            "level": risk_level_str,
            "components": risk_result.get("components", {}),
        },
        "engine_version": "v2.0-context-aware",
    }
