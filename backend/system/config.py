"""
AsynxDL — System Configuration Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Manajemen konfigurasi aplikasi: load/save config.
"""

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = {
    "app_version": "1.0.0",
    "api_port": 58296,
    "default_download_path": os.path.expandvars("%USERPROFILE%\\Downloads"),
    "max_threads_per_download": 8,
    "max_concurrent_downloads": 3,
    "speed_limit_kbps": 0,
    "language": "en",
    "theme": "dark",
    "run_on_startup": False,
    "first_run_completed": False,
}


def _config_dir() -> Path:
    r"""Return direktori konfigurasi aplikasi (%APPDATA%\AsynxDL)."""
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    return Path(os.path.expandvars(appdata)) / "AsynxDL"


def _config_path() -> Path:
    return _config_dir() / "config.json"





def load_config() -> dict[str, Any]:
    """Load config.json, create with defaults if missing."""
    path = _config_path()
    if not path.exists():
        config = DEFAULT_CONFIG.copy()
        return config

    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError):
        config = DEFAULT_CONFIG.copy()
        return config

    # Merge dengan default untuk field baru
    merged = DEFAULT_CONFIG.copy()
    merged.update(config)
    # Pastikan path default selalu di-resolve
    merged["default_download_path"] = os.path.expandvars(
        os.path.expanduser(merged.get("default_download_path", DEFAULT_CONFIG["default_download_path"]))
    )
    return merged


def save_config(config: dict[str, Any]) -> bool:
    """Simpan config ke disk secara atomic.

    Returns True jika sukses. Best-effort swallow OSError; caller bisa
    membatalkan aksi kalau return False.
    """
    try:
        _config_dir().mkdir(parents=True, exist_ok=True)
        path = _config_path()
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return True
    except OSError as exc:
        try:
            os.remove(tmp)
        except (FileNotFoundError, UnboundLocalError):
            pass
        print(f"[Config] save failed: {exc}")
        return False
    except Exception as exc:
        print(f"[Config] unexpected save failure: {exc}")
        return False


def update_config(**kwargs) -> dict[str, Any] | None:
    """Update beberapa field config dan simpan. None jika save gagal."""
    config = load_config()
    config.update(kwargs)
    if not save_config(config):
        return None
    return config


def is_first_run() -> bool:
    try:
        return not load_config().get("first_run_completed", False)
    except Exception:
        return False


def mark_first_run_completed() -> bool:
    return bool(update_config(first_run_completed=True))
