"""AsynxDL — APIClient (HTTP + WebSocket bridge ke backend FastAPI).

Audit-fix v1.0.x:
    - Semua method publik ``except`` di-``try/except`` dan envelope-error.
    - Token deps otomatis dimuat dari config (HMAC compare_digest
      server-side cocok).
"""

import json
import os
import threading
import time
from typing import Callable, Optional

import requests
import websocket

from backend.system.config import load_config


class APIClient:
    """HTTP + WebSocket client untuk komunikasi dengan backend FastAPI."""

    def __init__(self, host: str = "127.0.0.1", port: int = 58296):
        self.host = host
        self.port = port
        self._token = ""
        self._base_url = f"http://{host}:{port}"
        self._ws_url = f"ws://{host}:{port}/ws/progress"
        self._ws: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._on_progress: Optional[Callable[[dict], None]] = None
        self._running = False

    # ---------------------------------------------------------------- helpers
    def _load_token(self) -> str:
        if not self._token:
            try:
                self._token = load_config().get("api_secret_token", "")
            except Exception:
                self._token = ""
        return self._token

    def headers(self) -> dict:
        return {"X-AsynxDL-Token": self._load_token(),
                "Content-Type": "application/json"}

    def _envelope_err(self, op: str, exc: Exception) -> dict:
        msg = f"{type(exc).__name__}: {exc}".strip()
        print(f"[APIClient] {op} failed — {msg}")
        return {"error": msg}

    # ---------------------------------------------------------------- status
    def status(self) -> bool:
        try:
            resp = requests.get(f"{self._base_url}/status", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    # ---------------------------------------------------------------- HTTP ops
    def add_download(self, url: str, filename: str = "", save_path: str = "",
                     speed_limit_kbps: int = 0) -> dict:
        try:
            payload = {"url": url, "filename": filename,
                       "save_path": save_path,
                       "speed_limit_kbps": speed_limit_kbps}
            resp = requests.post(f"{self._base_url}/downloads/add",
                                 json=payload, headers=self.headers(),
                                 timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            return self._envelope_err("add_download", exc)

    def list_downloads(self) -> list:
        try:
            resp = requests.get(f"{self._base_url}/downloads",
                                 headers=self.headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            return [self._envelope_err("list_downloads", exc)]

    def pause(self, task_id: str) -> dict:
        try:
            resp = requests.patch(
                f"{self._base_url}/downloads/{task_id}/pause",
                headers=self.headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            return self._envelope_err("pause", exc)

    def resume(self, task_id: str) -> dict:
        try:
            resp = requests.patch(
                f"{self._base_url}/downloads/{task_id}/resume",
                headers=self.headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            return self._envelope_err("resume", exc)

    def delete(self, task_id: str, delete_parts: bool = True,
                remove_from_history: bool = False) -> dict:
        try:
            resp = requests.delete(
                f"{self._base_url}/downloads/{task_id}",
                params={"delete_parts": str(delete_parts).lower(),
                         "remove_from_history":
                             str(remove_from_history).lower()},
                headers=self.headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            return self._envelope_err("delete", exc)

    def remove_history(self, task_id: str, delete_parts: bool = True) -> dict:
        try:
            resp = requests.patch(
                f"{self._base_url}/downloads/{task_id}/remove_history",
                params={"delete_parts": str(delete_parts).lower()},
                headers=self.headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            return self._envelope_err("remove_history", exc)

    def get_settings(self) -> dict:
        try:
            resp = requests.get(f"{self._base_url}/settings",
                                 headers=self.headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            return self._envelope_err("get_settings", exc)

    def put_settings(self, settings: dict) -> dict:
        try:
            resp = requests.put(f"{self._base_url}/settings", json=settings,
                                 headers=self.headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            return self._envelope_err("put_settings", exc)

    def open_folder(self, path: str):
        folder = os.path.dirname(path) if os.path.isfile(path) else path
        os.startfile(folder)

    def run_file(self, path: str) -> bool:
        """Run the file at the given path using the default system application."""
        try:
            os.startfile(path)
            return True
        except Exception as exc:
            return self._envelope_err("run_file", exc)

    # ---------------------------------------------------------------- ws ops
    def set_progress_callback(self, callback: Callable[[dict], None]):
        self._on_progress = callback

    def start_ws(self):
        if self._running:
            return
        self._running = True
        token = self._load_token()

        def on_message(ws, message):
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                return
            if self._on_progress:
                try:
                    self._on_progress(data)
                except Exception:
                    pass

        def on_open(ws):
            try:
                ws.send(token)  # Kirim token sebagai pesan pertama
                ws.send("ping")  # Kirim ping setelah token terverifikasi
            except Exception:
                pass

        def run():
            while self._running:
                try:
                    self._ws = websocket.WebSocketApp(
                        self._ws_url,  # Token dihapus dari query parameter
                        on_message=on_message,
                        on_open=on_open,
                    )
                    self._ws.run_forever(ping_interval=15, ping_timeout=5)
                except Exception:
                    pass
                if self._running:
                    time.sleep(2)

        self._ws_thread = threading.Thread(target=run, daemon=True)
        self._ws_thread.start()

    def stop_ws(self):
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass


__all__: list[str] = ["APIClient"]
