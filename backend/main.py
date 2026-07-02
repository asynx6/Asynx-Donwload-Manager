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


def _is_another_instance_running(port: int) -> bool:
    """Check whether another AsynxDL process is already serving the API port."""
    try:
        import requests
        resp = requests.get(f"http://127.0.0.1:{port}/status", timeout=1.5)
        return resp.status_code == 200
    except Exception:
        return False


def _wait_for_backend(timeout: int = 10) -> bool:
    import requests
    config = load_config()
    port = config.get("api_port", 58296)
    url = f"http://127.0.0.1:{port}/status"
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(url, timeout=1)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def main():
    parser = argparse.ArgumentParser(description="AsynxDL — Download Manager")
    parser.add_argument("--minimized", action="store_true", help="Start minimized to tray")
    parser.add_argument("--first-run", action="store_true", help="Force first-run wizard")
    args = parser.parse_args()

    config = load_config()
    port = config.get("api_port", 58296)

    if _is_another_instance_running(port):
        print("[WARN] AsynxDL is already running. Only one instance is allowed.")
        sys.exit(0)

    # Start FastAPI server di thread daemon
    server_thread = start_server_thread(port=port)
    if not _wait_for_backend(timeout=10):
        print("[ERROR] Backend server tidak dapat di-start.")
        sys.exit(1)

    # Inisialisasi UI root (window disembunyikan dulu)
    needs_wizard = is_first_run() or args.first_run
    app = AsynxDLApp(minimized=needs_wizard or args.minimized)

    # First-run wizard
    if needs_wizard:
        def on_finish():
            app.show_window()

        wizard = FirstRunWizard(app._root, on_finish=on_finish)
        wizard.grab_set()
        app._root.wait_window(wizard)
        # Jika wizard ditutup sebelum selesai, tetap tampilkan window
        if not load_config().get("first_run_completed"):
            app.show_window()
    elif not args.minimized:
        # Pastikan window utama terlihat saat launch normal
        app.show_window()

    app.run()


if __name__ == "__main__":
    install_crash_handler()
    redirect_streams_to_log()
    run_with_crash_logging(main)
