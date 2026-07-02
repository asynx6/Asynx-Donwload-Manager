# AsynxDL — Advanced Download Manager

AsynxDL adalah download manager desktop modern untuk Windows, dibangun dengan Python + CustomTkinter (UI) + FastAPI (backend) + Chrome Extension (browser interceptor).

## Fitur Utama

- **Multi-threaded Chunked Download** — otomatis membagi file besar menjadi beberapa chunk dan mengunduh secara paralel.
- **Resume & Crash Recovery** — state progress disimpan ke metadata JSON; bisa dilanjutkan meski aplikasi crash.
- **Speed Limiter** — batasi kecepatan global per download (KB/s).
- **Queue & Max Concurrent** — antrian download dengan maksimal 3-5 download aktif secara bersamaan (RAM-friendly).
- **CustomTkinter UI** — tampilan modern dengan dark/light mode, animasi halus, dan kartu download interaktif.
- **System Tray** — minimize ke tray, resume/pause dari ikon tray.
- **Browser Extension** — Chrome Extension MV3 menangkap download dari browser dan mengirim ke aplikasi desktop.
- **Autentikasi Token** — setiap endpoint backend dilindungi `X-AsynxDL-Token` (kecuali health check).
- **RAM 4GB Optimized** — buffer kecil (64KB chunk, 1MB merger) untuk hemat memori.

## Struktur Project

```
AsynxDL/
├── backend/
│   ├── api/                  # FastAPI: auth, models, routes, state, server
│   ├── core/                 # Download engine: chunk, merger, validator, metadata, speed limiter
│   ├── system/               # config, startup, tray
│   └── main.py               # Entry point: server + UI
├── frontend/
│   └── ui/                   # CustomTkinter UI: app, api_client, components, windows, i18n
├── extension/browser/        # Chrome Extension MV3
├── tests/                    # Unit & integration tests
├── build/                    # PyInstaller spec & Inno Setup script
├── data/queue/               # Metadata queue JSON
└── plan.md                   # Blueprint arsitektur
```

## Cara Menjalankan (Development)

```powershell
# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Jalankan aplikasi
python -m backend.main
```

## Cara Build Executable

```powershell
# Build .exe dengan PyInstaller
python -m PyInstaller build/asynxdl.spec --clean --noconfirm

# Output: dist/AsynxDL.exe
```

## Cara Build Installer

1. Jalankan PyInstaller (langkah di atas).
2. Buka `build/installer.iss` dengan Inno Setup Compiler.
3. Compile — output `dist/AsynxDL_Setup_v1.0.0.exe`.

## Cara Install Extension

1. Buka Chrome → `chrome://extensions/`
2. Aktifkan **Developer mode**.
3. Klik **Load unpacked** → pilih folder `extension/browser/`.
4. Buka options extension → paste Secret Token dari aplikasi AsynxDL.

## Menjalankan Test

```powershell
python -m pytest tests/ -v
```

## Lisensi

Proprietary — AsynxDL Project.
