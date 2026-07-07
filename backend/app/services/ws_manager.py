"""In-process WebSocket fan-out with per-channel subscriptions.

Channels: detections:<camera_id>, alerts, analytics
"""

import asyncio
import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class WSManager:
    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, channel: str) -> None:
        await ws.accept()
        async with self._lock:
            self._channels[channel].add(ws)

    async def disconnect(self, ws: WebSocket, channel: str) -> None:
        async with self._lock:
            self._channels[channel].discard(ws)

    async def broadcast(self, channel: str, message: dict[str, Any]) -> None:
        data = json.dumps(message, default=str)
        async with self._lock:
            sockets = list(self._channels.get(channel, ()))
        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._channels[channel].discard(ws)


ws_manager = WSManager()
