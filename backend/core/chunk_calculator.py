"""AsynxDL — Dynamic chunk calculator.

Memilih jumlah chunk simultan yang ideal berdasarkan ukuran file target.

Pseudocode:

    size          chunks   rationale
    -----------------------------------
    <1 MB          4       chunk kecil butuh overhead minimal, parallel ringan
    1 MB-100 MB    8       baseline — seimbang antara connection cost & throughput
    100 MB-1 GB    16      speedup nyata untuk file besar
    1 GB-10 GB     24      saturasi hardware multi-lane (e.g. 8-core)
    >10 GB         32      push bandwidth maksimum untuk file jumbo

Fungsi disimpan murni (no side-effects) supaya deterministik & gampang
dites.
"""

from typing import Tuple


_MB = 1024 * 1024
_GB = 1024 * 1024 * 1024

_RANGES: Tuple[Tuple[int, int, int], ...] = (
    (0,                  1 * _MB,     4),
    (1 * _MB,            100 * _MB,   8),
    (100 * _MB,          1 * _GB,     16),
    (1 * _GB,            10 * _GB,    24),
    (10 * _GB,           float("inf"), 32),
)


def auto_chunks_for_size(size_bytes: int, cap: int = 32) -> int:
    """Kembalikan jumlah chunk simultan yang direkomendasikan untuk file
    seukuran ``size_bytes``. ``cap`` membatasi atasnya (default 32).

    Contoh::

        >>> auto_chunks_for_size(50_000)        # < 1MB → 4
        4
        >>> auto_chunks_for_size(500_000_000)   # 500 MB → 16
        16
        >>> auto_chunks_for_size(15_000_000_000) # 15 GB → 32
        32
    """
    if size_bytes is None or int(size_bytes) <= 0:
        return 4
    size = int(size_bytes)
    picked = 4
    for lower, upper, chunks in _RANGES:
        if lower <= size < upper:
            picked = chunks
            break
    return max(1, min(int(cap), picked))


def optimal_buffer_for_ping(ping_ms: float) -> int:
    """Kembalikan ukuran buffer (bytes) yang direkomendasikan untuk latency
    tersebut.

    | ping_ms        | buffer  |
    |----------------|---------|
    | <30            |  8 KB   |
    | 30-70          | 16 KB   |
    | 70-150         | 32 KB   |
    | >150 or loss   | 64 KB   |
    """
    try:
        p = float(ping_ms)
    except (TypeError, ValueError):
        return 32 * 1024
    if p < 30.0:
        return 8 * 1024
    if p < 70.0:
        return 16 * 1024
    if p < 150.0:
        return 32 * 1024
    return 64 * 1024


__all__: Tuple[str, ...] = ("auto_chunks_for_size", "optimal_buffer_for_ping",)
