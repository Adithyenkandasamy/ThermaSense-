"""Main analysis orchestrator."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.thermal_event import ThermalEvent
from app.services.ai_agent_service import investigate
from app.services.context_service import build_event_context
from app.services.history_service import calculate_history


async def process_event(db: AsyncSession, event_id: int) -> dict:
    event = await db.get(ThermalEvent, event_id)
    if event is None:
        raise ValueError(f"Event {event_id} not found")

    context = await build_event_context(event)
    history = await calculate_history(event)
    packet = {
        "event": {
            "latitude": event.latitude,
            "longitude": event.longitude,
            "frp": event.frp,
            "brightness": event.brightness,
            "confidence": event.confidence,
        },
        "geographic_context": context,
        "historical_context": history,
        "classification": {"type": "UNKNOWN", "confidence": 0.0},
        "risk": {"score": event.risk_score, "level": event.risk_level.value},
    }
    investigation = await investigate(packet)
    return {"packet": packet, "investigation": investigation}
