"""WebSocket routes for live event updates."""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.connection_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ws", tags=["websocket"])


@router.websocket("/events")
async def events_websocket(websocket: WebSocket) -> None:
    """
    Live event stream WebSocket endpoint.

    On connect: sends CONNECTED message.
    When new events are ingested/analysed: broadcasts THERMAL_EVENT_ANALYZED.

    The connection is kept alive by the keep-alive loop.
    Client can send any text to keep the connection alive (ping).
    """
    await manager.connect(websocket)
    try:
        while True:
            # Wait for client messages (ping/pong, keep-alive)
            # This also detects disconnect
            data = await websocket.receive_text()
            # Echo ping back as pong
            if data.strip().lower() in ("ping", "keepalive"):
                await websocket.send_json({"type": "PONG"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)
        manager.disconnect(websocket)
