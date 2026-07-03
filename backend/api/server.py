"""
AsynxDL — FastAPI Server
~~~~~~~~~~~~~~~~~~~~~~~~~
Assembly FastAPI app, middleware, router, and uvicorn runner.
Hardened: only localhost, strict CORS, 127.0.0.1 binding.
"""

import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import status, downloads, settings, ws_progress
from backend.api.state import manager as download_manager
from backend.system.config import load_config


def create_app() -> FastAPI:
    config = load_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Bug-2 fix: recovery stranded tasks dijalankan di background thread
        # supaya uvicorn bisa langsung bind socket (HTTP serve ready lebih
        # cepat). Tasks akan dipulihkan tanpa blocking startup.
        def _delayed_recover():
            try:
                recovered = download_manager.recover()
                if recovered:
                    print(f"[AsynxDL] Background recovery: "
                          f"{len(recovered)} tasks restored.")
            except Exception as exc:
                print(f"[AsynxDL] Background recovery failed: {exc}")
        threading.Thread(target=_delayed_recover, daemon=True).start()
        yield
        download_manager.shutdown()

    app = FastAPI(title="AsynxDL", version="1.0.2", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1"],
        allow_methods=["GET", "POST", "PATCH", "DELETE", "PUT"],
        allow_headers=["X-AsynxDL-Token", "Content-Type"],
        allow_credentials=False,
    )

    app.include_router(status.router)
    app.include_router(downloads.router, prefix="/downloads")
    app.include_router(settings.router, prefix="/settings")
    app.include_router(ws_progress.router)

    return app


def run_server(port: int = 58296, host: str = "127.0.0.1"):
    import uvicorn
    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="warning")


def start_server_thread(port: int = 58296) -> threading.Thread:
    """Start uvicorn server in a daemon thread. v1.0.2: no blocking sleep.

    Bug-2 fix: time.sleep(1.0) unconditional sebelumnya menambahkan +1 s
    ke setiap launch. Sekarang caller (_wait_for_backend) yang polling
    dengan backoff agresif sehingga boot time tetap konsisten.
    """
    t = threading.Thread(target=run_server, args=(port,), daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    run_server()
