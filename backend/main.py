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
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.server import start_server_thread
from backend.system.config import is_first_run, load_config
from backend.system.crash_logger import install_crash_handler, redirect_streams_to_log, run_with_crash_logging
from backend.system.tray import TrayIcon
from frontend.ui.app import AsynxDLApp
from frontend.ui.windows.first_run_wizard import FirstRunWizard
from frontend.ui.i18n import t
import customtkinter as ctk


def _is_another_instance_running(port: int) -> bool:
    """Check whether another AsynxDL process is already serving the API port."""
    try:
        import requests
        resp = requests.get(f"http://127.0.0.1:{port}/status", timeout=1.5)
        return resp.status_code == 200
    except Exception:
        return False


_BACKOFF_STEPS = (0.2, 0.4, 0.8, 1.5, 2.0)  # seconds -- exponential-ish


def _wait_for_backend(timeout: int = 10) -> bool:
    """Tunggu backend /status sampai ready dengan exponential backoff.

    Logika:
    - Mulai dengan delay kecil 200ms.
    - Setiap gagal, naikkan delay hingga max 2s.
    - Kalau timeout habis sebelum 200 OK, return False.
    """
    import requests
    config = load_config()
    port = config.get("api_port", 58296)
    url = f"http://127.0.0.1:{port}/status"
    start = time.time()
    attempt = 0
    while time.time() - start < timeout:
        try:
            resp = requests.get(url, timeout=1)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        delay = _BACKOFF_STEPS[min(attempt, len(_BACKOFF_STEPS) - 1)]
        time.sleep(delay)
        attempt += 1
    return False


def main():
    parser = argparse.ArgumentParser(description="AsynxDL — Download Manager")
    parser.add_argument("--minimized", action="store_true", help="Start minimized to tray")
    parser.add_argument("--first-run", action="store_true", help="Force first-run wizard")
    args = parser.parse_args()

    config = load_config()
    port = config.get("api_port", 58296)

    if _is_another_instance_running(port):
        # Kedua instance mencoba pakai port yang sama akan
        # blocking start_server_thread. Pre-empt langsung.
        print("[INFO] AsynxDL already running, exiting.")
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
