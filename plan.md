# 📦 AsynxDL — Blueprint & Rencana Pengembangan Lengkap

> **Peran dokumen ini:** Panduan arsitektur bagi AI implementor (DeepSeek).
> Dokumen ini **TIDAK** memuat kode lengkap — hanya logika, alur, struktur, dan snippet krusial.

---

## 📋 Metadata Proyek

| Key | Value |
|---|---|
| **Nama Proyek** | AsynxDL |
| **Versi** | 1.0.0-alpha |
| **Tujuan** | IDM Clone — Gratis, Super Ringan, Aman, Estetik |
| **Primary Stack** | Python 3.11+ · FastAPI · CustomTkinter · Chrome Extension MV3 |
| **Target OS** | Windows 10 / 11 (x64) |
| **API Port** | `58296` (fixed) |
| **RAM Target** | ≤ 60 MB saat idle |

---

## 🏛 1. ARSITEKTUR SISTEM (High-Level Overview)

### 1.1 Diagram Komponen

```
┌─────────────────────────────────────────────────────────────────┐
│                      SISTEM ASYNXDL                             │
│                                                                  │
│  ┌─────────────────┐        ┌──────────────────────────────┐   │
│  │ Chrome Extension│──POST──▶│  FastAPI Local Server        │   │
│  │  (Service Worker│  :58296 │  127.0.0.1:58296             │   │
│  │   MV3)          │◀──WS───│  + Auth Middleware            │   │
│  └─────────────────┘        └──────────┬───────────────────┘   │
│                                         │                        │
│                              ┌──────────▼───────────────────┐   │
│                              │  Core Downloader Engine       │   │
│                              │  ThreadPoolExecutor           │   │
│                              │  DownloadTask × N             │   │
│                              └──────────┬───────────────────┘   │
│                                    ↕    │ baca/tulis             │
│                              ┌─────┴────▼───────────────────┐   │
│  ┌─────────────────┐        │  Metadata Queue (data/queue/) │   │
│  │ CustomTkinter UI│◀──WS───│  *.json per download task     │   │
│  │  + System Tray  │        └───────────────────────────────┘   │
│  └─────────────────┘                                             │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Pola Komunikasi Antar Komponen

| Sumber | Tujuan | Protokol | Deskripsi |
|---|---|---|---|
| Chrome Extension | FastAPI | HTTP POST | Kirim URL baru yang di-intercept |
| CustomTkinter UI | FastAPI | HTTP REST | CRUD queue (pause, resume, delete) |
| FastAPI | CustomTkinter UI | WebSocket `/ws/progress` | Push update kecepatan & persentase real-time |
| Core Engine | Disk | File I/O | Tulis chunk `.part` dan metadata `.json` |
| Core Engine | FastAPI | Python call (in-process) | Update state → broadcast via WebSocket |

### 1.3 Proses Startup Aplikasi (Urutan Init)

```
main.py dijalankan
  1. Baca / generate config.json
  2. Resolve path data/queue/
  3. Load semua metadata .json yang statusnya PENDING / PAUSED (State Recovery)
  4. Start FastAPI server di thread terpisah (uvicorn)
  5. Init SystemTray (pystray, background thread)
  6. Restore queue items ke UI
  7. Show / hide main window (tergantung flag --minimized)
```

---

## 🔐 2. KEAMANAN PORT & VALIDASI API

### 2.1 Strategi Pengamanan Berlapis

**Layer 1 — Binding Address**
Server WAJIB bind hanya ke `127.0.0.1`, bukan `0.0.0.0`. Ini mencegah akses dari jaringan LAN atau internet luar.

**Layer 2 — Secret Token**
- Token di-generate sekali saat first-run menggunakan `uuid.uuid4()`.
- Disimpan di `config.json`.
- Setiap request ke endpoint non-`/status` WAJIB menyertakan header:
  `X-AsynxDL-Token: <secret>`

**Layer 3 — CORS Strict**
Hanya origin `http://127.0.0.1` yang diizinkan. Blokir semua request dari origin website luar.

### 2.2 Snippet Krusial — FastAPI Token Dependency

```python
# backend/api/auth.py
from fastapi import Request, HTTPException, Depends
from backend.system.config import load_config

async def verify_token(request: Request):
    expected = load_config().get("api_secret_token")
    received = request.headers.get("X-AsynxDL-Token")
    if not received or received != expected:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid Token")
```

Gunakan sebagai dependency di semua route: `@router.post("/add", dependencies=[Depends(verify_token)])`.

### 2.3 CORS Configuration

```python
# backend/api/server.py
app.add_middleware(CORSMiddleware,
    allow_origins=["http://127.0.0.1"],
    allow_methods=["GET", "POST", "PATCH", "DELETE", "PUT"],
    allow_headers=["X-AsynxDL-Token", "Content-Type"],
)
```

---

## ⚙️ 3. CORE DOWNLOADER ENGINE

### 3.1 Logika Multi-Thread Chunking

#### Alur Sebelum Download Dimulai

```
HEAD request ke URL
  ├── Dapatkan Content-Length (ukuran file total)
  ├── Cek header Accept-Ranges: bytes
  │     ├── Ada → mode CHUNKED (multi-thread)
  │     └── Tidak ada → mode SINGLE THREAD (fallback)
  │
  ├── check_disk_space(save_path, file_size) → raise jika tidak cukup
  ├── filename = sanitize_filename(filename_from_url)
  ├── filename = resolve_duplicate_name(save_path, filename)
  └── Buat metadata .json → tulis ke data/queue/
```

#### Kalkulasi Chunk

- `thread_count = min(8, max(1, file_size_bytes // (10 * 1024 * 1024)))`
  → Maksimal 8 thread, minimal 1, skala per 10 MB.
- `chunk_size = ceil(file_size / thread_count)`
- Per thread: `start = i * chunk_size`, `end = min(start + chunk_size - 1, file_size - 1)`
- Output per thread: file `.part{i}` di folder temp yang sama dengan save_path.

#### Snippet Krusial — HTTP Range Request

```python
# backend/core/chunk_manager.py
def download_chunk(url, start, end, part_path, limiter, stop_event):
    headers = {"Range": f"bytes={start}-{end}",
               "User-Agent": "Mozilla/5.0 (AsynxDL/1.0)"}
    with requests.get(url, headers=headers, stream=True, timeout=30) as r:
        with open(part_path, "wb") as f:
            for data in r.iter_content(chunk_size=65536):
                if stop_event.is_set(): break
                f.write(data)
                limiter.throttle(len(data))  # SpeedLimiter hook
```

### 3.2 Pause, Resume & Auto-Reconnect

**Mekanisme Pause:**
- Set `stop_event` (threading.Event) → semua thread berhenti di akhir iterasi stream.
- Update metadata `.json`: status = `"PAUSED"`, catat `bytes_done` per chunk.

**Mekanisme Resume:**
- Baca metadata `.json` → per chunk, skip byte yang sudah diunduh.
- Kirim Range header dengan `start = original_start + bytes_done`.
- Buka file `.part{i}` dalam mode `"ab"` (append binary), lanjutkan penulisan.

**Auto-Reconnect:**
- Bungkus `requests.get()` dalam loop retry dengan exponential backoff.
- Delay: `1s → 2s → 4s → 8s → 16s` (maks 5 kali).
- Setelah 5 kali gagal: update status = `"ERROR"`, broadcast ke UI.

### 3.3 Queue State Recovery (Fitur Baru)

**Saat aplikasi boot:**
1. Scan semua file `*.json` di folder `data/queue/`.
2. Filter: status == `"DOWNLOADING"` | `"PAUSED"` | `"PENDING"`.
3. Ubah status `"DOWNLOADING"` → `"PAUSED"` (karena proses sebelumnya sudah mati).
4. Restore setiap item ke UI sebagai `DownloadCard`.
5. User bisa klik [Resume] untuk melanjutkan dari byte terakhir.

**Logika deteksi crash vs intentional pause:**
Gunakan flag `"graceful_exit": false` di metadata. Set ke `true` saat user secara sengaja pause atau app keluar dengan benar. Jika nilai-nya `false` saat dibaca, artinya app crash → tampilkan badge "Interrupted" di UI.

### 3.4 Skema File Metadata `.json`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "url": "https://example.com/file.zip",
  "filename": "file.zip",
  "save_path": "C:\\Users\\User\\Downloads\\file.zip",
  "total_size": 104857600,
  "downloaded_size": 52428800,
  "status": "PAUSED",
  "graceful_exit": true,
  "speed_limit_kbps": 0,
  "thread_count": 8,
  "chunks": [
    {"index": 0, "start": 0,        "end": 13107199, "bytes_done": 13107200},
    {"index": 1, "start": 13107200, "end": 26214399, "bytes_done": 7340032}
  ],
  "created_at": "2025-01-01T10:00:00Z",
  "updated_at": "2025-01-01T10:05:00Z"
}
```

> ⚠️ File ini WAJIB di-flush ke disk setiap ≤ 1 detik selama download aktif agar recovery tetap akurat saat crash.

### 3.5 Speed Limiter (Token Bucket Algorithm)

**Logika class `SpeedLimiter`:**
- Inisialisasi: `limit_bytes_per_sec = kbps * 1024` (0 = unlimited).
- Method `throttle(bytes_written)`:
  - Catat `elapsed = time.monotonic() - last_check`.
  - Hitung `expected_time = bytes_written / limit_bytes_per_sec`.
  - Jika `expected_time > elapsed`: `time.sleep(expected_time - elapsed)`.
- Thread-safe: gunakan `threading.Lock()` saat update counter.

### 3.6 Validasi & Error Handling

#### A. Disk Space Check

```python
# backend/core/file_validator.py
import shutil, os

def check_disk_space(save_path: str, required_bytes: int) -> bool:
    drive = os.path.splitdrive(save_path)[0] or "/"
    free = shutil.disk_usage(drive).free
    return free > required_bytes * 1.05  # buffer 5%
```

#### B. Filename Sanitizer

```python
# backend/core/file_validator.py
import re

ILLEGAL_WIN = r'[\\/:*?"<>|\x00-\x1f]'

def sanitize_filename(name: str) -> str:
    name = re.sub(ILLEGAL_WIN, '_', name)
    return name.strip('. ')[:200]  # strip leading dots/spaces, maks 200 char
```

#### C. Auto-Rename Duplicate

```python
# backend/core/file_validator.py
def resolve_duplicate_name(folder: str, filename: str) -> str:
    base, ext = os.path.splitext(filename)
    counter = 1
    candidate = filename
    while os.path.exists(os.path.join(folder, candidate)):
        candidate = f"{base} ({counter}){ext}"
        counter += 1
    return candidate
```

### 3.7 File Merger

Setelah semua thread selesai:
1. Buat file output kosong di `save_path`.
2. Buka dalam mode `"wb"`, loop dari chunk 0 hingga N-1.
3. Baca `*.part{i}`, tulis ke file output, hapus `.part{i}`.
4. Verifikasi ukuran file final == `total_size` dari metadata.
5. Hapus file metadata `.json` dari `data/queue/`.
6. Update status di UI → `"COMPLETED"`.

---

## 🌐 4. LOCAL API SERVER (FastAPI)

### 4.1 Daftar Endpoint Lengkap

| Method | Path | Auth | Deskripsi |
|---|---|---|---|
| `GET` | `/status` | ❌ | Health check, tidak perlu token |
| `POST` | `/downloads/add` | ✅ | Tambah download baru |
| `GET` | `/downloads` | ✅ | List semua item queue |
| `GET` | `/downloads/{id}` | ✅ | Detail satu item |
| `PATCH` | `/downloads/{id}/pause` | ✅ | Pause download |
| `PATCH` | `/downloads/{id}/resume` | ✅ | Resume download |
| `DELETE` | `/downloads/{id}` | ✅ | Hapus item (+ file .part opsional) |
| `GET` | `/settings` | ✅ | Ambil config saat ini |
| `PUT` | `/settings` | ✅ | Update config |
| `WS` | `/ws/progress` | ✅ (via query param token) | Push progress real-time |

### 4.2 Request & Response Models (Pydantic)

**`AddDownloadRequest`:** `url`, `filename` (opsional), `save_path` (opsional, fallback ke config default), `speed_limit_kbps` (opsional).

**`DownloadItem`:** Semua field dari skema metadata `.json` di atas + field computed `speed_kbps` dan `eta_seconds`.

**`WebSocket Progress Payload`:**
```json
{
  "id": "uuid-v4",
  "status": "DOWNLOADING",
  "speed_kbps": 2048,
  "percent": 52.4,
  "downloaded_size": 54975488,
  "eta_seconds": 24
}
```

### 4.3 WebSocket Connection Manager

- Simpan daftar koneksi aktif dalam `set` di class `ConnectionManager`.
- Method `broadcast(message: dict)`: kirim JSON ke semua koneksi aktif.
- Background task di `server.py` loop setiap 500ms → ambil snapshot status semua DownloadTask aktif → broadcast.

---

## 🖥 5. GUI DESKTOP (CustomTkinter)

### 5.1 Tema Warna & Design System

| Element | Light Mode Hex | Dark Mode Hex |
|---|---|---|
| Background | `#F5F5F5` | `#1C1C1C` |
| Surface / Card | `#FFFFFF` | `#2A2A2A` |
| Border | `#E0E0E0` | `#3A3A3A` |
| Primary Accent | `#5B6BF8` | `#7B8BFF` |
| Text Primary | `#1A1A1A` | `#EFEFEF` |
| Text Secondary | `#6B6B6B` | `#9E9E9E` |
| Progress Fill | `#5B6BF8` | `#7B8BFF` |
| Success | `#2E7D32` | `#66BB6A` |
| Error | `#C62828` | `#EF5350` |

Font: **Inter** (bundle bersama app) atau fallback ke Segoe UI.

### 5.2 Layout Window Utama

```
┌──────────────────────────────────────────────────────────────────┐
│  🔽 AsynxDL v1.0          [🔍 Cari...]    [+ Tambah] [⚙ Setting] │
├──────────────────────────────────────────────────────────────────┤
│  [Semua ▼]  [⬇ Mengunduh]  [⏸ Dijeda]  [✅ Selesai]            │
├──────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 📄 ubuntu-22.04.3-desktop-amd64.iso            52%  ⬇    │  │
│  │ ██████████████░░░░░░░░░░░░   2.1 MB/s   ETA: 48 detik    │  │
│  │ [⏸ Jeda]  [✕ Batal]                  1.2 GB / 2.3 GB    │  │
│  └────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 📄 setup-v2.1.exe                            ✅ Selesai   │  │
│  │ ████████████████████████████  —               134 MB      │  │
│  │ [📂 Buka Folder]  [▶ Jalankan]  [🗑 Hapus]               │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 Window Settings

Konten settings window (popup terpisah, bukan dialog):
- **Default Path:** Text field + tombol [Browse] → `filedialog.askdirectory()`.
- **Speed Limit:** Toggle switch + input angka + dropdown unit (KB/s | MB/s). Default: OFF.
- **Max Thread per Download:** Slider 1–8. Default: 8.
- **Max Concurrent Downloads:** Input 1–5. Default: 3.
- **Bahasa:** Dropdown [English | Bahasa Indonesia].
- **Jalankan saat Windows Start:** Toggle → panggil `startup.set_startup()`.
- **Tema:** Toggle Light / Dark.

### 5.4 Sistem Multi-Bahasa (i18n)

- Semua string UI didefinisikan di `i18n/en.json` dan `i18n/id.json`.
- Loader: baca file JSON sesuai setting bahasa aktif → simpan sebagai dict global.
- Fungsi akses: `t("key.subkey")` → lookup dict, fallback ke English jika key tidak ditemukan.
- Perubahan bahasa di settings → reload dict tanpa restart app (cukup re-render semua widget).

**Contoh struktur `i18n/en.json`:**
```json
{
  "btn": { "pause": "Pause", "resume": "Resume", "cancel": "Cancel",
           "open_folder": "Open Folder", "run": "Run", "delete": "Delete" },
  "status": { "downloading": "Downloading", "paused": "Paused",
               "completed": "Completed", "error": "Error" },
  "settings": { "title": "Settings", "default_path": "Default Download Path",
                 "speed_limit": "Speed Limit", "language": "Language" }
}
```

### 5.5 System Tray

- Library: `pystray` + `Pillow`.
- Menu konteks klik-kanan tray icon:
  - **Show AsynxDL** → munculkan main window.
  - **Pause All** → pause semua download aktif.
  - **Settings** → buka settings window.
  - **───** (separator)
  - **Exit** → graceful shutdown.
- Event `window.protocol("WM_DELETE_WINDOW")` → hide window (bukan exit).
- `pystray.Icon` dijalankan di thread daemon terpisah.

### 5.6 Windows Auto-Startup

#### Snippet Krusial — Registry Write/Delete

```python
# backend/system/startup.py
import winreg, sys

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "AsynxDL"

def set_startup(enabled: bool):
    exe = sys.executable if getattr(sys, "frozen", False) else __file__
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY,
                          0, winreg.KEY_SET_VALUE)
    if enabled:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ,
                           f'"{exe}" --minimized')
    else:
        try: winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError: pass
    winreg.CloseKey(key)
```

---

## 🧩 6. BROWSER EXTENSION (Chrome MV3)

### 6.1 Manifest V3 — Kunci Konfigurasi

```json
{
  "manifest_version": 3,
  "name": "AsynxDL Interceptor",
  "version": "1.0.0",
  "permissions": ["downloads", "storage", "notifications"],
  "host_permissions": ["http://127.0.0.1:58296/*"],
  "background": { "service_worker": "background/service_worker.js" },
  "action":  { "default_popup": "popup/popup.html",
                "default_icon": { "16": "assets/icons/icon16.png" } }
}
```

### 6.2 Alur Service Worker Lengkap

```
chrome.downloads.onCreated.addListener(item)
  │
  ├─1. Segera: chrome.downloads.cancel(item.id)
  │
  ├─2. Fetch GET http://127.0.0.1:58296/status
  │     ├── Gagal / timeout → fallback: jangan cancel, biarkan Chrome download
  │     └── Berhasil → lanjut
  │
  ├─3. Ambil info file: filename dari item.filename, size dari item.totalBytes
  │
  ├─4. Simpan ke chrome.storage.session: { url, filename, size, suggestedSavePath }
  │
  └─5. Buka popup via chrome.action.openPopup() atau windows.create()
       (popup.js akan baca dari chrome.storage.session)
```

### 6.3 Pop-up Konfirmasi — Komponen UI

```
┌───────────────────────────────────────┐
│  ⬇  AsynxDL — Konfirmasi Unduhan      │
├───────────────────────────────────────┤
│  File   :  ubuntu-22.04.iso           │
│  Ukuran :  2.31 GB                    │
│  Simpan :  [C:\Users\...\Downloads ▾] │
│           [Browse folder...]          │
├───────────────────────────────────────┤
│       [✕ Batal]   [⬇ Mulai Unduh]    │
└───────────────────────────────────────┘
```

**Logic popup.js:**
1. Baca data dari `chrome.storage.session`.
2. Render info file ke DOM.
3. Tombol [Batal]: hapus data dari storage, tutup popup.
4. Tombol [Mulai Unduh]: POST ke `/downloads/add` dengan payload `{url, filename, save_path}` dan header `X-AsynxDL-Token`.
   - Jika sukses (HTTP 201): tampilkan animasi checkmark, tutup popup setelah 1.5 detik.
   - Jika gagal: tampilkan pesan error "Backend tidak merespons".

### 6.4 Extension ↔ Backend Token Pairing

**First-run flow:**
- Saat pertama install extension, tampilkan badge "Setup required".
- Buka options page extension yang meminta user memasukkan Secret Token.
- Token disimpan via `chrome.storage.local` dan digunakan di setiap request.
- Alternatif lebih user-friendly: Tampilkan token di UI desktop (bisa di-copy) dan halaman options extension menyediakan field paste.

---

## 📁 7. STRUKTUR FOLDER PROJECT (Directory Tree)

```
AsynxDL/
│
├── backend/
│   ├── core/
│   │   ├── downloader.py          # Orchestrator: DownloadTask class, ThreadPoolExecutor
│   │   ├── chunk_manager.py       # download_chunk() — HTTP Range + stream writer
│   │   ├── merger.py              # merge_parts() — gabung .part menjadi file final
│   │   ├── speed_limiter.py       # SpeedLimiter class — token bucket algorithm
│   │   ├── file_validator.py      # check_disk_space(), sanitize_filename(), resolve_duplicate_name()
│   │   └── metadata_manager.py    # create/update/load/delete metadata .json; thread-safe Lock
│   │
│   ├── api/
│   │   ├── server.py              # FastAPI app factory, uvicorn runner, CORS, startup event
│   │   ├── auth.py                # verify_token() FastAPI Dependency
│   │   ├── models.py              # Pydantic schemas: AddDownloadRequest, DownloadItem, SettingsModel
│   │   └── routes/
│   │       ├── downloads.py       # CRUD endpoint /downloads
│   │       ├── settings.py        # GET & PUT /settings
│   │       ├── status.py          # GET /status — health check tanpa auth
│   │       └── ws_progress.py     # WebSocket /ws/progress — ConnectionManager + broadcast loop
│   │
│   ├── system/
│   │   ├── config.py              # load_config(), save_config(), generate_secret_token()
│   │   ├── tray.py                # pystray Icon setup, menu definition, tray icon PNG
│   │   └── startup.py             # set_startup() via winreg (Windows only, guard sys.platform)
│   │
│   └── main.py                    # Entry point: init sequence, thread orchestration
│
├── frontend/
│   └── ui/
│       ├── app.py                 # CTk root window, lifecycle (close → tray, not exit)
│       ├── api_client.py          # Helper: HTTP calls ke FastAPI + WebSocket subscriber
│       ├── windows/
│       │   ├── main_window.py     # Frame utama: toolbar, filter tabs, scrollable card list
│       │   ├── settings_window.py # CTkToplevel: semua opsi pengaturan
│       │   └── about_window.py    # CTkToplevel: info versi, lisensi, link GitHub
│       ├── components/
│       │   ├── download_card.py   # CTkFrame widget: satu baris item download (state-aware)
│       │   ├── progress_bar.py    # CTkProgressBar custom dengan label % overlay
│       │   └── speed_label.py     # CTkLabel: format kecepatan + ETA, update setiap 500ms
│       ├── assets/
│       │   ├── icons/
│       │   │   ├── app.ico        # Icon utama aplikasi (multi-size: 16,32,48,64,128,256px)
│       │   │   └── tray.png       # Icon system tray (32x32 PNG, transparan)
│       │   └── fonts/
│       │       └── Inter-Regular.ttf
│       └── i18n/
│           ├── en.json            # Semua string UI bahasa Inggris
│           └── id.json            # Semua string UI bahasa Indonesia
│
├── extension/
│   └── browser/
│       ├── manifest.json          # Chrome Extension Manifest V3
│       ├── background/
│       │   └── service_worker.js  # Intercept, cancel native, relay ke backend
│       ├── popup/
│       │   ├── popup.html         # Struktur dialog konfirmasi
│       │   ├── popup.css          # Grey/white minimal theme, match desktop app
│       │   └── popup.js           # Baca storage, render info, kirim ke API
│       ├── options/
│       │   ├── options.html       # Halaman pengaturan extension (token pairing)
│       │   └── options.js         # Simpan token ke chrome.storage.local
│       ├── content/
│       │   └── injected.js        # (Opsional) In-page mini progress bar
│       └── assets/
│           └── icons/
│               ├── icon16.png
│               ├── icon48.png
│               └── icon128.png
│
├── data/
│   └── queue/                     # Runtime: file *.json metadata per download
│       └── .gitkeep               # Agar folder dicommit kosong
│
├── build/
│   ├── asynxdl.spec               # PyInstaller spec: onefile, datas, hidden imports, icon
│   ├── installer.iss              # Inno Setup script: install dir, shortcuts, uninstaller
│   └── version.txt                # Nomor versi untuk injeksi ke installer (e.g., "1.0.0")
│
├── tests/
│   ├── test_downloader.py         # Unit test: chunking, merge, retry, state recovery
│   ├── test_api.py                # Integration test: semua endpoint + auth rejection
│   ├── test_validator.py          # Unit test: sanitize, disk check, rename
│   └── fixtures/
│       └── sample_metadata.json   # Data fixture: contoh metadata untuk testing
│
├── requirements.txt               # Python dependencies (pinned versi)
├── .env.example                   # Template env (jangan commit file .env asli)
├── .gitignore                     # Exclude: data/queue/*.json, dist/, build/output/, .env
├── README.md                      # Dokumentasi pengguna dan developer
└── plan.md                        # File ini — blueprint arsitektur
```

---

## 🗺 8. ROADMAP & URUTAN EKSEKUSI TAHAP DEMI TAHAP

> **Prinsip:** Bangun dari inti ke luar. Core Logic → API Layer → UI Layer → Extension → Integrasi Penuh → Build.

---

### 📍 TAHAP 1 — Core Downloader Script

**Target:** Logika download mandiri yang bisa dijalankan via terminal, tanpa UI.

**File:** `backend/core/*.py`

**Urutan pengerjaan internal:**
1. `file_validator.py` → tiga fungsi: `check_disk_space`, `sanitize_filename`, `resolve_duplicate_name`.
2. `metadata_manager.py` → CRUD metadata `.json`; implementasikan `threading.Lock()` untuk keamanan thread.
3. `speed_limiter.py` → class `SpeedLimiter` dengan method `throttle(bytes_written)`.
4. `chunk_manager.py` → fungsi `download_chunk(...)` yang mendukung stop event dan speed limiter.
5. `merger.py` → fungsi `merge_parts(part_files, output_path)` dengan verifikasi ukuran akhir.
6. `downloader.py` → class `DownloadTask`:
   - Method `start()`: HEAD request, hitung chunk, spawn ThreadPoolExecutor.
   - Method `pause()`: set stop event, simpan state ke `.json`.
   - Method `resume()`: baca `.json`, restart thread dengan byte offset.
   - Method `cancel()`: stop semua thread, hapus `.part` files, hapus `.json`.

**Verifikasi Tahap 1:**
Jalankan `test_downloader.py`. Pastikan file berhasil diunduh, pause/resume akurat, dan file akhir tidak corrupt (verifikasi SHA-256 jika server menyediakan hash).

---

### 📍 TAHAP 2 — Local API Server & Keamanan Port

**Target:** Backend bisa diakses via HTTP dari tools lain (Postman, curl).

**File:** `backend/api/*.py` + `backend/system/config.py`

**Urutan pengerjaan internal:**
1. `config.py` → `load_config()`, `save_config()`, `generate_secret_token()` (uuid4 saat first-run).
2. `models.py` → semua Pydantic model untuk request dan response.
3. `auth.py` → dependency `verify_token`.
4. `routes/status.py` → `/status` tanpa auth.
5. `routes/downloads.py` → semua endpoint CRUD dengan auth dependency.
6. `routes/settings.py` → GET/PUT settings.
7. `routes/ws_progress.py` → `ConnectionManager` class + WebSocket endpoint + background broadcast loop.
8. `server.py` → assembly semua router, CORS, bind `127.0.0.1:58296`, jalankan uvicorn di thread.

**Verifikasi Tahap 2:**
Jalankan `test_api.py`. Test dengan Postman: request tanpa token → 403. Request dengan token valid → 200/201. WebSocket progress terbuka dan menerima update.

---

### 📍 TAHAP 3 — GUI Desktop, System Tray & i18n

**Target:** Aplikasi bisa dibuka, menampilkan queue, dan berjalan di tray.

**File:** `frontend/ui/**` + `backend/system/tray.py` + `backend/system/startup.py`

**Urutan pengerjaan internal:**
1. `i18n/en.json` & `i18n/id.json` → definisikan semua string terlebih dahulu. Ini pondasi UI.
2. `ui/api_client.py` → wrapper HTTP ke FastAPI + WebSocket listener.
3. `ui/components/progress_bar.py` & `speed_label.py` → widget terkecil, paling reusable.
4. `ui/components/download_card.py` → widget satu item, state-aware (berubah tampilan per status).
5. `ui/windows/settings_window.py` → window settings (lebih sederhana dari main window).
6. `ui/windows/about_window.py` → window about.
7. `ui/windows/main_window.py` → frame utama, integrasikan semua komponen.
8. `ui/app.py` → inisialisasi CTk, subscribe WebSocket, lifecycle management.
9. `system/tray.py` → setup pystray, hook ke app.
10. `system/startup.py` → fungsi registry (Windows only).

**Verifikasi Tahap 3:**
Jalankan app standalone (backend harus sudah jalan). Test: download card muncul dan update. Close window → icon tray muncul. Klik tray → window muncul. Ubah bahasa → semua string berubah tanpa restart.

---

### 📍 TAHAP 4 — Browser Extension & Pop-up Dialog

**Target:** Extension bisa intercept download dari Chrome dan meneruskan ke backend.

**File:** `extension/browser/**`

**Urutan pengerjaan internal:**
1. `assets/icons/` → buat/resize icon 16, 48, 128px (bisa gunakan Figma atau tool online).
2. `manifest.json` → konfigurasi MV3 lengkap.
3. `options/options.html` + `options.js` → form input Secret Token dan simpan ke `chrome.storage.local`.
4. `popup/popup.html` + `popup.css` → struktur dan styling dialog.
5. `popup/popup.js` → logic: baca storage, render, kirim ke API.
6. `background/service_worker.js` → intercept, cancel native download, ping backend, relay data, buka popup.

**Verifikasi Tahap 4:**
Load extension via `chrome://extensions → Load unpacked`. Klik link file di browser → native download terbatalkan → popup AsynxDL muncul → klik Start → download muncul di app desktop.

---

### 📍 TAHAP 5 — Integrasi Menyeluruh & State Recovery

**Target:** Semua komponen bekerja bersama secara mulus. Tidak ada data yang hilang saat restart.

**File:** `backend/main.py` (utama) + fine-tuning seluruh modul.

**Checklist Integrasi Wajib:**

| # | Cek | Modul Terkait |
|---|---|---|
| 1 | Startup recovery: metadata `.json` pending/paused di-restore ke UI | `main.py` + `metadata_manager` + `main_window` |
| 2 | WebSocket push: UI update setiap 500ms saat download aktif | `ws_progress.py` + `api_client.py` |
| 3 | Speed limit applied: perubahan di settings langsung efek ke download aktif | `settings_window` → API PUT `/settings` → `DownloadTask` |
| 4 | Token sync: token di `config.json` sama dengan yang di extension | `config.py` + `options.js` |
| 5 | Error state: download error → badge di card + tombol [Coba Lagi] | `download_card.py` + `downloader.py` |
| 6 | Graceful shutdown: semua thread pause (simpan state) sebelum exit | `tray.py` Exit menu + `main.py` |
| 7 | Duplicate queue prevention: cek apakah URL sudah ada di queue sebelum tambah | `routes/downloads.py` |
| 8 | Default path resolved: `%USERPROFILE%` → `os.path.expandvars()` | `config.py` + `file_validator.py` |

---

### 📍 TAHAP 6 — Build Akhir: Installer `.exe` Siap Pakai

**Target:** Satu file installer `.exe` yang bisa dijalankan orang awam tanpa install Python.

#### Sub-Tahap 6A — PyInstaller (Python → standalone .exe)

**File:** `build/asynxdl.spec`

Konfigurasi kunci `asynxdl.spec`:
- `mode`: `onefile` (satu file `.exe`, mudah distribusi).
- `datas`: include folder `frontend/ui/assets/`, `frontend/ui/i18n/`, `data/queue/.gitkeep`.
- `hiddenimports`: `pystray`, `PIL._tkinter_finder`, `customtkinter`, `uvicorn.logging`, `uvicorn.lifespan.on`.
- `icon`: path ke `frontend/ui/assets/icons/app.ico`.
- `console`: `False` (tidak tampilkan CMD window).
- Tambahkan runtime hook agar `winreg` module bisa ditemukan.

Perintah build: `pyinstaller build/asynxdl.spec`
Output: `dist/AsynxDL.exe`

#### Sub-Tahap 6B — Inno Setup (.exe → Installer Profesional)

**File:** `build/installer.iss`

Konfigurasi kunci `installer.iss`:
- **Source:** `dist\AsynxDL.exe`
- **Install directory:** `{autopf}\AsynxDL\`
- **Shortcut:** Desktop + Start Menu.
- **Post-install:** Jalankan `AsynxDL.exe --first-run` (trigger generate token + welcome wizard).
- **Uninstall:** Hapus registry startup key `HKCU\...\Run\AsynxDL` jika ada.
- **Icon:** Sertakan `.ico` untuk installer.

Output: `AsynxDL_Setup_v1.0.0.exe`

#### Sub-Tahap 6C — Extension: Distribusi

**Pilihan A (Development/Internal):**
Sertakan folder `extension/browser/` di dalam installer. Tampilkan halaman "cara load extension" di first-run wizard.

**Pilihan B (Publik):**
Buat zip dari folder `extension/browser/`, upload ke Chrome Web Store Developer Dashboard. Proses review ±3–7 hari kerja.

---

## 📦 9. DEPENDENCIES (requirements.txt)

```
fastapi==0.115.0
uvicorn[standard]==0.30.3
requests==2.32.3
pystray==0.19.5
Pillow==10.4.0
customtkinter==5.2.2
pydantic==2.9.0
pyinstaller==6.10.0
```

> **Catatan:** Pin versi eksplisit untuk reproducible build. Uji kompatibilitas sebelum upgrade.

---

## ⚙️ 10. KONFIGURASI (config.json — Skema Default)

```json
{
  "app_version": "1.0.0",
  "api_port": 58296,
  "api_secret_token": "AUTO_GENERATED_ON_FIRST_RUN",
  "default_download_path": "%USERPROFILE%\\Downloads",
  "max_threads_per_download": 8,
  "max_concurrent_downloads": 3,
  "speed_limit_kbps": 0,
  "language": "en",
  "theme": "light",
  "run_on_startup": false,
  "first_run_completed": false
}
```

Path config: `%APPDATA%\AsynxDL\config.json` (agar tidak hilang saat app di-uninstall dan re-install).

---

## ⚠️ 11. CATATAN PENTING UNTUK DEEPSEEK (Wajib Dibaca)

1. **Server binding:** SELALU `127.0.0.1`, BUKAN `0.0.0.0`. Ini keamanan mendasar.

2. **Token di semua non-status endpoint:** Implementasikan sebagai FastAPI `Depends(verify_token)`, bukan `@app.middleware`. Lebih eksplisit dan mudah di-exclude per endpoint.

3. **Thread safety metadata:** `metadata_manager.py` WAJIB menggunakan `threading.Lock()` global. Beberapa thread chunk dapat update metadata secara bersamaan.

4. **Flush metadata berkala:** Jangan tulis `.json` hanya di akhir download. Flush setiap ≤1 detik menggunakan timer thread terpisah atau flag dirty di class.

5. **Path resolution:** SELALU gunakan `os.path.expandvars("%USERPROFILE%\\Downloads")` dan `os.path.expanduser("~")`. Jangan hardcode path apapun.

6. **Jangan block UI thread:** Semua operasi jaringan di sisi UI (`api_client.py`) harus dijalankan di `threading.Thread` atau `asyncio`. Gunakan `root.after()` (Tkinter) untuk update widget dari thread lain.

7. **Windows-only guards:** Semua kode yang menggunakan `winreg` WAJIB dibungkus `if sys.platform == "win32":`. Ini memudahkan jika suatu saat ingin port ke macOS/Linux.

8. **PyInstaller + CustomTkinter:** CustomTkinter menggunakan file aset internal. Pastikan path ke aset CTk ikut tercakup di `datas` pada `.spec` menggunakan `customtkinter.PACKAGES_PATH`.

9. **Extension MV3 & Service Worker lifecycle:** Service worker MV3 bisa "mati" saat tidak ada event. Gunakan `chrome.storage.session` (bukan variable global) untuk simpan state antar event.

10. **First-run wizard:** Jangan langsung buka main window di first-run. Tampilkan wizard setup kecil: (1) pilih bahasa, (2) konfirmasi path download, (3) tampilkan Secret Token + instruksi setting ke extension, (4) opsi run on startup.

---

## 🗒 12. GLOSARIUM SINGKATAN

| Singkatan | Kepanjangan |
|---|---|
| CTk | CustomTkinter |
| MV3 | Manifest Version 3 (Chrome Extension) |
| ETA | Estimated Time of Arrival (sisa waktu) |
| CRUD | Create, Read, Update, Delete |
| RTO | Request Timeout |
| WS | WebSocket |

---

*Dokumen ini adalah panduan arsitektur definitif untuk AsynxDL v1.0.0.*
*Seluruh implementasi kode penuh diserahkan ke DeepSeek berdasarkan spesifikasi di atas.*
*Revisi blueprint cukup di file ini sebelum fase implementasi dimulai.*
