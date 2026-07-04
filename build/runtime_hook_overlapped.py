"""PyInstaller runtime hook — pre-load Windows C extensions SEBELUM
interpreter PyInstaller mengeksekusi kode user (backend/main.py dll.).

Context
-------
AsynxDL dibundle sebagai one-file single executable (``AsynxDL.exe``). PyInstaller
membuat tmp dir saat launch, meng-extract semua bundle ke situ, dan
sys.executable menunjuk ke ulang ke ``AsynxDL.exe`` mode ``--bootloader``.

Untuk mode ``run-after-relaunch`` (saat user memilih **Restart Now** di RestartDialog),
kita panggil ``os.execv(sys.executable, [sys.executable, ...])``. Execv memanggil
ulang bootloader, dan bootloader mengeksekusi ``main.py`` dari dalam bundle —
artinya segala import di awal ``main.py`` terjadi di interpreter yang BELUM
pernah menyentuh extension binary tertentu.

Solusi
------
Runtime hook ini dijalankan __sebelum__ module apapun (main.py, server.py,
api/*, etc). Ia mencoba pre-import ekstensi-ekstensi yang sering hilang
secara eksplisit dan __gently swallow exception__ ketika dev mode (stdlib
meng-handle-nya otomatis).

Daftar pre-import:
    1. ``_overlapped`` — Windows C-ext untuk ProactorEventLoop (uvicorn).
    2. ``asyncio`` + ``asyncio.windows_events`` — memaksa ProactorLoop selection.
    3. ``pydantic_core`` + ``pydantic_core._pydantic_core`` — Rust binary
       pyd. Setelah restart-via-execv, bundle kadang tidak me-recollect
       compiled binary ini sehingga ``ModuleNotFoundError: No module named
       'pydantic_core._pydantic_core'`` muncul.
    4. ``unicodedata`` + ``idna`` — stdlib C-ext (``unicodedata.pyd``).
       ``requests`` -> ``idna`` -> ``unicodedata`` chain gagal kalau
       bootloader luput meng-extract ``unicodedata.pyd`` ke bundle.

Hook ini adalah SATU-SATUNA first-line defense; ``backend/main.py`` masih
memiliki fallback belt-and-suspenders jika hook gagal di-fuse.
"""
import sys

# 1. ``_overlapped`` C-ext (Windows asyncio back-end).
try:
    import _overlapped  # noqa: F401
except Exception:
    # Bundle-mode: jika ``_overlapped`` masih belum di-collect oleh PyInstaller
    # heuristics, modul stdlib akan auto-load setiap kali asyncio.windows_events
    # menyentuh simbolnya. Dev mode: stdlib sudah punya ``_overlapped.pyd``.
    if getattr(sys, "frozen", False):
        # Last-ditch swallow: provisioning _overlapped adalah best-effort supaya
        # first-import tidak meledakkan seluruh app. Kita TIDAK raise.
        pass

# 2. Asyncio + ProactorEventLoop pre-warm.
try:
    import asyncio  # noqa: F401
    import asyncio.windows_events  # noqa: F401  # pragma: no cover - Windows only
except Exception:
    # Non-Windows runtime hook path.
    pass

# 3. pydantic_core (Rust-binary pyd). Jika bootloader tidak me-collect
#    ``_pydantic_core.pyd`` ke bundle, FastAPI/Pydantic v2 gagal import
#    di urutan: fastapi.routing -> fastapi.params -> pydantic -> pydantic_core.
#    Pre-import di sini supaya selalu tersedia sebelum user modules.
try:
    import pydantic_core  # noqa: F401
    import pydantic_core._pydantic_core  # noqa: F401
except Exception:
    if getattr(sys, "frozen", False):
        # Bundle-mode: biarkan PyInstaller mendeteksi saat runtime; fallback
        # di main.py akan preheat via ``importlib.import_module``.
        pass

# 4. ``unicodedata`` (stdlib C-ext). Chain:
#    ``requests`` -> ``idna`` -> ``unicodedata``. Kalau bootloader lupa
#    extract ``unicodedata.pyd``, import idna gagal dengan
#    ``ModuleNotFoundError: No module named 'unicodedata'``.
#    Pre-import di sini + ``idna`` sebagai bonus safety.
try:
    import unicodedata  # noqa: F401
    import idna  # noqa: F401
except Exception:
    if getattr(sys, "frozen", False):
        pass
