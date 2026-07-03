# AsynxDL — Manajer Download Canggih

<p align="center">
  <img src="frontend/ui/assets/icons/logo.png" alt="Logo AsynxDL" width="96">
</p>

<p align="center">
  <strong>Manajer download desktop multi-thread, dapat di-resume, untuk Windows</strong><br>
  Dibangun dengan Python · FastAPI · CustomTkinter · Ekstensi Chromium
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="Lisensi MIT"></a>
  <img src="https://img.shields.io/badge/platform-Windows-blue.svg" alt="Windows">
  <img src="https://img.shields.io/badge/python-3.14-blue.svg" alt="Python 3.14">
</p>

<p align="center">
  <a href="#unduhan">Unduhan</a> ·
  <a href="#fitur">Fitur</a> ·
  <a href="#instalasi">Instalasi</a> ·
  <a href="#ekstensi">Ekstensi</a> ·
  <a href="CONTRIBUTING.md">Berkontribusi</a>
</p>

---

## Unduhan

Installer dan executable portable sudah tersedia di halaman [Releases](https://github.com/asynxdl/asynxdl/releases) (atau di folder `dist/` setelah build).

| Paket | Deskripsi |
|--------|-------------|
| `dist/AsynxDL.exe` | Executable portable satu file (tanpa console) |
| `dist/AsynxDL_Debug.exe` | Versi console untuk debugging; jalankan dari CMD untuk melihat error |
| `dist/AsynxDL_Setup_v1.0.0.exe` | Installer Windows dengan shortcut desktop & ekstensi |

> **Mengatasi masalah startup:** Jika `AsynxDL.exe` tidak muncul jendelanya, jalankan `dist/AsynxDL_Debug.exe` dari terminal dan periksa file log di `%LOCALAPPDATA%\AsynxDL\logs\` (`app.log`, `crash-*.log`, `state.log`).

---

## Fitur

- **Download Multi-thread dengan Chunk** — Membagi file besar menjadi beberapa bagian dan mengunduhnya paralel (hingga 8 thread per file).
- **Resume & Pemulihan Crash** — State download disimpan ke metadata JSON. Bisa resume setelah crash atau restart.
- **Manajemen Antrian** — Maksimal 3 download bersamaan untuk menjaga RAM dan CPU tetap rendah.
- **Pembatas Kecepatan** — Atur batas kecepatan per download (KB/s).
- **Integrasi Browser** — Ekstensi Chromium (Manifest V3) menangkap download browser dan mengirimkannya ke aplikasi desktop.
- **System Tray** — Minimalkan ke tray dan kontrol aplikasi dari ikon tray.
- **Autentikasi Token** — Semua endpoint API dilindungi oleh token rahasia yang dibuat otomatis.
- **RAM-Friendly** — Dioptimalkan untuk laptop 4 GB RAM dengan buffer kecil (64 KB chunk, 1 MB merger).

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
├── plan.md                  # Blueprint arsitektur
├── LICENSE                  # Lisensi MIT
├── README.md                # Dokumentasi bahasa Inggris
└── README.id.md             # Dokumentasi bahasa Indonesia (file ini)
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

---

## Lisensi

Proyek ini dilisensikan di bawah [MIT License](LICENSE).

---

## Terima Kasih

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) untuk widget UI modern.
- [FastAPI](https://fastapi.tiangolo.com/) untuk backend berperforma tinggi.
- [PyInstaller](https://pyinstaller.org/) untuk packaging executable.
- [Inno Setup](https://jrsoftware.org/isinfo.php) untuk installer.
