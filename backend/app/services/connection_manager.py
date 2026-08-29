"""
WebSocket connection manager.

Manages active WebSocket connections and broadcasts event notifications
when new thermal events are ingested and/or analysed.

Design:
  - In-process (no Redis / message broker needed for hackathon scale).
  - Singleton instance `manager` imported by both routes and services.
  - Broadcast is fire-and-forget — disconnected clients are silently removed.
  - Works with FastAPI's async WebSocket support.

Broadcast message format:
    {
        "type": "THERMAL_EVENT_ANALYZED",
        "event_id": 123,
        "classification": "INDUSTRIAL_THERMAL",
        "risk_level": "HIGH",
        "risk_score": 86.0,
        "latitude": 12.3456,
        "longitude": 78.9012,
        "frp": 185.0
    }

    OR for new (unanalysed) event:
    {
        "type": "THERMAL_EVENT_NEW",
        "event_id": 456,
        "risk_level": "MODERATE",
        "risk_score": 42.0,
        "latitude": 12.500,
        "longitude": 78.800,
        "frp": 55.0
    }
"""

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections and broadcasts messages.

    Usage:
        manager = ConnectionManager()

        # In a WebSocket route:
        await manager.connect(websocket)

        # From a service:
        await manager.broadcast({"type": "THERMAL_EVENT_ANALYZED", ...})
    """

    def __init__(self) -> None:
        self._active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self._active.append(websocket)
        logger.info(
            "WebSocket client connected — total connections: %d",
            len(self._active),
        )
        # Send initial confirmation
        await websocket.send_json(
            {
                "type": "CONNECTED",
                "message": "ThermaSense live event stream ready",
                "active_connections": len(self._active),
            }
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket."""
        if websocket in self._active:
            self._active.remove(websocket)
        logger.info(
            "WebSocket client disconnected — remaining: %d",
            len(self._active),
        )

    async def broadcast(self, message: dict[str, Any]) -> None:
        """
        Broadcast a JSON message to all connected clients.

        Disconnected clients are silently removed from the pool.
        This is fire-and-forget — it does not block the caller.
        """
        if not self._active:
            return  # no clients, skip serialisation overhead

        disconnected: list[WebSocket] = []
        for ws in list(self._active):
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

        if disconnected:
            logger.debug("Removed %d disconnected WebSocket clients", len(disconnected))

    @property
    def connection_count(self) -> int:
        return len(self._active)


# ── Global singleton ───────────────────────────────────────────────────────
# Import this instance from anywhere in the application:
#   from app.services.connection_manager import manager
manager = ConnectionManager()
