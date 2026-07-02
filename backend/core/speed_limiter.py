"""
AsynxDL — Speed Limiter Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Implementasi Token Bucket Algorithm untuk membatasi kecepatan download.
Thread-safe via threading.Lock().

Kelas:
    - SpeedLimiter: membatasi byte per detik untuk setiap download task.
"""

import threading
import time


class SpeedLimiter:
    """Token Bucket Speed Limiter.

    Digunakan oleh chunk_manager.py untuk membatasi kecepatan download
    per chunk/task. Bersifat thread-safe.
    """

    def __init__(self, limit_kbps: int = 0):
        """Inisialisasi SpeedLimiter.

        Args:
            limit_kbps: Batas kecepatan dalam KB/s. 0 = unlimited.
        """
        self._lock = threading.Lock()
        self._last_check = time.monotonic()
        self._bytes_since_check = 0
        self._limit_bytes_per_sec = limit_kbps * 1024 if limit_kbps > 0 else 0

    @property
    def limit_kbps(self) -> int:
        """Batas kecepatan saat ini dalam KB/s (0 = unlimited)."""
        return self._limit_bytes_per_sec // 1024 if self._limit_bytes_per_sec else 0

    @limit_kbps.setter
    def limit_kbps(self, value: int):
        """Set batas kecepatan baru dalam KB/s (0 = unlimited).

        Args:
            value: KB/s baru.
        """
        with self._lock:
            self._limit_bytes_per_sec = value * 1024 if value > 0 else 0
            # Reset counter saat limit berubah
            self._last_check = time.monotonic()
            self._bytes_since_check = 0

    def throttle(self, bytes_written: int):
        """Jeda jika kecepatan melebihi batas.

        Method ini harus dipanggil setiap kali chunk data selesai ditulis.
        Jika limit = 0 (unlimited), method langsung return tanpa delay.

        Args:
            bytes_written: Jumlah byte yang baru saja ditulis.
        """
        if self._limit_bytes_per_sec <= 0:
            return

        with self._lock:
            self._bytes_since_check += bytes_written
            now = time.monotonic()
            elapsed = now - self._last_check

            expected_time = self._bytes_since_check / self._limit_bytes_per_sec
            if expected_time > elapsed:
                sleep_duration = expected_time - elapsed
                # Maksimum sleep 5 detik per call untuk responsivitas
                sleep_duration = min(sleep_duration, 5.0)
            else:
                sleep_duration = 0.0
                # Reset counter jika sudah "bayar hutang"
                self._bytes_since_check = 0
                self._last_check = now

        if sleep_duration > 0:
            time.sleep(sleep_duration)
