"""
AsynxDL — Status Route
~~~~~~~~~~~~~~~~~~~~~~
Health check endpoint tanpa autentikasi.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def status():
    return {"status": "ok", "app": "AsynxDL", "version": "1.0.0"}
