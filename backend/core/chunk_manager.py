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
from collections import OrderedDict
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
_MAX_HOSTS = 256
_HOST_TUNERS: OrderedDict[str, BufferTuner] = OrderedDict()
_HOST_ROUTERS: OrderedDict[str, TurboRouter] = OrderedDict()
_HOST_LOCKS: OrderedDict[str, threading.Lock] = OrderedDict()
_TUNERS_GUARD = threading.Lock()


def _ensure_host_engines(host: str) -> tuple[BufferTuner, TurboRouter]:
    """Lazily create per-host BufferTuner + TurboRouter. Thread-safe."""
    with _TUNERS_GUARD:
        if host not in _HOST_LOCKS:
            _HOST_LOCKS[host] = threading.Lock()
            _HOST_TUNERS[host] = BufferTuner(host=host)
            _HOST_ROUTERS[host] = TurboRouter(host=host)
        # LRU: move accessed entries to end; evict oldest if over capacity
        _HOST_LOCKS.move_to_end(host)
        _HOST_TUNERS.move_to_end(host)
        _HOST_ROUTERS.move_to_end(host)
        while len(_HOST_LOCKS) > _MAX_HOSTS:
            evicted_lock = _HOST_LOCKS.popitem(last=False)
            _HOST_TUNERS.popitem(last=False)
            _HOST_ROUTERS.popitem(last=False)
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
        """HTTPAdapter yang menerapkan SOCKET_OPTIONS + proper SSL context.

        FIX: sebelumnya init_poolmanager() membuat PoolManager bare tanpa SSL
        context dari parent → HTTPS bisa gagal di urllib3 ≥ 2.x.
        Sekarang panggil super() untuk inherit SSL context, lalu patch
        socket_options ke pool manager.
        """

        def init_poolmanager(self, *args, **kwargs) -> None:  # type: ignore[override]
            kwargs["socket_options"] = list(SOCKET_OPTIONS)
            super().init_poolmanager(*args, **kwargs)
            # Patch _new_pool supaya pool baru yang dibuat secara dinamis
            # juga mendapatkan SOCKET_OPTIONS.
            if self.poolmanager is not None:
                _orig_new_pool = self.poolmanager._new_pool
                _adapter_opts = list(SOCKET_OPTIONS)

                def _patched_new_pool(scheme, host, port, request_context=None):  # type: ignore[override]
                    pool = _orig_new_pool(scheme, host, port, request_context)
                    pool.socket_options = _adapter_opts
                    return pool

                self.poolmanager._new_pool = _patched_new_pool

        def proxy_manager_for(self, *args, **kwargs):  # type: ignore[override]
            kwargs["socket_options"] = list(SOCKET_OPTIONS)
            return super().proxy_manager_for(*args, **kwargs)


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
    """Return Content-Length from a HEAD request; 0 if not provided."""
    if session is None:
        session = _build_retry_session()
    headers = {"User-Agent": _USER_AGENT}
    try:
        resp = session.head(url, headers=headers, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        content_length = resp.headers.get("Content-Length")
        if content_length is None:
            return 0
        return int(content_length)
    except Exception:
        return 0


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
        start: inclusive byte offset (ignored for unknown-length streaming).
        end: inclusive byte offset; 0 or negative means unknown length.
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

    unknown_length = end <= 0
    headers = {"User-Agent": ua_string}
    if not unknown_length:
        headers["Range"] = f"bytes={start}-{end}"

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
                mode = "wb"
                bytes_done = 0
            else:
                mode = "ab"
                try:
                    bytes_done = os.path.getsize(part_path)
                except OSError:
                    bytes_done = 0

            if not unknown_length:
                resume_start = start + bytes_done
                if resume_start > end:
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

            with open(part_path, mode) as f:
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
    """Probe a URL before download for size, range support, filename, and checksum headers."""
    session = _build_retry_session()
    headers = {"User-Agent": _USER_AGENT}
    content_length = 0
    accept_ranges = False
    content_type = None
    etag = None
    digest = None
    last_modified = None

    # Try HEAD first
    try:
        resp = session.head(url, headers=headers, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        content_length = int(resp.headers.get("Content-Length", 0))
        accept_ranges = resp.headers.get("Accept-Ranges", "").lower() == "bytes"
        content_type = resp.headers.get("Content-Type")
        etag = resp.headers.get("ETag")
        digest = resp.headers.get("Digest")
        last_modified = resp.headers.get("Last-Modified")
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
            etag = etag or resp.headers.get("ETag")
            digest = digest or resp.headers.get("Digest")
            last_modified = last_modified or resp.headers.get("Last-Modified")
            # Close the connection without downloading the body
            resp.close()
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to probe URL {url}: {exc}") from exc

    # Validate range support by actually requesting a byte range only when
    # the server reported a content length.
    supports_range = False
    if content_length > 0 and accept_ranges:
        supports_range = _supports_range(url, session)

    filename = _extract_filename(url)

    expected_sha256 = None
    expected_md5 = None
    if digest:
        # Format: sha-256=...; md5=..., atau urutan-nya dipisahkan koma
        for part in digest.split(","):
            part = part.strip()
            if "=" not in part:
                continue
            algo, value = part.split("=", 1)
            algo = algo.strip().lower().replace("-", "")
            value = value.strip().strip('"')
            if algo == "sha256":
                expected_sha256 = value
            elif algo == "md5":
                expected_md5 = value

    return {
        "content_length": content_length,
        "supports_range": supports_range,
        "filename": filename,
        "content_type": content_type,
        "etag": etag,
        "expected_sha256": expected_sha256,
        "expected_md5": expected_md5,
        "last_modified": last_modified,
    }
