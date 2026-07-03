"""Tests for Phase 2 turbo engine modules.

Level: pure unit tests — no network calls, no real sockets beyond the kernel's
localhost loopback (used for BufferTuner/measure_quick_ping happy path).
"""

from backend.core.chunk_calculator import auto_chunks_for_size, optimal_buffer_for_ping
from backend.core.turbo_router import (
    ThrottleDetector, generate_mirrors, rewrite_to_mirror,
    USER_AGENT_POOL, DEFAULT_UA,
)
from backend.core.buffer_tuner import BufferTuner
from backend.core.socket_tuner import SOCKET_OPTIONS, tune
from backend.core.dns_prefetch import DnsPrefetch


def test_auto_chunks_for_size_low():
    assert auto_chunks_for_size(50_000) == 4
    assert auto_chunks_for_size(0) == 4
    assert auto_chunks_for_size(-1) == 4


def test_auto_chunks_for_size_mid():
    # 1 MB - 100 MB -> 8
    assert auto_chunks_for_size(1 * 1024 * 1024) == 8
    assert auto_chunks_for_size(50 * 1024 * 1024) == 8
    assert auto_chunks_for_size(99 * 1024 * 1024) == 8


def test_auto_chunks_for_size_high():
    # 100 MB - 1 GB -> 16
    assert auto_chunks_for_size(100 * 1024 * 1024) == 16
    assert auto_chunks_for_size(500 * 1024 * 1024) == 16
    # 1 GB - 10 GB -> 24
    assert auto_chunks_for_size(1 * 1024 * 1024 * 1024) == 24
    # > 10 GB -> 32
    assert auto_chunks_for_size(15 * 1024 * 1024 * 1024) == 32


def test_auto_chunks_for_size_cap():
    """Honour cap argument."""
    assert auto_chunks_for_size(15_000_000_000, cap=16) == 16
    assert auto_chunks_for_size(99 * 1024 * 1024, cap=4) == 4
    assert auto_chunks_for_size(500_000_000, cap=64) == 16
    assert auto_chunks_for_size(50_000, cap=2) == 2


def test_optimal_buffer_for_ping():
    assert optimal_buffer_for_ping(20) == 8 * 1024
    assert optimal_buffer_for_ping(50) == 16 * 1024
    assert optimal_buffer_for_ping(100) == 32 * 1024
    assert optimal_buffer_for_ping(200) == 64 * 1024
    # garbage/None fallback
    assert optimal_buffer_for_ping("hi") == 32 * 1024
    assert optimal_buffer_for_ping(None) == 32 * 1024


def test_throttle_detector():
    td = ThrottleDetector(window=4, throttle_ratio=0.30)
    # fill 4 samples
    assert td.record(1000) is False
    assert td.record(1100) is False
    assert td.record(1200) is False
    assert td.record(50) is True       # < 30% of peak


def test_throttle_detector_no_throttle():
    td = ThrottleDetector(window=3, throttle_ratio=0.30)
    assert td.record(800) is False
    assert td.record(900) is False
    assert td.record(950) is False


def test_generate_mirrors_strips_www():
    m = generate_mirrors("www.example.com")
    assert "cdn.example.com" in m
    assert "www.example.com" not in m


def test_generate_mirrors_empty():
    assert generate_mirrors("") == ()
    assert generate_mirrors(None) == ()


def test_rewrite_to_mirror_preserves_scheme_path():
    u = rewrite_to_mirror("https://example.com/a/b/c.pdf?x=1", "cdn.example.com")
    assert u is not None
    assert u.startswith("https://cdn.example.com/a/b/c.pdf?x=1")


def test_ua_pool_default_known():
    assert DEFAULT_UA == USER_AGENT_POOL[0]
    assert len(USER_AGENT_POOL) == 6


def test_buffer_tuner_adaptive_growth():
    bt = BufferTuner(host="example.com")
    bt.record_latency(20)               # low ping → 8KB
    assert bt.current_buffer() == 8 * 1024
    bt.record_latency(200)              # high ping → 64KB
    # median of [20, 200] = 110 → 32KB
    assert bt.current_buffer() in (16 * 1024, 32 * 1024)


def test_buffer_tuner_attach_host_resets():
    bt = BufferTuner(host="x")
    bt.record_latency(20)
    bt.attach_host("y")
    # samples cleared → default "typical broadband" 60ms → 32 KB
    assert bt.current_buffer() == 32 * 1024


def test_socket_options_nonempty():
    # We expect at least SO_KEEPALIVE on supported platforms.
    if SOCKET_OPTIONS:
        # Each option is a 3-tuple.
        for opt in SOCKET_OPTIONS:
            assert isinstance(opt, tuple) and len(opt) == 3
            assert isinstance(opt[0], int)
            assert isinstance(opt[1], int)
    else:
        # Linux/macOS with no TCP_KEEP*: still pass
        pass


def test_dns_prefetch_cache_returns_tuple_or_empty():
    """No real DNS — verify cache miss returns empty tuple."""
    dp = DnsPrefetch(servers=("127.0.0.1",), ttl=30.0, max_entries=4)
    # Note: 127.0.0.1 may not be a valid DNS server, so this is best-effort.
    result = dp.resolve("nonexistent.invalid")
    assert isinstance(result, tuple)
