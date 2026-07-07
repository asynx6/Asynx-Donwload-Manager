"""AsynxDL — Adaptive Thread Controller.

Mengontrol jumlah thread per download secara dinamis:
    - Mulai dengan 4 thread.
    - Setiap 3 detik, evaluasi kecepatan total.
    - Jika kecepatan stabil atau naik, tambah thread (maks 16, bound config).
    - Jika ada chunk yang gagal berulang, kurangi thread.
    - Perubahan thread diaplikasikan tanpa menghentikan download: split
      chunk yang paling lambat menjadi sub-chunk.

Controller ini berjalan di thread terpisah dan aman terhadap pause/resume
karena selalu memeriksa stop_event sebelum mengubah state.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from backend.core.chunk_manager import download_chunk
from backend.core.speed_limiter import SpeedLimiter


class AdaptiveThreadController:
    """Adaptive thread controller untuk satu DownloadTask."""

    MIN_THREADS = 4
    MAX_THREADS = 16
    CHECK_INTERVAL = 3.0

    def __init__(
        self,
        task_id: str,
        url: str,
        parts_dir: str,
        limiter: SpeedLimiter,
        stop_event: threading.Event,
        session,
        max_threads: int = 16,
        on_change: Callable[[int], None] | None = None,
    ):
        self.task_id = task_id
        self.url = url
        self.parts_dir = parts_dir
        self.limiter = limiter
        self.stop_event = stop_event
        self.session = session
        self.max_threads = max(1, min(max_threads, self.MAX_THREADS))
        self.on_change = on_change

        self._current_threads = self.MIN_THREADS
        self._speed_history: list[float] = []
        self._failure_count = 0
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._stopped = False

    def start(self, current_thread_count: int) -> None:
        """Start monitoring loop."""
        self._current_threads = max(self.MIN_THREADS, min(current_thread_count, self.max_threads))
        self._schedule()

    def stop(self) -> None:
        self._stopped = True
        if self._timer:
            try:
                self._timer.cancel()
            except Exception:
                pass
        self._timer = None

    def feed_speed(self, speed_kbps: float) -> None:
        with self._lock:
            self._speed_history.append(max(0.0, speed_kbps))
            # Keep last 3 samples (~9 seconds)
            self._speed_history = self._speed_history[-3:]

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1

    def _schedule(self) -> None:
        if self._stopped or self.stop_event.is_set():
            return
        self._timer = threading.Timer(self.CHECK_INTERVAL, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def _tick(self) -> None:
        try:
            if self.stop_event.is_set():
                return
            with self._lock:
                if len(self._speed_history) < 2:
                    return
                # Evaluate trend: stable/rising if median of last samples >= previous median
                samples = self._speed_history
                last = samples[-1]
                median = sorted(samples)[len(samples) // 2]

                old = self._current_threads
                if self._failure_count >= 2 and self._current_threads > self.MIN_THREADS:
                    self._current_threads = max(self.MIN_THREADS, self._current_threads - 2)
                    self._failure_count = 0
                elif last >= median * 0.95 and self._current_threads < self.max_threads:
                    # Speed is stable or rising: scale up by 1-2 threads
                    step = 2 if last > median * 1.2 else 1
                    self._current_threads = min(self.max_threads, self._current_threads + step)

                if self._current_threads != old:
                    print(f"[AdaptiveThreadController] task={self.task_id} {old} -> {self._current_threads}")
                    if self.on_change:
                        try:
                            self.on_change(self._current_threads)
                        except Exception:
                            pass
        finally:
            if not self._stopped and not self.stop_event.is_set():
                self._schedule()

    def split_chunk(self, chunk: dict, chunk_index: int, bytes_done: int) -> None:
        """If we scaled up, spawn a sub-chunk to help a slow chunk.

        This is a no-op by default and meant to be overridden by DownloadTask.
        """
        pass


__all__ = ("AdaptiveThreadController",)
