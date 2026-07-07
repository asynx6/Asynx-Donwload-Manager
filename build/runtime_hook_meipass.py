"""PyInstaller runtime hook — wipe stale ``_MEI*`` orphan dirs SEBELUM
bootloader extract bundle ke temp.

Context
-------
Setiap kali ``AsynxDL.exe`` jalan, bootloader membuat tmp directory
bernama ``_MEI<hash>`` di ``%TEMP%`` (Windows) atau ``/tmp`` dan extract
bundle di situ. Setelah restart (subprocess.Popen dari RestartDialog,
kasus Windows yang paling sering), proses baru kadang collision dengan
``_MEI*`` lama yang masih lock/terbuka sehingga bootloader gagal extract:

    FileNotFoundError: [Errno 2] No such file or directory:
        'C:\\Users\\asynx\\AppData\\Local\\Temp\\_MEI113562\\base_library.zip'

Solusi
------
Runtime hook ini berjalan __sebelum__ user code. Ia menghapus orphan
``_MEI*`` dir yang bukan dir process ini sendiri (``sys._MEIPASS``) dan
bukan yang baru dibuat oleh bootloader saat ini. Untuk dir yang locked,
dicoba rename dulu ke ``_MEI<hash>.old.<pid>`` lalu dihapus.

Idempoten + best-effort. Fokus di Windows (di mana ``_MEI*`` dipakai).
"""
import os
import sys
import time
import shutil


def _is_windows() -> bool:
    return sys.platform == "win32"


def _is_meipass_alive(path: str, now: float) -> bool:
    """Return True kalau directory di-create dalam 2 detik terakhir."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return False
    return (now - mtime) < 2.0


def _try_remove(path: str) -> bool:
    """Hapus directory. Jika locked, coba rename dulu ke *.old.<pid>."""
    try:
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.exists(path):
            return True
    except Exception:
        pass

    try:
        parent = os.path.dirname(path)
        name = os.path.basename(path)
        new_name = f"{name}.old.{os.getpid()}.{int(time.time())}"
        new_path = os.path.join(parent, new_name)
        os.rename(path, new_path)
        shutil.rmtree(new_path, ignore_errors=True)
        return not os.path.exists(new_path)
    except Exception:
        return False


def _wipe_stale_meipass(temp_dir: str) -> int:
    """Hapus orphan ``_MEI*`` dirs di ``temp_dir``."""
    removed = 0
    try:
        entries = os.listdir(temp_dir)
    except OSError:
        return 0
    meipass_self = getattr(sys, "_MEIPASS", None)
    now = time.time()
    for name in entries:
        if not (name.startswith("_MEI") or name.startswith("_MEI_")):
            continue
        full = os.path.join(temp_dir, name)
        if not os.path.isdir(full):
            continue
        if meipass_self and os.path.normpath(full) == os.path.normpath(meipass_self):
            continue
        if _is_meipass_alive(full, now):
            continue
        if _try_remove(full):
            removed += 1
    return removed


def main() -> None:
    if not _is_windows():
        return
    if not getattr(sys, "frozen", False):
        return
    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
    if not temp_dir or not os.path.isdir(temp_dir):
        return

    # Jika ini adalah child process hasil restart, beri waktu parent
    # lama selesai/ter-terminate agar _MEI lama bisa dibersihkan.
    if os.environ.get("ASYNXDL_RESTART_CHILD"):
        time.sleep(0.25)
    else:
        os.environ["ASYNXDL_RESTART_CHILD"] = "1"

    try:
        _wipe_stale_meipass(temp_dir)
    except Exception:
        pass


main()
