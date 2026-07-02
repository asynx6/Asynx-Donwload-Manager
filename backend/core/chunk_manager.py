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


_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AsynxDL/1.0"

# 64KB streaming buffer — keeps RAM low and avoids fragmentation
_CHUNK_BUFFER = 64 * 1024

_MAX_RETRIES = 5
_RETRY_BACKOFF_FACTOR = 1.0
_RETRY_STATUSES = [429, 500, 502, 503, 504]


def _build_retry_session() -> requests.Session:
    """Build a requests.Session with urllib3 retry strategy for transient errors."""
    session = requests.Session()
    retry_strategy = Retry(
        total=_MAX_RETRIES,
        backoff_factor=_RETRY_BACKOFF_FACTOR,
        status_forcelist=_RETRY_STATUSES,
        allowed_methods=["GET", "HEAD"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


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

    headers = {
        "Range": f"bytes={start}-{end}",
        "User-Agent": _USER_AGENT,
    }
    bytes_done = 0

    # Ensure directory exists once
    out_dir = os.path.dirname(part_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

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

            with f:
                with session.get(
                    url, headers=headers, stream=True, timeout=30, allow_redirects=True
                ) as response:
                    response.raise_for_status()
                    for data in response.iter_content(chunk_size=_CHUNK_BUFFER):
                        if stop_event.is_set():
                            return bytes_done
                        if data:
                            f.write(data)
                            data_len = len(data)
                            bytes_done += data_len
                            limiter.throttle(data_len)

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
