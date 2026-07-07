"""AsynxDL — Global Download Scheduler & Bandwidth Fairness.

Mengelola alokasi bandwidth global antar task download yang aktif.
Jika user mengatur "global speed limit", scheduler membagi limit tersebut
secara merata (max-min fairness) ke task yang sedang DOWNLOADING.

Juga menyediakan task priority: task dengan priority lebih tinggi mendapat
weight lebih besar.
"""

import threading
from typing import Dict


class DownloadScheduler:
    """Global scheduler untuk bandwidth fairness antar task."""

    def __init__(self, global_limit_kbps: int = 0):
        self._global_limit_kbps = max(0, global_limit_kbps)
        self._task_limits: Dict[str, int] = {}
        self._task_priorities: Dict[str, int] = {}
        self._lock = threading.Lock()

    def set_global_limit(self, kbps: int) -> None:
        with self._lock:
            self._global_limit_kbps = max(0, kbps)
            self._recompute()

    def register_task(self, task_id: str, priority: int = 5) -> None:
        with self._lock:
            self._task_priorities[task_id] = max(1, min(priority, 10))
            self._recompute()

    def unregister_task(self, task_id: str) -> None:
        with self._lock:
            self._task_priorities.pop(task_id, None)
            self._task_limits.pop(task_id, None)
            self._recompute()

    def _recompute(self) -> None:
        if not self._global_limit_kbps:
            self._task_limits = {tid: 0 for tid in self._task_priorities}
            return

        total_weight = sum(self._task_priorities.values())
        if total_weight == 0:
            self._task_limits = {tid: 0 for tid in self._task_priorities}
            return

        # Weighted fair share
        allocated: Dict[str, int] = {}
        for tid, weight in self._task_priorities.items():
            share = int(self._global_limit_kbps * (weight / total_weight))
            allocated[tid] = max(1, share)

        # Reconcile rounding so sum <= global limit
        total = sum(allocated.values())
        if total > self._global_limit_kbps:
            excess = total - self._global_limit_kbps
            # reduce from lowest priority tasks first
            for tid in sorted(allocated, key=lambda t: self._task_priorities[t]):
                if excess <= 0:
                    break
                reducible = allocated[tid] - 1
                take = min(reducible, excess)
                allocated[tid] -= take
                excess -= take

        self._task_limits = allocated

    def limit_for_task(self, task_id: str) -> int:
        with self._lock:
            return self._task_limits.get(task_id, 0)

    def priorities(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._task_priorities)

    def set_priority(self, task_id: str, priority: int) -> None:
        with self._lock:
            if task_id in self._task_priorities:
                self._task_priorities[task_id] = max(1, min(priority, 10))
                self._recompute()


# Singleton scheduler untuk seluruh aplikasi
_default_scheduler = DownloadScheduler()


def get_scheduler() -> DownloadScheduler:
    return _default_scheduler


__all__ = ("DownloadScheduler", "get_scheduler")
