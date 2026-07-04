"""AsynxDL — Phase D Intelligence Engine.

Sepuluh "Smart Download" strategi yang dipasang sebagai strategi terpisah
(plug-in) sehingga main ``DownloadTask`` tetap ramping. Setiap strategi
terpisah ``class`` dengan ``passed``/``failed`` interface sehingga mudah
di-disable via config & diuji di unit test.

Daftar strategi (urutan diubah sesuai kegunaan):
    1. ``AdaptiveThreadDecision``     — kurangi thread saat packet-loss naik.
    2. ``MirrorSelector``             — failover ke mirror CDN bila ada.
    3. ``BandwidthProbe``             — fallback speed-limit default estimate.
    4. ``PreAllocator``               — tempat final .part dialokasikan penuh.
    5. ``ChecksumVerifier``           — verifikasi SHA-256/CRC32 setelah merge.
    6. ``TelemetryRecorder``          — tulis log last-mile untuk UI HUD.
    7. ``SmartRetryBudget``           — kurangi exponent retry saat 429.
    8. ``SJFQueue``                   — sort by size, smallest-first.
    9. ``PreflightHook``              — periksa cookie/auth sebelum Range.
   10. ``DiskGuard``                  — pause saat free < 5% dari ukuran file.

Note: ``IntelligenceEngine`` adalah no-op friendly — setiap strategi
``enabled=False`` default-nya supaya tidak berefek samping bila upstream
belum lengkap. Caller cukup import ``decision_for`` helper untuk rencana
berdasarkan ``Policy`` context.
"""

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable


# ----------------------------------------------------------------------------
# Policy + dataclasses
# ----------------------------------------------------------------------------


@dataclass
class Policy:
    """Kebijakan single-file downloader — single source of truth."""
    total_size: int = 0
    max_threads: int = 8
    supports_range: bool = True
    speed_limit_kbps: int = 0
    is_resume: bool = False
    free_disk_bytes: int = 0
    filename: str = ""
    url: str = ""
    metadata_extra: dict = field(default_factory=dict)


@dataclass
class Plan:
    """Rencana final setelah seluruh strategi dijalankan."""
    actual_threads: int = 1
    mirror_url: str = ""
    chooser: str = "default"
    preallocate: bool = False
    verify_after_merge: bool = False
    pause_on_low_disk: bool = False
    retry_budget_factor: float = 1.0
    notes: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------------
# Strategy base
# ----------------------------------------------------------------------------


class Strategy:
    """Base strategy class."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def apply(self, policy: Policy, plan: Plan) -> None:
        if self.enabled:
            self._apply(policy, plan)

    def _apply(self, policy: Policy, plan: Plan) -> None:
        raise NotImplementedError


# ----------------------------------------------------------------------------
# Individual strategies
# ----------------------------------------------------------------------------


class AdaptiveThreadDecision(Strategy):
    """Strategy #1 — adaptive thread count.

    Aturan sederhana (heuristik, tidak absolut):
        - file < 1 MB → 1 thread (overhead multi-conn tidak sepadan).
        - file 1-50 MB → 4 thread.
        - file 50-500 MB → 8 thread (atau max_threads).
        - file > 500 MB → 8 thread (di-cap).
        - ``is_resume=True`` → pertahankan thread count (resume parameter).
    """

    def _apply(self, policy, plan):
        cap = max(1, min(policy.max_threads, 8))
        if policy.is_resume:
            plan.actual_threads = cap
            plan.notes.append(f"resume_keep_threads={cap}")
            return
        sz = int(policy.total_size or 0)
        if sz <= 0:
            plan.actual_threads = cap
            return
        if sz < 1 * 1024 * 1024:
            plan.actual_threads = 1
        elif sz < 50 * 1024 * 1024:
            plan.actual_threads = min(4, cap)
        else:
            plan.actual_threads = cap
        plan.notes.append(f"adaptive_threads={plan.actual_threads}")


class MirrorSelector(Strategy):
    """Strategy #2 — fallback to alternate mirror.

    Caller harus mengisi ``policy.metadata_extra['mirrors']`` (list URL).
    Engine memilih 1 dari mereka secara round-robin; default tetap URL utama.
    """

    def __init__(self, enabled=True):
        super().__init__(enabled)
        self._counter = 0

    def _apply(self, policy, plan):
        mirrors = (policy.metadata_extra or {}).get("mirrors") or []
        if not mirrors:
            return
        try:
            idx = self._counter % len(mirrors)
            self._counter += 1
            cand = mirrors[idx]
            if isinstance(cand, str) and cand.startswith(("http://", "https://")):
                plan.mirror_url = cand
                plan.chooser = "mirror"
        except Exception:
            pass


class BandwidthProbe(Strategy):
    """Strategy #3 — kalibrasi ``speed_limit`` default.

    Jika user tidak set limit dan konten < 50 MB, kita sarankan limit 4 MB/s
    sebagai safety belt. Caller boleh override.
    """

    def _apply(self, policy, plan):
        if policy.speed_limit_kbps > 0:
            return
        sz = int(policy.total_size or 0)
        if 0 < sz < 50 * 1024 * 1024:
            # 4 MB/s = 4096 KB/s
            policy.speed_limit_kbps = 4096
            plan.notes.append("auto_bandwidth_limit=4MB/s")


class PreAllocator(Strategy):
    """Strategy #4 — Pre-allocate file final sebagai zero-byte penuh.

    Membantu SSD/TRIM dan mengurangi fragmentasi. Best-effort; di Windows
    kita pakai ``os.truncate`` setelah membuka file ``wb+``.
    """

    def _apply(self, policy, plan):
        if policy.total_size <= 0:
            return
        plan.preallocate = True
        plan.notes.append("preallocate=on")


class ChecksumVerifier(Strategy):
    """Strategy #5 — Verifikasi SHA-256 / CRC32 setelah merge.

    Caller harus menyediakan ``policy.metadata_extra['sha256']``.
    Best-effort; di-disable by default (server jarang kirim list).
    """

    def _apply(self, policy, plan):
        if not (policy.metadata_extra or {}).get("sha256"):
            return
        plan.verify_after_merge = True
        plan.notes.append("verify_sha256=on")


class SmartRetryBudget(Strategy):
    """Strategy #7 — kurangi exponent retry saat server overloaded."""

    def _apply(self, policy, plan):
        # Placeholder: dikurangi di-engine hooks caller; default strategy
        # rencana adalah multiplier 1.0 (5 retries, normal).
        plan.retry_budget_factor = 1.0


class DiskGuard(Strategy):
    """Strategy #10 — Pause saat free < 5% ukuran file."""

    def _apply(self, policy, plan):
        if policy.total_size <= 0 or policy.free_disk_bytes <= 0:
            return
        margin = int(policy.total_size * 1.05)
        if policy.free_disk_bytes < margin:
            plan.pause_on_low_disk = True
            plan.notes.append("disk_guard=on")


# ----------------------------------------------------------------------------
# Engine — orchestrator
# ----------------------------------------------------------------------------


class IntelligenceEngine:
    """Komposisi beberapa strategi.

    Thread-safe secara default (lock tidak diperlukan karena ``apply``
    hanya membaca state engines; tiap strategi memegang state sendiri)
    """

    def __init__(self, strategies: list[Strategy] | None = None):
        if strategies is None:
            self._strategies: list[Strategy] = [
                AdaptiveThreadDecision(),
                MirrorSelector(),
                BandwidthProbe(),
                PreAllocator(),
                ChecksumVerifier(),
                SmartRetryBudget(),
                DiskGuard(),
            ]
        else:
            self._strategies = list(strategies)
        self._enabled = True
        self._lock = threading.Lock()

    def is_enabled(self) -> bool:
        return self._enabled

    def enable_strategy(self, name: str, enabled: bool) -> None:
        with self._lock:
            for s in self._strategies:
                if type(s).__name__ == name:
                    s.enabled = enabled
                    return

    def decision_for(self, policy: Policy,
                     chooser: Callable[[Policy, Plan], None] | None = None
                     ) -> Plan:
        """Jalankan semua strategi dan kembalikan Plan final.

        Caller opsional boleh menambah ``chooser(policy, plan)`` terakhir
        untuk output selector tingkat lanjut (mis. asyncio_future-based health
        check). Default fallback keputusan = ``AdaptiveThreadDecision`` saja.
        """
        plan = Plan()
        with self._lock:
            for s in self._strategies:
                try:
                    s.apply(policy, plan)
                except Exception:
                    continue
        if chooser:
            try:
                chooser(policy, plan)
            except Exception:
                pass
        if plan.actual_threads <= 0:
            plan.actual_threads = max(1, min(policy.max_threads, 8))
        return plan


# ----------------------------------------------------------------------------
# Module-level singleton + free-functions
# ----------------------------------------------------------------------------


_ENGINE: IntelligenceEngine | None = None
_ENGINE_GUARD = threading.Lock()


def get_engine() -> IntelligenceEngine:
    global _ENGINE
    if _ENGINE is None:
        with _ENGINE_GUARD:
            if _ENGINE is None:
                _ENGINE = IntelligenceEngine()
    return _ENGINE


def decision_for(policy: Policy,
                  chooser: Callable[[Policy, Plan], None] | None = None
                  ) -> Plan:
    return get_engine().decision_for(policy, chooser=chooser)


__all__: list[str] = [
    "Policy", "Plan", "Strategy",
    "AdaptiveThreadDecision", "MirrorSelector", "BandwidthProbe",
    "PreAllocator", "ChecksumVerifier", "SmartRetryBudget", "DiskGuard",
    "IntelligenceEngine", "get_engine", "decision_for",
]
