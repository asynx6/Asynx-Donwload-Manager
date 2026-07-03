"""AsynxDL — TCP Keep-Alive & Socket Buffer Tuning.

Tujuan: untuk file besar pada jaringan dengan latency tinggi (e.g. server jauh
di luar negeri atau ISP dengan packet loss acak), mempertahankan koneksi TCP
tetap hidup agar tidak perlu melakukan 3-way handshake ulang setiap chunk,
dan membesarkan socket buffer sehingga throughput tidak dibatasi oleh
windowing kernel.

API::

    from backend.core.socket_tuner import tune, SOCKET_OPTIONS
    tune(sock)                       # apply defaults to a single socket
    SOCKET_OPTIONS                   # tuple untuk dikirim ke urllib3

Catatan: aman untuk platform yang tidak mendukung opsi tertentu — kita
try/except AttributeError dan lanjut.
"""

from typing import Iterable, Tuple

try:
    import socket
    from socket import SO_SNDBUF, SO_RCVBUF, SO_KEEPALIVE, IPPROTO_TCP, TCP_KEEPIDLE, TCP_KEEPINTVL, TCP_KEEPCNT, TCP_NODELAY
except Exception:  # pragma: no cover - beberapa OS mungkin tanpa konstanta
    SO_SNDBUF = SO_RCVBUF = SO_KEEPALIVE = None  # type: ignore
    IPPROTO_TCP = None  # type: ignore
    TCP_KEEPIDLE = TCP_KEEPINTVL = TCP_KEEPCNT = TCP_NODELAY = None  # type: ignore


# Default tuning values
_KEEPIDLE_SEC  = 60
_KEEPINTVL_SEC = 10
_KEEPCNT       = 5
_SNDBUF        = 256 * 1024
_RCVBUF        = 256 * 1024


def _build_options() -> Tuple[Tuple[int, int, int], ...]:
    """Kembalikan tuple opsi yang didukung oleh platform ini.

    Digunakan oleh urllib3.HTTPAdapter(pool_connections=...) dan dikonversi
    ke ``urllib3.connectionpool.HTTPConnectionPool`` socket_options.
    """
    opts: list[Tuple[int, int, int]] = []
    if SO_KEEPALIVE is not None:
        opts.append((socket.SOL_SOCKET, SO_KEEPALIVE, 1))
    if IPPROTO_TCP is not None and TCP_NODELAY is not None:
        # Nagle off — kurangi latency untuk chunk kecil.
        opts.append((IPPROTO_TCP, TCP_NODELAY, 1))
    return tuple(opts)


SOCKET_OPTIONS: Tuple[Tuple[int, int, int], ...] = _build_options()


def tune(sock: "socket.socket") -> bool:
    """Apply Keep-Alive & buffer tuning to an existing socket. Return True
    jika berhasil (atau sebagian). Aman memfail silently."""
    try:
        if SO_KEEPALIVE is not None:
            try:
                sock.setsockopt(socket.SOL_SOCKET, SO_KEEPALIVE, 1)
            except Exception:
                pass

        if IPPROTO_TCP is not None and TCP_KEEPIDLE is not None:
            try:
                sock.setsockopt(IPPROTO_TCP, TCP_KEEPIDLE, _KEEPIDLE_SEC)
            except Exception:
                pass
        if IPPROTO_TCP is not None and TCP_KEEPINTVL is not None:
            try:
                sock.setsockopt(IPPROTO_TCP, TCP_KEEPINTVL, _KEEPINTVL_SEC)
            except Exception:
                pass
        if IPPROTO_TCP is not None and TCP_KEEPCNT is not None:
            try:
                sock.setsockopt(IPPROTO_TCP, TCP_KEEPCNT, _KEEPCNT)
            except Exception:
                pass

        if SO_SNDBUF is not None:
            try:
                sock.setsockopt(socket.SOL_SOCKET, SO_SNDBUF, _SNDBUF)
            except Exception:
                pass
        if SO_RCVBUF is not None:
            try:
                sock.setsockopt(socket.SOL_SOCKET, SO_RCVBUF, _RCVBUF)
            except Exception:
                pass

        # Nagle off → latency rendah untuk chunk kecil.
        if IPPROTO_TCP is not None and TCP_NODELAY is not None:
            try:
                sock.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
            except Exception:
                pass

        return True
    except Exception:
        return False


def tcp_options_for_urllib3() -> Iterable[Tuple[int, int, int]]:
    """Return opsi yang dipakai urllib3.HTTPAdapter (i.e.
    ``urllib3.poolmanager.PoolManager(socket_options=...)``).

    urllib3.set_socket_options expects the (level, optname, value) tuple
    with INTEGER values, which is what we already produced above.
    """
    return tuple(SOCKET_OPTIONS)


__all__: Tuple[str, ...] = ("tune", "tcp_options_for_urllib3", "SOCKET_OPTIONS",)
