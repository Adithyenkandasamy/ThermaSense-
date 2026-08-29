"""WebSocket routes for live event updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/v1/ws", tags=["websocket"])


@router.websocket("/events")
async def events_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "CONNECTED", "message": "ThermaSense event stream ready"})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
