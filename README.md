# AsynxDL — Advanced Download Manager

<p align="center">
  <img src="frontend/ui/assets/icons/logo.png" alt="AsynxDL Logo" width="96">
</p>

<p align="center">
  <strong>Multi-threaded, resumable, intelligent desktop download manager for Windows</strong><br>
  Built with Python · FastAPI · CustomTkinter · Chromium Extension
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/platform-Windows-blue.svg" alt="Windows">
  <img src="https://img.shields.io/badge/python-3.14-blue.svg" alt="Python 3.14">
</p>

<p align="center">
  <a href="#download">Download</a> ·
  <a href="#project-concept">Concept</a> ·
  <a href="#core-features">Features</a> ·
  <a href="#system-architecture--workflow">Architecture</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

---

## Download

Pre-built installer and portable executable are available in the [Releases](https://github.com/asynx6/Asynx-Donwload-Manager/releases) page (or in the `dist/` folder after building).

| Package | Description |
|--------|-------------|
| `dist/AsynxDL.exe` | Portable single-file executable (no console) |
| `dist/AsynxDL_Debug.exe` | Console version for debugging; run from cmd to see errors |
| `dist/AsynxDL_Setup_v1.0.0.exe` | Windows installer with desktop shortcut & extension |

> **Troubleshooting startup issues:** If `AsynxDL.exe` does not show a window after double-clicking, run `dist/AsynxDL_Debug.exe` from a terminal and check the log files in `%LOCALAPPDATA%\AsynxDL\logs\` (`app.log`, `crash-*.log`, `state.log`). The installer has also been tested with silent install/uninstall and cleans up the program directory and app data automatically.

---

## Installation

### Option A: Installer (Recommended)

1. Download `AsynxDL_Setup_v1.0.0.exe` from the `dist/` folder.
2. Run the installer and follow the setup wizard.
3. Choose whether to create a desktop shortcut.
4. Launch **AsynxDL** from the Start Menu or desktop shortcut.

> **Note:** The installer installs the app to `%LOCALAPPDATA%\Programs\AsynxDL` and stores your settings in `%APPDATA%\AsynxDL`. On first launch, the app shows a setup wizard to choose language, default download folder, and copy the secret token for the browser extension. The uninstaller removes the program directory, app data, and any leftover `.parts` folder automatically.

### Option B: Portable Executable

1. Download `dist/AsynxDL.exe`.
2. Double-click to run. No installation required.

### Option C: Run from Source (Development)

```powershell
# 1. Clone or download this repository
# 2. Install dependencies
python -m pip install -r requirements.txt

# 3. Run the app
python -m backend.main
```

---

## Browser Extension

AsynxDL ships with a Chromium-based browser extension (Manifest V3). It works with Google Chrome, Microsoft Edge, Brave, Opera, and other Chromium browsers.

1. Open your browser and go to the extensions page (`chrome://extensions/` or `edge://extensions/`).
2. Enable **Developer mode** (toggle in the top-right corner).
3. Click **Load unpacked** and select the folder `extension/browser/` (or `%LOCALAPPDATA%\Programs\AsynxDL\extension` after installation).
4. Open the AsynxDL desktop app, go through the first-run wizard, and copy the **Secret Token**.
5. Click the AsynxDL extension icon → **Options**, paste the token, and click **Save Token**.

After setup, the extension will intercept downloads in your browser and ask you to confirm them in the AsynxDL app.

---

## Building from Source

### Build the Executable

```powershell
# Build dist/AsynxDL.exe
python -m PyInstaller build/asynxdl.spec --clean --noconfirm
```

### Build the Windows Installer

1. Build the executable first (see above).
2. Open `build/installer.iss` in **Inno Setup Compiler**.
3. Click **Build** → output will be `dist/AsynxDL_Setup_v1.0.0.exe`.

Or use the helper script:

```powershell
build\build.bat
```

### Build the Extension Package

The extension is loaded unpacked during development. To package it as a `.zip` for distribution:

```powershell
# PowerShell
Compress-Archive -Path extension\browser\* -DestinationPath dist\AsynxDL_Extension.zip -Force
```

---

## Running Tests

```powershell
python -m pytest tests/ -v
```

The test suite includes:

- Metadata manager tests
- API authentication & routing tests
- Local HTTP server download simulation
- Real internet download via the API

---

## Project Structure

```
AsynxDL/
├── backend/                 # FastAPI server + download engine
│   ├── api/                 # Routes, auth, models, WebSocket
│   ├── core/                # Chunking, merging, metadata, speed limiter
│   ├── system/              # Config, startup, tray
│   └── main.py              # Application entry point
├── frontend/                # CustomTkinter desktop UI
│   └── ui/
├── extension/browser/       # Chrome Extension (Manifest V3)
├── tests/                   # Unit & integration tests
├── build/                   # PyInstaller + Inno Setup scripts
├── data/queue/              # Download metadata queue
├── LICENSE                  # MIT License
├── README.id.md             # Docs Indonesian
└── README.md                # This file
```

---

## Project Concept

AsynxDL is a native Windows download manager engineered to solve a specific problem: **the built-in browser download experience is fundamentally inadequate for large files, unreliable networks, and users who need control over their downloads**. Modern browsers treat downloads as monolithic, fire-and-forget operations with no visibility into chunk-level progress, no meaningful resume capability across browser restarts, and no intelligence about network conditions or server behavior.

AsynxDL exists at the intersection of three architectural decisions:

1. **Local-first, self-contained architecture.** The application runs a FastAPI HTTP server on `127.0.0.1:58296` as a daemon thread within the Python process. This local API serves as the single coordination point between the download engine (backend), the desktop UI (frontend), and the browser extension. No cloud services, no external dependencies at runtime. The API is protected by an auto-generated HMAC token (`X-AsynxDL-Token` header) with constant-time comparison to prevent timing attacks.

2. **Chunk-based parallel downloading with intelligent adaptation.** Rather than streaming a file in a single connection, AsynxDL probes the server for `Content-Length` and `Accept-Ranges`, calculates an optimal chunk count using a size-based heuristic (4 chunks for files <1MB, up to 32 for files >10GB), and distributes work across a `ThreadPoolExecutor`. Each chunk is downloaded independently, written to a pre-allocated `.part` file in `%LOCALAPPDATA%\AsynxDL\.parts`, and merged with checksum verification (SHA-256, MD5, ETag) after completion. The system dynamically adapts thread count based on observed throughput, detects server-side throttling via rolling-window bandwidth analysis, and can failover to mirror/CDN candidates automatically.

3. **RAM-friendly design for constrained hardware.** Every buffer, cache, and data structure in AsynxDL is bounded and designed for 4GB RAM laptops. The merge buffer is 1MB. The chunk streaming buffer adapts between 8KB and 64KB based on measured latency. DNS prefetch results are cached in a bounded LRU (512 entries, 600s TTL). Host-specific buffer tuners and turbo routers are bounded to 256 entries with LRU eviction. Metadata is stored as individual JSON files per task, not loaded into memory in bulk.

The core philosophy is **determinism and recoverability**: every download state is persisted to disk as JSON metadata before any bytes are transferred, every chunk operation is idempotent, and the system can recover from crashes, reboots, or force-kills by reconciling `.part` file sizes against recorded `bytes_done` values in metadata.

---

## Core Features

### Multi-threaded Chunked Download Engine

The download engine (`backend/core/downloader.py` → `DownloadTask`) orchestrates a complete download lifecycle:

| Phase | Component | Description |
|-------|-----------|-------------|
| Probe | `chunk_manager.probe_url()` | HEAD request to determine `Content-Length`, filename from `Content-Disposition`, and `Accept-Ranges` support |
| Range Fingerprint | `range_fingerprint.RangeFingerprint` | Sends a `Range: bytes=0-0` request and validates the server actually returns a `206` with correct `Content-Range` header; detects servers that claim range support but ignore it |
| Mirror Selection | `mirror_selector.MirrorSelector` | Generates candidate CDN/mirror hostnames (`cdn.*`, `edge.*`, `dl.*`, `static.*`, `mirror.*`, `download.*`, `fast.*`), probes each with HEAD requests in parallel using a `ThreadPoolExecutor(max_workers=6)`, and selects the lowest-latency mirror that returns matching `Content-Length` |
| Chunk Calculation | `chunk_calculator.auto_chunks_for_size()` | Size-based heuristic: <1MB→4, 1-100MB→8, 100MB-1GB→16, 1-10GB→24, >10GB→32 chunks |
| Pre-allocation | `preallocator.preallocate_file()` | Reserves disk space for the final file before download begins; uses `posix_fallocate` on POSIX and zero-fill (chunked 1MB writes) on Windows for files <100MB |
| Intelligence | `intelligence.decision_for()` | 10-strategy engine that adjusts thread count, mirror selection, pre-allocation, checksum verification, and disk guards based on a `Policy` context |
| Download | `chunk_manager.download_chunk()` | Each chunk is a `requests.get()` with `Range: bytes=start-end`, streaming into the `.part` file with a per-host adaptive buffer (8-64KB based on latency) |
| Speed Limiting | `speed_limiter.SpeedLimiter` | Token-bucket algorithm with `time.sleep()` throttle, shared across all chunk threads for a single task |
| Global Scheduling | `download_scheduler.DownloadScheduler` | Weighted fair-share bandwidth allocation across all active downloads when a global speed limit is configured; tasks are prioritized 1-10 |
| Merge | `merger.merge_parts()` | Sequential 1MB buffer read/write of all `.part` files into the final output, followed by size verification and optional SHA-256/MD5/ETag checksum validation |
| Cleanup | `parts_dir.purge_all_parts_for()` | Removes all `.part` and `.final` files for a task after successful merge |

### Network Intelligence & Anti-Throttle System

| Module | Function |
|--------|----------|
| `turbo_router.TurboRouter` | Combines throttle detection (rolling-window 6-sample bandwidth analysis), User-Agent rotation (6-string pool: Chrome/Firefox/Edge/Safari/Android/curl), and mirror hostname rotation |
| `bandwidth_probe.BandwidthProbe` | Samples speed every 10 seconds in a 30-second window; triggers throttle callback when current speed drops below 50% of the median |
| `adaptive_thread_controller.AdaptiveThreadController` | Evaluates speed trend every 3 seconds; scales threads up when speed is stable/rising (up to 16), scales down when failures are detected (minimum 4) |
| `geo_chunk_router.GeoChunkRouter` | Distributes chunks across multiple mirrors in round-robin for parallelism when multiple valid mirrors exist |
| `dns_prefetch.DnsPrefetch` | Resolves hostnames via DNS-over-UDP to `1.1.1.1`/`8.8.8.8` before connection; caches results in bounded LRU with 600s TTL; pure stdlib implementation (no `dnspython`) |
| `socket_tuner` | Configures TCP Keep-Alive (60s idle, 10s interval, 5 retries), Nagle off (`TCP_NODELAY`), and 256KB send/receive buffers on every socket |
| `buffer_tuner.BufferTuner` | Per-host adaptive read buffer: <30ms ping→8KB, 30-70ms→16KB, 70-150ms→32KB, >150ms→64KB; rolling window of 32 samples |

### Resume & Crash Recovery

- **Metadata Persistence:** Every download task has a JSON file in `data/queue/<uuid>.json` containing URL, filename, save path, total size, chunk byte offsets, checksums, and status.
- **Graceful Exit Flag:** The `graceful_exit` field in metadata tracks whether a download was paused intentionally (True) or interrupted by crash/force-kill (False). The UI shows "Interrupted" for non-graceful exits.
- **Resume Integrity Validation:** `resume_integrity.ResumeIntegrityValidator` reconciles `.part` file sizes against recorded `bytes_done` values during resume. Mismatched chunks are reset for re-download.
- **State Hash:** A SHA-256 hash of the resume state (chunks + sizes + URL + ETag) is computed to detect external tampering of metadata files.
- **Background Recovery:** On startup, the `DownloadManager` scans `data/queue/completed/` and active queue files to restore previous session state.

### Queue Management & Concurrency Control

- **Concurrent Limit:** Configurable maximum concurrent downloads (default 3, max 5). Downloads exceeding the limit are queued as `PENDING` and started when a slot opens.
- **SJF Scheduling:** Pending downloads use Shortest-Job-First ordering — smallest files first, with `created_at` as tie-breaker.
- **Per-task Thread Cap:** Maximum 8 threads per download (configurable), dynamically adjusted by the chunk calculator.

### Security Architecture

| Layer | Mechanism |
|-------|-----------|
| **Authentication** | HMAC constant-time token comparison (`hmac.compare_digest`) on `X-AsynxDL-Token` header; token generated as UUID on first run; placeholder/empty tokens are rejected |
| **Rate Limiting** | Sliding-window rate limiter: 60 requests/minute per IP, with LRU bucket eviction after 5 minutes of inactivity |
| **Host Defense** | `HeaderDefenseMiddleware` rejects requests with `Host` headers not matching `127.0.0.1`/`localhost`/`0.0.0.0` |
| **Path Traversal** | Pydantic `field_validator` rejects `..` traversal, null bytes, device paths (`\\.\`), and UNC paths (`\\server\share`) in `save_path` and `filename` |
| **SSRF Prevention** | Mirror selector validates that candidate hostnames do not resolve to private/loopback IP addresses |
| **CORS** | Restricted to `http://127.0.0.1` origin only; credentials disabled |

### Desktop UI (CustomTkinter)

- **Brutalist W98 Theme:** Mono-grey palette with zero `corner_radius`, square edges, and Arial font. Light and dark modes with runtime repaint via `theme.repaint()`.
- **Tab Navigation:** Two tabs — Home (download list) and Setting (configuration).
- **Home Panel:** Toolbar with search box + "Download" button; filter chips (All/Active/Paused/Done); scrollable card list with real-time progress updates via WebSocket.
- **Download Card:** Shows filename, status text, progress bar, speed/size/ETA info, and action buttons (Pause/Resume/Cancel/Open Folder/Run/Remove History) — all context-sensitive based on download state.
- **Settings Panel:** Form fields for default download path, speed limit, language (English/Indonesian), theme, and run-on-startup toggle.
- **Add Download Modal:** URL input with real-time validation, speed limit field, and "Start Download" button.
- **First-Run Wizard:** 3-step setup — language selection → download path + startup preference → secret token display for browser extension.
- **System Tray:** Minimize to tray with dynamic icon state (idle=blue, active=green, blocked=red); tray menu with Show/Pause All/Settings/Quit; balloon notification when downloads are running.
- **WebSocket Progress:** Real-time progress updates pushed from the backend via `ws://127.0.0.1:58296/ws/progress`, eliminating polling overhead.
- **Multi-language:** Full i18n support via JSON translation files (`frontend/ui/i18n/en.json`, `id.json`); runtime language switching without restart.

### Browser Extension (Manifest V3)

- **Download Interception:** `chrome.downloads.onCreated` listener cancels native Chrome downloads and relays them to the desktop app via `POST /downloads/add`.
- **Service Worker:** Background service worker (`background/service_worker.js`) handles interception, backend health checking, and popup triggering.
- **Popup UI:** Confirmation dialog showing intercepted filename, size, and save path; sends download to backend with token authentication.
- **Options Page:** Token configuration page for pasting the secret token from the desktop app.
- **Backend Health Check:** Extension pings `/status` before intercepting to ensure the desktop app is running.

### System Integration

| Feature | Implementation |
|---------|---------------|
| **Windows Auto-Startup** | Registry key `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\AsynxDL` with `--minimized` flag |
| **Single Instance** | Socket-based port probe (<10ms) on `127.0.0.1:58296`; second instance signals existing window via Win32 `FindWindowW` → `ShowWindow(SW_RESTORE)` → `SetForegroundWindow` |
| **Crash Logging** | Global `sys.excepthook` handler writes full traceback to `%LOCALAPPDATA%\AsynxDL\logs\crash-<timestamp>.log` |
| **Stream Redirection** | `stdout`/`stderr` redirected to `%LOCALAPPDATA%\AsynxDL\logs\app.log` for persistent logging in headless/`--minimized` mode |
| **State Heartbeat** | Window geometry and visibility state logged every 10 seconds to `state.log` with 256KB rotation |
| **Antivirus Integration** | Windows Defender `MpCmdRun.exe` scan available via `antivirus.scan_file()` (45-second timeout, no-UI mode) |

### PyInstaller Startup Hardening

The application entry point (`backend/main.py`) implements a multi-stage pre-import hardening sequence to handle PyInstaller one-file bundle edge cases:

1. **`_ensure_overlapped()`** — Pre-imports `_overlapped.pyd` (Windows asyncio C-extension) before any `asyncio` usage
2. **`_preheat_pydantic_core()`** — Pre-imports `pydantic_core._pydantic_core` (Rust binary) before FastAPI loads
3. **`_preheat_uvicorn_runtime()`** — Pre-imports `asyncio.windows_events` before uvicorn starts its `ProactorEventLoop`
4. **`_preheat_stdlib_extensions()`** — Pre-imports `unicodedata` and `idna` for crash-free re-spawn via `os.execv`

This ensures the application survives PyInstaller's `os.execv` restart path (used by the Restart Dialog) where child processes may lose access to bundled C-extensions.

---

## System Architecture & Workflow

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ASYNxDL ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    HTTP/WS     ┌──────────────────────────────┐  │
│  │   Browser    │ ◄────────────► │  FastAPI Server (port 58296) │  │
│  │  Extension   │   /downloads   │  ┌────────────────────────┐  │  │
│  │  (Manifest   │   /ws/progress │  │   DownloadManager      │  │  │
│  │   V3)        │   /settings    │  │   ┌──────────────────┐  │  │  │
│  └──────────────┘                │  │   │  DownloadTask ×N  │  │  │  │
│                                  │  │   │  (ThreadPoolExec) │  │  │  │
│  ┌──────────────┐   APIClient    │  │   └────────┬─────────┘  │  │  │
│  │  Desktop UI  │ ◄────────────► │  │            │            │  │  │
│  │ (CustomTkint │   HTTP/WS      │  │   ┌────────▼─────────┐  │  │  │
│  │  -er)        │                │  │   │  chunk_manager    │  │  │  │
│  │              │                │  │   │  merger           │  │  │  │
│  │ ┌──────────┐ │                │  │   │  metadata_manager │  │  │  │
│  │ │HomePanel │ │                │  │   │  speed_limiter    │  │  │  │
│  │ │Settings  │ │                │  │   │  download_sched.  │  │  │  │
│  │ └──────────┘ │                │  │   └──────────────────┘  │  │  │
│  └──────────────┘                │  └──────────────────────────┘  │
│                                  └──────────────────────────────────┘
│                                          │
│                                          ▼
│                              ┌──────────────────────────┐
│                              │  %LOCALAPPDATA%\AsynxDL   │
│                              │  ├─ .parts/              │
│                              │  │  └─ <uuid>.part{0..N} │
│                              │  └─ logs/                │
│                              │     ├─ app.log           │
│                              │     ├─ crash-*.log       │
│                              │     └─ state.log         │
│                              └──────────────────────────┘
│
│                              ┌──────────────────────────┐
│                              │  data/queue/              │
│                              │  ├─ <uuid>.json (active)  │
│                              │  └─ completed/            │
│                              │     └─ <uuid>.json        │
│                              └──────────────────────────┘
└─────────────────────────────────────────────────────────────────────┘
```

### Application Startup Sequence

1. **Pre-import Hardening:** `_ensure_overlapped()`, `_preheat_pydantic_core()`, `_preheat_uvicorn_runtime()`, `_preheat_stdlib_extensions()` execute before any framework imports
2. **Single Instance Check:** `_is_another_instance_running(port)` probes the TCP port; if occupied, signals existing window via Win32 and exits
3. **Server Launch:** `start_server_thread(port)` spawns a daemon thread running `uvicorn.run(app, host="127.0.0.1", port=58296)`
4. **Backend Readiness:** `_wait_for_backend(timeout=10)` polls with aggressive backoff (50ms → 50ms → 100ms → 200ms → 300ms steps); combines socket probe + HTTP GET to `/status`
5. **First-Run Wizard:** If `first_run_completed` is False in config, displays a 3-step wizard (language → path/startup → token)
6. **UI Launch:** `AsynxDLApp` initializes CustomTkinter root, loads theme, centers window, and renders `MainWindow` with Home/Settings tabs
7. **Tray Registration:** On window close, `TrayIcon` is created with dynamic state provider; runs in a background thread via `pystray`
8. **WebSocket Connection:** `APIClient.start_ws()` establishes persistent WebSocket to `/ws/progress` for real-time download progress; sends token as first message

### Download Lifecycle

```
User clicks "Download" or extension intercepts
    │
    ▼
POST /downloads/add (URL, filename, save_path, speed_limit)
    │
    ▼
DownloadManager.start_new()
    ├─ Validate URL scheme (HTTP/HTTPS only)
    ├─ Check for duplicate URL in active queue
    ├─ Resolve filename (user_input → Content-Disposition → URL path → "unnamed_file")
    ├─ Sanitize filename (illegal chars → _, strip dots/spaces, max 200 chars)
    ├─ Resolve duplicate name (append " (1)", " (2)", etc.)
    ├─ Create metadata JSON (data/queue/<uuid>.json)
    ├─ Queue or start based on concurrent slot availability
    │
    ▼
DownloadTask.start()  [runs in daemon thread]
    │
    ├─ 1. Probe URL (HEAD request → Content-Length, filename, Accept-Ranges)
    ├─ 2. Range Fingerprint (verify server actually honors Range headers)
    ├─ 3. Mirror Selection (parallel HEAD probes to CDN candidates)
    ├─ 4. Chunk Calculation (auto_chunks_for_size: 4-32 chunks)
    ├─ 5. Pre-allocate file (reserve disk space)
    ├─ 6. Intelligence Engine (adjust threads, mirrors, checksums)
    ├─ 7. Create metadata with chunk byte ranges
    ├─ 8. Pre-allocate .part files
    ├─ 9. Download chunks (ThreadPoolExecutor)
    │      ├─ Each thread: download_chunk(url, start, end, part_path)
    │      │  ├─ DNS prefetch (async, cached)
    │      │  ├─ HTTP GET with Range header
    │      │  ├─ Stream to .part file with adaptive buffer
    │      │  ├─ Speed limiter throttle
    │      │  └─ Update chunk bytes_done in metadata
    │      ├─ Bandwidth probe monitors throttle (every 10s)
    │      ├─ Adaptive thread controller adjusts count (every 3s)
    │      └─ Work stealer redistributes from slow chunks
    │
    ├─ 10. Merge parts (sequential 1MB buffer read/write)
    │      ├─ Verify total file size
    │      ├─ Verify SHA-256 / MD5 / ETag (if server provided)
    │      └─ Delete .part files
    │
    ├─ 11. Antivirus scan (Windows Defender, best-effort)
    ├─ 12. Mark metadata as COMPLETED → move to data/queue/completed/
    └─ 13. Broadcast progress via WebSocket to UI + extension
```

### API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/status` | No | Health check (no rate limit) |
| `GET` | `/health` | Yes | Detailed health + metrics |
| `POST` | `/downloads/add` | Yes | Add new download task |
| `GET` | `/downloads` | Yes | List all active + queued tasks |
| `GET` | `/downloads/{task_id}` | Yes | Get single task details |
| `PATCH` | `/downloads/{task_id}/pause` | Yes | Pause active download |
| `PATCH` | `/downloads/{task_id}/resume` | Yes | Resume paused/interrupted download |
| `DELETE` | `/downloads/{task_id}` | Yes | Delete download + optional parts |
| `PATCH` | `/downloads/{task_id}/remove_history` | Yes | Permanently remove from history |
| `GET` | `/settings` | Yes | Get current settings (token masked) |
| `PUT` | `/settings` | Yes | Update settings (token modification blocked) |
| `WS` | `/ws/progress` | Yes (first message) | Real-time progress broadcast |

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | ≥0.115.0 | HTTP API framework |
| `uvicorn[standard]` | ≥0.30.0 | ASGI server |
| `requests` | ≥2.32.0 | HTTP client for chunk downloads |
| `httpx` | ≥0.27.0 | HTTP/2 support for high-performance connections |
| `h2` | ≥4.1.0 | HTTP/2 protocol implementation |
| `pystray` | ≥0.19.5 | System tray integration |
| `Pillow` | ≥12.0 | Image processing for tray icon |
| `customtkinter` | ≥5.2.2 | Desktop UI framework |
| `pydantic` | ≥2.10.0 | Request/response validation |
| `pyinstaller` | ≥6.21.0 | Executable packaging |
| `websocket-client` | ≥1.8.0 | WebSocket client for progress updates |

### Configuration

Configuration is stored at `%APPDATA%\AsynxDL\config.json`:

```json
{
  "app_version": "1.0.0",
  "api_port": 58296,
  "api_secret_token": "<auto-generated-uuid>",
  "default_download_path": "%USERPROFILE%\\Downloads",
  "max_threads_per_download": 8,
  "max_concurrent_downloads": 3,
  "speed_limit_kbps": 0,
  "language": "en",
  "theme": "dark",
  "run_on_startup": false,
  "first_run_completed": false
}
```

---

## Troubleshooting

### App starts but no window appears after double-clicking

1. Wait 5–10 seconds. The app may still be initializing the local API server.
2. Check Task Manager for a process named `AsynxDL.exe`. If it exists, the app is running but the window may be off-screen or hidden.
3. Run `dist/AsynxDL_Debug.exe` from PowerShell or CMD to see real-time output.
4. Check the log directory:
   ```
   %LOCALAPPDATA%\AsynxDL\logs\
   ```
   - `app.log` — stdout/stderr output
   - `crash-*.log` — uncaught Python exceptions
   - `state.log` — window geometry and visibility state
5. If the app is stuck, kill it from Task Manager and try again.

### Uninstaller leaves files behind

If you still need to remove leftovers manually, delete:
```
%LOCALAPPDATA%\Programs\AsynxDL\
%LOCALAPPDATA%\AsynxDL\
%APPDATA%\AsynxDL\
```

---

## Contributing

We welcome contributions from the community. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide, including how to:

- Set up your development environment
- Follow the code style
- Run tests
- Open a Pull Request

A quick summary:

1. **Fork** the repository and clone your fork.
2. Create a new branch for your feature or bug fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Make your changes and follow the existing code style.
4. Add or update tests if applicable.
5. Run the test suite locally:
   ```bash
   python -m pytest tests/ -v
   ```
6. Commit with clear messages and push your branch.
7. Open a **Pull Request** describing what you changed and why.

### Code Style

- Use Python 3.11+ type hints where possible.
- Keep functions focused and under ~60 lines when reasonable.
- Use `r""` raw strings for Windows paths to avoid escape warnings.
- Add docstrings for public modules, classes, and methods.

### Reporting Bugs

If you find a bug, please open an issue with:

- A clear description of the problem.
- Steps to reproduce.
- Expected vs actual behavior.
- Windows version and app version.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Acknowledgements

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) for the modern UI widgets.
- [FastAPI](https://fastapi.tiangolo.com/) for the high-performance backend.
- [PyInstaller](https://pyinstaller.org/) for packaging the executable.
- [Inno Setup](https://jrsoftware.org/isinfo.php) for the installer.
