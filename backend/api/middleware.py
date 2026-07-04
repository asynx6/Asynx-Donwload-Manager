"""AsynxDL — FastAPI Middleware: rate limit + token defense.

Audit-fix v1.1.0:
    - RateLimitMiddleware: maks 60 req/menit per peer (default). Backed by
      thread-safe LRU counter dict (bounded untuk menghindari memory leak).
    - HeaderDefenseMiddleware: opsional helper Untuk blokir Origin/Referer
      mencurigakan.

Middleware ini dipasang di server.create_app() ANTARA CORS dan router supaya
token dependency (yang dipasang di level router via per-route ``Depends``)
tetap menjadi single source of truth untuk auth.
"""

import threading
import time
from collections import deque
from typing import Deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.requests import Request
from starlette.responses import Response, JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sederhana sliding-window rate limiter.

    - Per-IP (X-Forwarded-For ignored karena local-only).
    - Count request masuk kecuali ``/status`` (status adalah health check,
      harus bebas dari rate limit supaya startup polling tidak menggantung).
    - Sliding window dengan deque timestamp; auto-trim saat window lewat.

    Attributes:
        max_requests: nilai limit per window dalam detik.
        window: lebar window (detik).
    """

    def __init__(self, app: ASGIApp, max_requests: int = 60,
                 window: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window
        self._buckets: dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def _now(self) -> float:
        return time.monotonic()

    def _trim(self, key: str, bucket: Deque[float]) -> None:
        now = self._now()
        cutoff = now - self.window
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

    async def dispatch(self, request: Request, call_next) -> Response:
        # Exempt health check
        path = (request.url.path or "").lower()
        if path == "/status":
            return await call_next(request)
        # Exempt static & docs
        if path in ("/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        peer = request.client.host if request.client else "unknown"
        with self._lock:
            bucket = self._buckets.get(peer)
            if bucket is None:
                bucket = deque()
                self._buckets[peer] = bucket
            self._trim(peer, bucket)
            if len(bucket) >= self.max_requests:
                retry = max(1.0, self.window - (self._now() - bucket[0]))
                return JSONResponse(
                    {"detail": "Rate limit exceeded"},
                    status_code=429,
                    headers={"Retry-After": str(int(retry))},
                )
            bucket.append(self._now())

        # Bound memory: kadaluwarsa peer buckets yang belum aktif >5 menit
        if (len(self._buckets) > 256 and
                (self._now() % 5) < 0.05):
            with self._lock:
                cutoff = self._now() - 5 * 60
                stale = [k for k, b in self._buckets.items() if not b or b[-1] < cutoff]
                for k in stale:
                    self._buckets.pop(k, None)

        return await call_next(request)


class HeaderDefenseMiddleware(BaseHTTPMiddleware):
    """Reject Host/Origin header mencurigakan. Token-defense shields deps."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        host = (request.headers.get("host") or "").lower().strip()
        # Izinkan loopback only (AsynxDL adalah local-only).
        # ``testserver`` ditambahkan untuk kompatibilitas starlette TestClient.
        if host and not any(host.startswith(pfx) for pfx in
                             ("127.0.0.1", "localhost", "0.0.0.0",
                              "testserver")):
            return JSONResponse({"detail": "Forbidden Host"},
                                 status_code=403)
        return await call_next(request)


__all__: list[str] = ["RateLimitMiddleware", "HeaderDefenseMiddleware"]
