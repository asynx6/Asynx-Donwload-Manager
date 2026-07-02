"""
AsynxDL — FastAPI Authentication Dependency
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Verifikasi X-AsynxDL-Token di header request.
"""

from fastapi import Request, HTTPException

from backend.system.config import load_config

_TOKEN_HEADER = "X-AsynxDL-Token"


async def verify_token(request: Request):
    """Verify that the request carries the configured secret token.

    Raises:
        HTTPException(403) when token is missing or invalid.
    """
    expected = load_config().get("api_secret_token")
    received = request.headers.get(_TOKEN_HEADER)
    if not received or not expected or received != expected:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid Token")
