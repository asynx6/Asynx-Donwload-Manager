# AsynxDL — Advanced Download Manager

<p align="center">
  <img src="frontend/ui/assets/icons/app.png" alt="AsynxDL Logo" width="96">
</p>

<p align="center">
  <strong>Multi-threaded, resumable, desktop download manager for Windows</strong><br>
  Built with Python · FastAPI · CustomTkinter · Chrome Extension
</p>

<p align="center">
  <a href="#download">Download</a> ·
  <a href="#features">Features</a> ·
  <a href="#installation">Installation</a> ·
  <a href="#extension">Chrome Extension</a> ·
  <a href="#contributing">Contributing</a>
</p>

---

## Download

Pre-built installer and portable executable are available in the [Releases](https://github.com/asynxdl/asynxdl/releases) page (or in the `dist/` folder after building).

| Package | Description |
|--------|-------------|
| `dist/AsynxDL.exe` | Portable single-file executable |
| `dist/AsynxDL_Setup_v1.0.0.exe` | Windows installer with desktop shortcut & extension |

---

## Features

- **Multi-threaded Chunked Download** — Splits large files into chunks and downloads them in parallel (up to 8 threads per file).
- **Resume & Crash Recovery** — Download state is persisted to JSON metadata. Resume even after a crash or reboot.
- **Queue Management** — Max concurrent downloads (default 3) to keep RAM and CPU usage low.
- **Speed Limiter** — Set a per-download speed limit (KB/s).
- **Browser Integration** — Chrome Extension (Manifest V3) intercepts browser downloads and sends them to the desktop app.
- **System Tray** — Minimize to tray and control the app from the tray icon.
- **Token Authentication** — All API endpoints are protected by an auto-generated secret token.
- **RAM-Friendly** — Optimized for 4 GB RAM laptops using small buffers (64 KB chunk, 1 MB merger).

---

## Installation

### Option A: Installer (Recommended)

1. Download `AsynxDL_Setup_v1.0.0.exe` from the `dist/` folder.
2. Run the installer and follow the setup wizard.
3. Choose whether to create a desktop shortcut.
4. Launch **AsynxDL** from the Start Menu or desktop shortcut.

> **Note:** On first launch, the app shows a setup wizard to choose language, default download folder, and copy the secret token for the browser extension.

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

## Chrome Extension

1. Open Chrome and go to `chrome://extensions/`.
2. Enable **Developer mode** (toggle in the top-right corner).
3. Click **Load unpacked** and select the folder `extension/browser/` (or `C:\Program Files\AsynxDL\extension` after installation).
4. Open the AsynxDL desktop app, go through the first-run wizard, and copy the **Secret Token**.
5. Click the AsynxDL extension icon → **Options**, paste the token, and click **Save Token**.

After setup, the extension will intercept downloads in Chrome and ask you to confirm them in the AsynxDL app.

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
├── plan.md                  # Architecture blueprint
├── LICENSE                  # MIT License
└── README.md                # This file
```

---

## Contributing

We welcome contributions from the community!

### How to Contribute

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
