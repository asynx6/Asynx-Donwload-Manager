"""AsynxDL — Work Stealer.

Pantau thread pool download. Jika thread selesai lebih cepat, identifikasi chunk
lain yang paling lambat (berdasarkan bytes_done / expected speed). Ambil sub-range
dari chunk lambat dan assign ke thread idle (hanya untuk server yang support Range).

Ini membutuhkan akses ke executor aktif dan metadata chunk. Sederhana: setelah thread
idle, WorkStealer menemukan chunk lambat dan memulai future baru untuk sub-range.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from backend.core.chunk_manager import download_chunk
from backend.core.speed_limiter import SpeedLimiter


class WorkStealer:
    """Work-stealing untuk thread download idle."""

    def __init__(
        self,
        task_id: str,
        base_url: str,
        parts_dir: str,
        limiter: SpeedLimiter,
        stop_event: threading.Event,
        session,
        chunks: list[dict],
        active_futures: list,
        executor: ThreadPoolExecutor | None,
    ):
        self.task_id = task_id
        self.base_url = base_url
        self.parts_dir = parts_dir
        self.limiter = limiter
        self.stop_event = stop_event
        self.session = session
        self.chunks = chunks
        self.active_futures = active_futures
        self.executor = executor

    def maybe_steal(self) -> bool:
        """Cek apakah ada chunk lambat yang bisa di-steal. Return True jika berhasil."""
        if self.stop_event.is_set() or not self.executor:
            return False
        # Temukan chunk yang paling lambat (remaining bytes terbesar)
        slowest = None
        max_remaining = 0
        for chunk in self.chunks:
            idx = chunk["index"]
            start = chunk["start"] + chunk.get("bytes_done", 0)
            end = chunk["end"]
            if start >= end:
                continue
            remaining = end - start + 1
            if remaining > max_remaining:
                max_remaining = remaining
                slowest = chunk

        if slowest is None or max_remaining < 64 * 1024:
            return False

        idx = slowest["index"]
        start = slowest["start"] + slowest.get("bytes_done", 0)
        end = slowest["end"]
        mid = start + (end - start) // 2
        if mid >= end - 1:
            return False

        # Update slowest chunk boundary to cover only first half; create new chunk for second half
        slowest["end"] = mid
        new_chunk = {
            "index": idx,  # we reuse same index with part suffix? Actually we cannot collide.
            "start": mid + 1,
            "end": end,
            "bytes_done": 0,
        }
        # To avoid part file collision, we use a different part filename suffix for stolen chunk.
        part_path = f"{self.parts_dir}/{self.task_id}.part{idx}_steal{int(time.time())}"
        new_chunk["part_path"] = part_path
        self.chunks.append(new_chunk)

        future = self.executor.submit(
            download_chunk,
            url=self.base_url,
            start=new_chunk["start"],
            end=new_chunk["end"],
            part_path=part_path,
            limiter=self.limiter,
            stop_event=self.stop_event,
            session=self.session,
        )
        self.active_futures.append((future, new_chunk))
        return True


__all__ = ("WorkStealer",)
