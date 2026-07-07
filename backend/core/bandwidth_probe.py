"""AsynxDL — Bandwidth Probe & Throttle Detector.

Setiap 10 detik, catat kecepatan download total. Deteksi throttle jika
kecepatan turun >50% dari median 30 detik terakhir. Jika throttle terdeteksi,
broadcast event throttle sehingga TurboRouter / MirrorSelector dapat memutuskan
apakah perlu ganti mirror/UA.

Bersih dari efek samping: tidak mengubah state task; hanya membaca dan report.
"""

import threading
import time
from collections import deque
from typing import Callable


class BandwidthProbe:
    """Probe kecepatan per task dan deteksi throttle."""

    # Window sample (detik) dan threshold throttle (50% drop)
    SAMPLE_INTERVAL = 10.0
    WINDOW_SIZE = 3  # 3 x 10 detik = 30 detik
    THROTTLE_THRESHOLD = 0.5

    def __init__(self, on_throttle: Callable[[float, float], None] | None = None):
        self._samples: deque[float] = deque(maxlen=self.WINDOW_SIZE)
        self._lock = threading.Lock()
        self._on_throttle = on_throttle
        self._last_speed = 0.0
        self._throttled = False
        self._timer: threading.Timer | None = None
        self._stopped = False

    def feed(self, speed_kbps: float) -> None:
        """Feed kecepatan terkini (KB/s)."""
        self._last_speed = max(0.0, speed_kbps)

    def start(self) -> None:
        self._schedule()

    def stop(self) -> None:
        self._stopped = True
        if self._timer:
            try:
                self._timer.cancel()
            except Exception:
                pass
        self._timer = None

    def _schedule(self) -> None:
        if self._stopped:
            return
        self._timer = threading.Timer(self.SAMPLE_INTERVAL, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def _tick(self) -> None:
        try:
            with self._lock:
                self._samples.append(self._last_speed)
                if len(self._samples) >= 2:
                    median = sorted(self._samples)[len(self._samples) // 2]
                    if median > 0 and self._last_speed < median * self.THROTTLE_THRESHOLD:
                        self._throttled = True
                        if self._on_throttle:
                            try:
                                self._on_throttle(self._last_speed, median)
                            except Exception:
                                pass
                    else:
                        self._throttled = False
        finally:
            if not self._stopped:
                self._schedule()

    def is_throttled(self) -> bool:
        return self._throttled

    def median(self) -> float:
        with self._lock:
            if not self._samples:
                return 0.0
            return sorted(self._samples)[len(self._samples) // 2]


__all__ = ("BandwidthProbe",)
