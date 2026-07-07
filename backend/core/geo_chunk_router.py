"""AsynxDL — Geo Chunk Router.

Jika ada >=2 mirror valid, alokasikan chunk ke mirror berbeda secara
round-robin (atau berdasarkan latensi). `download_chunk` menerima URL override
sehingga chunk 0-3 bisa dari mirror A, chunk 4-7 dari mirror B.
"""

from urllib.parse import urlparse

from backend.core.mirror_selector import MirrorSelector


class GeoChunkRouter:
    """Distribusi chunk download ke beberapa mirror/CDN untuk parallelism."""

    def __init__(self, primary_url: str, fallback_urls: list[str], expected_length: int | None = None):
        self.primary_url = primary_url
        self.fallback_urls = list(fallback_urls or [])
        self.expected_length = expected_length
        self._urls: list[str] = [primary_url]
        self._latencies: dict[str, float] = {}
        self._lock = None  # not needed; read-only after probe

    def probe(self) -> list[str]:
        """Probe all candidate URLs and return the list of valid URLs sorted by latency."""
        all_candidates = [self.primary_url] + self.fallback_urls
        valid = []
        for url in all_candidates:
            try:
                selector = MirrorSelector(url, expected_length=self.expected_length)
                best, _ = selector.select()
                results = selector.results()
                for r in results:
                    if r.get("url") == best and r.get("ok"):
                        self._latencies[best] = r.get("latency_ms", float("inf"))
                        valid.append(best)
                        break
            except Exception:
                pass
        # Sort by latency, primary first if tie
        valid = sorted(set(valid), key=lambda u: (self._latencies.get(u, float("inf")), 0 if u == self.primary_url else 1))
        self._urls = valid or [self.primary_url]
        return self._urls

    def url_for_chunk(self, chunk_index: int, total_chunks: int) -> str:
        """Round-robin assign chunk to a URL."""
        if not self._urls:
            return self.primary_url
        return self._urls[chunk_index % len(self._urls)]

    def urls(self) -> list[str]:
        return list(self._urls)


__all__ = ("GeoChunkRouter",)
