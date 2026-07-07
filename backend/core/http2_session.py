"""AsynxDL — HTTP/2 Session Wrapper.

Wrapper sederhana di atas httpx untuk server yang mengiklankan HTTP/2.
Jika HTTP/2 gagal atau server tidak support, fallback otomatis ke requests.Session.
Session di-cache per task untuk connection reuse.
"""

import requests
from typing import Any

try:
    import httpx
    _HTTPX_AVAILABLE = True
except Exception:  # pragma: no cover
    _HTTPX_AVAILABLE = False


class Http2Session:
    """Hybrid HTTP/2 + HTTP/1.1 session untuk download."""

    def __init__(self, prefer_http2: bool = True):
        self.prefer_http2 = prefer_http2 and _HTTPX_AVAILABLE
        self._httpx_client: Any | None = None
        self._requests_session: requests.Session | None = None
        self._use_http2 = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _ensure_client(self):
        if self._httpx_client is None and self.prefer_http2:
            try:
                self._httpx_client = httpx.Client(
                    http2=True,
                    follow_redirects=True,
                    timeout=httpx.Timeout(30.0),
                    limits=httpx.Limits(max_connections=10, max_keepalive_connections=10),
                )
                self._use_http2 = True
            except Exception as exc:
                print(f"[Http2Session] httpx init failed: {exc}")
                self._use_http2 = False
                self._httpx_client = None

        if self._requests_session is None:
            from backend.core.chunk_manager import _build_retry_session
            self._requests_session = _build_retry_session()

    def get(self, url: str, headers: dict | None = None, stream: bool = True, timeout: float = 30.0, allow_redirects: bool = True):
        self._ensure_client()
        if self._use_http2 and self._httpx_client:
            try:
                # httpx stream returns a Response that supports iter_bytes
                resp = self._httpx_client.get(url, headers=headers, timeout=timeout, follow_redirects=True)
                if resp.status_code < 400:
                    return _HttpxResponseAdapter(resp)
                # If server returned error, fall back to requests
                self._use_http2 = False
            except Exception as exc:
                print(f"[Http2Session] httpx request failed: {exc}; fallback to requests")
                self._use_http2 = False

        return self._requests_session.get(
            url,
            headers=headers,
            stream=stream,
            timeout=timeout,
            allow_redirects=allow_redirects,
        )

    def head(self, url: str, headers: dict | None = None, timeout: float = 30.0, allow_redirects: bool = True):
        self._ensure_client()
        if self._use_http2 and self._httpx_client:
            try:
                resp = self._httpx_client.head(url, headers=headers, timeout=timeout, follow_redirects=True)
                if resp.status_code < 400:
                    return resp
                self._use_http2 = False
            except Exception as exc:
                print(f"[Http2Session] httpx head failed: {exc}; fallback to requests")
                self._use_http2 = False
        return self._requests_session.head(url, headers=headers, timeout=timeout, allow_redirects=allow_redirects)

    def close(self):
        if self._httpx_client:
            try:
                self._httpx_client.close()
            except Exception:
                pass
            self._httpx_client = None
        if self._requests_session:
            try:
                self._requests_session.close()
            except Exception:
                pass
            self._requests_session = None


class _HttpxResponseAdapter:
    """Adapt httpx.Response ke API requests.Response yang dipakai download_chunk."""

    def __init__(self, response):
        self._resp = response
        self.status_code = response.status_code
        self.headers = dict(response.headers)
        self.url = str(response.url)
        self.reason_phrase = response.reason_phrase

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} {self.reason_phrase} for url {self.url}")

    def iter_content(self, chunk_size: int = 1024):
        return self._resp.iter_bytes(chunk_size)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        try:
            self._resp.close()
        except Exception:
            pass


__all__ = ("Http2Session",)
