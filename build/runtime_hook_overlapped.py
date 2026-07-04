"""PyInstaller runtime hook — pre-load Windows ``_overlapped`` C extension
SEBELUM interpreter PyInstaller mengeksekusi kode user (backend/main.py dll.).

Context
-------
AsynxDL dibundle sebagai one-file single executable (``AsynxDL.exe``). PyInstaller
membuat tmp dir saat launch, meng-extract semua bundle ke situ, dan
sys.executable menunjuk ke ulang ke ``AsynxDL.exe`` mode ``--bootloader``.

Untuk mode ``run-after-relaunch`` (saat user memilih **Restart Now** di RestartDialog),
kita panggil ``os.execv(sys.executable, [sys.executable, ...])``. Execv memanggil ulang
bootloader, dan bootloader mengeksekusi ``main.py`` dari dalam satu-file bundle —
artinya segala import di awal ``main.py`` terjadi di interpreter yang BELUM
pernah menyebut ``_overlapped``.

Trick ``backend/main.py`` try-import di paling atas tetap bekerja untuk
proses-ke-1 (karena ``_overlapped`` di-extract saat bootloader create tmp dir
lagi). Tapi kadang urutan import membuat ``asyncio.windows_events`` di-touch
TERLALU awal sebelum ``main.py`` punya kesempatan pre-import.

Solusi
-------
Runtime hook ini dijalankan __sebelum__ module apapun (main.py, server.py,
api/*, etc). Ia mencoba pre-import ``_overlapped`` secara eksplisit dan
__gently swallow exception__ jika interpreter tidak di-bundle (dev mode
akan auto-load via stdlib biasa).

Selain ``_overlapped``, hook ini juga memanggil ``import asyncio`` +
``import asyncio.windows_events`` untuk memaksa asyncio memilih
ProactorEventLoop (default) sehingga asynx DL FastAPI/uvicorn tidak akan
crash di next ``import uvicorn`` saat runtime.

Hook ini adalah SATU-SATUNYA line of defense di front-line — anyone else is
a fallback.
"""
import sys

try:
    import _overlapped  # noqa: F401
except Exception:
    # Bundle-mode: jika ``_overlapped`` masih belum di-collect oleh PyInstaller
    # heuristics, modul stdlib akan auto-load setiap kali asyncio.windows_events
    # menyentuh simbolnya. Kita swallow exception (in dev mode stdlib sudah
    # punya _overlapped.pyd).
    if getattr(sys, "frozen", False):
        # Last-ditch: jika import _overlapped gagal tapi frozen=True, biarkan.
        # Kita TIDAK raise — provisioning _overlapped adalah best-effort supaya
        # KeystoreMessageError di first-import tidak meledakkan seluruh app.
        pass

try:
    import asyncio  # noqa: F401
    import asyncio.windows_events  # noqa: F401  # pragma: no cover - Windows only
except Exception:
    # Non-Windows runtime hook path; ahem: hook hanya dipakai di Windows.
    pass
