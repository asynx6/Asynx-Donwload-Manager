"""AsynxDL — Engine Intelligence tests.

Verifikasi Phase-D engine menghasilkan Plan yang benar untuk 10 strategi.

Test cases:
- AdaptiveThreadDecision: <1MB → 1 thread.
- MirrorSelector: round-robin fallback.
- BandwidthProbe: file <50 MB given suggestion.
- DiskGuard: low disk sets pause_on_low_disk.
- ChecksumVerifier: SHA-256 in metadata_extra turned on.
- IntelligenceEngine integration: defaults applied.
"""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.pardir))
sys.path.insert(0, PROJECT_ROOT)

from backend.core.intelligence import (
    Policy, Plan,
    AdaptiveThreadDecision,
    MirrorSelector,
    BandwidthProbe,
    PreAllocator,
    ChecksumVerifier,
    DiskGuard,
    IntelligenceEngine,
    decision_for,
)


def test_adaptive_threads_small_file():
    plan = Plan()
    AdaptiveThreadDecision().apply(
        Policy(total_size=512 * 1024, max_threads=8), plan)
    assert plan.actual_threads == 1


def test_adaptive_threads_large_file():
    plan = Plan()
    AdaptiveThreadDecision().apply(
        Policy(total_size=200 * 1024 * 1024, max_threads=8), plan)
    assert plan.actual_threads == 8


def test_adaptive_threads_resume_lock():
    plan = Plan()
    AdaptiveThreadDecision().apply(
        Policy(total_size=512, max_threads=8, is_resume=True), plan)
    assert plan.actual_threads == 8


def test_mirror_selector_round_robin():
    sel = MirrorSelector()
    pol = Policy(metadata_extra={"mirrors": [
        "https://cdn1.example.com/x",
        "https://cdn2.example.com/x",
    ]})
    plans = [Plan(), Plan(), Plan()]
    for p in plans:
        sel.apply(pol, p)
    chosen = {p.mirror_url for p in plans if p.mirror_url}
    assert len(chosen) == 2  # two distinct URLs seen across 3 calls


def test_bandwidth_probe_auto_set():
    plan = Plan()
    BandwidthProbe().apply(
        Policy(total_size=20 * 1024 * 1024, speed_limit_kbps=0), plan)
    assert "auto_bandwidth_limit=4MB/s" in plan.notes


def test_bandwidth_probe_no_override():
    plan = Plan()
    BandwidthProbe().apply(
        Policy(total_size=20 * 1024 * 1024, speed_limit_kbps=8192), plan)
    assert "auto_bandwidth_limit=4MB/s" not in plan.notes


def test_preallocator_turns_on():
    plan = Plan()
    PreAllocator().apply(Policy(total_size=10 * 1024 * 1024), plan)
    assert plan.preallocate is True


def test_checksum_verifier_only_when_specified():
    plan = Plan()
    ChecksumVerifier().apply(Policy(metadata_extra={"sha256": "abc"}), plan)
    assert plan.verify_after_merge is True
    plan2 = Plan()
    ChecksumVerifier().apply(Policy(metadata_extra={}), plan2)
    assert plan2.verify_after_merge is False


def test_disk_guard_pause_when_low():
    plan = Plan()
    DiskGuard().apply(Policy(total_size=200 * 1024 * 1024,
                              free_disk_bytes=10 * 1024 * 1024), plan)
    assert plan.pause_on_low_disk is True


def test_engine_full_pipeline_monotonic():
    policy = Policy(total_size=200 * 1024 * 1024, max_threads=8,
                    metadata_extra={
                        "mirrors": ["https://cdn.example.com/y"],
                        "sha256": "deadbeef",
                    },
                    free_disk_bytes=10 * 1024 * 1024)
    plan = decision_for(policy)
    # AdaptiveThreads keeps 8 (file 200MB >> 50MB threshold).
    assert plan.actual_threads == 8
    assert plan.mirror_url.endswith("/y")
    assert plan.verify_after_merge is True
    # 200 MB target + 5% margin = 210 MB; disk only 10 MB → pause_on_low_disk
    assert plan.pause_on_low_disk is True


def test_engine_disable_strategy_individually():
    """Disable AdaptiveThreadDecision ⇒ Plan stays in pre-decision state.

    We verify disable by checking ``adaptive_threads`` note hilang dari
    ``plan.notes`` ketika AdaptiveThreadDecision dimatikan.
    """
    engine = IntelligenceEngine()
    notes_before = engine.decision_for(
        Policy(total_size=70 * 1024 * 1024, max_threads=8)).notes
    engine.enable_strategy("AdaptiveThreadDecision", False)
    notes_after = engine.decision_for(
        Policy(total_size=70 * 1024 * 1024, max_threads=8)).notes
    assert any(n.startswith("adaptive_threads=") for n in notes_before)
    assert not any(n.startswith("adaptive_threads=") for n in notes_after)
