"""
AsynxDL — WebSocket Progress Route
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Endpoint /ws/progress untuk push real-time progress ke UI.
"""

import asyncio
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from backend.api.auth import verify_token
from backend.system.config import load_config

router = APIRouter()


class ConnectionManager:
    """Manager koneksi WebSocket aktif."""

    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message: dict):
        """Broadcast JSON ke semua koneksi aktif."""
        async with self._lock:
            connections = list(self._connections)
        dead = set()
        for conn in connections:
            try:
                await conn.send_json(message)
            except Exception:
                dead.add(conn)
        if dead:
            async with self._lock:
                self._connections -= dead


manager = ConnectionManager()


def _verify_query_token(token: str) -> bool:
    expected = load_config().get("api_secret_token")
    return token == expected


@router.websocket("/ws/progress")
async def ws_progress(websocket: WebSocket, token: str = Query(...)):
    if not _verify_query_token(token):
        await websocket.close(code=1008)
        return
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; client bisa kirim ping
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)


def broadcast_progress(message: dict):
    """Sync-friendly wrapper untuk broadcast; di-schedule di event loop."""
    try:
        loop = asyncio.get_running_loop()
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), loop)
    except RuntimeError:
        # Tidak ada event loop running (misal saat test sync)
        pass


# Register callback ke DownloadManager
from backend.api.state import manager as download_manager

download_manager.set_progress_callback(broadcast_progress)
