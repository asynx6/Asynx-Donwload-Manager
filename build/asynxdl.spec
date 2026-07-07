# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path
import customtkinter

PROJECT_ROOT = Path(r'C:\Users\asynx\Downloads\AsynxDL')

block_cipher = None

added_files = [
    (str(PROJECT_ROOT / 'Logo.png'), '.'),
    (str(PROJECT_ROOT / 'frontend' / 'ui' / 'assets'), 'frontend/ui/assets'),
    (str(PROJECT_ROOT / 'frontend' / 'ui' / 'i18n'), 'frontend/ui/i18n'),
    (str(PROJECT_ROOT / 'data' / 'queue'), 'data/queue'),
    (str(PROJECT_ROOT / 'extension' / 'browser'), 'extension/browser'),
]  # fmt: skip

# Include customtkinter assets
ctk_path = Path(customtkinter.__file__).parent
if ctk_path.exists():
    added_files.append((str(ctk_path / 'assets'), 'customtkinter/assets'))

a = Analysis(
    [str(PROJECT_ROOT / 'backend' / 'main.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'pystray',
        'PIL._tkinter_finder',
        'customtkinter',
        'uvicorn.logging',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'requests',
        'websocket',
        'winreg',
        # Explicit modules added in phase-2 + audit. These anchor Analysis
        # when PyInstaller heuristics miss dynamically-imported helpers.
        'backend',
        'backend.api',
        'backend.api.routes',
        'backend.core',
        'backend.core.parts_dir',
        'backend.system',
        'frontend',
        'frontend.ui',
        'frontend.ui.windows',
        'frontend.ui.components',
        # C extension Windows ini dipakai ProactorEventLoop (default uvicorn).
        # Lihat backend/main.py juga untuk defensive try-import dan
        # /build/runtime_hook_overlapped.py untuk pre-bundle preload.
        '_overlapped',
        'asyncio.windows_events',
        # Phase-D intelligence engine: rotasi User-Agent + httpx http2 opsional.
        'httpx',
        'httpx._transports.default',
        'h2',
        'h2.connection',
        'h2.config',
        'h2.events',
        'h2.errors',
        'h2.settings',
        'h2.streams',
        'h2.utilities',
        'hyperframe',
        'hyperframe.frame',
        'hpack',
        'hpack.hpack',
        'hpack.huffman_table',
        # Phase-F: pydantic_core (Rust binary pyd). Setelah execv-relaunch,
        # bundle kadang tidak me-collect ``_pydantic_core.pyd``. Hiddenimport
        # ini sebagai fallback tambahan selain runtime_hook yang me-pre-import.
        'pydantic_core',
        'pydantic_core._pydantic_core',
        # Phase-G: unicodedata (stdlib C-extension). Setelah restart via
        # execv, bootloader lupa extract ``unicodedata.pyd`` sehingga chain
        # ``requests -> idna -> unicodedata`` gagal.
        'unicodedata',
        'idna',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[
        # Pre-bundle preload _overlapped SEBELUM user code apapun jalan.
        # Final fix untuk 'ModuleNotFoundError: No module named _overlapped'
        # yang muncul ketika user pilih 'Restart Now' (os.execv ulang
        # bootloader).
        str(PROJECT_ROOT / 'build' / 'runtime_hook_overlapped.py'),
        # Phase-H: wipe orphan ``_MEI*`` tmp dirs agar bootloader extract
        # berikutnya tidak kena ``FileNotFoundError: base_library.zip``
        # (gejala remaining dari ``os.execv`` yang dipakai RestartDialog).
        str(PROJECT_ROOT / 'build' / 'runtime_hook_meipass.py'),
    ],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AsynxDL',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / 'frontend' / 'ui' / 'assets' / 'icons' / 'app.ico'),
)
