"""AsynxDL — adaptive buffer tuner.

Menentukan ukuran baca (chunk size per-iter_content) untuk download_chunk()
berdasarkan latency rolling-window ke server target.

Logika:
- Catat latency sample (`record_latency`) setiap kali koneksi baru dibuka
  atau tiap detik.
- Ping rendah  (<30 ms) → buffer kecil (8 KB) → lebih banyak progress tick,
  lebih responsif ke pause/resume.
- Ping menengah (30-150 ms) → buffer 16 / 32 KB.
- Ping tinggi / loss  (>150 ms) → 64 KB agar sekali iter_content mengirim
  banyak payload, mengurangi jumlah syscall & TLS overhead per byte.

Bounded: rolling window MOD 32 sample (deque(maxlen=32)).
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Optional

from .chunk_calculator import optimal_buffer_for_ping


_DEFAULT_WINDOW = 32


class BufferTuner:
    """Adaptive buffer tuner — singleton-style."""

    def __init__(self, host: Optional[str] = None, window_size: int = _DEFAULT_WINDOW) -> None:
        self._host = host or ""
        self._samples: Deque[float] = deque(maxlen=window_size)
        self._lock = threading.Lock()
        self._last_buffer = 32 * 1024    # sensible default

    # ------------------------------------------------------------------ API

    def attach_host(self, host: str) -> None:
        """Reset samples & buffer untuk host baru atau pergantian host."""
        with self._lock:
            if host and host != self._host:
                self._host = host
                self._samples.clear()
            # Reset baseline lookup buffer sehingga caller melihat default 32 KB
            # sampai record_latency() baru dipanggil.
            self._last_buffer = 32 * 1024

    def record_latency(self, ms: float) -> None:
        with self._lock:
            try:
                self._samples.append(float(ms))
            except Exception:
                pass
            median = self._median_locked()
            self._last_buffer = optimal_buffer_for_ping(median)

    def current_buffer(self) -> int:
        with self._lock:
            return int(self._last_buffer)

    def median(self) -> float:
        with self._lock:
            return self._median_locked()

    # ------------------------------------------------------------------ internals

    def _median_locked(self) -> float:
        if not self._samples:
            return 60.0          # default "typical broadband"
        samples = sorted(self._samples)
        n = len(samples)
        if n == 1:
            return samples[0]
        if n % 2 == 1:
            return float(samples[n // 2])
        return float(samples[n // 2 - 1] + samples[n // 2]) / 2.0

    def measure_quick_ping(self, host: Optional[str] = None, port: int = 443, timeout: float = 1.0) -> Optional[float]:
        """Rough TCP-handshake latency measurement (TTSL-like).

        Return latency in milliseconds (None if couldn't measure).
        """
        target = host or self._host
        if not target:
            return None
        import socket as _socket
        t0 = time.perf_counter()
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((target, port))
        except Exception:
            return None
        finally:
            try:
                s.close()
            except Exception:
                pass
        return float((time.perf_counter() - t0) * 1000.0)


__all__: Tuple[str, ...] = ("BufferTuner",)
