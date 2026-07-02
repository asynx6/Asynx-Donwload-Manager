import threading
import time


class SpeedLimiter:
    """Token Bucket Speed Limiter with real-time memory-friendly counters.

    Thread-safe. Uses integer byte counters and short sleeps to avoid
    accumulating large in-memory state for RAM-constrained systems.
    """

    def __init__(self, limit_kbps: int = 0):
        self._lock = threading.Lock()
        self._last_check = time.monotonic()
        self._bytes_since_check = 0
        self._limit_bytes_per_sec = limit_kbps * 1024 if limit_kbps > 0 else 0

    @property
    def limit_kbps(self) -> int:
        return self._limit_bytes_per_sec // 1024 if self._limit_bytes_per_sec else 0

    @limit_kbps.setter
    def limit_kbps(self, value: int):
        with self._lock:
            self._limit_bytes_per_sec = value * 1024 if value > 0 else 0
            self._last_check = time.monotonic()
            self._bytes_since_check = 0

    def throttle(self, bytes_written: int):
        """Pause if throughput exceeds the configured limit.

        Args:
            bytes_written: bytes just written by the caller.
        """
        if bytes_written <= 0:
            return
        if self._limit_bytes_per_sec <= 0:
            return

        with self._lock:
            self._bytes_since_check += bytes_written
            now = time.monotonic()
            elapsed = now - self._last_check
            expected_time = self._bytes_since_check / self._limit_bytes_per_sec
            sleep_duration = 0.0
            if expected_time > elapsed:
                sleep_duration = min(expected_time - elapsed, 5.0)
            else:
                self._bytes_since_check = 0
                self._last_check = now

        if sleep_duration > 0:
            time.sleep(sleep_duration)
