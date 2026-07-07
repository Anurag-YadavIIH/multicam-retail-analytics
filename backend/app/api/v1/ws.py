"""WebSocket endpoints. Token is passed as a query param (?token=...).

Channels:
  /ws/detections/{camera_id}  live boxes + track ids
  /ws/alerts                  alert stream
  /ws/analytics               live snapshot stream
"""

import jwt as pyjwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from backend.app.core.security import decode_token
from backend.app.services.ws_manager import ws_manager

router = APIRouter(tags=["websocket"])


def _authorized(token: str | None, camera_id: int | None = None) -> bool:
    if not token:
        return False
    try:
        payload = decode_token(token)
    except pyjwt.PyJWTError:
        return False
    if payload.get("type") == "access":
        return True
    # a create_stream_token() token also works, but only for its own camera's channel
    return (
        camera_id is not None
        and payload.get("type") == "stream"
        and payload.get("camera_id") == camera_id
    )


async def _serve(ws: WebSocket, channel: str, camera_id: int | None = None) -> None:
    if not _authorized(ws.query_params.get("token"), camera_id):
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await ws_manager.connect(ws, channel)
    try:
        while True:
            await ws.receive_text()  # keepalive pings from client
    except WebSocketDisconnect:
        await ws_manager.disconnect(ws, channel)


@router.websocket("/ws/detections/{camera_id}")
async def ws_detections(ws: WebSocket, camera_id: int) -> None:
    await _serve(ws, f"detections:{camera_id}", camera_id)


@router.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket) -> None:
    await _serve(ws, "alerts")


@router.websocket("/ws/analytics")
async def ws_analytics(ws: WebSocket) -> None:
    await _serve(ws, "analytics")
