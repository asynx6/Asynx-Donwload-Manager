"""AsynxDL — WebSocket Progress Route.

Audit-fix v1.1.0:
    - ``verify_token_string`` (HMAC compare_digest) menggantikan ``==`` untuk
      avoid timing attack.
    - Empty/placeholder token di config = auto-reject upgrade.
"""

import asyncio
import hmac
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from backend.api.auth import verify_token_string, _load_real_token
from backend.api.state import manager as download_manager

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
        dead: set[WebSocket] = set()
        for conn in connections:
            try:
                await conn.send_json(message)
            except Exception:
                dead.add(conn)
        if dead:
            async with self._lock:
                self._connections -= dead


manager = ConnectionManager()


@router.websocket("/ws/progress")
async def ws_progress(websocket: WebSocket, token: str = Query(...)):
    if not _load_real_token() or not verify_token_string(token):
        # Reject sebelum accept() supaya client tidak mendapatkan partial frame.
        await websocket.close(code=1008, reason="forbidden")
        return
    await manager.connect(websocket)
    try:
        while True:
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
        pass


# Register callback ke DownloadManager
download_manager.set_progress_callback(broadcast_progress)
