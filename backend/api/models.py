"""AsynxDL — Pydantic v2 models for API.

Audit-fix v1.1.0:
    - ``AnyHttpUrl`` untuk URL (auto-reject malformed schemes + non-http).
    - ``field_validator`` untuk ``save_path``: tolak path traversal
      (``../../``) yang coba keluar dari direktori.
    - Type strict: ``int`` untuk speed limit (auto-cast dengan error jelas).
"""

from typing import Any

from pydantic import BaseModel, AnyHttpUrl, Field, field_validator


def _reject_path_traversal(path: str) -> str:
    """Larang path escape via ``..``, drive prefix tidak aman, atau null byte."""
    if not path:
        return path
    # 1. Tolak null byte
    if "\x00" in path:
        raise ValueError("save_path contains NULL byte")
    # 2. Tolak parent-directory reference (``..`` segments)
    #    Normalisasi dengan os.path.normpath dulu untuk menghindari bypass
    #    lewat ``./../``.
    import os
    normalized = os.path.normpath(path)
    if normalized.split(os.sep).count("..") > 0 or normalized.startswith(".."):
        raise ValueError("save_path contains '..' path traversal")
    # 3. Tolak device paths (Windows): ``\\.\`` dan ``\\?\``
    if path.replace("/", "\\").startswith("\\\\.\\"):
        raise ValueError("save_path references a device")
    if path.replace("/", "\\").startswith("\\\\?\\"):
        raise ValueError("save_path references extended-length path")
    # 4. SECURITY #14: Tolak UNC paths (``\\server\share``) yang bisa
    #    mengakses network share Windows.
    if path.replace("/", "\\").startswith("\\\\"):
        raise ValueError("save_path references a UNC path")
    return path


class AddDownloadRequest(BaseModel):
    """Payload POST /downloads/add."""

    url: AnyHttpUrl = Field(..., description="HTTP(S) URL sumber unduhan")
    filename: str = Field("", description="Override nama file (opsional)")
    save_path: str = Field("",
                            description="Direktori simpan (kosong = default)")
    speed_limit_kbps: int = Field(0, ge=0, le=1_000_000,
                                   description="0 = unlimited")

    @field_validator("save_path")
    @classmethod
    def _safe_save_path(cls, v: str) -> str:
        return _reject_path_traversal(v)

    @field_validator("filename")
    @classmethod
    def _safe_filename(cls, v: str) -> str:
        if not v:
            return v
        if len(v) > 240:
            raise ValueError("filename too long")
        if any(c in v for c in ("\x00", "\r", "\n")):
            raise ValueError("filename contains unsafe control chars")
        # Tolak path traversal pada filename juga (``../../x`` dll).
        import os as _os
        if _os.path.normpath(v).split(_os.sep).count("..") > 0 or _os.path.normpath(v).startswith(".."):
            raise ValueError("filename contains '..' path traversal")
        return v


class DownloadItem(BaseModel):
    """Tipe data balikan untuk listing & singletons endpoint."""

    id: str
    url: str = ""
    filename: str = ""
    save_path: str = ""
    total_size: int = 0
    downloaded_size: int = 0
    status: str = "PENDING"
    speed_kbps: float = 0.0
    percent: float = 0.0
    eta_seconds: int = 0
    graceful_exit: bool = True
    speed_limit_kbps: int = 0
    thread_count: int = 1
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    model_config = {"extra": "ignore"}


class SettingsModel(BaseModel):
    """GET /settings response (mask token)."""

    api_port: int = 58296
    api_secret_token: str = ""
    default_download_path: str = ""
    max_threads_per_download: int = 8
    max_concurrent_downloads: int = 3
    speed_limit_kbps: int = 0
    language: str = "en"
    theme: str = "dark"
    run_on_startup: bool = False
    first_run_completed: bool = False

    model_config = {"extra": "ignore"}


__all__: list[str] = [
    "AddDownloadRequest", "DownloadItem", "SettingsModel",
    "_reject_path_traversal",
]
