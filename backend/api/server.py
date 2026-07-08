"""
AsynxDL — FastAPI Server
~~~~~~~~~~~~~~~~~~~~~~~~~
Assembly FastAPI app, middleware, router, dan uvicorn runner.
Hardened: only localhost, strict CORS, 127.0.0.1 binding, Host defense,
sliding-window rate limit.
"""

import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.middleware import HeaderDefenseMiddleware
from backend.api.routes import status, downloads, settings, ws_progress
from backend.api.state import manager as download_manager
from backend.system.config import load_config


def create_app() -> FastAPI:
    config = load_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        def _delayed_recover() -> None:
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

    app = FastAPI(title="AsynxDL", version="1.0.7", lifespan=lifespan)

    # ------------------------------------------------------------- middleware
    # Order matters: Header defense → CORS → router.
    # Rate limit DIHAPUS — AsynxDL bind 127.0.0.1 saja (localhost only),
    # tidak ada attack surface dari network luar. Rate limit cuma bikin
    # masalah saat user download banyak file sekaligus.
    # Token auth juga DIHAPUS — localhost-only app tidak butuh auth.
    app.add_middleware(HeaderDefenseMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1"],
        allow_methods=["GET", "POST", "PATCH", "DELETE", "PUT"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )

    # ------------------------------------------------------------- routes
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
    """Start uvicorn server in a daemon thread.

    Caller ``_wait_for_backend`` melakukan polling agresif (backoff) sehingga
    boot time tetap konsisten tanpa perlu unconditional sleep di sini.
    """
    t = threading.Thread(target=run_server, args=(port,), daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    run_server()
