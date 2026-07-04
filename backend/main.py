"""
AsynxDL — Entry Point Aplikasi Lengkap
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Menjalankan urutan startup:
    1. Load config
    2. Start FastAPI server di thread
    3. First-run wizard (jika diperlukan)
    4. Buka UI CustomTkinter
"""

import argparse
import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# `_overlapped` adalah C extension Windows yang dipakai oleh ProactorEventLoop
# (default uvicorn). PyInstaller satu-file kadang tidak meng-collect-nya secara
# otomatis untuk second launch via os.execv — tambahkan eksplisit di sini agar
# asyncio.windows_events import-nya stabil sehingga restart tidak lagi
# menghasilkan: ModuleNotFoundError: No module named '_overlapped'.
try:
    import _overlapped  # noqa: F401
except Exception:
    # Di dev-mode (running via interpreter biasa), stdlib sudah auto-load.
    # Pada bundle-mode satu-file, _overlapped.pyd di-bundle lewat hiddenimports
    # di build/asynxdl.spec; force-import ini memastikan ia terekstrak sebelum
    # backend.api.server menyentuh asyncio.
    if getattr(sys, "frozen", False):
        raise

from backend.api.server import start_server_thread
from backend.system.config import is_first_run, load_config
from backend.system.crash_logger import install_crash_handler, redirect_streams_to_log, run_with_crash_logging
from backend.system.tray import TrayIcon
from frontend.ui.app import AsynxDLApp
from frontend.ui.windows.first_run_wizard import FirstRunWizard
from frontend.ui.i18n import t
import customtkinter as ctk


def _is_another_instance_running(port: int) -> bool:
    """Bug-2 fix: socket-based port probe (<10 ms) replaces HTTP probe.
    Bonus: tidak perlu `requests` overhead / TLS negotiation dance."""
    host = "127.0.0.1"
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except (ConnectionRefusedError, OSError, socket.timeout):
        return False


# Bug-2 fix: tighter backoff sequence — worst case ~0.7 s total. Sebelumnya
# (0.2, 0.4, 0.8, 1.5, 2.0) = ~5 s worst case. Server sudah di-spawn di
# thread namun uvicorn boot memerlukan sedikit waktu warm-up.
_BACKOFF_STEPS = (0.05, 0.05, 0.1, 0.2, 0.3)


def _wait_for_backend(timeout: int = 5) -> bool:
    """Tunggu backend /status sampai ready dengan backoff yang lebih ketat.

    v1.0.2: total worst case timeout 5 s (dari 10 s) + probe lebih responsif.
    """
    config = load_config()
    port = config.get("api_port", 58296)
    url = f"http://127.0.0.1:{port}/status"
    start = time.time()
    attempt = 0
    while time.time() - start < timeout:
        # Fast-path: socket probe (no full HTTP roundtrip)
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                # Kalau socket OK, kirim HTTP kecil untuk verifikasi.
                try:
                    resp = _quick_http_get(url, timeout=0.5)
                    if resp == 200:
                        return True
                except Exception:
                    pass
        except (ConnectionRefusedError, OSError, socket.timeout):
            pass
        delay = _BACKOFF_STEPS[min(attempt, len(_BACKOFF_STEPS) - 1)]
        time.sleep(delay)
        attempt += 1
    return False


def _quick_http_get(url: str, timeout: float = 0.5) -> int:
    """Minimal HTTP/1.0 GET — pakai urllib (built-in) yang ringan."""
    import urllib.request
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status


def main():
    parser = argparse.ArgumentParser(description="AsynxDL — Download Manager")
    parser.add_argument("--minimized", action="store_true", help="Start minimized to tray")
    parser.add_argument("--first-run", action="store_true", help="Force first-run wizard")
    args = parser.parse_args()

    config = load_config()
    port = config.get("api_port", 58296)

    if _is_another_instance_running(port):
        # Kedua instance mencoba pakai port yang sama akan
        # blocking start_server_thread. Pre-empt langsung,
        # tapi sebelum exit: signal existing instance untuk restore
        # window-nya (kalau dia di-tray), supaya user yang double-click
        # app icon merasakan app muncul, bukan silent no-op.
        print("[INFO] AsynxDL already running, signaling existing instance.")
        try:
            from backend.system.instance import signal_existing_window_to_show
            restored = signal_existing_window_to_show("AsynxDL")
            if restored:
                print("[INFO] Existing window restored to foreground.")
            else:
                print("[INFO] Existing window not found by title (likely tray-only).")
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[WARN] signal_existing_instance failed: {exc}")
        sys.exit(0)

    # Start FastAPI server di thread daemon
    server_thread = start_server_thread(port=port)
    if not _wait_for_backend(timeout=10):
        print("[ERROR] Backend server tidak dapat di-start.")
        sys.exit(1)

    # Cek apakah perlu wizard pertama kali
    needs_wizard = is_first_run() or args.first_run

    if needs_wizard:
        # Create a hidden root so the wizard is the only visible window on launch.
        root = ctk.CTk()
        root.withdraw()
        root.title(t("app.title"))

        def on_finish():
            pass

        wizard = FirstRunWizard(root, on_finish=on_finish)
        wizard.transient(root)
        wizard.grab_set()
        wizard.lift()
        wizard.focus_force()
        root.wait_window(wizard)

        if not load_config().get("first_run_completed"):
            print("[INFO] First-run wizard tidak diselesaikan. Keluar.")
            sys.exit(0)

        # After wizard is completed, create the real dashboard using the same root
        # so the dashboard appears exactly once and the wizard is gone.
        app = AsynxDLApp(root=root, minimized=args.minimized)
    else:
        app = AsynxDLApp(minimized=args.minimized)

    # Pastikan window utama terlihat saat launch normal (bukan minimized)
    if not args.minimized:
        app.show_window()

    app.run()


if __name__ == "__main__":
    install_crash_handler()
    redirect_streams_to_log()
    run_with_crash_logging(main)
