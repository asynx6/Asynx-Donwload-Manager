"""AsynxDL — Security dependency helpers.

Audit-fix 2026 v1.1.0:
    - ``hmac.compare_digest`` untuk token verification (no plain ``==``).
    - Zero-token config never accepted: kalau ``api_secret_token`` kosong/
      auto-placeholder, server menolak request.
    - Token-bytes comparison yang aman terhadap timing attacks.
"""

import hmac

from fastapi import Request, HTTPException

from backend.system.config import load_config


_TOKEN_HEADER = "X-AsynxDL-Token"
_PLACEHOLDER_TOKENS = frozenset({"", "AUTO_GENERATED_ON_FIRST_RUN"})


def _load_real_token() -> str:
    """Muat token config; placeholder dianggap invalid."""
    token = (load_config().get("api_secret_token") or "").strip()
    if not token or token in _PLACEHOLDER_TOKENS:
        return ""
    return token


def verify_token(request: Request) -> None:
    """FastAPI dependency: wajib ada X-AsynxDL-Token valid di header.

    Raises:
        HTTPException(403) jika token missing / invalid / placeholder.
    """
    expected = _load_real_token()
    received = (request.headers.get(_TOKEN_HEADER) or "")
    if not expected or not received:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid Token")
    # Constant-time compare
    if not hmac.compare_digest(expected.encode("utf-8"),
                                received.encode("utf-8")):
        raise HTTPException(status_code=403, detail="Forbidden: Invalid Token")


def verify_token_string(received: str) -> bool:
    """Verify token sebagai string (untuk WebSocket query param)."""
    expected = _load_real_token()
    if not expected or not received:
        return False
    return hmac.compare_digest(expected.encode("utf-8"),
                                received.encode("utf-8"))


__all__: list[str] = ["verify_token", "verify_token_string",
                       "_TOKEN_HEADER", "_load_real_token"]
