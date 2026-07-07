# ROMBAK README.md README.id.md

# AsynxDL — Manajer Download Canggih

<p align="center">
  <img src="frontend/ui/assets/icons/logo.png" alt="Logo AsynxDL" width="96">
</p>

<p align="center">
  <strong>Manajer download desktop multi-thread, dapat di-resume, dan cerdas untuk Windows</strong><br>
  Dibangun dengan Python · FastAPI · CustomTkinter · Ekstensi Chromium
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="Lisensi MIT"></a>
  <img src="https://img.shields.io/badge/platform-Windows-blue.svg" alt="Windows">
  <img src="https://img.shields.io/badge/python-3.14-blue.svg" alt="Python 3.14">
</p>

<p align="center">
  <a href="#unduhan">Unduhan</a> ·
  <a href="#konsep-proyek">Konsep</a> ·
  <a href="#fitur-utama">Fitur</a> ·
  <a href="#sistem-kerja--arsitektur">Arsitektur</a> ·
  <a href="CONTRIBUTING.md">Berkontribusi</a>
</p>

---

## Unduhan

Installer dan executable portable sudah tersedia di halaman [Releases](https://github.com/asynx6/asynxdl/releases) (atau di folder `dist/` setelah build).

| Paket | Deskripsi |
|--------|-------------|
| `dist/AsynxDL.exe` | Executable portable satu file (tanpa console) |
| `dist/AsynxDL_Debug.exe` | Versi console untuk debugging; jalankan dari CMD untuk melihat error |
| `dist/AsynxDL_Setup_v1.0.0.exe` | Installer Windows dengan shortcut desktop & ekstensi |

> **Mengatasi masalah startup:** Jika `AsynxDL.exe` tidak muncul jendelanya, jalankan `dist/AsynxDL_Debug.exe` dari terminal dan periksa file log di `%LOCALAPPDATA%\AsynxDL\logs\` (`app.log`, `crash-*.log`, `state.log`).

---

## Instalasi

### Opsi A: Installer (Direkomendasikan)

1. Unduh `AsynxDL_Setup_v1.0.0.exe` dari folder `dist/`.
2. Jalankan installer dan ikuti wizard.
3. Pilih apakah ingin membuat shortcut desktop.
4. Buka **AsynxDL** dari Start Menu atau shortcut desktop.

> **Catatan:** Installer memasang aplikasi ke `%LOCALAPPDATA%\Programs\AsynxDL` dan menyimpan pengaturan di `%APPDATA%\AsynxDL`. Saat pertama kali dibuka, aplikasi menampilkan wizard setup untuk memilih bahasa, folder download default, dan menyalin token rahasia untuk ekstensi browser.

### Opsi B: Executable Portable

1. Unduh `dist/AsynxDL.exe`.
2. Klik dua kali untuk menjalankan. Tidak perlu instalasi.

### Opsi C: Jalankan dari Source (Pengembangan)

```powershell
# 1. Clone atau unduh repository ini
# 2. Install dependensi
python -m pip install -r requirements.txt

# 3. Jalankan aplikasi
python -m backend.main
```

---

## Ekstensi Browser

AsynxDL menyertakan ekstensi browser berbasis Chromium (Manifest V3). Berfungsi di Google Chrome, Microsoft Edge, Brave, Opera, dan browser Chromium lainnya.

1. Buka browser dan kunjungi halaman ekstensi (`chrome://extensions/` atau `edge://extensions/`).
2. Aktifkan **Mode Pengembang** (toggle di pojok kanan atas).
3. Klik **Muat yang belum dibongkar** dan pilih folder `extension/browser/` (atau `%LOCALAPPDATA%\Programs\AsynxDL\extension` setelah instalasi).
4. Buka aplikasi desktop AsynxDL, lewati wizard pertama kali, dan salin **Token Rahasia**.
5. Klik ikon ekstensi AsynxDL → **Opsi**, tempel token, lalu klik **Simpan Token**.

Setelah setup, ekstensi akan menangkap download di browser dan menanyakan konfirmasi di aplikasi AsynxDL.

---

## Build dari Source

### Build Executable

```powershell
# Build dist/AsynxDL.exe
python -m PyInstaller build/asynxdl.spec --clean --noconfirm
```

### Build Installer Windows

1. Build executable terlebih dahulu (lihat di atas).
2. Buka `build/installer.iss` di **Inno Setup Compiler**.
3. Klik **Build** → output akan menjadi `dist/AsynxDL_Setup_v1.0.0.exe`.

Atau gunakan helper script:

```powershell
build\build.bat
```

### Package Ekstensi

Ekstensi dimuat unpacked saat development. Untuk membuat `.zip` untuk distribusi:

```powershell
Compress-Archive -Path extension\browser\* -DestinationPath dist\AsynxDL_Extension.zip -Force
```

---

## Menjalankan Test

```powershell
python -m pytest tests/ -v
```

Test suite mencakup:

- Metadata manager tests
- API authentication & routing tests
- Simulasi download dengan server HTTP lokal
- Download internet nyata via API

---

## Struktur Proyek

```
AsynxDL/
├── backend/                 # Server FastAPI + mesin download
│   ├── api/                 # Routes, auth, models, WebSocket
│   ├── core/                # Chunking, merging, metadata, speed limiter
│   ├── system/              # Config, startup, tray
│   └── main.py              # Entry point aplikasi
├── frontend/                # UI desktop CustomTkinter
│   └── ui/
├── extension/browser/       # Ekstensi Chromium (Manifest V3)
├── tests/                   # Unit & integration tests
├── build/                   # PyInstaller + Inno Setup scripts
├── data/queue/              # Metadata queue download
├── LICENSE                  # Lisensi MIT
├── README.md                # Dokumentasi bahasa Inggris
└── README.id.md             # Dokumentasi bahasa Indonesia (file ini)
```

---

## Konsep Proyek

AsynxDL adalah manajer download native Windows yang dirancang untuk menyelesaikan masalah spesifik: **pengalaman download bawaan browser secara fundamental tidak memadai untuk file besar, jaringan tidak stabil, dan pengguna yang membutuhkan kontrol penuh atas unduhan mereka**. Browser modern memperlakukan download sebagai operasi monolitik tanpa visibilitas pada tingkat chunk, tanpa kemampuan resume yang bermakna lintas restart browser, dan tanpa kecerdasan tentang kondisi jaringan atau perilaku server.

AsynxDL hadir dari persimpangan tiga keputusan arsitektur:

1. **Arsitektur lokal-first, mandiri.** Aplikasi menjalankan server HTTP FastAPI di `127.0.0.1:58296` sebagai thread daemon dalam proses Python. API lokal ini menjadi titik koordinasi tunggal antara mesin download (backend), UI desktop (frontend), dan ekstensi browser. Tidak ada layanan cloud, tidak ada dependensi eksternal saat runtime. API dilindungi oleh token HMAC yang dibuat otomatis (`header X-AsynxDL-Token`) dengan perbandingan constant-time untuk mencegah serangan timing.

2. **Download paralel berbasis chunk dengan adaptasi cerdas.** Alih-alih melakukan stream file dalam satu koneksi tunggal, AsynxDL melakukan probe ke server untuk `Content-Length` dan `Accept-Ranges`, menghitung jumlah chunk optimal menggunakan heuristik berbasis ukuran (4 chunk untuk file <1MB, hingga 32 untuk file >10GB), dan mendistribusikan pekerjaan melalui `ThreadPoolExecutor`. Setiap chunk diunduh secara independen, ditulis ke file `.part` yang dialokasikan sebelumnya di `%LOCALAPPDATA%\AsynxDL\.parts`, dan digabungkan dengan verifikasi checksum (SHA-256, MD5, ETag) setelah selesai. Sistem secara dinamis menyesuaikan jumlah thread berdasarkan throughput yang diamati, mendeteksi throttling sisi server melalui analisis bandwidth rolling-window, dan dapat melakukan failover ke kandidat mirror/CDN secara otomatis.

3. **Desain hemat RAM untuk perangkat terbatas.** Setiap buffer, cache, dan struktur data dalam AsynxDL dibatasi dan dirancang untuk laptop RAM 4GB. Buffer merge adalah 1MB. Buffer streaming chunk beradaptasi antara 8KB dan 64KB berdasarkan latensi yang diukur. Hasil DNS prefetch di-cache dalam LRU yang dibatasi (512 entri, TTL 600 detik). Buffer tuner per-host dan turbo router dibatasi hingga 256 entri dengan LRU eviction. Metadata disimpan sebagai file JSON individual per task, bukan dimuat ke memori secara bulk.

Filosofi inti adalah **determinisme dan recoverability**: setiap status download dipersist ke disk sebagai metadata JSON sebelum satu byte pun ditransfer, setiap operasi chunk bersifat idempoten, dan sistem dapat memulihkan diri dari crash, reboot, atau force-kill dengan merekonsiliasi ukuran file `.part` terhadap nilai `bytes_done` yang tercatat dalam metadata.

---

## Fitur Utama

### Mesin Download Multi-thread Chunked

Mesin download (`backend/core/downloader.py` → `DownloadTask`) mengorkestrasikan siklus hidup download yang lengkap:

| Fase | Komponen | Deskripsi |
|------|----------|-----------|
| Probe | `chunk_manager.probe_url()` | Request HEAD untuk menentukan `Content-Length`, nama file dari `Content-Disposition`, dan dukungan `Accept-Ranges` |
| Range Fingerprint | `range_fingerprint.RangeFingerprint` | Mengirim request `Range: bytes=0-0` dan memvalidasi bahwa server benar-benar mengembalikan `206` dengan header `Content-Range` yang benar; mendeteksi server yang mengklaim dukungan range tetapi mengabaikannya |
| Pemilihan Mirror | `mirror_selector.MirrorSelector` | Menghasilkan kandidat hostname CDN/mirror (`cdn.*`, `edge.*`, `dl.*`, `static.*`, `mirror.*`, `download.*`, `fast.*`), memprobe setiap kandidat dengan request HEAD secara paralel menggunakan `ThreadPoolExecutor(max_workers=6)`, dan memilih mirror dengan latensi terendah yang mengembalikan `Content-Length` cocok |
| Kalkulasi Chunk | `chunk_calculator.auto_chunks_for_size()` | Heuristik berbasis ukuran: <1MB→4, 1-100MB→8, 100MB-1GB→16, 1-10GB→24, >10GB→32 chunk |
| Pre-alokasi | `preallocator.preallocate_file()` | Mengalokasikan ruang disk untuk file final sebelum download dimulai; menggunakan `posix_fallocate` di POSIX dan zero-fill (chunked writes 1MB) di Windows untuk file <100MB |
| Intelligence | `intelligence.decision_for()` | Mesin 10 strategi yang menyesuaikan jumlah thread, pemilihan mirror, pre-alokasi, verifikasi checksum, dan guard disk berdasarkan konteks `Policy` |
| Download | `chunk_manager.download_chunk()` | Setiap chunk adalah `requests.get()` dengan header `Range: bytes=start-end`, streaming ke file `.part` dengan buffer adaptif per-host (8-64KB berdasarkan latensi) |
| Pembatas Kecepatan | `speed_limiter.SpeedLimiter` | Algoritma token-bucket dengan throttle `time.sleep()`, dibagikan ke semua thread chunk untuk satu task |
| Penjadwalan Global | `download_scheduler.DownloadScheduler` | Alokasi bandwidth weighted fair-share lintas semua download aktif saat batas kecepatan global dikonfigurasi; task diprioritaskan 1-10 |
| Merge | `merger.merge_parts()` | Baca/tulis sequential dengan buffer 1MB dari semua file `.part` ke output final, diikuti verifikasi ukuran dan opsi verifikasi checksum SHA-256/MD5/ETag |
| Cleanup | `parts_dir.purge_all_parts_for()` | Menghapus semua file `.part` dan `.final` untuk suatu task setelah merge berhasil |

### Sistem Kecerdasan Jaringan & Anti-Throttle

| Modul | Fungsi |
|-------|--------|
| `turbo_router.TurboRouter` | Menggabungkan deteksi throttle (analisis bandwidth rolling-window 6 sampel), rotasi User-Agent (pool 6 string: Chrome/Firefox/Edge/Safari/Android/curl), dan rotasi hostname mirror |
| `bandwidth_probe.BandwidthProbe` | Mensampel kecepatan setiap 10 detik dalam window 30 detik; memicu callback throttle saat kecepatan saat ini turun di bawah 50% dari median |
| `adaptive_thread_controller.AdaptiveThreadController` | Mengevaluasi tren kecepatan setiap 3 detik; menambah thread saat kecepatan stabil/naik (maks 16), mengurangi saat kegagalan terdeteksi (minimum 4) |
| `geo_chunk_router.GeoChunkRouter` | Mendistribusikan chunk ke beberapa mirror secara round-robin untuk paralelisme ketika beberapa mirror valid tersedia |
| `dns_prefetch.DnsPrefetch` | Resolve hostname via DNS-over-UDP ke `1.1.1.1`/`8.8.8.8` sebelum koneksi; cache hasil dalam LRU yang dibatasi dengan TTL 600 detik; implementasi murni stdlib (tanpa `dnspython`) |
| `socket_tuner` | Mengkonfigurasi TCP Keep-Alive (idle 60s, interval 10s, 5 retry), Nagle off (`TCP_NODELAY`), dan buffer kirim/terima 256KB pada setiap socket |
| `buffer_tuner.BufferTuner` | Buffer baca adaptif per-host: ping <30ms→8KB, 30-70ms→16KB, 70-150ms→32KB, >150ms→64KB; rolling window 32 sampel |

### Resume & Pemulihan Crash

- **Persistensi Metadata:** Setiap task download memiliki file JSON di `data/queue/<uuid>.json` yang berisi URL, nama file, path simpan, ukuran total, offset byte chunk, checksum, dan status.
- **Flag Graceful Exit:** Field `graceful_exit` dalam metadata melacak apakah download di-pause secara sengaja (True) atau terputus oleh crash/force-kill (False). UI menampilkan "Interrupted" untuk exit non-graceful.
- **Validasi Integritas Resume:** `resume_integrity.ResumeIntegrityValidator` merekonsiliasi ukuran file `.part` terhadap nilai `bytes_done` yang tercatat saat resume. Chunk yang tidak cocok direset untuk di-download ulang.
- **Hash State:** Hash SHA-256 dari status resume (chunk + ukuran + URL + ETag) dihitung untuk mendeteksi perubahan eksternal pada file metadata.
- **Recovery Background:** Saat startup, `DownloadManager` memindai folder `data/queue/completed/` dan file queue aktif untuk memulihkan status sesi sebelumnya.

### Manajemen Antrian & Kontrol Konkurensi

- **Batas Konkuren:** Jumlah download bersamaan yang dapat dikonfigurasi (default 3, maks 5). Download yang melebihi batas diantrikan sebagai `PENDING` dan dimulai saat slot tersedia.
- **Penjadwalan SJF:** Download pending menggunakan pengurutan Shortest-Job-First — file terkecil lebih dulu, dengan `created_at` sebagai tie-breaker.
- **Batas Thread per-task:** Maksimum 8 thread per download (dapat dikonfigurasi), disesuaikan secara dinamis oleh kalkulator chunk.

### Arsitektur Keamanan

| Lapisan | Mekanisme |
|---------|-----------|
| **Autentikasi** | Perbandingan token HMAC constant-time (`hmac.compare_digest`) pada header `X-AsynxDL-Token`; token dibuat sebagai UUID saat pertama kali dijalankan; token placeholder/kosong ditolak |
| **Pembatasan Rate** | Rate limiter sliding-window: 60 request/menit per IP, dengan LRU bucket eviction setelah 5 menit tidak aktif |
| **Pertahanan Host** | `HeaderDefenseMiddleware` menolak request dengan header `Host` yang tidak cocok dengan `127.0.0.1`/`localhost`/`0.0.0.0` |
| **Path Traversal** | Pydantic `field_validator` menolak traversal `..`, null byte, device path (`\\.\`), dan UNC path (`\\server\share`) pada `save_path` dan `filename` |
| **Pencegahan SSRF** | Mirror selector memvalidasi bahwa hostname kandidat tidak resolve ke IP private/loopback |
| **CORS** | Dibatasi pada origin `http://127.0.0.1` saja; credentials dinonaktifkan |

### UI Desktop (CustomTkinter)

- **Tema Brutalist W98:** Palet mono-grey dengan `corner_radius` nol, tepi persegi, dan font Arial. Mode light dan dark dengan runtime repaint via `theme.repaint()`.
- **Navigasi Tab:** Dua tab — Home (daftar download) dan Setting (konfigurasi).
- **Panel Home:** Toolbar dengan search box + tombol "Download"; chip filter (Semua/Aktif/Jeda/Selesai); daftar kartu scrollable dengan pembaruan progress real-time via WebSocket.
- **Kartu Download:** Menampilkan nama file, teks status, progress bar, info kecepatan/ukuran/ETA, dan tombol aksi (Jeda/Lanjutkan/Batal/Buka Folder/Jalankan/Hapus Riwayat) — semua sensitif konteks berdasarkan status download.
- **Panel Settings:** Field formulir untuk path download default, batas kecepatan, bahasa (Inggris/Indonesia), tema, dan toggle run-on-startup.
- **Modal Tambah Download:** Input URL dengan validasi real-time, field batas kecepatan, dan tombol "Mulai Download".
- **Wizard Pertama Kali:** Setup 3 langkah — pemilihan bahasa → path download + preferensi startup → tampilan token rahasia untuk ekstensi browser.
- **System Tray:** Minimalkan ke tray dengan ikon status dinamis (idle=blue, active=green, blocked=red); menu tray dengan Tampilkan/Jeda Semua/Pengaturan/Keluar; notifikasi balon saat download sedang berjalan.
- **WebSocket Progress:** Pembaruan progress real-time didorong dari backend melalui `ws://127.0.0.1:58296/ws/progress`, menghilangkan overhead polling.
- **Multi-bahasa:** Dukungan i18n penuh melalui file terjemahan JSON (`frontend/ui/i18n/en.json`, `id.json`); penggantian bahasa tanpa restart.

### Ekstensi Browser (Manifest V3)

- **Intersepsi Download:** Listener `chrome.downloads.onCreated` membatalkan download Chrome native dan merelay-nya ke aplikasi desktop melalui `POST /downloads/add`.
- **Service Worker:** Service worker latar belakang (`background/service_worker.js`) menangani intersepsi, pengecekan kesehatan backend, dan pemicuan popup.
- **UI Popup:** Dialog konfirmasi yang menampilkan nama file, ukuran, dan path simpan yang diintersepsi; mengirim download ke backend dengan autentikasi token.
- **Halaman Opsi:** Halaman konfigurasi token untuk menempelkan token rahasia dari aplikasi desktop.
- **Pemeriksaan Kesehatan Backend:** Ekstensi melakukan ping ke `/status` sebelum mengintersepsi untuk memastikan aplikasi desktop sedang berjalan.

### Integrasi Sistem

| Fitur | Implementasi |
|-------|-------------|
| **Auto-Startup Windows** | Key registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\AsynxDL` dengan flag `--minimized` |
| **Single Instance** | Socket-based port probe (<10ms) pada `127.0.0.1:58296`; instance kedua memberi sinyal ke window yang ada melalui Win32 `FindWindowW` → `ShowWindow(SW_RESTORE)` → `SetForegroundWindow` |
| **Logging Crash** | Handler global `sys.excepthook` menulis traceback lengkap ke `%LOCALAPPDATA%\AsynxDL\logs\crash-<timestamp>.log` |
| **Redirect Stream** | `stdout`/`stderr` dialihkan ke `%LOCALAPPDATA%\AsynxDL\logs\app.log` untuk logging persisten dalam mode headless/`--minimized` |
| **Heartbeat State** | Geometri window dan status visibility dilog setiap 10 detik ke `state.log` dengan rotasi 256KB |
| **Integrasi Antivirus** | Scan Windows Defender `MpCmdRun.exe` tersedia melalui `antivirus.scan_file()` (timeout 45 detik, mode tanpa UI) |

### Hardening Startup PyInstaller

Entry point aplikasi (`backend/main.py`) mengimplementasikan urutan pre-import hardening multi-langkah untuk menangani edge case bundle PyInstaller one-file:

1. **`_ensure_overlapped()`** — Pre-import `_overlapped.pyd` (C-extension asyncio Windows) sebelum penggunaan `asyncio` apa pun
2. **`_preheat_pydantic_core()`** — Pre-import `pydantic_core._pydantic_core` (binary Rust) sebelum FastAPI dimuat
3. **`_preheat_uvicorn_runtime()`** — Pre-import `asyncio.windows_events` sebelum uvicorn memulai `ProactorEventLoop`
4. **`_preheat_stdlib_extensions()`** — Pre-import `unicodedata` dan `idna` untuk crash-free re-spawn via `os.execv`

Ini memastikan aplikasi bertahan dari path restart `os.execv` PyInstaller (yang digunakan oleh Restart Dialog) di mana proses anak dapat kehilangan akses ke C-extension yang di-bundle.

---

## Sistem Kerja & Arsitektur

### Alur Data Tingkat Tinggi

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ARSITEKTUR ASYNxDL                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    HTTP/WS     ┌──────────────────────────────┐  │
│  │   Ekstensi   │ ◄────────────► │  Server FastAPI (port 58296) │  │
│  │   Browser    │   /downloads   │  ┌────────────────────────┐  │  │
│  │  (Manifest   │   /ws/progress │  │   DownloadManager      │  │  │
│  │   V3)        │   /settings    │  │   ┌──────────────────┐  │  │  │
│  └──────────────┘                │  │   │  DownloadTask ×N  │  │  │  │
│                                  │  │   │  (ThreadPoolExec) │  │  │  │
│  ┌──────────────┐   APIClient    │  │   └────────┬─────────┘  │  │  │
│  │  UI Desktop  │ ◄────────────► │  │            │            │  │  │
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
│                              │  ├─ <uuid>.json (aktif)   │
│                              │  └─ completed/            │
│                              │     └─ <uuid>.json        │
│                              └──────────────────────────┘
└─────────────────────────────────────────────────────────────────────┘
```

### Urutan Startup Aplikasi

1. **Pre-import Hardening:** `_ensure_overlapped()`, `_preheat_pydantic_core()`, `_preheat_uvicorn_runtime()`, `_preheat_stdlib_extensions()` dieksekusi sebelum import framework apa pun
2. **Pemeriksaan Single Instance:** `_is_another_instance_running(port)` memprobe TCP port; jika terisi, memberi sinyal ke window yang ada melalui Win32 dan keluar
3. **Peluncuran Server:** `start_server_thread(port)` membuat thread daemon yang menjalankan `uvicorn.run(app, host="127.0.0.1", port=58296)`
4. **Kesiapan Backend:** `_wait_for_backend(timeout=10)` melakukan polling dengan backoff agresif (50ms → 50ms → 100ms → 200ms → 300ms); menggabungkan probe socket + HTTP GET ke `/status`
5. **Wizard Pertama Kali:** Jika `first_run_completed` adalah False dalam config, menampilkan wizard 3 langkah (bahasa → path/startup → token)
6. **Peluncuran UI:** `AsynxDLApp` menginisialisasi root CustomTkinter, memuat tema, mengcenter window, dan merender `MainWindow` dengan tab Home/Settings
7. **Registrasi Tray:** Saat window ditutup, `TrayIcon` dibuat dengan state provider dinamis; berjalan di thread latar belakang melalui `pystray`
8. **Koneksi WebSocket:** `APIClient.start_ws()` meng-establish WebSocket persisten ke `/ws/progress` untuk pembaruan progress real-time; mengirim token sebagai pesan pertama

### Siklus Hidup Download

```
Pengguna mengklik "Download" atau ekstensi mengintersepsi
    │
    ▼
POST /downloads/add (URL, filename, save_path, speed_limit)
    │
    ▼
DownloadManager.start_new()
    ├─ Validasi skema URL (hanya HTTP/HTTPS)
    ├─ Cek URL duplikat dalam antrian aktif
    ├─ Resolve nama file (user_input → Content-Disposition → path URL → "unnamed_file")
    ├─ Sanitasi nama file (karakter ilegal → _, strip titik/spasi, maks 200 karakter)
    ├─ Resolve nama duplikat (tambah " (1)", " (2)", dst.)
    ├─ Buat metadata JSON (data/queue/<uuid>.json)
    ├─ Antrikan atau mulai berdasarkan ketersediaan slot konkuren
    │
    ▼
DownloadTask.start()  [berjalan di thread daemon]
    │
    ├─ 1. Probe URL (HEAD request → Content-Length, nama file, Accept-Ranges)
    ├─ 2. Range Fingerprint (validasi server benar-benar menghormati header Range)
    ├─ 3. Pemilihan Mirror (parallel HEAD probe ke kandidat CDN)
    ├─ 4. Kalkulasi Chunk (auto_chunks_for_size: 4-32 chunk)
    ├─ 5. Pre-alokasi file (reservasi ruang disk)
    ├─ 6. Intelligence Engine (sesuaikan thread, mirror, checksum)
    ├─ 7. Buat metadata dengan range byte chunk
    ├─ 8. Pre-alokasi file .part
    ├─ 9. Download chunk (ThreadPoolExecutor)
    │      ├─ Setiap thread: download_chunk(url, start, end, part_path)
    │      │  ├─ DNS prefetch (async, cached)
    │      │  ├─ HTTP GET dengan header Range
    │      │  ├─ Stream ke file .part dengan buffer adaptif
    │      │  ├─ Throttle pembatas kecepatan
    │      │  └─ Update bytes_done chunk di metadata
    │      ├─ Bandwidth probe memantau throttle (setiap 10 detik)
    │      ├─ Adaptive thread controller menyesuaikan jumlah (setiap 3 detik)
    │      └─ Work stealer mendistribusikan ulang dari chunk lambat
    │
    ├─ 10. Gabung parts (sequential read/write buffer 1MB)
    │      ├─ Verifikasi ukuran total file
    │      ├─ Verifikasi SHA-256 / MD5 / ETag (jika server menyediakan)
    │      └─ Hapus file .part
    │
    ├─ 11. Scan antivirus (Windows Defender, best-effort)
    ├─ 12. Tandai metadata sebagai COMPLETED → pindah ke data/queue/completed/
    └─ 13. Broadcast progress melalui WebSocket ke UI + ekstensi
```

### Endpoint API

| Metode | Endpoint | Autentikasi | Deskripsi |
|--------|----------|-------------|-----------|
| `GET` | `/status` | Tidak | Health check (tanpa rate limit) |
| `GET` | `/health` | Ya | Kesehatan detail + metrik |
| `POST` | `/downloads/add` | Ya | Tambah task download baru |
| `GET` | `/downloads` | Ya | Daftar semua task aktif + antrian |
| `GET` | `/downloads/{task_id}` | Ya | Dapatkan detail task tunggal |
| `PATCH` | `/downloads/{task_id}/pause` | Ya | Jeda download aktif |
| `PATCH` | `/downloads/{task_id}/resume` | Ya | Lanjutkan download yang dijeda/terputus |
| `DELETE` | `/downloads/{task_id}` | Ya | Hapus download + opsi parts |
| `PATCH` | `/downloads/{task_id}/remove_history` | Ya | Hapus permanen dari riwayat |
| `GET` | `/settings` | Ya | Dapatkan pengaturan saat ini (token di-mask) |
| `PUT` | `/settings` | Ya | Perbarui pengaturan (modifikasi token diblokir) |
| `WS` | `/ws/progress` | Ya (pesan pertama) | Broadcast progress real-time |

### Dependensi

| Paket | Versi | Tujuan |
|-------|-------|--------|
| `fastapi` | ≥0.115.0 | Framework API HTTP |
| `uvicorn[standard]` | ≥0.30.0 | Server ASGI |
| `requests` | ≥2.32.0 | HTTP client untuk download chunk |
| `httpx` | ≥0.27.0 | Dukungan HTTP/2 untuk koneksi berperforma tinggi |
| `h2` | ≥4.1.0 | Implementasi protokol HTTP/2 |
| `pystray` | ≥0.19.5 | Integrasi system tray |
| `Pillow` | ≥12.0 | Pemrosesan gambar untuk ikon tray |
| `customtkinter` | ≥5.2.2 | Framework UI desktop |
| `pydantic` | ≥2.10.0 | Validasi request/response |
| `pyinstaller` | ≥6.21.0 | Packaging executable |
| `websocket-client` | ≥1.8.0 | WebSocket client untuk pembaruan progress |

### Konfigurasi

Konfigurasi disimpan di `%APPDATA%\AsynxDL\config.json`:

```json
{
  "app_version": "1.0.0",
  "api_port": 58296,
  "api_secret_token": "<uuid-otomatis-dibuat>",
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

### Aplikasi berjalan tapi tidak muncul jendela

1. Periksa Task Manager untuk proses `AsynxDL.exe`. Jika ada, aplikasi sedang berjalan tapi jendela mungkin off-screen atau tersembunyi.
2. Jalankan `dist/AsynxDL_Debug.exe` dari PowerShell atau CMD untuk melihat output real-time.
3. Periksa direktori log:
   ```
   %LOCALAPPDATA%\AsynxDL\logs\
   ```
   - `app.log` — output stdout/stderr
   - `crash-*.log` — exception Python yang tidak tertangani
   - `state.log` — state geometry dan visibility jendela
4. Jika aplikasi macet, kill dari Task Manager dan coba lagi.

### Uninstaller meninggalkan file

Jika masih ada sisa file, hapus manual:
```
%LOCALAPPDATA%\Programs\AsynxDL\
%LOCALAPPDATA%\AsynxDL\
%APPDATA%\AsynxDL\
```

---

## Berkontribusi

Kami menyambut kontribusi dari komunitas. Silakan baca [CONTRIBUTING.md](CONTRIBUTING.md) untuk panduan lengkap, termasuk cara:

- Menyiapkan development environment
- Mengikuti code style
- Menjalankan test
- Membuka Pull Request

Ringkasan singkat:

1. **Fork** repository dan clone fork Anda.
2. Buat branch baru untuk fitur atau bug fix:
   ```bash
   git checkout -b feature/nama-fitur-anda
   ```
3. Buat perubahan dan ikuti code style yang ada.
4. Tambahkan atau update test jika diperlukan.
5. Jalankan test suite secara lokal:
   ```bash
   python -m pytest tests/ -v
   ```
6. Commit dengan pesan yang jelas dan push branch Anda.
7. Buka **Pull Request** yang menjelaskan apa yang diubah dan mengapa.

### Code Style

- Gunakan Python 3.11+ type hints di mana memungkinkan.
- Pertahankan fungsi fokus dan di bawah ~60 baris jika wajar.
- Gunakan raw string `r""` untuk path Windows untuk menghindari escape warning.
- Tambahkan docstring untuk modul publik, kelas, dan metode.

### Melaporkan Bug

Jika Anda menemukan bug, buka issue dengan:

- Deskripsi masalah yang jelas.
- Langkah reproduksi.
- Perilaku yang diharapkan vs aktual.
- Versi Windows dan versi aplikasi.

---

## Lisensi

Proyek ini dilisensikan di bawah [MIT License](LICENSE).

---

## Terima Kasih

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) untuk widget UI modern.
- [FastAPI](https://fastapi.tiangolo.com/) untuk backend berperforma tinggi.
- [PyInstaller](https://pyinstaller.org/) untuk packaging executable.
- [Inno Setup](https://jrsoftware.org/isinfo.php) untuk installer.
