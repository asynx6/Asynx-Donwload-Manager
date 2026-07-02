"""
AsynxDL — FastAPI Pydantic Models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Request/response schemas untuk API.
"""

from typing import Optional
from pydantic import BaseModel, Field


class AddDownloadRequest(BaseModel):
    url: str
    filename: Optional[str] = ""
    save_path: Optional[str] = ""
    speed_limit_kbps: Optional[int] = 0


class DownloadItem(BaseModel):
    id: str
    url: str
    filename: str
    save_path: str
    total_size: int
    downloaded_size: int
    status: str
    graceful_exit: bool
    speed_limit_kbps: int
    thread_count: int
    chunks: list
    created_at: str
    updated_at: str
    speed_kbps: float = 0.0
    eta_seconds: int = 0
    percent: float = 0.0


class SettingsModel(BaseModel):
    app_version: Optional[str] = "1.0.0"
    api_port: Optional[int] = 58296
    api_secret_token: Optional[str] = ""
    default_download_path: Optional[str] = ""
    max_threads_per_download: Optional[int] = Field(8, ge=1, le=8)
    max_concurrent_downloads: Optional[int] = Field(3, ge=1, le=5)
    speed_limit_kbps: Optional[int] = 0
    language: Optional[str] = "en"
    theme: Optional[str] = "light"
    run_on_startup: Optional[bool] = False
    first_run_completed: Optional[bool] = True


class ProgressPayload(BaseModel):
    id: str
    status: str
    speed_kbps: float
    percent: float
    downloaded_size: int
    eta_seconds: int
