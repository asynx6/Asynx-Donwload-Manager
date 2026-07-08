"""AsynxDL — Intelligent Mirror & CDN Selection.

Sebelum download dimulai, kirim HEAD request kecil ke beberapa candidate
mirror/CDN dari hostname target. Pilih mirror dengan latensi terendah yang
juga mengembalikan Content-Length cocok dan status 2xx. Simpan fallback list
untuk failover nanti.
"""

import ipaddress
import os
import socket
import threading
import time
from urllib.parse import urlparse, urlunparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from backend.core.chunk_manager import _build_retry_session


_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AsynxDL/1.0"


def _is_private_or_loopback(hostname: str) -> bool:
    """Check apakah hostname resolve ke IP private/loopback.

    SECURITY #13: Mencegah SSRF ke internal network.
    """
    if not hostname:
        return False
    # Cek langsung apakah hostname adalah IP literal
    try:
        addr = ipaddress.ip_address(hostname)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        pass
    # Resolve hostname dan cek semua IP yang di-resolve
    try:
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        for _family, _type, _proto, _canonname, sockaddr in infos:
            ip_str = sockaddr[0]
            try:
                addr = ipaddress.ip_address(ip_str)
                if addr.is_private or addr.is_loopback or addr.is_link_local:
                    return True
            except ValueError:
                continue
    except (socket.gaierror, OSError):
        pass
    return False


def _candidate_hosts(hostname: str) -> list[str]:
    """Generate mirror hostname variants dari hostname asli.

    Skip untuk IP loopback/private — tidak ada CDN mirror untuk localhost.
    """
    if not hostname:
        return []
    # FIX: skip mirror probing untuk loopback/private IP (localhost, 192.168.x, dll)
    # Tidak ada CDN mirror untuk IP internal; probing hanya buang waktu.
    if _is_private_or_loopback(hostname):
        return [hostname]
    hostname = hostname.lower().lstrip("www.")
    # FIX: hanya 3 mirror paling umum, bukan7 — mengurangi DNS probe overhead
    prefixes = ["cdn", "dl", "mirror"]
    candidates = [hostname]
    seen = {hostname}
    for prefix in prefixes:
        h = f"{prefix}.{hostname}"
        if h not in seen:
            candidates.append(h)
            seen.add(h)
    return candidates


def _build_candidate_urls(original_url: str) -> list[str]:
    """Build full URL candidate dengan mengganti netloc."""
    parsed = urlparse(original_url)
    if not parsed.hostname:
        return [original_url]
    hosts = _candidate_hosts(parsed.hostname)
    candidates = []
    for host in hosts:
        new = parsed._replace(netloc=host)
        candidates.append(urlunparse(new))
    return candidates


def _probe_one(url: str, expected_length: int | None, timeout: float = 3.0) -> dict:
    """Kirim HEAD request ke URL candidate dan ukur latensi.

    SECURITY #13: Validasi bahwa target bukan IP private/loopback.
    FIX: Pakai session tanpa retry supaya DNS failure tidak nunggu 5x backoff.
    """
    # SSRF guard: tolak probe ke host yang resolve ke IP private/loopback.
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if _is_private_or_loopback(host):
            return {"url": url, "ok": False, "latency_ms": 0, "reason": "private/loopback IP rejected"}
    except Exception:
        pass
    # FIX: plain session tanpa retry — mirror probe harus cepat.
    # _build_retry_session() punya 5 retries + backoff = DNS failure makan ~15s.
    session = requests.Session()
    session.headers["User-Agent"] = _USER_AGENT
    start = time.monotonic()
    try:
        resp = session.head(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=timeout,
            allow_redirects=True,
        )
        latency_ms = (time.monotonic() - start) * 1000.0
        if resp.status_code < 200 or resp.status_code >= 400:
            return {"url": url, "ok": False, "latency_ms": latency_ms, "reason": f"status {resp.status_code}"}
        length = int(resp.headers.get("Content-Length", 0))
        # Abaikan jika panjang diketahui dan tidak cocok (kecuali original yang kita toleransi)
        if expected_length and expected_length > 0 and length > 0 and length != expected_length:
            return {"url": url, "ok": False, "latency_ms": latency_ms, "reason": "content-length mismatch"}
        return {
            "url": url,
            "ok": True,
            "latency_ms": latency_ms,
            "content_length": length,
            "accept_ranges": resp.headers.get("Accept-Ranges", "").lower() == "bytes",
            "etag": resp.headers.get("ETag"),
            "digest": resp.headers.get("Digest"),
        }
    except Exception as exc:
        latency_ms = (time.monotonic() - start) * 1000.0
        return {"url": url, "ok": False, "latency_ms": latency_ms, "reason": str(exc)}
    finally:
        try:
            session.close()
        except Exception:
            pass


class MirrorSelector:
    """Pilih URL mirror terbaik dari URL asli."""

    def __init__(self, original_url: str, expected_length: int | None = None, max_workers: int = 6):
        self.original_url = original_url
        self.expected_length = expected_length
        self.max_workers = max_workers
        self._results: list[dict] = []
        self._lock = threading.Lock()

    def select(self) -> tuple[str, list[str]]:
        """Return (best_url, fallback_urls). best_url == original jika tidak ada yang lebih baik."""
        candidates = _build_candidate_urls(self.original_url)
        # Selalu uji original juga.
        if self.original_url not in candidates:
            candidates.insert(0, self.original_url)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(_probe_one, url, self.expected_length): url for url in candidates}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    with self._lock:
                        self._results.append(result)
                except Exception:
                    pass

        # Sort: ok dulu, lalu latency terendah. Original diutamakan jika latency sama.
        ok_results = [r for r in self._results if r.get("ok")]
        ok_results.sort(key=lambda r: (r["latency_ms"], 0 if r["url"] == self.original_url else 1))

        best_url = self.original_url
        fallbacks = []
        if ok_results:
            best_url = ok_results[0]["url"]
            fallbacks = [r["url"] for r in ok_results[1:] if r["url"] != best_url]

        return best_url, fallbacks

    def results(self) -> list[dict]:
        with self._lock:
            return list(self._results)


__all__ = ("MirrorSelector", "_build_candidate_urls")
