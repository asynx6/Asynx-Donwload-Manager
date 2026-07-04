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
        # Tanpa di sini, second-launch via os.execv gagal dengan
        #   ModuleNotFoundError: No module named '_overlapped'
        # Lihat backend/main.py juga untuk defensive try-import.
        '_overlapped',
        'asyncio.windows_events',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
