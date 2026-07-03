"""
AsynxDL — Chunk Manager Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Download one chunk of a file via HTTP Range request.
Supports stop event (pause), speed limiter, and auto-retry.
Memory-optimized for 4GB RAM: small fixed buffer, no large in-memory buffers.

Functions:
    - download_chunk(url, start, end, part_path, limiter, stop_event)
    - probe_url(url)
"""

import os
import threading
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import unquote, urlparse

from .speed_limiter import SpeedLimiter
from .socket_tuner import SOCKET_OPTIONS
from .buffer_tuner import BufferTuner
from .dns_prefetch import resolve_for_url
from .turbo_router import TurboRouter, DEFAULT_UA as _USER_AGENT_CHUNK


# UA stabil untuk probe/head-request. w3.org & beberapa host memfilter UA
# "browser looking" sebagai bot — menyimpan string "AsynxDL/1.0" saja lulus.
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AsynxDL/1.0"


# 32KB streaming buffer baseline — konservatif untuk RAM 4GB & jaringan lambat.
# Di-override per-host oleh BufferTuner (Phase 2) menjadi 8/16/32/64 KB.
_DEFAULT_CHUNK_BUFFER = 32 * 1024

_MAX_RETRIES = 5
_RETRY_BACKOFF_FACTOR = 1.0
_RETRY_STATUSES = [429, 500, 502, 503, 504]


# Host-scoped buffer tuner cache (bounded LRU; thread-local tidak karena kita
# ingin tuner belajar antar-chunk). Modul dict, kunci hostname.
_HOST_TUNERS: dict[str, BufferTuner] = {}
_HOST_ROUTERS: dict[str, TurboRouter] = {}
_HOST_LOCKS: dict[str, threading.Lock] = {}
_TUNERS_GUARD = threading.Lock()


def _ensure_host_engines(host: str) -> tuple[BufferTuner, TurboRouter]:
    """Lazily create per-host BufferTuner + TurboRouter. Thread-safe."""
    with _TUNERS_GUARD:
        if host not in _HOST_LOCKS:
            _HOST_LOCKS[host] = threading.Lock()
            _HOST_TUNERS[host] = BufferTuner(host=host)
            _HOST_ROUTERS[host] = TurboRouter(host=host)
        return _HOST_TUNERS[host], _HOST_ROUTERS[host]


def _reset_host_engines(host: str) -> None:
    """Reset buffer samples & router state untuk hostname (mis. setelah retry)."""
    with _TUNERS_GUARD:
        if host in _HOST_TUNERS:
            try:
                _HOST_TUNERS[host].attach_host(host)
            except Exception:
                pass
        if host in _HOST_ROUTERS:
            try:
                _HOST_ROUTERS[host].attach_host(host)
            except Exception:
                pass


def _build_retry_session() -> requests.Session:
    """Build a requests.Session with urllib3 retry strategy + Phase 2 socket options.

    urllib3 ≥ 2.x tidak lagi menerima ``socket_options`` di ``HTTPAdapter.__init__``
    — hanya sebagai atributumum via custom PoolManager. Kita subclass
    ``HTTPAdapter`` lalu override ``init_poolmanager`` untuk meneruskan
    ``SOCKET_OPTIONS`` (TCP Keep-Alive, Nagle off, buffer 256KB).
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=_MAX_RETRIES,
        backoff_factor=_RETRY_BACKOFF_FACTOR,
        status_forcelist=_RETRY_STATUSES,
        allowed_methods=["GET", "HEAD"],
    )
    return _attach_adapter(session, retry_strategy)


if hasattr(HTTPAdapter, "init_poolmanager"):
    class _TurboHttpAdapter(HTTPAdapter):
        """HTTPAdapter yang menerapkan SOCKET_OPTIONS pada setiap poolmanager."""

        def init_poolmanager(self, *args, **kwargs) -> None:  # type: ignore[override]
            from urllib3 import PoolManager
            self.poolmanager = PoolManager(
                num_pools=kwargs.get("num_pools", 10),
                maxsize=kwargs.get("maxsize", 10),
                block=kwargs.get("block", False),
                socket_options=list(SOCKET_OPTIONS),
                retries=Retry(
                    total=_MAX_RETRIES,
                    backoff_factor=_RETRY_BACKOFF_FACTOR,
                    status_forcelist=_RETRY_STATUSES,
                    allowed_methods=["GET", "HEAD"],
                ),
            )

        def proxy_manager_for(self, *args, **kwargs):  # type: ignore[override]
            from urllib3 import ProxyManager
            return ProxyManager(
                proxy_url=kwargs.get("proxy_url"),
                num_pools=kwargs.get("num_pools", 10),
                maxsize=kwargs.get("maxsize", 10),
                block=kwargs.get("block", False),
                socket_options=list(SOCKET_OPTIONS),
            )


    def _attach_adapter(session: requests.Session, retry_strategy: Retry) -> requests.Session:
        adapter = _TurboHttpAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session
else:
    def _attach_adapter(session: requests.Session, retry_strategy: Retry) -> requests.Session:
        # Fallback: behave like the legacy call — works on urllib3 < 2.
        adapter = HTTPAdapter(max_retries=retry_strategy, socket_options=list(SOCKET_OPTIONS))
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session


def _warm_dns(host: str) -> None:
    """Trigger DNS prefetch in a background thread untuk memotong handshake latency."""
    if not host:
        return
    def _go() -> None:
        try:
            ips = resolve_for_url("http://" + host)
            return ips  # cached; tidak dipakai di sini (requests dengan hostname asli)
        except Exception:
            return None
    threading.Thread(target=_go, daemon=True, name=f"dns_prefetch_{host}").start()


def _get_content_length(url: str, session: requests.Session | None = None) -> int:
    """Return Content-Length from a HEAD request."""
    if session is None:
        session = _build_retry_session()
    headers = {"User-Agent": _USER_AGENT}
    resp = session.head(url, headers=headers, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    content_length = resp.headers.get("Content-Length")
    if content_length is None:
        raise ValueError("Server did not provide Content-Length header")
    return int(content_length)


def _supports_range(url: str, session: requests.Session | None = None) -> bool:
    """Check if the server actually supports byte ranges by sending a test Range request."""
    if session is None:
        session = _build_retry_session()
    try:
        headers = {
            "Range": "bytes=0-0",
            "User-Agent": _USER_AGENT,
        }
        resp = session.get(url, headers=headers, timeout=30, allow_redirects=True, stream=True)
        if resp.status_code == 206:
            # Consume tiny body to close connection cleanly
            _ = resp.content
            return True
        # If server returns 200 for the whole file, it does not honor ranges
        return False
    except requests.RequestException:
        return False


def _extract_filename(url: str) -> str:
    """Extract a filename from the URL path."""
    path = urlparse(url).path
    filename = os.path.basename(path)
    if filename:
        return unquote(filename)
    return "unnamed_file"


def download_chunk(
    url: str,
    start: int,
    end: int,
    part_path: str,
    limiter: SpeedLimiter,
    stop_event: threading.Event,
    session: requests.Session | None = None,
) -> int:
    """Download a single byte range into a .part file.

    Streaming, small buffer, manual retry for network errors, and responsive
    to stop_event for pause/cancel. No large buffers are kept in memory.

    Args:
        url: source URL.
        start: inclusive byte offset.
        end: inclusive byte offset.
        part_path: destination .part file path.
        limiter: SpeedLimiter instance.
        stop_event: threading.Event to stop early.
        session: optional requests.Session (recommended for reuse).

    Returns:
        bytes written for this chunk.

    Raises:
        RuntimeError: if the chunk cannot be completed after retries.
    """
    if session is None:
        session = _build_retry_session()

    # Phase 2: bikin / attach per-host engine (BufferTuner + TurboRouter) sehingga
    # iter_content()_chunk_size adaptif dan UA rotation berlaku untuk percobaan
    # retry berurutan.
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        host = ""
    tuner, router = _ensure_host_engines(host) if host else (None, None)
    ua_string = router.next_user_agent() if router is not None else _USER_AGENT_CHUNK
    if tuner is not None:
        # attempt #1: quick TCP-handshake latency sample untukBufferTuner
        try:
            ms = tuner.measure_quick_ping(timeout=0.7)
            if ms is not None and ms > 0:
                tuner.record_latency(ms)
        except Exception:
            pass
    iter_chunk_size = tuner.current_buffer() if tuner is not None else _DEFAULT_CHUNK_BUFFER
    headers = {
        "Range": f"bytes={start}-{end}",
        "User-Agent": ua_string,
    }
    bytes_done = 0

    # Ensure directory exists once
    out_dir = os.path.dirname(part_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Trigger warm DNS (background) — first-chunk latency akan turun
    _warm_dns(host)

    for attempt in range(1, _MAX_RETRIES + 1):
        if stop_event.is_set():
            return bytes_done

        try:
            if attempt == 1 and not os.path.exists(part_path):
                f = open(part_path, "wb")
                bytes_done = 0
            else:
                try:
                    bytes_done = os.path.getsize(part_path)
                except OSError:
                    bytes_done = 0
                f = open(part_path, "ab")

            resume_start = start + bytes_done
            if resume_start > end:
                f.close()
                return bytes_done
            headers["Range"] = f"bytes={resume_start}-{end}"

            # Phase 2: rotate UA per attempt (server throttle-friendliness),
            # ukuran buffer adaptif dari ping-rolling.
            if router is not None:
                try:
                    ua_string = router.next_user_agent()
                    headers["User-Agent"] = ua_string
                except Exception:
                    pass
            if tuner is not None:
                try:
                    new_buf = tuner.current_buffer()
                    if new_buf > 0:
                        iter_chunk_size = new_buf
                except Exception:
                    pass

            # Attempt #2 (first retry) — re-warm DNS (router mungkin belum
            # punya IP cached setelah attempt pertama gagal).
            if attempt == 2 and router is not None:
                _warm_dns(host)

            with f:
                with session.get(
                    url, headers=headers, stream=True, timeout=30, allow_redirects=True
                ) as response:
                    response.raise_for_status()
                    for data in response.iter_content(chunk_size=iter_chunk_size):
                        if stop_event.is_set():
                            return bytes_done
                        if data:
                            f.write(data)
                            data_len = len(data)
                            bytes_done += data_len
                            limiter.throttle(data_len)
                            # Phase 2: feed throttle-detector.
                            if router is not None:
                                try:
                                    kbps = (data_len / 1024.0)
                                    if kbps > 0:
                                        router.record_speed(kbps)
                                except Exception:
                                    pass

            return bytes_done

        except (requests.RequestException, OSError) as exc:
            if attempt == _MAX_RETRIES:
                raise RuntimeError(
                    f"Chunk {start}-{end} failed after {_MAX_RETRIES} retries: {exc}"
                ) from exc
            delay = min(_RETRY_BACKOFF_FACTOR * (2 ** (attempt - 1)), 30.0)
            if stop_event.wait(delay):
                return bytes_done

    return bytes_done


def probe_url(url: str) -> dict:
    """Probe a URL before download for size, range support, and filename."""
    session = _build_retry_session()
    headers = {"User-Agent": _USER_AGENT}
    content_length = 0
    accept_ranges = False
    content_type = None

    # Try HEAD first
    try:
        resp = session.head(url, headers=headers, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        content_length = int(resp.headers.get("Content-Length", 0))
        accept_ranges = resp.headers.get("Accept-Ranges", "").lower() == "bytes"
        content_type = resp.headers.get("Content-Type")
    except requests.RequestException:
        pass

    # If HEAD failed or gave no length, try a GET and read just the headers
    if content_length <= 0:
        try:
            resp = session.get(url, headers=headers, timeout=30, allow_redirects=True, stream=True)
            resp.raise_for_status()
            content_length = int(resp.headers.get("Content-Length", 0))
            accept_ranges = resp.headers.get("Accept-Ranges", "").lower() == "bytes"
            content_type = resp.headers.get("Content-Type")
            # Close the connection without downloading the body
            resp.close()
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to probe URL {url}: {exc}") from exc

    # Validate range support by actually requesting a byte range
    supports_range = False
    if content_length > 0:
        supports_range = _supports_range(url, session)

    filename = _extract_filename(url)
    return {
        "content_length": content_length,
        "supports_range": supports_range,
        "filename": filename,
        "content_type": content_type,
    }
