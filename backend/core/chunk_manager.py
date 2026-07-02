"""
AsynxDL — Chunk Manager Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Download satu chunk file via HTTP Range request.
Mendukung stop event (pause), speed limiter, dan auto-retry.

Fungsi:
    - download_chunk(url, start, end, part_path, limiter, stop_event)
"""

import os
import threading
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .speed_limiter import SpeedLimiter


# User-Agent yang digunakan untuk semua request HTTP
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AsynxDL/1.0"

# Ukuran buffer stream (64KB) — dioptimalkan untuk SSD dan RAM 4GB
_CHUNK_BUFFER = 65536  # 64 KB

# Konfigurasi retry
_MAX_RETRIES = 5
_RETRY_BACKOFF_FACTOR = 1.0  # delay = backoff * (2 ** (retries - 1))
_RETRY_STATUSES = [429, 500, 502, 503, 504]


def _build_retry_session() -> requests.Session:
    """Bangun requests.Session dengan retry strategy bawaan.

    Session ini di-cache dalam download_chunk() via parameter opsional.
    """
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
    """Lakukan HEAD request untuk mendapatkan Content-Length.

    Args:
        url: URL file yang akan diunduh.
        session: Session requests (opsional, dibuat baru jika tidak diberikan).

    Returns:
        Ukuran file dalam byte.

    Raises:
        ValueError: Jika header Content-Length tidak ditemukan.
        requests.RequestException: Jika HEAD request gagal.
    """
    if session is None:
        session = _build_retry_session()
    headers = {"User-Agent": _USER_AGENT}
    resp = session.head(url, headers=headers, timeout=30)
    resp.raise_for_status()
    content_length = resp.headers.get("Content-Length")
    if content_length is None:
        raise ValueError("Server tidak menyediakan Content-Length header")
    return int(content_length)


def _supports_range(url: str, session: requests.Session | None = None) -> bool:
    """Cek apakah server mendukung Range request.

    Args:
        url: URL file.
        session: Session requests (opsional).

    Returns:
        True jika server mendukung Accept-Ranges: bytes.
    """
    if session is None:
        session = _build_retry_session()
    try:
        headers = {"User-Agent": _USER_AGENT}
        resp = session.head(url, headers=headers, timeout=30)
        accept_ranges = resp.headers.get("Accept-Ranges", "").lower()
        return accept_ranges == "bytes"
    except requests.RequestException:
        return False


def _extract_filename(url: str) -> str:
    """Ekstrak nama file dari URL.

    Args:
        url: URL file.

    Returns:
        Nama file dari bagian akhir URL path/query.
    """
    from urllib.parse import unquote, urlparse
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
    """Download satu chunk file via HTTP Range request.

    Fungsi ini berjalan di thread terpisah. Setiap iterasi buffered,
    memeriksa stop_event untuk pause/cancel, dan memanggil
    limiter.throttle() untuk kontrol kecepatan.

    Retry logic: requests.Session bawaan sudah menangani retry
    untuk error transient (5xx, 429). Untuk error koneksi lain,
    fungsi ini melakukan retry manual dengan exponential backoff.

    Args:
        url: URL file sumber.
        start: Byte offset awal (inklusif).
        end: Byte offset akhir (inklusif).
        part_path: Path file .part tempat menulis data.
        limiter: SpeedLimiter instance untuk kontrol kecepatan.
        stop_event: threading.Event — set True untuk pause/cancel.
        session: requests.Session reuse (opsional).

    Returns:
        Total byte yang berhasil diunduh untuk chunk ini.

    Raises:
        RuntimeError: Jika chunk gagal setelah semua retry.
        OSError: Jika gagal menulis ke disk.
    """
    if session is None:
        session = _build_retry_session()

    headers = {
        "Range": f"bytes={start}-{end}",
        "User-Agent": _USER_AGENT,
    }
    chunk_size = end - start + 1
    bytes_done = 0

    # Manual retry loop untuk menangani error yang tidak dicover oleh
    # urllib3 Retry (misal: ChunkedEncodingError, timeout non-5xx)
    for attempt in range(1, _MAX_RETRIES + 1):
        if stop_event.is_set():
            return bytes_done

        try:
            # Buka file di mode append binary
            if attempt == 1:
                os.makedirs(os.path.dirname(part_path), exist_ok=True)
                # Mulai dari awal untuk attempt pertama
                f = open(part_path, "wb")
                bytes_done = 0
            else:
                # Resume dari posisi terakhir jika retry
                try:
                    bytes_done = os.path.getsize(part_path)
                except OSError:
                    bytes_done = 0
                f = open(part_path, "ab")

            with f:
                # Range header disesuaikan untuk resume
                resume_start = start + bytes_done
                if resume_start > end:
                    # Chunk sudah selesai
                    return bytes_done
                headers["Range"] = f"bytes={resume_start}-{end}"

                with session.get(url, headers=headers, stream=True,
                                 timeout=30) as response:
                    response.raise_for_status()

                    for data in response.iter_content(chunk_size=_CHUNK_BUFFER):
                        if stop_event.is_set():
                            return bytes_done

                        if data:
                            f.write(data)
                            data_len = len(data)
                            bytes_done += data_len
                            limiter.throttle(data_len)

            # Download selesai untuk chunk ini
            return bytes_done

        except (requests.RequestException, OSError) as exc:
            if attempt == _MAX_RETRIES:
                raise RuntimeError(
                    f"Chunk {start}-{end} gagal setelah {_MAX_RETRIES} retry: {exc}"
                ) from exc
            # Exponential backoff: 1s, 2s, 4s, 8s, 16s
            delay = _RETRY_BACKOFF_FACTOR * (2 ** (attempt - 1))
            if stop_event.wait(delay):
                return bytes_done

    return bytes_done


def probe_url(url: str) -> dict:
    """Probe URL untuk mendapatkan info sebelum download.

    Args:
        url: URL file.

    Returns:
        Dict dengan keys:
            - content_length: int (byte)
            - supports_range: bool
            - filename: str (dari URL)
            - content_type: str | None
    """
    session = _build_retry_session()
    try:
        headers = {"User-Agent": _USER_AGENT}
        resp = session.head(url, headers=headers, timeout=30)
        resp.raise_for_status()
        content_length = int(resp.headers.get("Content-Length", 0))
        accept_ranges = resp.headers.get("Accept-Ranges", "").lower() == "bytes"
        content_type = resp.headers.get("Content-Type")
        filename = _extract_filename(url)
        return {
            "content_length": content_length,
            "supports_range": accept_ranges,
            "filename": filename,
            "content_type": content_type,
        }
    except requests.RequestException as exc:
        raise RuntimeError(f"Gagal probe URL {url}: {exc}") from exc
