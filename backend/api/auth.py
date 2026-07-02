"""
AsynxDL — FastAPI Authentication Dependency
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Verifikasi X-AsynxDL-Token di header request.
"""

from fastapi import Request, HTTPException, Depends

from backend.system.config import load_config


async def verify_token(request: Request):
    expected = load_config().get("api_secret_token")
    received = request.headers.get("X-AsynxDL-Token")
    if not received or received != expected:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid Token")


# Dependency alias yang sering digunakan
token_required = Depends(verify_token)
