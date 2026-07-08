"""
AsynxDL — Downloads Routes
~~~~~~~~~~~~~~~~~~~~~~~~~~
CRUD endpoint untuk download queue.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.api.models import AddDownloadRequest, DownloadItem
from backend.api.state import manager

router = APIRouter()


@router.post("/add", response_model=DownloadItem)
async def add_download(req: AddDownloadRequest):
    result = manager.start_new(
        url=str(req.url),  # FIX: AnyHttpUrl bukan str — konversi dulu
        filename=req.filename or "",
        save_path=req.save_path or "",
        speed_limit_kbps=req.speed_limit_kbps or 0,
    )
    if "error" in result:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail=result["error"])
    return DownloadItem(**result)


@router.get("", response_model=list[DownloadItem])
async def list_downloads():
    return [DownloadItem(**item) for item in manager.get_all()]


@router.get("/{task_id}", response_model=DownloadItem)
async def get_download(task_id: str):
    item = manager.get_one(task_id)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Task not found")
    return DownloadItem(**item)


@router.patch("/{task_id}/pause")
async def pause_download(task_id: str):
    result = manager.pause(task_id)
    if "error" in result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.patch("/{task_id}/resume")
async def resume_download(task_id: str):
    result = manager.resume(task_id)
    if "error" in result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.delete("/{task_id}")
async def delete_download(
    task_id: str,
    delete_parts: bool = True,
    remove_from_history: bool = False,
):
    """Hapus download active. ``remove_from_history=True`` juga menghapus
    history completed/ kalau task ada di sana."""
    result = manager.delete(
        task_id, delete_parts=delete_parts, remove_from_history=remove_from_history
    )
    if "error" in result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.patch("/{task_id}/remove_history")
async def remove_history(task_id: str, delete_parts: bool = True):
    """Hapus permanen dari history completed/ + bersihkan parts."""
    result = manager.remove_history(task_id, delete_parts=delete_parts)
    if "error" in result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=result["error"])
    return result
