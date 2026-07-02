"""
AsynxDL — FastAPI Pydantic Models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Request/response schemas untuk API.
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class AddDownloadRequest(BaseModel):
    url: str
    filename: Optional[str] = Field(default="", max_length=200)
    save_path: Optional[str] = Field(default="", max_length=260)
    speed_limit_kbps: Optional[int] = Field(default=0, ge=0, le=1000000)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v or not v.startswith(("http://", "https://")):
            raise ValueError("URL must be a valid http:// or https:// address")
        return v

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: Optional[str]) -> Optional[str]:
        if v:
            if ".." in v or v.count("/") > 0 or v.count("\\") > 0:
                raise ValueError("Filename cannot contain directory traversal or path separators")
            from backend.core.file_validator import sanitize_filename
            return sanitize_filename(v)
        return v

    @field_validator("save_path")
    @classmethod
    def validate_save_path(cls, v: Optional[str]) -> Optional[str]:
        if v:
            from backend.core.file_validator import normalize_path
            return normalize_path(v)
        return v


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
