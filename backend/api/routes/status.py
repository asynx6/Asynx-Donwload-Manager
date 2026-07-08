"""
AsynxDL — Status and Health Routes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Health check dan telemetry metrics endpoints.
"""

from fastapi import APIRouter
from backend.api.state import manager

router = APIRouter()


@router.get("/status")
async def status():
    return {"status": "ok", "app": "AsynxDL", "version": "1.0.0"}


@router.get("/health")
async def health():
    metrics = manager.get_metrics()
    return {
        "status": "healthy",
        "app": "AsynxDL",
        "version": "1.0.0",
        "metrics": metrics
    }
