"""AsynxDL — Turbo Router (UA rotation + mirror rotation + throttle detect).

Tujuan: kalau server target mulai throttle (bandwidth tiba-tiba turun
ke <30 % dari median 3 detik terakhir), kita otomatis:
    1. Rotasi User-Agent ke string berikutnya dari pool.
    2. Coba hostname cermin umum (cdn.<host>, edge.<host>, mirror.<host>,
       dll) supaya request sampai ke Server berbeda.

Pool UA berisi 6 string yang umum-diterima server. Pool mirror dibangun
deterministik dari hostname asli.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, List, Optional, Tuple
from urllib.parse import urlparse


# --------------------------------------------------------------------------- #
# User-Agent pool
# --------------------------------------------------------------------------- #
USER_AGENT_POOL: Tuple[str, ...] = (
    # Chrome on Windows 11
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) "
    "Gecko/20100101 Firefox/128.0",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    # Chrome on Android (mobile)
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    # curl-like (calendar-friendly)
    "curl/8.7.1",
)

DEFAULT_UA = USER_AGENT_POOL[0]


# --------------------------------------------------------------------------- #
# Throttle detector
# --------------------------------------------------------------------------- #
class ThrottleDetector:
    """Deteksi throttle dengan rolling-window bandwidth.

    Pendekatan: track byte-windowing callbacks.
    """
    def __init__(self, window: int = 6, throttle_ratio: float = 0.30) -> None:
        self._samples: Deque[float] = deque(maxlen=window)
        self._ratio = throttle_ratio
        self._throttled = False
        self._lock = threading.Lock()

    def record(self, kbps: float) -> bool:
        """Catat sample kecepatan. Return True jika throttled."""
        with self._lock:
            try:
                if float(kbps) > 0:
                    self._samples.append(float(kbps))
            except Exception:
                pass
            if len(self._samples) < 3:
                return False
            peak = max(self._samples)
            current = self._samples[-1]
            self._throttled = current < (peak * self._ratio)
            return self._throttled

    @property
    def is_throttled(self) -> bool:
        with self._lock:
            return self._throttled

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()
            self._throttled = False


# --------------------------------------------------------------------------- #
# Mirror hostname rotation
# --------------------------------------------------------------------------- #

# Templates for mirror hostnames. ``{host}`` replaced with the original host
# (sans leading "www." etc.).
_MIRROR_TEMPLATES: Tuple[str, ...] = (
    "cdn.{host}",
    "edge.{host}",
    "mirror.{host}",
    "cdn2.{host}",
    "dl.{host}",
    "static.{host}",
)


def _strip_www(host: str) -> str:
    if host.startswith("www."):
        return host[4:]
    return host


def generate_mirrors(host: str) -> Tuple[str, ...]:
    """Return candidate mirror hostnames derived from ``host``.

    Note: hasil tidak dijamin valid (server asli bisa tidak punya mirror),
    tapi caller dapat mencoba fallback satu-per-satu.
    """
    host_clean = _strip_www(host or "")
    if not host_clean:
        return ()
    mirrors: List[str] = []
    for tpl in _MIRROR_TEMPLATES:
        candidate = tpl.format(host=host_clean)
        if candidate and candidate not in mirrors:
            mirrors.append(candidate)
    return tuple(mirrors)


def rewrite_to_mirror(url: str, mirror_host: str) -> Optional[str]:
    """Replace host portion of ``url`` with ``mirror_host``."""
    try:
        parts = urlparse(url)
        if not parts.scheme or not parts.netloc:
            return None
        # preserve port
        original_host = parts.hostname or ""
        port = parts.port
        new_netloc = mirror_host
        if port:
            new_netloc = f"{mirror_host}:{port}"
        # reconstruct
        from urllib.parse import urlunparse
        return urlunparse((parts.scheme,
                           new_netloc,
                           parts.path,
                           parts.params,
                           parts.query,
                           parts.fragment))
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# UA rotator (module-level, thread-safe)
# --------------------------------------------------------------------------- #
class UaRotator:
    """Cycle through USER_AGENT_POOL deterministically per host."""

    def __init__(self, hosts: Optional[List[str]] = None) -> None:
        self._idx: dict[str, int] = {h: 0 for h in hosts or []}
        self._lock = threading.Lock()

    def next_for_host(self, host: str) -> str:
        with self._lock:
            idx = self._idx.get(host, 0)
            ua = USER_AGENT_POOL[idx % len(USER_AGENT_POOL)]
            self._idx[host] = idx + 1
            return ua

    def rotate(self, host: str) -> str:
        return self.next_for_host(host)


# --------------------------------------------------------------------------- #
# TurboRouter (top-level)
# --------------------------------------------------------------------------- #
class TurboRouter:
    """Combines throttle-detect + UA rotation + mirror rotation."""

    def __init__(self, host: Optional[str] = None) -> None:
        self._host = host or ""
        self._throttle = ThrottleDetector()
        self._mirrors_list: Tuple[str, ...] = generate_mirrors(self._host) if self._host else ()
        self._mirror_idx: int = 0
        self._ua = UaRotator([self._host] if self._host else [])
        self._lock = threading.Lock()

    def attach_host(self, host: str) -> None:
        with self._lock:
            self._host = host
            self._mirrors_list = generate_mirrors(host)
            self._mirror_idx = 0
            self._throttle.reset()

    def record_speed(self, kbps: float) -> bool:
        """Return True if throttled."""
        return self._throttle.record(kbps)

    @property
    def is_throttled(self) -> bool:
        return self._throttle.is_throttled

    def next_user_agent(self) -> str:
        return self._ua.rotate(self._host or "_")

    def next_mirror(self) -> Optional[str]:
        with self._lock:
            if not self._mirrors_list:
                return None
            if self._mirror_idx >= len(self._mirrors_list):
                return None
            mirror = self._mirrors_list[self._mirror_idx]
            self._mirror_idx += 1
            return mirror

    def reset(self) -> None:
        with self._lock:
            self._mirror_idx = 0
            self._throttle.reset()


__all__: Tuple[str, ...] = (
    "USER_AGENT_POOL", "DEFAULT_UA",
    "ThrottleDetector", "UaRotator",
    "generate_mirrors", "rewrite_to_mirror",
    "TurboRouter",
)
