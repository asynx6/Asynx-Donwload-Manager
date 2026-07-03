"""
AsynxDL — Parts Directory Helper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Utilitas untuk direktori .parts di %LOCALAPPDATA%\\AsynxDL\\.parts.

Tujuan:
- Beri satu source of truth untuk path parts directory.
- Beri fungsi purge_all_parts_for(task_id) yang membersihkan
  semua file .{task_id}.partN dan .{task_id}.final, termasuk yang
  orphan (task_id metadata hilang / corrupt).
- Beri purge_all_orphans(max_age_days) untuk maintenance berkala.

Karena alasan berikut, helper ini diekstrak dari backend.core.downloader
ke modul terpisah:
- downloader.py fokus pada orchestration per task.
- cleanup logic butuh dipakai dari manager/state layer juga.
"""

import glob
import os
import time
from typing import Optional


# AsynxDL application cache directory under %LOCALAPPDATA%
_APP_LOCAL_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "AsynxDL"
)


def _ensure_app_local_dir() -> str:
    os.makedirs(_APP_LOCAL_DIR, exist_ok=True)
    return _APP_LOCAL_DIR


def get_parts_dir() -> str:
    """Return path absolut ke folder .parts (otomatis dibuat dan hidden
    di Windows).

    Folder ini sementara dipakai untuk menyimpan chunk files saat
    download berlangsung; setelah merge berhasil, chunk dihapus dan
    file final dipindah ke save_path user.
    """
    _ensure_app_local_dir()
    parts_dir = os.path.join(_APP_LOCAL_DIR, ".parts")
    os.makedirs(parts_dir, exist_ok=True)
    try:
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(parts_dir, 0x02)
    except Exception:
        pass
    return parts_dir


def purge_all_parts_for(task_id: str, parts_dir: Optional[str] = None) -> int:
    """Hapus semua .{task_id}.partN dan .{task_id}.final.

    Returns jumlah file yang berhasil dihapus. Aman untuk file yang
    sudah tidak ada (tidak lempar OSError).
    """
    if not task_id or len(task_id) > 80:
        return 0
    target_dir = parts_dir or get_parts_dir()
    removed = 0

    # Part files: pattern .{task_id}.part0, .{task_id}.part1, ...
    for part in glob.glob(os.path.join(target_dir, f".{task_id}.part*")):
        try:
            os.remove(part)
            removed += 1
        except OSError:
            pass

    # Compatibility: juga hapus {task_id}.part* (tanpa leading dot)
    for part in glob.glob(os.path.join(target_dir, f"{task_id}.part*")):
        try:
            os.remove(part)
            removed += 1
        except OSError:
            pass

    # File final sementara
    for final_name in (f".{task_id}.final", f"{task_id}.final"):
        path = os.path.join(target_dir, final_name)
        try:
            os.remove(path)
            removed += 1
        except FileNotFoundError:
            pass
        except OSError:
            pass

    return removed


def purge_all_orphans(max_age_days: int = 14, parts_dir: Optional[str] = None) -> int:
    """Hapus .part/.final orphan yang lebih tua dari ``max_age_days``.

    Orphan = file di .parts/ yang task_id-nya tidak punya metadata di
    data/queue/completed/ maupun data/queue/*.json. Dipakai saat
    uninstall atau maintenance.

    Returns jumlah file yang dihapus.
    """
    target_dir = parts_dir or get_parts_dir()
    if not os.path.isdir(target_dir):
        return 0
    cutoff = time.time() - (max_age_days * 86400)
    removed = 0
    for entry in os.listdir(target_dir):
        path = os.path.join(target_dir, entry)
        try:
            if not os.path.isfile(path):
                continue
            mtime = os.path.getmtime(path)
            if mtime > cutoff:
                continue
            os.remove(path)
            removed += 1
        except OSError:
            pass
    return removed
