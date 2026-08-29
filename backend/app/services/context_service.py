"""Geospatial context builder placeholder for the modular monolith."""

from app.models.thermal_event import ThermalEvent


async def build_event_context(event: ThermalEvent) -> dict:
    return {
        "event_id": event.id,
        "location": {"latitude": event.latitude, "longitude": event.longitude},
        "nearby_facilities": [],
        "land_cover": "UNKNOWN",
    }
