"""Historical feature calculations for thermal events."""

from app.models.thermal_event import ThermalEvent


async def calculate_history(event: ThermalEvent) -> dict:
    current_frp = event.frp or 0.0
    return {
        "event_id": event.id,
        "detections_7d": 0,
        "detections_30d": 0,
        "detections_90d": 0,
        "active_days": 0,
        "average_frp": 0.0,
        "maximum_frp": current_frp,
        "historical_baseline": 0.0,
        "current_frp": current_frp,
        "anomaly_ratio": 1.0 if current_frp > 0 else 0.0,
        "persistence_score": 0.0,
    }
