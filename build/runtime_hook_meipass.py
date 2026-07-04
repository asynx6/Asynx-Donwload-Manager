"""PyInstaller runtime hook — wipe stale ``_MEI*`` orphan dirs SEBELUM
bootloader extract bundle ke temp.

Context
-------
Setiap kali ``AsynxDL.exe`` jalan, bootloader membuat tmp directory
bernama ``_MEI<hash>`` di ``%TEMP%`` (Windows) atau ``/tmp`` dan extract
bundle di situ. Setelah ``os.execv(sys.executable, ...)`` (Restart Now
di RestartDialog, kasus Windows yang paling sering), 1 proses python
berganti menjadi 1 proses ``AsynxDL.exe`` baru. Bootloader baru akan
membuat hash baru — NAMUN Windows tempfile / OS kadang menghasilkan
hash yang sama (``_MEI113562`` diulang setelah pemakaian sebelumnya),
lalu bootloader gagal extract karena salah menunjuk dir half-baked
yang masih ada di tmp:

    FileNotFoundError: [Errno 2] No such file or directory:
        'C:\\Users\\asynx\\AppData\\Local\\Temp\\_MEI113562\\base_library.zip'

Solusi
------
Runtime hook ini berjalan __sebelum__ bootloader extract. Ia menghapus
orphan ``_MEI*`` dir yang __bukan__ dir process ini sendiri
(``sys._MEIPASS``) dan __bukan__ barusan di-create (heuristic:
modified dalam 2 detik terakhir).

Idempoten + best-effort. Tidak menghapus tmp dir proses ini sendiri.
Hanya fokus di Windows (di mana ``_MEI*`` namespace dipakai).
"""
import os
import sys
import time


def _is_windows() -> bool:
    return sys.platform == "win32"


def _meipass_is_alive(path: str, now: float) -> bool:
    """Return True kalau directory di-create dalam 2 detik terakhir.

    Heuristic untuk membedakan ``_MEI*`` yang baru di-create oleh
    bootloader (jangan dihapus) vs orphan lama (boleh dihapus).

    Catatan: ``os.path.getmtime`` mengembalikan wall-time seconds
    (Unix epoch), bukan monotonic. Maka ``now`` HARUS wall-time juga
    (``time.time()``), bukan ``time.monotonic()``.
    """
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return False
    return (now - mtime) < 2.0  # grace window 2 detik


def _wipe_stale_meipass(temp_dir: str) -> int:
    """Hapus orphan ``_MEI*`` dirs di ``temp_dir``.

    Returns jumlah directories yang dihapus (best-effort, swallow
    semua ``OSError`` individual).
    """
    removed = 0
    try:
        entries = os.listdir(temp_dir)
    except OSError:
        return 0
    meipass_self = getattr(sys, "_MEIPASS", None)
    now = time.time()  # wall-time, matching os.path.getmtime output
    for name in entries:
        if not (name.startswith("_MEI") or name.startswith("_MEI_")):
            continue
        full = os.path.join(temp_dir, name)
        if not os.path.isdir(full):
            continue
        # Jangan hapus tmp dir process ini sendiri.
        if meipass_self and os.path.normpath(full) == os.path.normpath(meipass_self):
            continue
        # Jangan hapus yang baru di-create (mungkin bootloader running).
        if _meipass_is_alive(full, now):
            continue
        try:
            # Recursive remove. Best-effort; kalo gagal karena lock,
            # skip saja.
            import shutil
            shutil.rmtree(full, ignore_errors=True)
            removed += 1
        except Exception:
            pass
    return removed


def main() -> None:
    """Entrypoint runtime hook."""
    if not _is_windows():
        return
    # Skip di dev mode (tidak frozen) — orphan tidak terjadi.
    if not getattr(sys, "frozen", False):
        return
    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
    if not temp_dir or not os.path.isdir(temp_dir):
        return
    try:
        _wipe_stale_meipass(temp_dir)
    except Exception:
        pass


main()
