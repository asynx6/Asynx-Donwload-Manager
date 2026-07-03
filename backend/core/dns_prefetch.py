"""AsynxDL — DNS A-record prefetch resolver.

Tujuan: memotong waktu handshake DNS. Kita resolve hostname ke IP melalui
DNS-over-UDP publik (1.1.1.1 / 8.8.8.8) sebelum melakukan HTTPS connection.
Hasil dipasang ke cache (TTL 600 detik) sehingga request kedua untuk hostname
yang sama tidak menambah RTT.

Implementasi: pure stdlib (`socket`, `struct`, `idna`). Tidak butuh
``dnspython`` atau perpustakaan tambahan supaya tetap ringan untuk
RAM 4 GB.
"""

from __future__ import annotations

import os
import socket
import struct
import threading
import time
from collections import OrderedDict
from typing import List, Optional, Tuple


# --------------------------------------------------------------------------- #
# DNS constants
# --------------------------------------------------------------------------- #
_DNS_PORT      = 53
_DEFAULT_SERVERS: Tuple[str, ...] = ("1.1.1.1", "8.8.8.8")
_DEFAULT_TTL   = 600.0   # seconds
_TIMEOUT_SEC   = 1.5
_MAX_ENTRIES   = 512     # bounded LRU cache


def _build_query(hostname: str, query_id: int) -> bytes:
    """Bangun DNS A-record query bytes.

    Layout:
      - Header (12 byte): id, flags, qd=1, an=0, ns=0, ar=0
      - Question: encoded hostname + type=A + class=IN
    """
    header = struct.pack(
        ">HHHHHH",
        query_id,
        0x0100,             # RD=1 (recursion desired)
        1, 0, 0, 0,         # qdcount=1, ancount=0, nscount=0, arcount=0
    )
    qname = b""
    for label in hostname.encode("idna").decode("ascii").split("."):
        if not label:
            continue
        qname += bytes([len(label)]) + label.encode("ascii")
    qname += b"\x00"
    question = qname + struct.pack(">HH", 1, 1)  # QTYPE=A, QCLASS=IN
    return header + question


def _parse_response(resp: bytes) -> List[str]:
    """Parse DNS response, return list of A-record IPv4 strings (max 8).
    Ignore semua record non-A / CNAME-chained (kami stop di A).
    """
    try:
        if len(resp) < 12:
            return []
        _id, flags, qd, an, ns, ar = struct.unpack(">HHHHHH", resp[:12])
        if (flags & 0x8000) == 0:
            return []           # not a response
        if an == 0:
            return []

        offset = 12
        # skip question section
        for _ in range(qd):
            offset = _skip_name(resp, offset)
            offset += 4  # type + class
            if offset > len(resp):
                return []

        results: List[str] = []
        for _ in range(an):
            if offset >= len(resp):
                break
            offset = _skip_name(resp, offset)
            if offset + 10 > len(resp):
                break
            rtype, _rclass, _ttl, rdlen = struct.unpack(">HHIH", resp[offset:offset+10])
            offset += 10
            if rtype == 1 and rdlen == 4:  # A-record
                ip_bytes = resp[offset:offset+4]
                results.append(socket.inet_ntoa(ip_bytes))
                if len(results) >= 8:
                    break
            offset += rdlen
        return results
    except Exception:
        return []


def _skip_name(buf: bytes, offset: int) -> int:
    """Skip DNS name field (with compression).

    Return the offset right after the name field.
    """
    while offset < len(buf):
        length = buf[offset]
        if length == 0:
            return offset + 1
        if (length & 0xC0) == 0xC0:        # pointer
            return offset + 2
        offset += 1 + length
    return offset


def _query_udp(hostname: str, server: str, timeout: float = _TIMEOUT_SEC) -> Optional[List[str]]:
    """Send DNS query over UDP and parse."""
    try:
        ip_addrs = _query(hostname, server, timeout=timeout)
        return ip_addrs
    except Exception:
        return None


def _query(hostname: str, server: str, timeout: float = _TIMEOUT_SEC) -> Optional[List[str]]:
    """Send a single datagram A-record query."""
    query_id = (int(time.time() * 1000) & 0xFFFF) or 1
    payload  = _build_query(hostname, query_id)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        s.sendto(payload, (server, _DNS_PORT))
        try:
            data, _ = s.recvfrom(2048)
        except socket.timeout:
            return None
        ips = _parse_response(data)
        return ips or None


# --------------------------------------------------------------------------- #
# Bounded LRU + TTL cache
# --------------------------------------------------------------------------- #
class _Cache:
    def __init__(self, max_entries: int = _MAX_ENTRIES, ttl: float = _DEFAULT_TTL) -> None:
        self._max = max_entries
        self._ttl = ttl
        self._data: "OrderedDict[str, Tuple[float, Tuple[str, ...]]]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Tuple[str, ...]]:
        now = time.monotonic()
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            ts, value = entry
            if now - ts > self._ttl:
                try:
                    del self._data[key]
                except KeyError:
                    pass
                return None
            # refresh LRU position
            self._data.move_to_end(key)
            return tuple(value)

    def put(self, key: str, value: Tuple[str, ...]) -> None:
        with self._lock:
            self._data[key] = (time.monotonic(), tuple(value))
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)


# --------------------------------------------------------------------------- #
# Public DnsPrefetch — module-level singleton
# --------------------------------------------------------------------------- #
class DnsPrefetch:
    """High-level DNS prefetch utility.

    Pakai::

        ips = DnsPrefetch().resolve("download.example.com")
        if ips:
            host_header_ip = ips[0]
        # urllib3 sockets bind ulang ke IP &
        # ``Host: download.example.com`` tetap dikirim
    """

    def __init__(self, servers: Tuple[str, ...] = _DEFAULT_SERVERS,
                 ttl: float = _DEFAULT_TTL, max_entries: int = _MAX_ENTRIES) -> None:
        self._servers = tuple(servers)
        self._cache = _Cache(max_entries=max_entries, ttl=ttl)

    def resolve(self, hostname: str, use_system_fallback: bool = True) -> Tuple[str, ...]:
        """Return tuple of IPv4 strings for ``hostname``.

        Try cache → upstreams → system resolver (best-effort).
        """
        if not hostname:
            return ()
        # if hostname is literal IPv4, return as-is
        try:
            socket.inet_aton(hostname)
            return (hostname,)
        except OSError:
            pass
        # if literal IPv6
        if ":" in hostname:
            try:
                socket.inet_pton(socket.AF_INET6, hostname)
                return (hostname,)
            except OSError:
                pass

        cached = self._cache.get(hostname)
        if cached:
            return cached

        # try each upstream
        for server in self._servers:
            ips = _query_udp(hostname, server, _TIMEOUT_SEC)
            if ips:
                self._cache.put(hostname, tuple(ips))
                return tuple(ips)

        # last resort: system resolver
        if use_system_fallback:
            try:
                addrinfo = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
                ips: List[str] = []
                for family, _type, _proto, _cn, sockaddr in addrinfo:
                    if family == socket.AF_INET and sockaddr and sockaddr[0] not in ips:
                        ips.append(sockaddr[0])
                        if len(ips) >= 8:
                            break
                if ips:
                    self._cache.put(hostname, tuple(ips))
                    return tuple(ips)
            except Exception:
                pass

        return ()


# Default singleton — created on import
_DEFAULT_PREFETCH: Optional[DnsPrefetch] = None
_DEFAULT_PREFETCH_LOCK = threading.Lock()


def prefetch() -> DnsPrefetch:
    """Return the process-wide DnsPrefetch singleton."""
    global _DEFAULT_PREFETCH
    if _DEFAULT_PREFETCH is None:
        with _DEFAULT_PREFETCH_LOCK:
            if _DEFAULT_PREFETCH is None:
                _DEFAULT_PREFETCH = DnsPrefetch()
    return _DEFAULT_PREFETCH


def resolve_for_url(url: str) -> Tuple[str, ...]:
    """Helper: ambil hostname dari URL dan resolve via DnsPrefetch."""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
        if not host:
            return ()
        return prefetch().resolve(host)
    except Exception:
        return ()


__all__: Tuple[str, ...] = ("DnsPrefetch", "prefetch", "resolve_for_url",)
