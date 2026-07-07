"""AsynxDL — Range Fingerprint & Tamper Detection.

Memverifikasi apakah server benar-benar mendukung byte ranges dengan benar.
Beberapa server mengiklankan "Accept-Ranges: bytes" tapi mengabaikan header
Range (mengembalikan 200 seluruh file). Fingerprint mendeteksi ini dan
menandai URL sebagai "range_unreliable".

Juga mendeteksi "tamper": content-range yang tidak sesuai permintaan, atau
body yang lebih besar dari yang diminta.
"""

import requests

from backend.core.chunk_manager import _build_retry_session, _USER_AGENT


class RangeFingerprint:
    """Fingerprint range support sebenarnya dari server."""

    def __init__(self, url: str):
        self.url = url
        self.supports_range = False
        self.range_unreliable = False
        self.tamper_detected = False

    def probe(self) -> dict:
        """Kirim Range request kecil dan analisis response."""
        session = _build_retry_session()
        headers = {
            "User-Agent": _USER_AGENT,
            "Range": "bytes=0-0",
        }
        try:
            resp = session.get(
                self.url,
                headers=headers,
                timeout=30,
                allow_redirects=True,
                stream=True,
            )
            status = resp.status_code
            content_range = resp.headers.get("Content-Range", "")
            # FIX #16: avoid downloading full body; use Content-Length header
            cl = resp.headers.get("Content-Length", "")
            try:
                length = int(cl) if cl else 0
            except (ValueError, TypeError):
                length = 0

            if status == 206 and content_range:
                # Verifikasi bahwa range benar-benar dimulai dari 0
                if content_range.startswith("bytes 0-"):
                    self.supports_range = True
                else:
                    self.tamper_detected = True
                    self.range_unreliable = True
            elif status == 200:
                # Server mengabaikan Range → fallback single-thread
                self.range_unreliable = True
                if length > 1:
                    self.tamper_detected = True
            else:
                self.range_unreliable = True

            return {
                "status": status,
                "content_range": content_range,
                "body_length": length,
                "supports_range": self.supports_range,
                "range_unreliable": self.range_unreliable,
                "tamper_detected": self.tamper_detected,
            }
        except Exception as exc:
            self.range_unreliable = True
            return {"error": str(exc), "range_unreliable": True}
        finally:
            try:
                session.close()
            except Exception:
                pass


def verify_range_support(url: str) -> dict:
    """Helper cepat untuk cek range support sebenarnya."""
    fp = RangeFingerprint(url)
    return fp.probe()


__all__ = ("RangeFingerprint", "verify_range_support")
